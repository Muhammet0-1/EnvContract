# EnvContract

Compare the **keys** in two explicitly supplied local dotenv files without printing their values. A small, offline Python standard-library CLI; no installation, environment loading, interpolation, network requests, shell execution or automatic file discovery.

Türkçe: [Kullanım rehberi](README.tr.md).

## Quick start

The intended baseline is Python 3.10 or newer; compatibility with older versions is unverified. Actual verification: Linux x86_64, Python 3.14.8. Windows, macOS and other Python versions have not been tested.

Extract this directory and run commands from it. `reference.env` describes expected keys; `target.env` is the file to inspect. Every bundled value is synthetic.

```text
python3 envcontract.py examples/reference.env examples/target.env
python3 envcontract.py examples/reference.env examples/target.env --json
python3 envcontract.py examples/reference.env examples/target-fixed.env
python3 -m unittest discover -s tests -v
```

The first two commands return **1**. They report missing `API_TOKEN`, extra `LEGACY_FLAG`, repeated `LOG_LEVEL` on target lines 4 and 5, and empty `DATABASE_URL` on target line 3. The fixed demo returns **0**. The tool never fixes files; `target-fixed.env` is a separate prepared example.

```text
EnvContract: findings
missing: API_TOKEN
extra: LEGACY_FLAG
duplicates.reference: (none)
duplicates.target: LOG_LEVEL [lines 4, 5]
empty.reference: (none)
empty.target: DATABASE_URL [lines 3]
exit_code: 1
```

Replace both paths with files you deliberately choose. Use only local files you are entitled to inspect. No secret values belong in command-line arguments. Paths are not printed by EnvContract, but your shell history or process listing can still contain the arguments. Do not upload real dotenv files for help.

## Findings and exit codes

- `0`: no findings within this narrow comparison. Two empty files, or the same nonempty valid file passed twice, can also return 0.
- `1`: missing/extra names, duplicate assignments, or empty values in either file.
- `2`: invalid arguments, unreadable/nonregular/oversized/changing input, unsupported syntax or encoding; an output failure also returns 2 where possible.

Missing means a reference key absent from the target. Extra means a target key absent from the reference. Names are case-sensitive, even on systems where the eventual application may behave differently. Duplicates include **all** assignment line numbers; empties include every empty occurrence. No last-value-wins rule hides earlier assignments. Values are never compared for equality.

An empty reference placeholder is a finding too. Populate the reference with harmless, nonempty example values when you want a clean baseline. A whitespace-only quoted value is treated as empty, even though another loader might preserve that whitespace. There is no optional-key, ignore, autofix or allow-empty feature.

## Supported dotenv subset

This is a deliberately limited format, not a universal dotenv parser or a replacement for your application's loader.

- UTF-8, optionally one BOM at the very beginning. LF and CRLF line endings; a final line without a newline is accepted. Each file is limited to **1,048,576 bytes**, including BOM/comments.
- Empty lines and lines whose first non-space/tab character is `#` are ignored.
- Assignments use `KEY=VALUE`. ASCII key names must match `[A-Za-z_][A-Za-z0-9_]*`. Spaces/tabs around the name, `=` and unquoted value are accepted.
- An unquoted `#` begins a comment, with or without a preceding space. Quote a literal hash. Unquoted inner spaces and `=` are accepted; single/double quotes inside an unquoted value are rejected.
- Single-quoted and double-quoted values must close on the **same physical line**. The matching quote terminates the value. After it, only spaces/tabs and an optional `#` comment are allowed. The opposite quote character may occur inside.
- Backslashes and backticks in values are rejected. This includes escaped quotes, literal `\n`, Windows backslash paths and line continuation. Use a supported literal representation only if your application agrees with it; do not mechanically rewrite a production file to satisfy this checker.
- `$NAME`, `${NAME}` and `$(...)` are accepted as literal nonempty text, including in quotes. They are **never expanded or executed**. A clean report does not establish that their dependencies exist or their eventual resolved values are nonempty.
- Control/format/surrogate/private-use/unassigned characters and Unicode line/paragraph separators are rejected, except supported tabs and line endings. Embedded BOM, bare CR, NUL and terminal escape characters are errors. UTF-16 and invalid UTF-8 are rejected.
- `export`, bare names without `=`, multiline quoted values, JSON containing unquoted quote characters, and other unsupported syntax return 2. Values of supported assignments remain private; ignored comments are never echoed.

Only regular files are read. A user-supplied symlink to a regular file is followed. Named pipes/devices are rejected; POSIX reads use nonblocking open to avoid waiting for a FIFO writer. A detected size/mtime change during reading is rejected, but this is not a coherent snapshot of two actively changing files. Compare stable copies if another process is modifying them.

## Output contract and privacy

Text and JSON reports go to stdout; normal diagnostic paths leave stderr empty. JSON uses `schema_version: 1`, `status`, `exit_code`, `findings` and `errors`. Arrays are sorted by key name; line numbers follow file order. There are no timestamps or file paths, making unchanged input output repeatable.

On input errors, `findings` is `null`; `errors` contains the input role (`reference`, `target` or `arguments`), a fixed error code and sometimes a line number. The first error stops evaluation. Exception text, raw lines, values and invalid CLI arguments are not echoed. A broken output stream may prevent a complete report.

**Key names can also be confidential.** Review reports before sharing. This tool is not a secret scanner or anonymizer. It reads selected values into process memory to classify their syntax and emptiness; it does not provide secure memory erasure, protection from a compromised host, or protection from external tracing. A key that embeds sensitive text will appear in findings as a key.

No report validates passwords, endpoints, variable types, runtime precedence, required application variables not listed in the reference, availability or security. `synthetic_token` is only demo text. Never deploy it as a credential.

## Alternatives and sources

[dotenv-linter](https://github.com/dotenv-linter/dotenv-linter) already provides checking, fixing and file comparison. [dotenv-safe](https://github.com/rolodato/dotenv-safe) loads variables and checks expected names against the resulting Node.js process environment. These are established alternatives; EnvContract makes no novelty or superiority claim. Its scope is two explicit files, standard-library Python, conservative syntax, and value-free reports.

The [dotenv parsing rules](https://github.com/motdotla/dotenv#what-rules-does-the-parsing-engine-follow) include features outside this subset. Consult the loader used by your own application. Tests use Python's [unittest](https://docs.python.org/3/library/unittest.html). Sources checked 29 October 2026.

## License

MIT text is supplied in `LICENSE` for the proposed release. Repository name and license are part of the owner's final publication review; this local package has not been published.
