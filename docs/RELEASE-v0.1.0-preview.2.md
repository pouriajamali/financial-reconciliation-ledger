# v0.1.0-preview.2 — complete synthetic discrepancy details

Standalone `reconcile` adds a complete `discrepancies.json` sidecar bound to exact
summary bytes and the same audited snapshot. Missing, unexpected, duplicate and
wrong-amount issues carry synthetic request IDs, 1-based row indices, audited entry
sequences and exact expected/actual minor units. Overlapping counts, mismatch flags,
existing summary/stdout schemas, exits, strict input JSON, LAB/scale2 ledger and
saved post/receipt bytes remain compatible. The legacy demo output is unchanged.

Sidecar limits are 4000 issues / 2MiB without truncation. Pending files use CreateNew;
details and text are finalized before summary.json. Failed caps, ownership checks,
writes or renames are incomplete and may leave owned pending/orphan evidence.
Retry into a new folder. Comparison never posts; normal SQLite hot-journal recovery
remains permitted, so physical immutability of every crashed book is not claimed.

Servicing: SDK 10.0.404, bundled runtime 10.0.15, Microsoft.Data.Sqlite/Core 10.0.15;
SQLitePCLRaw 2.1.13 retained with existing licenses and notices. No new dependency,
schema migration, real account/currency/API, fuzzy matching, new fee/refund/partial
settlement or case queue.

## Observed native verification

[Automatic CI run 42877963989](https://github.com/pouriajamali/financial-reconciliation-ledger/actions/runs/42877963989)
verified [runtime source d1fa486eaeb79c1910771b2d1a508505f9316c7f](https://github.com/pouriajamali/financial-reconciliation-ledger/commit/d1fa486eaeb79c1910771b2d1a508505f9316c7f):

- [Windows x64](https://github.com/pouriajamali/financial-reconciliation-ledger/actions/runs/42877963989/job/130046335275):
  144 tests passed, 0 failed, 1 explicit skip (`linux-fifo-refused-before-open`,
  `LINUX_ONLY`). The symlink-refusal case passed on this runner.
- [Ubuntu 24.04/glibc x64](https://github.com/pouriajamali/financial-reconciliation-ledger/actions/runs/42877963989/job/130046335444):
  145 tests passed, 0 failed, 0 skipped, including the Linux FIFO and symlink cases.

Both jobs built, extracted and executed their actual matching-OS self-contained
archives from that exact source commit: 22 package checks passed per OS. These
include literal seven-issue and full 2001-issue comparisons, summary/sidecar binding
and byte-identical repeated reports. Test receipts recorded runtime 10.0.15 and
provider assembly 10.0.15.0. Hosted runner images are existing hosts; this is not
clean-machine installation certification, power-loss durability or a benchmark.
Synthetic evidence does not establish customer demand, financial correctness
outside this contract, accounting/security certification or throughput.

## Archive verification

Before extracting a distributed archive, verify the known-key checksum signature
and then the chosen archive's SHA256 using the [provenance guide](../PROVENANCE.md).
Missing signature assets mean incomplete publication; unsigned matching checksums
alone do not establish authenticated provenance. Commit/SSH checksum signatures
are separate from OS binary signing. Existing v0.1.0-preview.1 assets, tags and
signatures remain immutable.
