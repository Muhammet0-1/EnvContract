#!/usr/bin/env python3
"""Compare explicitly supplied dotenv files without emitting their values."""

import argparse
import json
import os
import re
import stat
import sys
import unicodedata
from dataclasses import dataclass, field

VERSION = "1.0.0"
MAX_BYTES = 1024 * 1024
KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*", re.ASCII)


class InputError(Exception):
    """Only fixed codes and numeric line locations may cross the CLI boundary."""

    def __init__(self, code, line=None):
        super().__init__(code)
        self.code = code
        self.line = line


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default message can contain arbitrary user-supplied values.
        raise InputError("invalid_arguments")


@dataclass
class KeyInfo:
    lines: list = field(default_factory=list)
    empty_lines: list = field(default_factory=list)


def read_input(path):
    """Read at most MAX_BYTES+1 bytes; never wait on a FIFO or read a device."""
    fd = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
        fd = os.open(path, flags)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise InputError("not_regular_file")
        if before.st_size > MAX_BYTES:
            raise InputError("size_limit")
        with os.fdopen(fd, "rb") as handle:
            fd = None
            data = handle.read(MAX_BYTES + 1)
            after = os.fstat(handle.fileno())
        if len(data) > MAX_BYTES:
            raise InputError("size_limit")
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise InputError("changed_during_read")
        return data
    except (OSError, ValueError):
        raise InputError("read_error") from None
    finally:
        if fd is not None:
            os.close(fd)


def is_empty(raw_value, line_number):
    value = raw_value.strip(" \t")
    if value.startswith(("'", '"')):
        quote = value[0]
        end = value.find(quote, 1)
        if end < 0:
            raise InputError("unclosed_quote_or_multiline", line_number)
        tail = value[end + 1:].lstrip(" \t")
        if tail and not tail.startswith("#"):
            raise InputError("trailing_content", line_number)
        content = value[1:end]
    else:
        content = value.split("#", 1)[0].strip(" \t")
        if "'" in content or '"' in content:
            raise InputError("unsupported_quote", line_number)
    if "\\" in content or "`" in content:
        raise InputError("unsupported_escape_or_backtick", line_number)
    # Whitespace-only quoted values count as empty; no escapes/interpolation.
    return not content.strip()


def parse_input(data):
    try:
        text = data.decode("utf-8-sig", errors="strict")
    except UnicodeError:
        raise InputError("invalid_utf8") from None
    result = {}
    lines = text.split("\n")
    for number, line in enumerate(lines, 1):
        # CR is accepted only as the CR half of a CRLF pair.
        if number < len(lines) and line.endswith("\r"):
            line = line[:-1]
        if any((unicodedata.category(c).startswith("C") and c != "\t")
               or c in "\u2028\u2029" for c in line):
            raise InputError("unsupported_control_character", number)
        stripped = line.strip(" \t")
        if not stripped or stripped.startswith("#"):
            continue
        name, separator, raw_value = stripped.partition("=")
        name = name.strip(" \t")
        if not separator or not KEY.fullmatch(name):
            raise InputError("invalid_assignment", number)
        empty = is_empty(raw_value, number)
        info = result.setdefault(name, KeyInfo())
        info.lines.append(number)
        if empty:
            info.empty_lines.append(number)
    return result


def findings(reference, target):
    return {
        "missing": sorted(reference.keys() - target.keys()),
        "extra": sorted(target.keys() - reference.keys()),
        "duplicates": {
            role: [{"key": key, "lines": data[key].lines}
                   for key in sorted(data) if len(data[key].lines) > 1]
            for role, data in (("reference", reference), ("target", target))
        },
        "empty": {
            role: [{"key": key, "lines": data[key].empty_lines}
                   for key in sorted(data) if data[key].empty_lines]
            for role, data in (("reference", reference), ("target", target))
        },
    }


def compare(reference, target):
    result = findings(reference, target)
    found = (result["missing"] or result["extra"] or
             any(result["duplicates"].values()) or any(result["empty"].values()))
    return {"schema_version": 1, "status": "findings" if found else "clean",
            "exit_code": 1 if found else 0, "findings": result, "errors": []}


def report_text(report):
    output = ["EnvContract: " + report["status"]]
    for error in report["errors"]:
        location = error["input"]
        if "line" in error:
            location += ":" + str(error["line"])
        output.append(location + ": " + error["code"])
    if report["findings"] is not None:
        data = report["findings"]
        for kind in ("missing", "extra"):
            output.append(kind + ": " + (", ".join(data[kind]) or "(none)"))
        for kind in ("duplicates", "empty"):
            for role in ("reference", "target"):
                entries = data[kind][role]
                items = [x["key"] + " [lines " + ", ".join(map(str, x["lines"])) + "]"
                         for x in entries]
                output.append(kind + "." + role + ": " + ("; ".join(items) or "(none)"))
    output.append("exit_code: " + str(report["exit_code"]))
    return "\n".join(output) + "\n"


def emit(output, exit_code):
    """Use one protected writer for reports, help and version output."""
    try:
        sys.stdout.write(output)
        sys.stdout.flush()
    except (OSError, UnicodeError):
        # Avoid interpreter shutdown diagnostics containing stream details.
        try:
            sys.stdout.close()
        except OSError:
            pass
        return 2
    return exit_code


def main(argv=None):
    args_list = list(sys.argv[1:] if argv is None else argv)
    json_output = "--json" in args_list
    parser = SafeArgumentParser(prog="envcontract", allow_abbrev=False, add_help=False,
                                description="Compare two local dotenv key contracts; values are never printed.")
    parser.add_argument("reference", nargs="?", help="explicit reference file")
    parser.add_argument("target", nargs="?", help="explicit target file")
    parser.add_argument("--json", action="store_true", help="emit a deterministic JSON report")
    parser.add_argument("-h", "--help", action="store_true", help="show usage")
    parser.add_argument("--version", action="store_true", help="show version")
    role = "arguments"
    try:
        args = parser.parse_args(args_list)
        if args.help:
            return emit(parser.format_help(), 0)
        if args.version:
            return emit("EnvContract " + VERSION + "\n", 0)
        if args.reference is None or args.target is None:
            raise InputError("invalid_arguments")
        json_output = args.json
        role = "reference"
        reference = parse_input(read_input(args.reference))
        role = "target"
        target = parse_input(read_input(args.target))
        report = compare(reference, target)
    except InputError as error:
        detail = {"input": role, "code": error.code}
        if error.line is not None:
            detail["line"] = error.line
        report = {"schema_version": 1, "status": "error", "exit_code": 2,
                  "findings": None, "errors": [detail]}
    output = (json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
              if json_output else report_text(report))
    return emit(output, report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
