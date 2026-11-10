using System.Text;

namespace ReconciliationLedger;
internal static class Program
{
    public static int Main(string[] args)
    {
        try
        {
            if (args is ["--version"])
            {
                Console.WriteLine("Financial Reconciliation Ledger " + Contract.Version);
                return 0;
            }

            object report;
            int exit = 0;
            switch (args)
            {
                case ["init", var target]:
                    string nonce = Store.Init(target);
                    report = new
                    {
                        schema = "synthetic-ledger-init-v1",
                        version = Contract.Version,
                        toolBuild = Report.Build,
                        complete = true,
                        outcome = "pass",
                        profile = Contract.Profile,
                        bookId = nonce,
                        unit = "LAB",
                        scale = 2,
                        limits = Report.Limits
                    };
                    break;
                case ["post", var folder, var input]:
                    var post = Post.Parse(Safe.Read(input));
                    var result = Store.Apply(folder, post);
                    report = new
                    {
                        schema = "synthetic-ledger-operation-v1",
                        version = Contract.Version,
                        toolBuild = Report.Build,
                        complete = true,
                        outcome = "pass",
                        result,
                        limits = Report.Limits
                    };
                    break;
                case ["reconcile", var folder, var input, var output]:
                    var comparison = Reconcile.Run(folder, input, output);
                    exit = comparison.ExitCode;
                    report = new
                    {
                        schema = "synthetic-ledger-operation-v1",
                        version = Contract.Version,
                        toolBuild = Report.Build,
                        complete = true,
                        outcome = comparison.Outcome,
                        result = comparison,
                        limits = Report.Limits
                    };
                    break;
                case ["demo", var output]:
                    report = Demo.Run(output);
                    break;
                default:
                    throw new Problem("CLI_INVALID");
            }

            Console.WriteLine(Contract.Serialize(report));
            return exit;
        }
        catch (Exception e)when (e is not OutOfMemoryException)
        {
            var p = e as Problem;
            bool rejected = p?.Rejected == true;
            int exit = rejected ? 2 : 1;
            Console.WriteLine(Contract.Serialize(new { schema = "synthetic-ledger-error-v1", version = Contract.Version, toolBuild = Report.Build, complete = rejected, outcome = rejected ? "rejected" : "incomplete", exitCode = exit, reason = p?.Code ?? "IO_SQLITE_OR_CONFIGURATION_FAILURE", limits = Report.Limits }));
            return exit;
        }
    }
}

internal static class Demo
{
    internal static Post Request(string book, string id, long amount = 12345) => Post.Parse(Encoding.UTF8.GetBytes(Contract.Serialize(new { profile = Contract.Profile, bookId = book, requestId = id, unit = "LAB", scale = 2, splits = new[] { new Split("cash", amount, 0), new Split("clearing", 0, amount) } })));
    public static object Run(string destination)
    {
        destination = Safe.Normalize(destination);
        string owner = Guid.NewGuid().ToString("N");
        Safe.Fresh(destination, owner);
        string folder = Path.Combine(destination, "book"), book = Store.Init(folder);
        var first = Request(book, "DEMO_A", 123456789012);
        var a = Store.Apply(folder, first);
        var second = Post.Parse(Encoding.UTF8.GetBytes(Contract.Serialize(new { profile = Contract.Profile, bookId = book, requestId = "DEMO_B", unit = "LAB", scale = 2, splits = new[] { new Split("cash", 1000, 0), new Split("clearing", 0, 975), new Split("fees", 0, 25) } })));
        var b = Store.Apply(folder, second);
        var retry = Store.Apply(folder, first);
        bool rejectedConflict = false, rejectedUnbalanced = false;
        try
        {
            Store.Apply(folder, Request(book, "DEMO_A", 1));
        }
        catch (Problem e)when (e.Code == "REQUEST_ID_CONFLICT")
        {
            rejectedConflict = true;
        }

        string unbalanced = first.Canonical.Replace("\"credit\":123456789012", "\"credit\":123456789011", StringComparison.Ordinal);
        try
        {
            Post.Parse(Encoding.UTF8.GetBytes(unbalanced));
        }
        catch (Problem e)when (e.Code == "POST_UNBALANCED")
        {
            rejectedUnbalanced = true;
        }

        var snapshot = Store.Snapshot(folder);
        var matching = new Statement(book, "LAB", 2, 2, [new("DEMO_A", first.Total), new("DEMO_B", second.Total)]);
        var negative = new Statement(book, "LAB", 2, 2, [new("DEMO_A", first.Total - 1), new("UNEXPECTED", 1), new("UNEXPECTED", 1)]);
        var pass = Reconcile.Compare(snapshot, matching);
        var fail = Reconcile.Compare(snapshot, negative);
        if (a.Disposition != "posted" || b.Disposition != "posted" || retry.Disposition != "replayed" || retry.Receipt != a.Receipt || retry.ReceiptSha256 != a.ReceiptSha256 || !rejectedConflict || !rejectedUnbalanced || snapshot.Entries.Length != 2 || pass.Outcome != "pass" || fail.Outcome != "fail" || fail.Missing != 1 || fail.Unexpected != 2 || fail.Duplicates != 1 || fail.WrongAmount != 1)
            throw new Problem("DEMO_ASSERTION_FAILED");
        Safe.WriteNew(Path.Combine(destination, "post.json"), Encoding.UTF8.GetBytes(first.Canonical + "\n"));
        object StatementJson(Statement s) => new
        {
            schema = "synthetic-statement-v1",
            bookId = s.BookId,
            unit = s.Unit,
            scale = s.Scale,
            throughSequence = s.ThroughSequence,
            rows = s.Rows
        };
        Safe.WriteNew(Path.Combine(destination, "statement-match.json"), Encoding.UTF8.GetBytes(Contract.Serialize(StatementJson(matching)) + "\n"));
        Safe.WriteNew(Path.Combine(destination, "statement-negative.json"), Encoding.UTF8.GetBytes(Contract.Serialize(StatementJson(negative)) + "\n"));
        var report = new
        {
            schema = "synthetic-ledger-demo-v1",
            version = Contract.Version,
            toolBuild = Report.Build,
            complete = true,
            outcome = "pass",
            bookId = book,
            entries = 2,
            preciseAmountMinor = first.Total,
            posted = a,
            replayed = retry,
            rejectedConflict,
            rejectedUnbalanced,
            balancesDebitMinusCredit = snapshot.DebitMinusCredit,
            matching = pass,
            negative = fail,
            limits = Report.Limits
        };
        // The demo already owns its root; reports live in their own fresh child.
        if (Safe.Owned(destination) != owner)
            throw new Problem("OWNERSHIP_CHANGED");
        Report.Write(Path.Combine(destination, "report"), report);
        return report;
    }
}
