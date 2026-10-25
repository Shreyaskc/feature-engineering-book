# Vendored original book module

`foundations_lab.py` is an unchanged copy of the original Chapters 1–2 book
module at `book1-foundations/lab/foundations_lab.py`. The baseline fixture
`fixtures/base.json` is also an unchanged copy. This is reuse of this book's
original lab, not a third-party dependency.

Chapter 7 imports its immutable source records, strict source adapter and
revision-selection contract. Chapter 7's additional fixture is separately
named `chapter7_extension.json`. No deletion or restoration fixture is used.
