using System.Text;
using Microsoft.Data.Sqlite;

namespace ReconciliationLedger;

internal static class Store
{
    public const int ApplicationId = 0x4c414231;
    internal static Action<string>? PhaseForTests = null;
    internal static readonly Dictionary<string, string> Schema = BuildSchema();
    private static Dictionary<string, string> BuildSchema()
    {
        Dictionary<string, string> schema = new(StringComparer.Ordinal)
        {
            ["meta"] = "CREATE TABLE meta(id INTEGER PRIMARY KEY CHECK(id=1),profile TEXT NOT NULL,book_id TEXT NOT NULL) STRICT",
            ["journal"] = "CREATE TABLE journal(seq INTEGER PRIMARY KEY,request_id TEXT NOT NULL UNIQUE,canonical TEXT NOT NULL,request_hash TEXT NOT NULL,receipt TEXT NOT NULL,receipt_hash TEXT NOT NULL) STRICT",
            ["splits"] = "CREATE TABLE splits(seq INTEGER NOT NULL REFERENCES journal(seq),account TEXT NOT NULL,debit INTEGER NOT NULL CHECK(debit>=0),credit INTEGER NOT NULL CHECK(credit>=0),PRIMARY KEY(seq,account)) STRICT"
        };
        foreach (string table in new[] { "meta", "journal", "splits" })
            foreach (string operation in new[] { "UPDATE", "DELETE" })
            {
                string name = table + "_no_" + operation.ToLowerInvariant();
                schema[name] = $"CREATE TRIGGER {name} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END";
            }
        return schema;
    }
    internal static SqliteCommand Command(SqliteConnection c, SqliteTransaction? t, string sql, params (string Name, object Value)[] parameters)
    {
        var command = c.CreateCommand(); command.Transaction = t; command.CommandTimeout = 3; command.CommandText = sql;
        foreach (var p in parameters) command.Parameters.AddWithValue(p.Name, p.Value);
        return command;
    }
    internal static void Execute(SqliteConnection c, SqliteTransaction? t, string sql, params (string Name, object Value)[] p)
    { using var command = Command(c, t, sql, p); command.ExecuteNonQuery(); }
    private static SqliteConnection Open(string folder, bool create = false)
    {
        if (!create) Safe.Header(folder); // Reject foreign headers before SQLite recovery can write.
        var c = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = Path.Combine(folder, "book.sqlite"), Mode = create ? SqliteOpenMode.ReadWriteCreate : SqliteOpenMode.ReadWrite, Cache = SqliteCacheMode.Private, Pooling = false, DefaultTimeout = 3 }.ToString());
        try
        {
            c.Open(); c.EnableExtensions(false);
            Execute(c, null, "PRAGMA foreign_keys=ON; PRAGMA trusted_schema=OFF; PRAGMA synchronous=FULL; PRAGMA busy_timeout=3000");
            return c;
        }
        catch { c.Dispose(); throw; }
    }
    public static string Init(string folder)
    {
        folder = Safe.Normalize(folder); string nonce = Guid.NewGuid().ToString("N"); Safe.Fresh(folder, nonce);
        using (var reserved = new FileStream(Path.Combine(folder, "book.sqlite"), FileMode.CreateNew, FileAccess.Write)) { }
        using var c = Open(folder, true);
        Execute(c, null, "PRAGMA journal_mode=DELETE");
        using var t = c.BeginTransaction(deferred: false);
        Execute(c, t, $"PRAGMA application_id={ApplicationId}; PRAGMA user_version=1");
        foreach (string sql in Schema.Values) Execute(c, t, sql);
        Execute(c, t, "INSERT INTO meta VALUES(1,$profile,$book)", ("$profile", Contract.Profile), ("$book", nonce));
        t.Commit(); return nonce;
    }
    private static long Int(SqliteDataReader r, int ordinal)
        => r.GetValue(ordinal) is long v ? v : throw new Problem("SQLITE_STORAGE_CLASS_INVALID");
    private static string Text(SqliteDataReader r, int ordinal, int cap = 4096)
        => r.GetValue(ordinal) is string v && Encoding.UTF8.GetByteCount(v) <= cap ? v : throw new Problem("SQLITE_STORAGE_CLASS_OR_VALUE_INVALID");
    private static void Pragma(SqliteConnection c, SqliteTransaction t, string sql, object expected)
    {
        using var command = Command(c, t, sql);
        if (!Equals(command.ExecuteScalar(), expected)) throw new Problem("BOOK_HEADER_OR_MODE_INVALID");
    }
    internal static string Receipt(Post post, int seq) => Contract.Serialize(new SavedReceipt("synthetic-post-receipt-v1", Contract.Profile, post.BookId, post.RequestId, seq, Contract.Hash(post.Canonical), "LAB", 2, post.Total));
    internal static BookSnapshot Audit(SqliteConnection c, SqliteTransaction t, string nonce)
    {
        Pragma(c, t, "PRAGMA application_id", (long)ApplicationId); Pragma(c, t, "PRAGMA user_version", 1L);
        Pragma(c, t, "PRAGMA journal_mode", "delete"); Pragma(c, t, "PRAGMA foreign_keys", 1L);
        Pragma(c, t, "PRAGMA trusted_schema", 0L);
        Pragma(c, t, "PRAGMA quick_check", "ok");
        using (var cmd = Command(c, t, "PRAGMA foreign_key_check")) using (var r = cmd.ExecuteReader()) if (r.Read()) throw new Problem("BOOK_FOREIGN_KEY_INVALID");
        var observed = new Dictionary<string, string>(StringComparer.Ordinal);
        HashSet<string> autoIndexes = new(StringComparer.Ordinal);
        using (var cmd = Command(c, t, "SELECT type,name,sql FROM sqlite_schema LIMIT 20"))
        using (var r = cmd.ExecuteReader())
            while (r.Read())
            {
                string type = Text(r, 0), name = Text(r, 1);
                if (type == "index" && r.IsDBNull(2)) { if (!autoIndexes.Add(name)) throw new Problem("BOOK_SCHEMA_INVALID"); }
                else if (!observed.TryAdd(name, Text(r, 2))) throw new Problem("BOOK_SCHEMA_INVALID");
            }
        if (observed.Count != Schema.Count || Schema.Any(p => !observed.TryGetValue(p.Key, out var value) || value != p.Value) || !autoIndexes.SetEquals(["sqlite_autoindex_journal_1", "sqlite_autoindex_splits_1"])) throw new Problem("BOOK_SCHEMA_INVALID");
        using (var cmd = Command(c, t, "SELECT id,profile,book_id FROM meta LIMIT 2"))
        using (var r = cmd.ExecuteReader())
        {
            if (!r.Read() || Int(r, 0) != 1 || Text(r, 1) != Contract.Profile || Text(r, 2) != nonce || r.Read()) throw new Problem("BOOK_IDENTITY_INVALID");
        }
        List<Entry> entries = []; Dictionary<int, Split[]> expected = []; Dictionary<string, long> balances = Contract.Accounts.ToDictionary(a => a, _ => 0L, StringComparer.Ordinal);
        using (var cmd = Command(c, t, "SELECT seq,request_id,canonical,request_hash,receipt,receipt_hash FROM journal ORDER BY seq LIMIT 1001"))
        using (var r = cmd.ExecuteReader())
            while (r.Read())
            {
                if (entries.Count >= Contract.Capacity || Int(r, 0) != entries.Count + 1) throw new Problem("BOOK_SEQUENCE_OR_CAPACITY_INVALID");
                int seq = entries.Count + 1; string id = Text(r, 1, 64), canonical = Text(r, 2), hash = Text(r, 3, 64), receipt = Text(r, 4), receiptHash = Text(r, 5, 64);
                Post post;
                try { post = ReconciliationLedger.Post.Parse(Encoding.UTF8.GetBytes(canonical)); }
                catch (Problem) { throw new Problem("BOOK_CANONICAL_RECEIPT_INVALID"); }
                if (post.BookId != nonce || post.RequestId != id || post.Canonical != canonical || hash != Contract.Hash(canonical) || Receipt(post, seq) != receipt || Contract.Hash(receipt) != receiptHash) throw new Problem("BOOK_CANONICAL_RECEIPT_INVALID");
                entries.Add(new(seq, post, receipt, receiptHash)); expected.Add(seq, post.Splits);
                foreach (var split in post.Splits) balances[split.Account] = checked(balances[split.Account] + split.Debit - split.Credit);
            }
        int rows = 0; HashSet<(int, string)> seen = [];
        using (var cmd = Command(c, t, "SELECT seq,account,debit,credit FROM splits ORDER BY seq,account LIMIT 3001"))
        using (var r = cmd.ExecuteReader())
            while (r.Read())
            {
                if (++rows > 3000) throw new Problem("BOOK_SPLIT_LIMIT"); long seq = Int(r, 0); string account = Text(r, 1, 8); long dr = Int(r, 2), cr = Int(r, 3);
                if (seq is < 1 or > Contract.Capacity || !expected.TryGetValue((int)seq, out var splits) || !seen.Add(((int)seq, account)) || !splits.Contains(new(account, dr, cr))) throw new Problem("BOOK_SPLIT_AGREEMENT_INVALID");
            }
        if (rows != expected.Values.Sum(s => s.Length) || balances.Values.Sum() != 0) throw new Problem("BOOK_SPLIT_AGREEMENT_INVALID");
        return new(nonce, entries.ToArray(), balances);
    }
    public static BookSnapshot Snapshot(string folder)
    {
        folder = Safe.Normalize(folder); string nonce = Safe.Owned(folder); Safe.BookFiles(folder);
        using var c = Open(folder); using var t = c.BeginTransaction(deferred: true);
        var snapshot = Audit(c, t, nonce); t.Commit();
        if (Safe.Owned(folder) != nonce) throw new Problem("OWNERSHIP_CHANGED"); Safe.BookFiles(folder); return snapshot;
    }
    public static PostResult Apply(string folder, Post post)
    {
        post = ReconciliationLedger.Post.Parse(Encoding.UTF8.GetBytes(post.Canonical));
        folder = Safe.Normalize(folder); string nonce = Safe.Owned(folder); Safe.BookFiles(folder);
        if (post.BookId != nonce) throw new Problem("POST_BOOK_MISMATCH", true);
        using var c = Open(folder); using var t = c.BeginTransaction(deferred: false); var snapshot = Audit(c, t, nonce);
        var existing = snapshot.Entries.SingleOrDefault(e => e.Post.RequestId == post.RequestId);
        if (existing != null)
        {
            if (existing.Post.Canonical != post.Canonical) throw new Problem("REQUEST_ID_CONFLICT", true);
            t.Commit(); return new("replayed", existing.Receipt, existing.ReceiptSha256);
        }
        if (snapshot.Entries.Length >= Contract.Capacity) throw new Problem("BOOK_CAPACITY_REACHED", true);
        int seq = snapshot.LastSequence + 1; string canonical = post.Canonical, receipt = Receipt(post, seq), receiptHash = Contract.Hash(receipt);
        Execute(c, t, "INSERT INTO journal VALUES($seq,$id,$canonical,$hash,$receipt,$receiptHash)", ("$seq", seq), ("$id", post.RequestId), ("$canonical", canonical), ("$hash", Contract.Hash(canonical)), ("$receipt", receipt), ("$receiptHash", receiptHash));
        foreach (var s in post.Splits) Execute(c, t, "INSERT INTO splits VALUES($seq,$account,$debit,$credit)", ("$seq", seq), ("$account", s.Account), ("$debit", s.Debit), ("$credit", s.Credit));
        PhaseForTests?.Invoke("before-commit");
        if (Safe.Owned(folder) != nonce) throw new Problem("OWNERSHIP_CHANGED"); Safe.BookFiles(folder);
        t.Commit();
        PhaseForTests?.Invoke("after-commit-before-response");
        return new("posted", receipt, receiptHash);
    }
}
