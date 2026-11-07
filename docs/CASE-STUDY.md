# Decisions and their limits

The problem is a small reproducible journal exercise: an uncertain response after
a local commit must not create a second post on an identical retry, while a
different request with the same ID must not masquerade as the original.

One immediate SQLite transaction binds identity, account splits, canonical request
hash and exact receipt. Request spelling and split order are normalized explicitly.
The same receipt is returned before new-post quotas are checked, even at1000 rows.
A write lock serializes two actual clients; tests assert the resulting records and
receipts rather than measuring throughput.

The two interruption tests use only the test assembly's own child executable.
Bounded IPC identifies nonce, phase and actual PID before the parent terminates
that owned process. A precommit test observes no partial journal/splits/receipt;
a postcommit test observes a committed receipt and retrieves it through retry.
Neither demonstrates power-loss durability, external replication or generic
distributed exactly-once delivery. A lost response is not called a rollback.

Read acceptance audits exact schema/trigger text, actual SQLite types, referential
consistency, balanced splits and canonical receipt bytes. Fixtures deliberately
store TEXT/REAL/BLOB in place of an integer, restore schema text, and verify that
the resulting book is refused; reader coercion cannot make that valid. These
checks do not authenticate history against an owner able to rewrite a whole file.

Reconciliation identifies one audited snapshot. A later append is outside its named
sequence. Duplicate rows remain counted, with exact missing/unexpected/duplicate/
amount totals and bounded generic diagnostics. Invalid JSON is file-fatal; report
write failure is incomplete. Agreement with a synthetic statement leaves provenance
UNVERIFIED, freshness NOT_CHECKED and external completeness NOT_PROVEN.

Existing baselines: [TigerBeetle data modeling](https://docs.tigerbeetle.com/coding/data-modeling/)
and [reliable submission](https://docs.tigerbeetle.com/coding/reliable-transaction-submission/),
[Microsoft SQLite transactions](https://learn.microsoft.com/en-us/dotnet/standard/data/sqlite/transactions),
and [SQLite atomic-commit limits](https://www.sqlite.org/atomiccommit.html).
This sample adds a bounded guided demo, inspectable evidence and ready .NET bundles;
it does not replace a specialized ledger or establish demand. **No performance
experiment was run and no speed advantage is claimed.**
