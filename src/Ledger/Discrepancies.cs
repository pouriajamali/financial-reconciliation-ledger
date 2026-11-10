using System.Text;

namespace ReconciliationLedger;

internal sealed record Discrepancy(string Code, string RequestId, int? StatementRowIndex, int? EntrySequence, long? ExpectedAmountMinor, long? ActualAmountMinor, int? FirstStatementRowIndex);

internal static class Discrepancies
{
    public const string Schema = "synthetic-reconciliation-discrepancies-v1";
    public const int IssueLimit = 4000, ByteLimit = 2 * 1024 * 1024;

    public static Discrepancy[] Create(BookSnapshot book, Statement statement)
    {
        var expected = book.Entries.ToDictionary(e => e.Post.RequestId, StringComparer.Ordinal);
        Dictionary<string, int> firstRows = new(StringComparer.Ordinal);
        List<Discrepancy> issues = [];
        for (int index = 0; index < statement.Rows.Length; index++)
        {
            var row = statement.Rows[index];
            int rowIndex = index + 1;
            expected.TryGetValue(row.RequestId, out var entry);
            if (firstRows.TryGetValue(row.RequestId, out int firstRow))
                issues.Add(new("DUPLICATE_REQUEST_ID", row.RequestId, rowIndex, entry?.Sequence, entry?.Post.Total, row.AmountMinor, firstRow));
            else
                firstRows.Add(row.RequestId, rowIndex);

            if (entry == null)
                issues.Add(new("UNEXPECTED_REQUEST_ID", row.RequestId, rowIndex, null, null, row.AmountMinor, null));
            else if (row.AmountMinor != entry.Post.Total)
                issues.Add(new("WRONG_AMOUNT", row.RequestId, rowIndex, entry.Sequence, entry.Post.Total, row.AmountMinor, null));
        }

        foreach (var entry in book.Entries.OrderBy(e => e.Sequence))
            if (!firstRows.ContainsKey(entry.Post.RequestId))
                issues.Add(new("MISSING_REQUEST_ID", entry.Post.RequestId, null, entry.Sequence, entry.Post.Total, null, null));
        return issues.ToArray();
    }

    public static byte[] Serialize(byte[] summary, BookSnapshot book, string statementSha256, string snapshotReceiptListSha256, Discrepancy[] issues)
    {
        if (issues.Length > IssueLimit)
            throw new Problem("DISCREPANCY_ISSUE_LIMIT");
        byte[] bytes = Encoding.UTF8.GetBytes(Contract.Serialize(new
        {
            schema = Schema,
            summarySha256 = Contract.Hash(summary),
            bookId = book.BookId,
            statementSha256,
            snapshotReceiptListSha256,
            throughSequence = book.LastSequence,
            issues
        }) + "\n");
        if (bytes.Length > ByteLimit)
            throw new Problem("DISCREPANCY_BYTE_LIMIT");
        return bytes;
    }
}
