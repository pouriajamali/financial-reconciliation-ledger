# Synthetic ledger contract v1

The public exercise is fixed to synthetic-ledger-v1, LAB scale2, cash/clearing/fees.
It is not a bank, ledger service, arbitrary SQLite repair or accounting certification.

## Inputs

`init <new-book-directory>` creates a fresh marked book. The32-byte lowercase hex
marker/book ID, app ID0x4c414231, user_version1 and fixed schema bind acceptance.
Never use real statements or accounts. Paths with controls, network roots, observed
links or unsupported file types are refused. Filesystem replacement races/native
memory are not a security sandbox claim.

Post JSON has exactly profile/bookId/requestId/unit/scale/splits. Each of2..3 split
objects has exactly account/debit/credit. Accounts are unique known labels; one
side is a positive integer <=10^12 and the other zero; debit/credit sums must match.
Integer tokens contain digits only: no exponent, fraction, negative or string.
Request IDs match [A-Za-z0-9][A-Za-z0-9_-]{0,63} with absolute anchors. Unknown,
missing or duplicate object keys are invalid; no trimming or silent coercion.

Statement JSON has exactly schema/bookId/unit/scale/throughSequence/rows.
Schema is synthetic-statement-v1. Each row has requestId/amountMinor; amount is
integer0..3*10^12 and means total debit per post. Unit is a bounded ASCII label,
scale0..9 and sequence0..1000. Valid wrong book/unit/scale/sequence values produce
completed comparison failure. Duplicate rows are preserved and counted; duplicate
JSON keys or malformed structure make the entire assessment incomplete.

Input1MiB/depth8,1000 journal posts/3000 splits/1000 statement rows,16MiB main book,
32MiB combined known sidecars, maximum5 known book files and20 generic diagnostic
examples with exact independent totals. No settings, plugins, SQL or remote inputs.

## Commit and retry

One immediate SQLite transaction includes journal identity, all splits and exact
receipt bytes/hash. Canonical fixed field order and account-sorted splits bind ID
to content. Same ID/content returns exactly the original receipt bytes/hash even
when input key/whitespace/split order differs or the book is full. Different content
with that ID is conflict. A new post at capacity is rejected within that same write
transaction. No second row is created by replay.

The application is append-only; exact SQL triggers refuse updates/deletes. Before
acceptance, audit schema/trigger identity, actual storage types, foreign keys,
sequence/split balance and canonical request/receipt agreement. Coercible values
are insufficient. A self-consistent rewritten file cannot be detected without an
external trust anchor, so this is not authenticated/tamper-proof history.

SQLite uses private cache, pooling off, parameters, foreign keys on, extensions off,
trusted_schema off, DELETE journal and FULL synchronous. Only owned versioned books
permit normal SQLite recovery. Foreign headers are refused before opening; no
manual journal deletion/reset or arbitrary database repair. SQLite busy/I/O/timeouts
are incomplete. This is not a guarantee of hostile-filesystem operation deadlines.

Before-commit owned process interruption may demonstrate no partial post for that
case. After-commit/before-response interruption is uncertain response delivery;
same-ID retry recovers the committed receipt. Tests bind nonce/phase/PID to their
own executable. Neither establishes power-loss durability/distributed exactly-once.
Fault probes exist only in the excluded test assembly, never public CLI options.

## Reconciliation and reports

Compare one audited read-transaction snapshot; explicitly report its last sequence.
Declared throughSequence must equal it. A later append is outside that identified
snapshot. Count missing expected IDs, unexpected rows, duplicate rows beyond the
first and wrong-amount rows separately; never silently net or discard duplicates.
Book/unit/scale/scope mismatch are independent failure flags. Agreement leaves
provenance UNVERIFIED, freshness NOT_CHECKED, external completeness NOT_PROVEN.

Exit0 means completed accepted operation/matching assessment, exit2 means completed
rejection/comparison failure, exit1 means incomplete/unsupported/parse/I/O/timeout/
report failure. Fresh marked report directories use pending files and JSON last;
missing/invalid output after response loss is not success. Reports include source/
build/version and limits without raw exceptions or absolute private paths. Hashes
bind bytes, not source rights or authenticity.
Comparison reports name bookId (audited book), declaredBookId (statement claim),
and statementSha256 from the exact already-read input byte buffer. On mismatch
these IDs remain distinct; the declared value never replaces the audited identity.
snapshotDigestSchema is synthetic-ledger-snapshot-v1. snapshotReceiptListSha256
hashes UTF-8 bytes with no BOM/newline of compact JSON in this exact property order:
{"schema":"synthetic-ledger-snapshot-v1","bookId":"<audited id>","throughSequence":2,"receipts":[{"sequence":1,"receiptSha256":"<hash1>"},{"sequence":2,"receiptSha256":"<hash2>"}]}
Receipts are in ascending audited sequence order. Each receiptSha256 hashes the
exact saved receipt TEXT encoded as UTF-8 without adding a newline; the audit
already verifies these bytes against the saved hash/canonical receipt. Empty
books use throughSequence0 and receipts[]. The comparison result names that same
snapshot's last sequence; an append after snapshot capture changes none of its
book/sequence/frame fields. This framing is versioned independently of SQLite.
Init/post/reconcile stdout also includes version/toolBuild; saved receipt bytes
remain independent of the current invocation's outer version/disposition.

