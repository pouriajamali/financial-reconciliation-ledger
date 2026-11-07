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

Public MIT reusable synthetic sample; customer-specific code/data/config/deployments,
secrets and unreleased commercial additions remain separate private work. No transfer
of shared/private/employer source, tests, data, schemas, contracts or ideas. Existing
MIT/upstream grants remain intact; checksum signing does not prohibit licensed reuse.
