# Data provenance

All supplied records are synthetic teaching fixtures from the confirmed companion ZIP version 0. No employer, personal customer or confidential data is used. No external dataset was downloaded, so there is no open-data license or sampling pipeline to imply. Integer times are relative teaching minutes and amounts are illustrative units; they are not real transaction observations.

| Lesson | Fixture origin | Branch and meaning |
|---|---|---|
| Readiness | `prerequisites/book_refresher_examples.json`, `fixtures/readiness.json` | Two reader-draft refresher examples, with the SQL ownership correction explicitly recorded, plus a small separately labeled synthetic join/ranking preview; not part of the 72 chapter-listing population. |
| Chapters 1–2 | `chapters01_02/fixtures/*.json` | Base A–D history; named deletion/restoration extensions. Known zero and unknown history remain distinct. |
| Chapter 3 | `chapter03/fixtures/*.json` | The same base contract, independent SQLite selection, isolated deletion/restoration exercises. |
| Chapter 4 | `chapter04/chapter4.py` constants | Synthetic decisions, outcomes and finalization certificates. Five eligible rows, decision-grain joins and fit-only preprocessing. |
| Chapter 5 | `chapter05/chapter5.py` constants | Fixed [540,600) window, immediate/delayed publication and separately named late E. |
| Chapter 6 | `chapter06/parity_lab.py` / `expected_outputs/fixture.json` | Derived source/publication trace with delayed store/cache visibility; not a deployed cache. |
| Chapter 7 | `chapter07/fixtures/base.json`, `chapter7_extension.json` | Separate B2 correction and late E; corrected rolling values [102,112,0]. |
| Chapter 8 | `chapter08/fixtures/*.json` and controlled fault functions | Five allowlisted teaching faults and seeded finite generated cases. No mutation of the reference source. |
| Chapter 9 | `chapter09/fixtures/*.json`, metric and action contracts | Fictional incident and retained local recovery evidence. Four replay requests are not four independent production trials. |
| Chapter 10 | `chapter10/fixtures/*.json` | Base plus challenge A2/F1/late E; distinct from Chapter 7's B2 branch. |

The shared base produces historical D1=50 and rolling D2=95. Holding [540,600) fixed and moving knowledge to 610 gives 85. Chapter 10's challenge produces D1/D2=50/100, closed fixed-window=90, audit-at-620=105. These differences are part of the curriculum.

[Source identity](../provenance/CODE_BASELINE.json) records public source descriptions, versions, sizes and SHA-256 values without private storage identifiers. [Upstream source manifests](../provenance/CODE_BASELINE.json) retain earlier archive/member history. [Active file hashes](../provenance/LAB_FILES.json) and [explicit differences](../provenance/UPSTREAM_DIFF.json) record repository adaptation. Hashes establish local byte identity, not authorship or a signature.

Expected outputs remain imported, including their old runtime metadata. Observed artifacts record the executing runtime honestly. Only the runtime leaves named by the verifier are compared separately; runtime stays part of Chapter 7 dataset identity and Chapter 10 retained-artifact verification.
