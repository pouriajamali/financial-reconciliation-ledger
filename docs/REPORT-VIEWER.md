# Offline report viewer

Open `tools/report-viewer.html` as a local file in a current browser. Select
`summary.json` and `discrepancies.json` from the same standalone `reconcile`
output folder, then choose **Open report**. Filter on **Wrong amount** to see
`DEMO_A` at statement row 1 in the README's negative example. Expected and
observed values remain exact integer minor units.

The viewer checks SHA-256 over the exact summary bytes, shared book, statement
and snapshot identifiers, and the discrepancy counts before displaying rows.
It also displays scope flags, including a mismatch with zero issue records.
The pair's internal consistency does not authenticate who produced the files.
The viewer uses no network resources or persisted browser storage. It does not
write to the ledger or the selected files.

The HTML is a separate download. It accepts reports produced by the existing
signed native `v0.1.0-preview.3` CLI. The CLI's JSON contracts and exit codes are
unchanged.
