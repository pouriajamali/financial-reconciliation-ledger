# v0.1.0-preview.2 — complete synthetic discrepancy details

Local source candidate for review; no tag/release or new public download has been
published. Linux execution and exact-source hosted CI remain a later gate.

Standalone `reconcile` adds a complete `discrepancies.json` sidecar bound to exact
summary bytes and the same audited snapshot. Missing, unexpected, duplicate and
wrong-amount issues carry synthetic request IDs,1-based row indices, audited entry
sequences and exact expected/actual minor units. Overlapping counts, mismatch flags,
existing summary/stdout schemas, exits, strict input JSON, LAB/scale2 ledger and
saved post/receipt bytes remain compatible. The legacy demo output is unchanged.

Sidecar limits are4000 issues/2MiB without truncation. Pending files use CreateNew;
details and text are finalized before summary.json. Failed caps, ownership checks,
writes or renames are incomplete and may leave owned pending/orphan evidence.
Retry into a new folder. Comparison never posts; normal SQLite hot-journal recovery
remains permitted, so physical immutability of every crashed book is not claimed.

Servicing: SDK10.0.404, bundled runtime10.0.15, Microsoft.Data.Sqlite/Core10.0.15;
SQLitePCLRaw2.1.13 retained with existing licenses and notices. No new dependency,
schema migration, real account/currency/API, fuzzy matching, new fee/refund/partial
settlement or case queue. Synthetic/local tests do not prove business demand,
financial correctness outside this contract, security certification or throughput.

Future publication must reuse tested matching-OS Windows/Linux archives from the
same signed source commit, include source and signed checksums/key, and verify real
downloads. Existing v0.1.0-preview.1 assets/tags/signatures remain immutable.
