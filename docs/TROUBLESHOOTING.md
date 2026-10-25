# Troubleshooting

| Symptom | Meaning and next step |
|---|---|
| Python reports 3.9.6 | Use the installed newer interpreter that created your environment; the Mac system interpreter is too old. |
| `.venv/bin/python` missing | Run the environment creation command from the repository root. Check `pwd` and the installed `python3`. |
| `No module named sqlite3` or SQL window error | That Python lacks the required SQLite capability. Check its actual linked SQLite, not the separately installed sqlite CLI. |
| “Assertion checks require” / optimized Python | Remove `-O`, `-OO` or optimization settings. Assertions must run. |
| Lesson hash or inventory differs | Review edits against Git and the original archive. Do not regenerate expected outputs or manifests simply to obtain PASS. Run experiments in a copy. |
| Expected semantic output differs | Inspect `generated/<suite>/run_N/commands.json`: it records the exact argv, stdout, stderr and exit code. Investigate the first failing command. |
| Runtime metadata differs | The verifier accepts only listed runtime fields after verifying they match the executing interpreter. All semantic values, code/source hashes and artifact readback remain checked. |
| Unknown history prints `None` / `null` | This is an intentional distinct state from known zero. Check coverage evidence before changing it. |
| Chapter 6 expects 85 while Chapter 4 has 95 | Chapter 6 retains [540,600); Chapter 4's D2 uses [550,610). Different windows answer different questions. |
| A capstone output directory is nonempty | The capstone deliberately rejects overwrite. Use a new path in an experimental copy. The root runner already uses clean directories. |
| PASS with zero suites | Source-only and environment checks execute no lab. `--prerequisites-only` executes 12 readiness tests while reporting zero chapter suites. Run `verify_all.py` without flags for readiness plus all chapter evidence. |
| Temporary-directory error | Use a writable local TMPDIR and rerun. Do not elevate the lesson process or change machine permissions broadly. |

For isolated edits use the [tested copied-chapter workflow](EXPERIMENTING.md). Run behavioral tests and printed listings directly in the copy.

The old per-chapter verification scripts now dispatch to the portable root command. Their upstream implementations, old checksum lists and recorded reports remain in the source ZIP; they are historical artifacts, not the active repository integrity contract.
