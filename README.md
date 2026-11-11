# Financial Reconciliation Ledger

A guided .NET/SQLite exercise: balanced synthetic journal posts, exact retry
receipts and offline statement comparison. **No real money or account connection.**
The useful result is the engineering decision and its evidence: what is rejected,
what survives a controlled process interruption, and which test demonstrates it.

## Complete discrepancy reports: 0.1.0-preview.2

The current preview adds complete per-row discrepancy details to standalone
`reconcile`. Use the versioned packages and verification files below; the
immutable older preview remains available for its original behavior.

`discrepancies.json` identifies each missing/unexpected/duplicate/wrong-amount issue
by synthetic request ID,1-based statement row, audited sequence and expected/actual
integer amounts. Categories overlap; details are never silently truncated. It is
bound to the exact summary bytes and the same single snapshot. Check the summary's
outcome and scope flags too: empty details do not override a mismatched book/scope.
See the [sidecar contract](docs/CONTRACT.md) and
[release notes](docs/RELEASE-v0.1.0-preview.2.md).

Both summary formats, exit codes, strict input JSON, LAB/scale2 accounts and saved
receipts remain compatible. Only standalone comparison adds the file; `demo` keeps
its existing output. No posting/settlement action or human case queue is added.

## Try the ready package

[Preview v0.1.0-preview.2 and downloads](https://github.com/pouriajamali/financial-reconciliation-ledger/releases/tag/v0.1.0-preview.2)
contains self-contained Windows x64 and Ubuntu 24.04/glibc x64 bundles, plus source.
An installed .NET SDK is unnecessary for those bundles. Existing native OS
prerequisites still apply; this is not a clean-machine certification.

| Package | Download |
|---|---|
| Windows x64 | [ZIP](https://github.com/pouriajamali/financial-reconciliation-ledger/releases/download/v0.1.0-preview.2/financial-reconciliation-ledger-v0.1.0-preview.2-win-x64.zip) |
| Ubuntu 24.04/glibc x64 | [tar.gz](https://github.com/pouriajamali/financial-reconciliation-ledger/releases/download/v0.1.0-preview.2/financial-reconciliation-ledger-v0.1.0-preview.2-linux-x64.tar.gz) |
| Exact tagged source | [ZIP](https://github.com/pouriajamali/financial-reconciliation-ledger/releases/download/v0.1.0-preview.2/financial-reconciliation-ledger-v0.1.0-preview.2-source.zip) |

Verification files: [SHA256SUMS.txt](https://github.com/pouriajamali/financial-reconciliation-ledger/releases/download/v0.1.0-preview.2/SHA256SUMS.txt),
[checksum signature](https://github.com/pouriajamali/financial-reconciliation-ledger/releases/download/v0.1.0-preview.2/SHA256SUMS.txt.sig),
[public signing key](https://github.com/pouriajamali/financial-reconciliation-ledger/releases/download/v0.1.0-preview.2/SIGNING-PUBLIC-KEY.pub).
Verify them before extracting or executing a package.

Download your archive, `SHA256SUMS.txt`, its `.sig` and `SIGNING-PUBLIC-KEY.pub`.
Follow the [known-key verification guide](PROVENANCE.md) **before extracting or
running**. Missing signature assets mean incomplete publication, not permission to
skip verification. SSH checksum signatures establish origin/integrity, not OS code
signing, exclusive ownership or restrictions on copying permitted by MIT.

Extract into a fresh directory, open a terminal there, and run:

```powershell
.\ledger.exe --version
.\ledger.exe demo .\demo-new
.\ledger.exe post .\demo-new\book .\demo-new\post.json
.\ledger.exe reconcile .\demo-new\book .\demo-new\statement-match.json .\match-report-new
.\ledger.exe reconcile .\demo-new\book .\demo-new\statement-negative.json .\negative-report-new
```

```sh
./ledger --version
./ledger demo ./demo-new
./ledger post ./demo-new/book ./demo-new/post.json
./ledger reconcile ./demo-new/book ./demo-new/statement-match.json ./match-report-new
./ledger reconcile ./demo-new/book ./demo-new/statement-negative.json ./negative-report-new
```

Use new output names each time. The retry returns `replayed` with the **same saved
receipt bytes and SHA256**, keeping two journal entries. Matching comparison exits0;
the deliberately negative comparison exits2 and reports missing1, unexpected2,
duplicate1 and wrongAmount1. That negative outcome is expected evidence.
Read `demo-new/report/summary.json` and `summary.txt`, or each comparison's report.
Standalone comparison folders also contain `discrepancies.json`; the demo report
keeps its existing format. The book remains local; nothing is sent over a network.

## Decisions and proof

| Decision | Observable behavior | Reproducible test |
|---|---|---|
| Integer minor units, fixed LAB/scale2 | Decimal/exponent/string/overflow, unbalanced, duplicate/unknown accounts rejected | `integer-*`, `post-unbalanced`, `post-duplicate-account` |
| One SQLite transaction for journal, splits and receipt | Before-commit owned child interruption leaves no partial post | `owned-process-before-commit` |
| Commit can precede response delivery | After-commit interruption means response loss; same-ID retry recovers the original receipt | `owned-process-after-commit-before-response` |
| Canonical content binds request ID | Reordered equivalent input replays; changed content conflicts; full-capacity replay still works | `journal-reordered-request-exact-receipt`, `capacity-replay-and-new-refusal` |
| Audit stored facts before accepting a book | Altered schema/trigger/storage class/split/hash/receipt is incomplete | `audit-*` |
| Compare one identified snapshot | Later appends stay outside that snapshot; duplicate rows are counted | `comparison-snapshot-later-append`, `comparison-exact-error-counts` |
| Complete discrepancy details | Exact seven-issue and full 2001-issue reports retain overlapping counts and summary binding | `m1-ac02-literal-seven-issues`, `m1-ac07-literal-2001-issues` |
| Report failure is never green | Malformed statement or occupied pending report exits1 | `statement-duplicate-key-cli-incomplete`, `report-collision-never-pass` |

These process tests are **not power-loss durability or distributed exactly-once
proof**. Application append-only guards are not authenticated or tamper-proof
history: a file owner can replace a book with another self-consistent book.
Test IPC limits the phase line and caps stderr at4KiB; the real oversized-child
case `owned-process-stderr-byte-budget` verifies rejection before acceptance.

## Small, explicit contract

One `synthetic-ledger-v1` profile, accounts `cash`, `clearing`, `fees`, toy unit
`LAB`, scale2. LAB is not a real/ISO currency. Posts contain2..3 unique splits,
one positive debit or credit per split, up to10^12 minor units each, balanced sums.
No floating-point money, FX, interest, tax, real chart/account import or valuation.
IDs use bounded ASCII; input is strict JSON, not a generic CSV parser.

```text
ledger init <new-book-directory>
ledger post <owned-book-directory> <synthetic-post.json>
ledger reconcile <owned-book-directory> <synthetic-statement.json> <new-report-directory>
ledger demo <new-directory>
```

Only this tool's marked, versioned books are accepted. It does not repair arbitrary
SQLite databases. Normal SQLite journal recovery is permitted for an owned book;
the tool never manually removes journals or resets an existing directory. Busy/I/O
or unsupported inputs are incomplete. There are no SQL, plugin, host, settings,
fault-injection, network, real account or order options.

Input1MiB/depth8;1000 journal entries/3000 splits;1000 statement rows;16MiB book
plus bounded sidecars;20 generic diagnostic examples plus exact totals. Observed
links, network paths, controls and nonregular inputs are refused. These checks are
bounded application safeguards, not a hostile-file/native-memory/filesystem sandbox.

Comparison creates no new journal posts. Clean, quiescent book files are checked
for unchanged hashes/inventory; normal SQLite hot-journal recovery remains allowed,
so this is not physical read-only access for every crashed state. Sidecar publication
can leave pending/orphan files after failure; retry into a fresh output directory.

Statement amounts are **total debit minor units per request**, not net balances.
The declared `throughSequence` must equal the audited snapshot's last sequence.
Agreement leaves provenance **UNVERIFIED**, freshness **NOT_CHECKED**, and external
completeness **NOT_PROVEN**. No source authenticity, use-rights or accounting
certification is inferred. Reports include debit-minus-credit toy balances only.
Standalone comparison JSON identifies the audited book, snapshot sequence, SHA256
of the exact statement bytes, and SHA256 of the ordered sequence/receipt-hash list.
These bind the observed inputs/snapshot, without authenticating their origin.

Exit0: completed accepted operation or matching comparison. Exit2: completed
rejection/comparison failure. Exit1: incomplete, unsupported, malformed, I/O,
timeout or report failure. A missing report after response loss is not success.

## Build and reproduce

Requires .NET SDK10.0.404 and Python3.12 for packaging. Dependencies are locked:
Microsoft.Data.Sqlite10.0.15, SQLitePCLRaw2.1.13 and resolved transitive packages;
runtime10.0.15. CI uses matching Windows/Ubuntu builds, tests actual extracted
archives and aggregates those same archives without rebuilding them.

```sh
dotnet restore tests/Ledger.Tests --locked-mode
dotnet run --project tests/Ledger.Tests -c Release --no-restore -- --work artifacts/tests-new
```

M1 regressions include literal seven-issue and2001-issue cases, ordinal IDs,
Int64 values, independent summary/sidecar hashes, same-build byte replay, one-snapshot
later-append behavior, quiescent no-post checks and each pending-write/final-rename
ownership/collision/failure boundary. Cap rejection is tested directly with deliberately
over-limit internal values; valid bounded inputs cannot reach those guards today.

[Exact-tag native CI](https://github.com/pouriajamali/financial-reconciliation-ledger/actions/runs/42880953244) ran at
`68aaecf26e9cd87190445f936c6df660d67e6bc5`: Windows 144 passed / 0 failed /
1 explicit Linux-only FIFO skip; Ubuntu 145 passed / 0 failed / 0 skipped.
The symlink case passed on both runners. Each job built, extracted and executed
its actual matching-OS archive, with 22 package checks passing per OS. These
observations are separate from the earlier source and documentation-only CI runs.

Tests create fresh synthetic books. Interruption/concurrency workers belong only
to the test assembly and are excluded from distributables. OS-specific skips are
explicit in `receipt.json`; existing WSL hosts are not empty-OS installs. No
benchmark or speed improvement is claimed. See [case study](docs/CASE-STUDY.md),
[contract](docs/CONTRACT.md), [contributing](CONTRIBUTING.md) and [notices](NOTICE.md).

## Public example, private customer work

This standalone reusable synthetic sample is public under [MIT](LICENSE), created
for Pouria Jamali with AI assistance. Customer-specific code, data, credentials,
configuration, deployments and unreleased commercial additions belong in separate
private work; never submit them here. No private/shared/employer project code,
tests, schemas, contracts or ideas were transferred. Existing MIT grants remain
unchanged; making a repository private cannot retract previously published copies.
No customer demand, sales, revenue, exclusive authorship or independent-skill claim.

[CI resource policy](docs/CI-POLICY.md): documentation-only changes get real lightweight document/pipeline checks; source, tag and manual runs retain native validation. Published runtime tags and release assets remain unchanged.

## Source and published runtime

The discrepancy sidecar uses SDK 10.0.404, runtime/provider 10.0.15 and
SQLitePCLRaw 2.1.13. Reproduce the current packages from
[signed tag v0.1.0-preview.2](https://github.com/pouriajamali/financial-reconciliation-ledger/tree/v0.1.0-preview.2), exact source
[`68aaecf26e9cd87190445f936c6df660d67e6bc5`](https://github.com/pouriajamali/financial-reconciliation-ledger/tree/68aaecf26e9cd87190445f936c6df660d67e6bc5).
Later documentation on `main` does not change these tagged archive bytes.

Archives retain the documentation snapshot at their source commit, including
prepublication status wording. This current page provides the updated download
pointers; old archives are not rewritten to refresh that historical wording.

The immutable [previous preview v0.1.0-preview.1](https://github.com/pouriajamali/financial-reconciliation-ledger/releases/tag/v0.1.0-preview.1)
retains its original runtime/provider 10.0.14 and SDK 10.0.403 reproduction baseline.
Its exact [frozen source f137244914e8b392fffab386756fa12eb43f00f1](https://github.com/pouriajamali/financial-reconciliation-ledger/tree/f137244914e8b392fffab386756fa12eb43f00f1)
and existing assets, checksums, signatures and tags remain unchanged.
