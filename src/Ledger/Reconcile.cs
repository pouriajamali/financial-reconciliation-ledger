using System.Text;

namespace ReconciliationLedger;

internal sealed record Comparison(bool Complete, string Outcome, int SnapshotSequence, bool BookMismatch, bool UnitMismatch, bool ScopeMismatch, int Missing, int Unexpected, int Duplicates, int WrongAmount, string[] DiagnosticCodes)
{
    public int ExitCode => Outcome == "pass" ? 0 : 2;
    public string Provenance => "UNVERIFIED";
    public string Freshness => "NOT_CHECKED";
    public string ExternalCompleteness => "NOT_PROVEN";
}

internal static class Reconcile
{
    public const string DigestSchema = "synthetic-ledger-snapshot-v1";
    internal static Action? SnapshotForTests = null;
    public static Comparison Compare(BookSnapshot book, Statement statement)
    {
        var expected = book.Entries.ToDictionary(e => e.Post.RequestId, e => e.Post.Total, StringComparer.Ordinal);
        HashSet<string> seen = new(StringComparer.Ordinal); int duplicates = 0, unexpected = 0, wrong = 0; List<string> examples = [];
        void Example(string code) { if (examples.Count < 20) examples.Add(code); }
        foreach (var row in statement.Rows)
        {
            if (!seen.Add(row.RequestId)) { duplicates++; Example("DUPLICATE_REQUEST_ID"); }
            if (!expected.TryGetValue(row.RequestId, out long value)) { unexpected++; Example("UNEXPECTED_REQUEST_ID"); }
            else if (row.AmountMinor != value) { wrong++; Example("WRONG_AMOUNT"); }
        }
        int missing = expected.Keys.Count(id => !seen.Contains(id));
        for (int i = 0; i < Math.Min(missing, 20); i++) Example("MISSING_REQUEST_ID");
        bool bookMismatch = book.BookId != statement.BookId, unitMismatch = statement.Unit != "LAB" || statement.Scale != 2, scopeMismatch = statement.ThroughSequence != book.LastSequence;
        if (bookMismatch) Example("BOOK_MISMATCH"); if (unitMismatch) Example("UNIT_OR_SCALE_MISMATCH"); if (scopeMismatch) Example("SNAPSHOT_SCOPE_MISMATCH");
        bool pass = !bookMismatch && !unitMismatch && !scopeMismatch && missing + unexpected + duplicates + wrong == 0;
        return new(true, pass ? "pass" : "fail", book.LastSequence, bookMismatch, unitMismatch, scopeMismatch, missing, unexpected, duplicates, wrong, examples.ToArray());
    }
    public static Comparison Run(string folder, string input, string output)
    {
        folder = Safe.Normalize(folder); input = Safe.Normalize(input); output = Safe.Normalize(output);
        Safe.Separate(output, folder); Safe.Separate(output, input);
        byte[] statementBytes = Safe.Read(input); var statement = Statement.Parse(statementBytes); var book = Store.Snapshot(folder);
        SnapshotForTests?.Invoke(); // A later append is outside the named snapshot.
        string snapshotReceiptListSha256 = Contract.Hash(Contract.Serialize(new { schema = DigestSchema, bookId = book.BookId, throughSequence = book.LastSequence, receipts = book.Entries.Select(e => new { sequence = e.Sequence, receiptSha256 = e.ReceiptSha256 }).ToArray() }));
        var result = Compare(book, statement);
        Report.Write(output, new { schema = "synthetic-reconciliation-report-v1", version = Contract.Version, toolBuild = Report.Build, bookId = book.BookId, declaredBookId = statement.BookId, statementSha256 = Contract.Hash(statementBytes), snapshotDigestSchema = DigestSchema, snapshotReceiptListSha256, result, limits = Report.Limits }); return result;
    }
}

internal static class Report
{
    internal static Action<string>? BeforeWriteForTests = null;
    public static string Build => System.Reflection.CustomAttributeExtensions.GetCustomAttribute<System.Reflection.AssemblyInformationalVersionAttribute>(typeof(Report).Assembly)?.InformationalVersion ?? "UNAVAILABLE";
    public const string Limits = "Synthetic LAB scale2 journal only. Agreement is not authenticity, rights, freshness, external completeness or certified accounting. Process interruption is not power-loss or distributed exactly-once proof. Existing native hosts; not a hostile-file/filesystem sandbox.";
    public static void Write<T>(string output, T report)
    {
        output = Safe.Normalize(output); string nonce = Guid.NewGuid().ToString("N"); Safe.Fresh(output, nonce); BeforeWriteForTests?.Invoke(output);
        byte[] bytes = Encoding.UTF8.GetBytes(Contract.Serialize(report) + "\n");
        using var document = Contract.Document(bytes); var value = document.RootElement;
        string outcome = value.TryGetProperty("outcome", out var top) ? top.GetString()! : value.GetProperty("result").GetProperty("outcome").GetString()!;
        if (Safe.Owned(output) != nonce) throw new Problem("OWNERSHIP_CHANGED");
        Safe.WriteNew(Path.Combine(output, "summary.txt.pending"), Encoding.UTF8.GetBytes("Financial Reconciliation Ledger: " + outcome + "\nVersion " + Contract.Version + "; synthetic LAB scale2 only.\nProvenance UNVERIFIED; freshness NOT_CHECKED; external completeness NOT_PROVEN.\nSee summary.json for exact counts and receipt disposition.\n" + Limits + "\n"));
        Safe.WriteNew(Path.Combine(output, "summary.json.pending"), bytes);
        if (Safe.Owned(output) != nonce) throw new Problem("OWNERSHIP_CHANGED");
        File.Move(Path.Combine(output, "summary.txt.pending"), Path.Combine(output, "summary.txt"));
        File.Move(Path.Combine(output, "summary.json.pending"), Path.Combine(output, "summary.json"));
    }
}
