# Feature engineering companion labs

Portable Python and SQLite labs cover data contracts, point-in-time feature computation, transformations, validation, delivery and replay. The fixtures are synthetic and the required track uses Python standard-library components. Use Python 3.12 or newer with SQLite window-function support.

Start with [setup](docs/SETUP.md), [readiness concepts](prerequisites/README.md), the [chapter map](docs/CHAPTER_MAP.md) and [practice exercises](docs/LAB_PRACTICE.md). [Canonical listings](docs/LISTINGS.md) map commands to their executable sources.

```sh
python3 -B verify_all.py --source-only
python3 -B verify_all.py --check-env
python3 -B verify_all.py --prerequisites-only
python3 -B verify_all.py --chapter 03
python3 -B verify_all.py
python3 -B -m unittest discover -s tests -v
```

Use --chapter followed by a two-digit chapter number, such as `--chapter 03`. The full runner executes selected lessons in fresh local copies. Keep assertions enabled and inspect exit status and semantic results. Hosted CI performs source checks only and executes no labs or models.

The curated software baseline and synthetic expected contracts under provenance/ support reproducibility; raw execution evidence and original private review materials are excluded. [Data definitions](DATA_DICTIONARY.md), [data provenance](docs/DATA_PROVENANCE.md) and [troubleshooting](docs/TROUBLESHOOTING.md) describe scope and limitations. These finite teaching examples do not establish production performance or correctness for other datasets.

User-owned companion software and associated documentation use [MIT](LICENSE), subject to [license scope](LICENSE_SCOPE.md) and [third-party notices](THIRD_PARTY_NOTICES.md). Manuscripts, covers, illustrations and book-production programs are separate private works.
