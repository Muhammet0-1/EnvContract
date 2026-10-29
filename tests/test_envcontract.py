"""CLI contract tests. All inputs are synthetic and live in a temporary directory."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "envcontract.py"
spec = importlib.util.spec_from_file_location("envcontract", CLI)
app = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = app
spec.loader.exec_module(app)
SECRET = "SYNTHETIC_PRIVATE_VALUE_5d83d94e"


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.ref = self.base / (SECRET + "_reference.env")
        self.target = self.base / (SECRET + "_target.env")
        self.write("A=" + SECRET + "\n", "A=another_synthetic_value\n")

    def write(self, reference, target):
        for path, content in ((self.ref, reference), (self.target, target)):
            path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)

    def run_cli(self, *extra, expected=0, paths=None):
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (self.ref, self.target) if p.is_file() and os.access(p, os.R_OK)}
        command = [sys.executable, str(CLI), *(paths or [str(self.ref), str(self.target)]), *extra]
        first = subprocess.run(command, capture_output=True, timeout=5)
        second = subprocess.run(command, capture_output=True, timeout=5)
        self.assertEqual(first.returncode, expected, first.stdout)
        self.assertEqual((first.returncode, first.stdout, first.stderr),
                         (second.returncode, second.stdout, second.stderr))
        self.assertEqual(first.stderr, b"")
        for output in (first.stdout, first.stderr):
            self.assertNotIn(SECRET.encode(), output)
            self.assertNotIn(str(self.base).encode(), output)
        for p, digest in before.items():
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), digest)
        if "--json" in extra:
            data = json.loads(first.stdout)
            self.assertEqual(data["exit_code"], expected)
            self.assertEqual(data["schema_version"], 1)
            if expected == 2:
                self.assertIsNone(data["findings"])
                self.assertEqual(len(data["errors"]), 1)
            return data
        return first.stdout.decode("ascii")

    def test_equal_keys_ignore_different_values(self):
        self.assertEqual(self.run_cli("--json")["status"], "clean")

    def test_text_clean(self):
        self.assertIn("EnvContract: clean", self.run_cli())

    def test_all_four_findings_demo(self):
        self.ref.write_bytes((ROOT / "examples/reference.env").read_bytes())
        self.target.write_bytes((ROOT / "examples/target.env").read_bytes())
        result = self.run_cli("--json", expected=1)["findings"]
        self.assertEqual(result["missing"], ["API_TOKEN"])
        self.assertEqual(result["extra"], ["LEGACY_FLAG"])
        self.assertEqual(result["duplicates"]["target"], [{"key": "LOG_LEVEL", "lines": [4, 5]}])
        self.assertEqual(result["empty"]["target"], [{"key": "DATABASE_URL", "lines": [3]}])

    def test_fixed_demo(self):
        self.ref.write_bytes((ROOT / "examples/reference.env").read_bytes())
        self.target.write_bytes((ROOT / "examples/target-fixed.env").read_bytes())
        self.run_cli("--json")

    def test_missing(self):
        self.write("B=x\nA=x\n", "A=x\n")
        self.assertEqual(self.run_cli("--json", expected=1)["findings"]["missing"], ["B"])

    def test_extra(self):
        self.write("A=x\n", "Z=x\nA=x\nB=x\n")
        self.assertEqual(self.run_cli("--json", expected=1)["findings"]["extra"], ["B", "Z"])

    def test_duplicates_both_files_all_lines(self):
        self.write("A=x\nA=y\nA=z\n", "A=x\nA=y\n")
        data = self.run_cli("--json", expected=1)["findings"]["duplicates"]
        self.assertEqual(data["reference"][0]["lines"], [1, 2, 3])
        self.assertEqual(data["target"][0]["lines"], [1, 2])

    def test_empty_reference_is_finding(self):
        self.write("A=\n", "A=x\n")
        self.assertEqual(self.run_cli("--json", expected=1)["findings"]["empty"]["reference"],
                         [{"key": "A", "lines": [1]}])

    def test_every_empty_occurrence_reported(self):
        self.write("A=x\n", "A=\nA=x\nA='  '\n")
        self.assertEqual(self.run_cli("--json", expected=1)["findings"]["empty"]["target"][0]["lines"], [1, 3])

    def test_empty_unquoted_single_double_and_whitespace(self):
        for value in ("", " ", "''", '""', "' \t '", '"  "', "#comment"):
            with self.subTest(value_kind=len(value)):
                self.write("A=x\n", "A=" + value + "\n")
                self.run_cli("--json", expected=1)

    def test_quotes_and_hashes(self):
        self.write("A='one # two' # comment\nB=\"quoted 'inner'\"\n", "A=\"#\"#comment\nB='two \"inner\"'\n")
        self.run_cli("--json")

    def test_comments_and_spaces(self):
        self.write(" \t# comment\n A \t= " + SECRET + "#comment\n\n", "\tA=two words # comment\n")
        self.run_cli("--json")

    def test_bom_and_crlf(self):
        self.write(b"\xef\xbb\xbfA=x\r\nB=y\r\n", b"A=x\nB=y\n")
        self.run_cli("--json")

    def test_utf8_values(self):
        self.write("A=örnek\n", "A='İstanbul 😀'\n")
        self.run_cli("--json")

    def test_literals_not_expanded_or_executed(self):
        marker = self.base / "must_not_exist"
        self.write("A=${SYNTHETIC_MISSING}\n", "A=$(touch " + str(marker) + ")\n")
        self.run_cli("--json")
        self.assertFalse(marker.exists())

    def test_external_environment_does_not_supply_missing_key(self):
        self.write("ENVCONTRACT_SYNTHETIC_EXTERNAL=x\n", "#empty\n")
        with mock.patch.dict(os.environ, {"ENVCONTRACT_SYNTHETIC_EXTERNAL": SECRET}):
            self.assertEqual(self.run_cli("--json", expected=1)["findings"]["missing"],
                             ["ENVCONTRACT_SYNTHETIC_EXTERNAL"])

    def test_case_sensitive_names(self):
        self.write("A=x\n", "a=x\n")
        data = self.run_cli("--json", expected=1)["findings"]
        self.assertEqual(data["missing"], ["A"])
        self.assertEqual(data["extra"], ["a"])

    def test_empty_files_have_no_contract_findings(self):
        self.write("", "")
        self.run_cli("--json")

    def test_same_file_is_allowed(self):
        self.run_cli("--json", paths=[str(self.ref), str(self.ref)])

    def test_invalid_assignments_redacted(self):
        for line in (SECRET, "1BAD=" + SECRET, "A-B=" + SECRET, "A.B=" + SECRET,
                     "İ=" + SECRET, "export A=" + SECRET, "=" + SECRET):
            with self.subTest(case=line[:3]):
                self.write("A=x\n", line + "\n")
                self.assertEqual(self.run_cli("--json", expected=2)["errors"][0]["code"], "invalid_assignment")
                self.run_cli(expected=2)

    def test_multiline_quotes_rejected(self):
        for quote in ("'", '"'):
            self.write("A=x\n", "A=" + quote + SECRET + "\nnext" + quote + "\n")
            self.assertEqual(self.run_cli("--json", expected=2)["errors"][0]["line"], 1)

    def test_unclosed_quote(self):
        self.write("A=x\n", "A='" + SECRET)
        self.run_cli("--json", expected=2)

    def test_trailing_content(self):
        self.write("A=x\n", "A='x' " + SECRET + "\n")
        self.run_cli("--json", expected=2)

    def test_embedded_unquoted_quote(self):
        self.write("A=x\n", "A=pre'" + SECRET + "'\n")
        self.run_cli("--json", expected=2)

    def test_backslash_and_backtick_rejected(self):
        for value in (SECRET + "\\", '"' + SECRET + '\\n"', "`" + SECRET + "`", "'x\\y'"):
            self.write("A=x\n", "A=" + value + "\n")
            self.run_cli("--json", expected=2)

    def test_control_and_unicode_line_separators(self):
        for control in ("\x00", "\x1b", "\r", "\x85", "\u2028", "\u2029", "\u202e", "\ufeff"):
            self.write("A=x\n", "A=" + SECRET + control + "x\n")
            self.run_cli("--json", expected=2)

    def test_lone_final_cr(self):
        self.write("A=x\n", "A=" + SECRET + "\r")
        self.run_cli("--json", expected=2)

    def test_invalid_utf8(self):
        self.write(b"A=x\n", b"A=" + SECRET.encode() + b"\xff")
        self.assertEqual(self.run_cli("--json", expected=2)["errors"][0]["code"], "invalid_utf8")

    def test_utf16_rejected(self):
        self.write("A=x\n", ("A=" + SECRET).encode("utf-16"))
        self.run_cli("--json", expected=2)

    def test_exact_size_limit(self):
        data = b"A=x\n#" + b"x" * (app.MAX_BYTES - 5)
        self.write(data, data)
        self.run_cli("--json")

    def test_over_size_limit_both_roles(self):
        data = b"#" + b"x" * app.MAX_BYTES
        for role in ("reference", "target"):
            self.write(data if role == "reference" else b"A=x", data if role == "target" else b"A=x")
            result = self.run_cli("--json", expected=2)
            self.assertEqual(result["errors"][0], {"input": role, "code": "size_limit"})

    def test_missing_reference(self):
        self.ref.unlink()
        self.assertEqual(self.run_cli("--json", expected=2)["errors"][0]["input"], "reference")

    def test_missing_target(self):
        self.target.unlink()
        self.assertEqual(self.run_cli("--json", expected=2)["errors"][0]["input"], "target")

    def test_directory_rejected(self):
        self.run_cli("--json", expected=2, paths=[str(self.base), str(self.target)])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO test")
    def test_fifo_rejected_without_blocking(self):
        fifo = self.base / "synthetic_fifo"
        os.mkfifo(fifo)
        self.run_cli("--json", expected=2, paths=[str(fifo), str(self.target)])

    @unittest.skipUnless(hasattr(os, "geteuid") and os.geteuid() != 0, "requires non-root POSIX")
    def test_real_permission_denial(self):
        self.target.chmod(0)
        try:
            self.run_cli("--json", expected=2)
        finally:
            self.target.chmod(0o600)

    def test_arguments_redacted(self):
        self.run_cli("--json", "--unknown=" + SECRET, expected=2)
        self.run_cli("--unknown=" + SECRET, expected=2)

    def test_missing_arguments(self):
        self.run_cli("--json", expected=2, paths=[str(self.ref)])

    def test_no_partial_findings_on_error(self):
        self.write("A=x\nB=x\n", "A=\n" + SECRET + "\n")
        self.assertIsNone(self.run_cli("--json", expected=2)["findings"])

    def test_text_findings_do_not_print_values(self):
        self.write("A=" + SECRET + "\nB=" + SECRET + "\n", "A=\nA=" + SECRET + "\nC=" + SECRET + "\n")
        text = self.run_cli(expected=1)
        self.assertIn("missing: B", text)
        self.assertIn("extra: C", text)
        self.assertIn("duplicates.target: A [lines 1, 2]", text)

    def test_help_and_version(self):
        for option in ("--help", "--version"):
            result = subprocess.run([sys.executable, str(CLI), option], capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, b"")
            self.assertNotIn(SECRET.encode(), result.stdout)

    def test_closed_output_pipe_reports_and_help(self):
        for flags in ([], ["-u"]):
            for args in (["--help"], ["--version"], [str(self.ref), str(self.target)],
                         [str(self.ref), str(self.target), "--json"]):
                read_fd, write_fd = os.pipe()
                os.close(read_fd)
                try:
                    result = subprocess.run([sys.executable, *flags, str(CLI), *args],
                                            stdout=write_fd, stderr=subprocess.PIPE, timeout=5)
                finally:
                    os.close(write_fd)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stderr, b"")

    @unittest.skipUnless(Path("/dev/full").exists(), "requires /dev/full")
    def test_full_output_device_reports_and_help(self):
        for args in (["--help"], ["--version"], [str(self.ref), str(self.target)]):
            with open("/dev/full", "wb") as sink:
                result = subprocess.run([sys.executable, str(CLI), *args], stdout=sink,
                                        stderr=subprocess.PIPE, timeout=5)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stderr, b"")


class ReadFailureTests(unittest.TestCase):
    def test_io_exception_details_are_discarded(self):
        with mock.patch.object(app.os, "open", side_effect=PermissionError(SECRET)):
            with self.assertRaises(app.InputError) as raised:
                app.read_input("synthetic")
        self.assertEqual(str(raised.exception), "read_error")

    def test_read_change_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.env"
            path.write_bytes(b"A=x\n")
            original = os.stat(path)
            before = mock.Mock(st_mode=original.st_mode, st_size=4, st_mtime_ns=1)
            after = mock.Mock(st_mode=original.st_mode, st_size=5, st_mtime_ns=2)
            with mock.patch.object(app.os, "fstat", side_effect=[before, after]):
                with self.assertRaises(app.InputError) as raised:
                    app.read_input(path)
            self.assertEqual(str(raised.exception), "changed_during_read")


if __name__ == "__main__":
    unittest.main()
