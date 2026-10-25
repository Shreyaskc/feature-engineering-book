# Execution scope and optional integrations

Every core lesson runs offline with synthetic data and the Python standard library. Chapter 3 runs real local SQLite queries in an in-memory database. Chapter 7 writes disposable local files for staged datasets, checkpoints and release-pointer simulations. Chapters 6, 9 and 10 simulate publication, cache, observability and recovery contracts.

No Spark, Flink, Kafka, Feast, cloud object store, hosted feature store, Redis, remote database, managed orchestration, paid API, deployed service or real external rollback was executed. Those integrations are not implemented as runnable labs in the confirmed source archive. No optional adapter is presented as verified or required.

The lessons test finite declared contracts, not engine-specific watermark behavior, distributed transactions, multi-host races, production latency, business impact or predictive model quality. Chapter 10 emits feature rows; it does not fit a model and carries an explicit training boundary.

Before adding an integration, keep it in a separate optional directory with its own prerequisites, pinned dependencies, sample-data provenance, local/no-mutation mode and measured evidence. Do not infer distributed guarantees from a local simulator. Actual execution must remain on the approved Mac mini unless the owner changes that requirement. Hosted CI checks source/provenance only.
