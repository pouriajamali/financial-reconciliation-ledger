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
The report names the audited book and hashes the exact statement bytes and ordered
snapshot receipt list. Different books at the same sequence remain distinguishable;
input whitespace changes the raw-input hash while the same audited snapshot hash
stays stable. A concurrent later append cannot enter the captured snapshot digest.
Those hashes bind observations, not authenticity or source/use rights.

Existing baselines: [TigerBeetle data modeling](https://docs.tigerbeetle.com/coding/data-modeling/)
and [reliable submission](https://docs.tigerbeetle.com/coding/reliable-transaction-submission/),
[Microsoft SQLite transactions](https://learn.microsoft.com/en-us/dotnet/standard/data/sqlite/transactions),
and [SQLite atomic-commit limits](https://www.sqlite.org/atomiccommit.html).
This sample adds a bounded guided demo, inspectable evidence and ready .NET bundles;
it does not replace a specialized ledger or establish demand. **No performance
experiment was run and no speed advantage is claimed.**


## M1: finding a specific synthetic capture discrepancy

Exact ID/amount matching already existed. The added capability is a bounded,
hash-bound `discrepancies.json` for standalone comparison, retaining every issue
with request ID, statement row, expected/actual amount and audited post sequence.
It uses the existing parsed statement and captured snapshot, without a second
store read or an Apply call. Existing inputs, summary schemas, exit codes and
receipt bytes remain compatible; the legacy demo is unchanged.

Two literal counterexamples keep the evidence independent of the detail builder:
A100/B200 against A99/X1/X2/A98 yields seven issues (D2/U2/W2/M1), while1000 X1
rows yield2001 issues (D999/U1000/M2/W0). Counts overlap deliberately; they are not
unique affected payments. Scope flags can fail even with empty details.

All pending writes precede publication; details and text precede the final summary.
Tests exercise each write/rename, ownership change and collision; failures remain
incomplete and leave owned evidence. The final marker is not a power-loss-atomic
multi-file transaction. Direct internal over-limit values test both output guards;
no valid-input cap reachability or performance claim is inferred.

No-post checks establish unchanged logical facts and clean/quiescent file hashes.
The existing SQLite open still allows normal hot-journal recovery, so arbitrary
crashed books are outside the physical no-write observation. The scenario remains
synthetic LAB capture comparison, with no PSP integration, real currency, new fee,
refund/partial-settlement handling or case queue. Customer demand, revenue and
accounting certification remain unproven.

## Versioned native evidence and downloads

[Preview v0.1.0-preview.2](https://github.com/pouriajamali/financial-reconciliation-ledger/releases/tag/v0.1.0-preview.2)
uses signed annotated tag `55a88ef8bed94ac55d961f898f8544466917d5dd` at source
[`68aaecf26e9cd87190445f936c6df660d67e6bc5`](https://github.com/pouriajamali/financial-reconciliation-ledger/tree/68aaecf26e9cd87190445f936c6df660d67e6bc5).
[Exact-tag CI run 42880953244](https://github.com/pouriajamali/financial-reconciliation-ledger/actions/runs/42880953244)
recorded Windows 144 passed / 0 failed / 1 explicit Linux-only FIFO skip and
Ubuntu 145 passed / 0 failed / 0 skipped. Symlink refusal passed on both runners;
Linux FIFO refusal passed on Ubuntu. Each job built, extracted and executed its
actual matching-OS self-contained archive: 22 package checks passed per OS, with
runtime 10.0.15 and provider assembly 10.0.15.0 in the test receipts.

The aggregation job reused those tested runtime archives without rebuilding,
verified their manifests/hashes, and generated the exact tagged source ZIP.
Use the versioned downloads and [known-key verification guide](../PROVENANCE.md)
before extracting or running them. Signature verification and native tests have
different coverage; neither is accounting, security, clean-install or business
certification. A documentation-only CI success is not native execution evidence.

The archived README/provenance text remains its source-time snapshot; current
documentation updates publication pointers without changing frozen package bytes.
The older [v0.1.0-preview.1 release](https://github.com/pouriajamali/financial-reconciliation-ledger/releases/tag/v0.1.0-preview.1)
and its [f137244914e8b392fffab386756fa12eb43f00f1 source](https://github.com/pouriajamali/financial-reconciliation-ledger/tree/f137244914e8b392fffab386756fa12eb43f00f1)
retain their original assets, signatures and reproduction baseline.
