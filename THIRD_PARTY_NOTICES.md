# Third-party notices

The lab implementations, tests and synthetic fixtures are original book-companion software supplied by the project owner. Reused foundation and serving modules are copies of that same lab software; their existing attribution and source hashes are retained. No outside data or model was used to create a claimed production result.

| Component | Use | Applicable upstream terms | Bundled here? |
|---|---|---|---|
| CPython and its standard library | Local interpreter and standard-library modules; tested on CPython 3.14.6 | [Python Software Foundation license and included notices](https://docs.python.org/3.14/license.html) | No interpreter or standard-library distribution is bundled. Runtime imports do not relicense Python. |
| SQLite | Local in-memory SQL through Python's sqlite3 module; tested SQLite 3.53.4 | [SQLite public-domain dedication](https://www.sqlite.org/copyright.html). Separate upstream build scripts may have other terms. | No SQLite binary or source distribution is bundled. |
| actions/checkout v4.2.2, commit 11bd71901bbe5b1630ceea73d27597364c9af683 | Hosted source/provenance workflow | [Upstream MIT license and copyright](https://github.com/actions/checkout/blob/v4.2.2/LICENSE) | Referenced by workflow; its implementation is not vendored. |

The historical bootstrap script links to official Python and SQLite source downloads and their hashes. Downloaded upstream releases retain their own licenses; the project's MIT file does not replace them. Do not assume licenses for any future dependency, external dataset or model. Preserve its actual upstream notices and record its provenance before adding it.

The project license text is based on the [official SPDX MIT text](https://spdx.org/licenses/MIT.html), with only the copyright year and holder placeholder filled. Full manuscript prose, covers and book-production sources are excluded; no manuscript license is granted.