Public MIT reusable synthetic sample; customer-specific code/data/config/deployments,
secrets and unreleased commercial additions remain separate private work. No transfer
of shared/private/employer source, tests, data, schemas, contracts or ideas. Existing
MIT/upstream grants remain intact; checksum signing does not prohibit licensed reuse.

## Standalone discrepancy sidecar v1 (source candidate 0.1.0-preview.2)

Standalone `reconcile` adds `discrepancies.json`; the existing `summary.json`,
`summary.txt`, stdout, exit semantics and all saved post/receipt bytes retain their
existing formats. `demo` does not add this sidecar. A synthetic capture fixture
uses debit cash / credit clearing and a separate synthetic statement; the amount
is the post's total debit, never a real payment, balance or net settlement.

The UTF-8/no-BOM sidecar ends with one LF. Its fields, in fixed order, are:
`schema` (`synthetic-reconciliation-discrepancies-v1`), `summarySha256`, `bookId`,
`statementSha256`, `snapshotReceiptListSha256`, `throughSequence`, `issues`.
`summarySha256` hashes the exact summary.json bytes, including its final LF.
Other identities bind the same already-read statement and single audited snapshot
as the summary. No new timestamp, invocation ID or output path is serialized.

Each issue has these fields in this exact order, including explicit nulls:
`code`, `requestId`, `statementRowIndex`, `entrySequence`, `expectedAmountMinor`,
`actualAmountMinor`, `firstStatementRowIndex`. The row index is 1-based in `rows`,
not a text line number. Entry sequence/expected amount refer to an audited post;
they are null for an unknown ID. Actual amount/row index are null for a missing ID.
Only duplicates have a nonnull firstStatementRowIndex. All amounts remain exact
integer minor units, including zero actual amounts and values above Int32 range.

| Code | One issue for each |
|---|---|
| DUPLICATE_REQUEST_ID | Occurrence after the first, pointing to its first row |
| UNEXPECTED_REQUEST_ID | Row whose ID is absent from the snapshot |
| WRONG_AMOUNT | Known-ID row with an unequal amount |
| MISSING_REQUEST_ID | Snapshot post with no statement row of that ID |

Categories overlap: an unknown duplicate is both duplicate and unexpected; a
known duplicate may also have a wrong amount. A known wrong amount is not missing.
IDs use ordinal case-sensitive equality without trimming. Rows appear in statement
order, duplicate first and then unexpected/wrong amount; missing posts follow in
ascending entry sequence. Each code's cardinality equals its existing independent
summary count. All issues are present: at most4000 and2MiB serialized UTF-8 bytes,
including the final LF. Exceeding either guard is incomplete, never truncation.
The existing20 generic diagnostic examples remain separate and unchanged.

Book/unit-or-scale/snapshot-scope mismatches remain summary flags, not row issues.
An empty issues array does not imply pass if a flag fails. For a fixed build, exact
input bytes and unchanged book, reports in fresh output folders are byte-identical.
Whitespace changes the statement hash and summary binding, even if issues agree.
A newly initialized book or changed build is not covered by that byte identity.

All three pending files use CreateNew. Discrepancies are finalized first, text
second and summary.json last. Both a valid summary and its hash-bound sidecar are
required for the new standalone report contract. A collision, ownership change,
cap or write/rename failure exits1 without successful completion. Owned pending or
orphan sidecar files may remain; no output is overwritten or automatically cleaned.
Use a fresh folder to retry. This is not power-loss-atomic publication or a hostile
filesystem/race sandbox. Readers must check the summary outcome, counts and flags.

Comparison adds no posts/replays or journal/split/receipt writes. Clean, quiescent
book file inventory and hashes are checked before/after pass, fail and report
failure. The existing ReadWrite SQLite open may perform normal hot-journal
recovery; physical immutability for every interrupted/crashed state is not claimed.
Only synthetic IDs/amounts belong in these detail files. No new import format,
real currency/account/API, fuzzy matching, fee/refund/partial-settlement workflow
or human case queue is provided. Provenance UNVERIFIED, freshness NOT_CHECKED and
external completeness NOT_PROVEN remain unchanged.
