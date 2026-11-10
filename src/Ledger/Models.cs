using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace ReconciliationLedger;
internal sealed class Problem(string code, bool rejected = false) : Exception(code)
{
    public string Code { get; } = code;
    public bool Rejected { get; } = rejected;
}

internal static partial class Contract
{
    public const string Version = "0.1.0-preview.2", Profile = "synthetic-ledger-v1";
    public const int Capacity = 1000, InputLimit = 1024 * 1024;
    public const long AmountLimit = 1_000_000_000_000;
    public static readonly string[] Accounts = ["cash", "clearing", "fees"];
    public static readonly JsonSerializerOptions Json = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase
    };
    [GeneratedRegex(@"\A[a-f0-9]{32}\z")]
    private static partial Regex NoncePattern();
    [GeneratedRegex(@"\A[A-Za-z0-9][A-Za-z0-9_-]{0,63}\z")]
    private static partial Regex IdPattern();
    public static string Nonce(string s) => NoncePattern().IsMatch(s) ? s : throw new Problem("BOOK_ID_INVALID");
    public static string Id(string s) => IdPattern().IsMatch(s) ? s : throw new Problem("REQUEST_ID_INVALID");
    public static string Hash(byte[] b) => Convert.ToHexString(SHA256.HashData(b)).ToLowerInvariant();
    public static string Hash(string s) => Hash(Encoding.UTF8.GetBytes(s));
    public static string Serialize<T>(T value) => JsonSerializer.Serialize(value, Json);
    public static void Fields(JsonElement e, params string[] names)
    {
        if (e.ValueKind != JsonValueKind.Object)
            throw new Problem("JSON_SHAPE_INVALID");
        HashSet<string> seen = new(StringComparer.Ordinal);
        foreach (var p in e.EnumerateObject())
            if (!seen.Add(p.Name))
                throw new Problem("JSON_DUPLICATE_KEY");
        if (!seen.SetEquals(names))
            throw new Problem("JSON_FIELDS_INVALID");
    }

    public static string Text(JsonElement e, string name)
    {
        var v = e.GetProperty(name);
        if (v.ValueKind != JsonValueKind.String)
            throw new Problem("JSON_STRING_REQUIRED");
        return v.GetString()!;
    }

    public static long Integer(JsonElement e, string name)
    {
        var v = e.GetProperty(name);
        if (v.ValueKind != JsonValueKind.Number || v.GetRawText().Any(c => c is < '0' or > '9') || !v.TryGetInt64(out long value))
            throw new Problem("INTEGER_ENCODING_INVALID");
        return value;
    }

    public static JsonDocument Document(byte[] bytes)
    {
        if (bytes.Length > InputLimit)
            throw new Problem("INPUT_BYTE_LIMIT");
        try
        {
            return JsonDocument.Parse(bytes, new JsonDocumentOptions { MaxDepth = 8 });
        }
        catch (JsonException)
        {
            throw new Problem("JSON_INVALID");
        }
    }
}

internal sealed record Split(string Account, long Debit, long Credit);
internal sealed record Post(string Profile, string BookId, string RequestId, string Unit, int Scale, Split[] Splits)
{
    public long Total => Splits.Sum(s => s.Debit);
    // Explicit serialization avoids deriving the hash from arbitrary input spelling
    // or serializing computed properties such as Total.
    public string Canonical => Contract.Serialize(new { profile = Profile, bookId = BookId, requestId = RequestId, unit = Unit, scale = Scale, splits = Splits.OrderBy(s => s.Account, StringComparer.Ordinal).ToArray() });

    public static Post Parse(byte[] bytes)
    {
        using var d = Contract.Document(bytes);
        var r = d.RootElement;
        Contract.Fields(r, "profile", "bookId", "requestId", "unit", "scale", "splits");
        string profile = Contract.Text(r, "profile"), book = Contract.Nonce(Contract.Text(r, "bookId")), id = Contract.Id(Contract.Text(r, "requestId"));
        if (profile != Contract.Profile || Contract.Text(r, "unit") != "LAB" || Contract.Integer(r, "scale") != 2)
            throw new Problem("POST_PROFILE_UNIT_INVALID", true);
        var items = r.GetProperty("splits");
        if (items.ValueKind != JsonValueKind.Array || items.GetArrayLength()is < 2 or > 3)
            throw new Problem("SPLIT_COUNT_INVALID", true);
        List<Split> splits = [];
        HashSet<string> accounts = new(StringComparer.Ordinal);
        long debit = 0, credit = 0;
        foreach (var item in items.EnumerateArray())
        {
            Contract.Fields(item, "account", "debit", "credit");
            string account = Contract.Text(item, "account");
            long dr = Contract.Integer(item, "debit"), cr = Contract.Integer(item, "credit");
            if (!Contract.Accounts.Contains(account) || !accounts.Add(account) || dr > Contract.AmountLimit || cr > Contract.AmountLimit || (dr == 0) == (cr == 0))
                throw new Problem("SPLIT_VALUE_INVALID", true);
            debit = checked(debit + dr);
            credit = checked(credit + cr);
            splits.Add(new(account, dr, cr));
        }

        if (debit != credit)
            throw new Problem("POST_UNBALANCED", true);
        return new(profile, book, id, "LAB", 2, splits.OrderBy(s => s.Account, StringComparer.Ordinal).ToArray());
    }
}

internal sealed record StatementRow(string RequestId, long AmountMinor);
internal sealed record Statement(string BookId, string Unit, int Scale, int ThroughSequence, StatementRow[] Rows)
{
    public static Statement Parse(byte[] bytes)
    {
        using var d = Contract.Document(bytes);
        var r = d.RootElement;
        Contract.Fields(r, "schema", "bookId", "unit", "scale", "throughSequence", "rows");
        if (Contract.Text(r, "schema") != "synthetic-statement-v1")
            throw new Problem("STATEMENT_PROFILE_UNSUPPORTED");
        string book = Contract.Nonce(Contract.Text(r, "bookId")), unit = Contract.Id(Contract.Text(r, "unit"));
        long scale = Contract.Integer(r, "scale"), through = Contract.Integer(r, "throughSequence");
        if (scale > 9 || through > Contract.Capacity)
            throw new Problem("STATEMENT_SCOPE_INVALID");
        var rows = r.GetProperty("rows");
        if (rows.ValueKind != JsonValueKind.Array || rows.GetArrayLength() > Contract.Capacity)
            throw new Problem("STATEMENT_ROW_LIMIT");
        List<StatementRow> parsed = [];
        foreach (var row in rows.EnumerateArray())
        {
            Contract.Fields(row, "requestId", "amountMinor");
            string id = Contract.Id(Contract.Text(row, "requestId"));
            long amount = Contract.Integer(row, "amountMinor");
            if (amount > 3 * Contract.AmountLimit)
                throw new Problem("STATEMENT_AMOUNT_LIMIT");
            parsed.Add(new(id, amount)); // Preserve duplicates for completed comparison failure.
        }

        return new(book, unit, (int)scale, (int)through, parsed.ToArray());
    }
}

internal sealed record SavedReceipt(string Schema, string Profile, string BookId, string RequestId, int Sequence, string RequestSha256, string Unit, int Scale, long TotalDebitMinor);
internal sealed record Entry(int Sequence, Post Post, string Receipt, string ReceiptSha256);
internal sealed record PostResult(string Disposition, string Receipt, string ReceiptSha256);
internal sealed record BookSnapshot(string BookId, Entry[] Entries, Dictionary<string, long> DebitMinusCredit)
{
    public int LastSequence => Entries.Length;
}
