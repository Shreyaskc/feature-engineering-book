# Begin here

You need a terminal, an installed CPython 3.12 or newer with its standard `sqlite3` and `venv` modules, and permission to write in this project and its temporary directory. No SQL server or Python packages are needed. Git is useful for cloning and saving exercises; an editor that opens Python, JSON and Markdown is sufficient.

Before Chapter 1, be comfortable with variables, lists, dictionaries, functions, loops, `None`, and reading a small assertion. The reader draft's “Reading the lab code” appendix explains the Python and SQL forms used here. JSON files are input records or expected reports; `null` is Python's `None`. A traceback ends with the error that caused a command to fail. The shell's current directory is where relative paths start.

## 1. Check the installed interpreter

From the repository root:

```sh
python3 --version
python3 -c "import platform, sqlite3; print(platform.python_version()); print(sqlite3.sqlite_version)"
```

The tested Mac has Homebrew's existing CPython **3.14.6** at `/opt/homebrew/bin/python3`, linked to SQLite **3.53.4**. Its Apple-provided `/usr/bin/python3` is **3.9.6**, which is too old. No new interpreter, machine package, credential or service was installed for this work. Other CPython 3.12+ combinations may work; they become verified only after the full command passes on that interpreter. SQLite window-function support is checked directly.

If Python is missing, obtain it from the [official Python downloads](https://www.python.org/downloads/). Choose an installer suitable for your own operating system; that installation is a separate machine change. This guide does not require rebuilding CPython or SQLite. The original exact-version Linux source-build instructions are preserved as historical release evidence in `provenance/upstream/SETUP.md`; that recipe was not run on the Mac.

## 2. Create an isolated environment

Choose an absent `.venv` directory. These commands install no third-party packages and require no network:

```sh
python3 -m venv --without-pip .venv
.venv/bin/python -B verify_all.py --check-env
```

Using the explicit interpreter path keeps the command independent of shell activation. `-B` suppresses bytecode; do not use `-O` or `-OO`, because assertions are part of the checks. A virtual environment isolates packages while retaining its base interpreter and SQLite library. See the [official venv guide](https://docs.python.org/3.14/library/venv.html) and [SQLite window-function documentation](https://www.sqlite.org/windowfunctions.html).

Expected: PASS, the actual interpreter/SQLite versions, assertions enabled, temporary-directory access, SQLite window functions, no required third-party packages, and zero lab suites. This is a readiness check, not test evidence.

## 3. Practice the assumed concepts

Complete the [readiness lab](../prerequisites/README.md) before Chapter 1:

```sh
.venv/bin/python -B verify_all.py --prerequisites-only
```

Expect 12 readiness tests, the two book refresher examples (the SQL body includes explicit connection closure), matching expected/observed JSON and two clean runs. This is distinct from the machine readiness check. It covers None/zero/False, immutable records, time/window boundaries, fixtures/assertions, and small SQL join/ranking previews. Its [source-view map](prerequisite-map.json) is for the book editor.

## 4. Learn progressively

```sh
.venv/bin/python -B verify_all.py --chapter 01
.venv/bin/python -B verify_all.py --chapter 02
.venv/bin/python -B verify_all.py --chapter 03
```

Continue with `04` through `10` using the [chapter map](CHAPTER_MAP.md). Chapters 1 and 2 share one suite. Predict the output before running, inspect the corresponding observed report, try the chapter's exercises, and compare with its worked solutions. Later chapters reuse earlier contracts but keep fixture extensions explicitly separate.

To run all nine distinct suites:

```sh
.venv/bin/python -B verify_all.py
```

Expect progress on stderr, final JSON on stdout, exit code 0 and PASS with the separate readiness module and nine chapter suites. Failure returns a nonzero exit code and FAIL in the named summary. Reports begin as RUNNING to prevent an interrupted rerun from leaving an old PASS. Start with one lesson if a full report feels large.

Commands execute in disposable copies; they do not rewrite the tracked expectations. To experiment, follow the [tested copied-chapter workflow](EXPERIMENTING.md), retaining an absolute path to the original venv and running direct behavioral tests/listings. The copied verifier wrappers need their original parent layout. Directly running `chapter4.py` or `chapter5.py` in the active source directory rewrites recorded artifacts and will correctly fail the next integrity check.

## Dependency contract

Runtime dependencies: CPython standard library, including SQLite window functions. Required third-party dependency count: **zero**. There is deliberately no pip install step, lockfile with unused packages, Spark installation, container daemon or paid API. Actual tested versions and hardware are recorded in [validation](VALIDATION.md). Numeric, ordering, availability, tombstone and provenance assertions remain in force across runtime versions.
