# Four acceptance boundaries

- Audit actual SQLite storage classes and exact schema/trigger/canonical receipt
  agreement before accepting a marked book; reader coercion is insufficient.
- A same-ID/content replay at full capacity returns original receipt bytes/hash
  without another row. Replay and quota decisions share the same immediate transaction.
- Duplicate statement IDs are completed comparison failures with exact row totals;
  duplicate JSON keys or malformed structure are file-fatal incomplete. Never silently net.
- Postcommit response loss is not rollback. Own-child phase/nonce/PID evidence and
  same-ID receipt recovery distinguish before/after commit; no power-loss guarantee.
