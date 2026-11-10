using System.Diagnostics;
using System.Text;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using ReconciliationLedger;
using App = ReconciliationLedger.Program;

internal static class Program
{
    private static string Root = "";
    private static int Passed, Failed, Skipped;
    private static readonly List<object> Results = [];
    private static void Assert(bool condition, string reason = "ASSERTION")
    {
        if (!condition)
            throw new Exception(reason);
    }

    private static void Problem(Action action, string? code = null)
    {
        try
        {
            action();
        }
        catch (ReconciliationLedger.Problem p)
        {
            Assert(code == null || p.Code == code, "WRONG_PROBLEM_" + p.Code);
            return;
        }

        throw new Exception("EXPECTED_PROBLEM");
    }

    private static string Fresh(string name) => Path.Combine(Root, name);
    private static (string Folder, string Id) Book(string name)
    {
        string folder = Fresh(name);
        return (folder, Store.Init(folder));
    }

    private static byte[] Bytes(string value) => Encoding.UTF8.GetBytes(value);
    private static string StatementJson(string book, int seq, params StatementRow[] rows) => Contract.Serialize(new { schema = "synthetic-statement-v1", bookId = book, unit = "LAB", scale = 2, throughSequence = seq, rows });
    private static string LiteralSnapshotFrame(BookSnapshot book) => "{\"schema\":\"synthetic-ledger-snapshot-v1\",\"bookId\":\"" + book.BookId + "\",\"throughSequence\":" + book.LastSequence.ToString(System.Globalization.CultureInfo.InvariantCulture) + ",\"receipts\":[" + string.Join(",", book.Entries.Select(e => "{\"sequence\":" + e.Sequence.ToString(System.Globalization.CultureInfo.InvariantCulture) + ",\"receiptSha256\":\"" + Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(Bytes(e.Receipt))).ToLowerInvariant() + "\"}")) + "]}";
    private static void Sql(string folder, string sql)
    {
        using var c = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = Path.Combine(folder, "book.sqlite"), Mode = SqliteOpenMode.ReadWrite, Pooling = false }.ToString());
        c.Open();
        Store.Execute(c, null, sql);
    }

    private static void Test(string name, Action action)
    {
        try
        {
            action();
            Passed++;
            Results.Add(new { name, outcome = "pass" });
            Console.WriteLine("PASS " + name);
        }
        catch (Exception e)
        {
            Failed++;
            Results.Add(new { name, outcome = "fail", reason = e.GetType().Name, detail = e.Message });
            Console.WriteLine("FAIL " + name + " " + e.GetType().Name + " " + e.Message);
        }
        finally
        {
            Store.PhaseForTests = null;
            Reconcile.SnapshotForTests = null;
            Report.BeforeWriteForTests = null;
            Report.BeforeFileForTests = null;
        }
    }

    private static (int Exit, JsonElement Output) Cli(params string[] args)
    {
        var original = Console.Out;
        using var text = new StringWriter();
        int exit;
        try
        {
            Console.SetOut(text);
            exit = App.Main(args);
        }
        finally
        {
            Console.SetOut(original);
        }

        using var doc = JsonDocument.Parse(text.ToString());
        return (exit, doc.RootElement.Clone());
    }

    private static Process Child(string folder, string id, long amount, string phase)
    {
        string host = Environment.ProcessPath!;
        var s = new ProcessStartInfo(host)
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            RedirectStandardInput = true
        };
        if (Path.GetFileNameWithoutExtension(host).Equals("dotnet", StringComparison.OrdinalIgnoreCase))
            s.ArgumentList.Add(typeof(Program).Assembly.Location);
        foreach (string arg in new[]
        {
            "--test-worker",
            folder,
            id,
            amount.ToString(System.Globalization.CultureInfo.InvariantCulture),
            phase
        }

        )
            s.ArgumentList.Add(arg);
        s.Environment["LEDGER_TEST_TOKEN"] = Safe.Owned(folder);
        return Process.Start(s)!;
    }

    private static string BoundedLine(Process p)
    {
        async Task<string> Read()
        {
            var s = new StringBuilder();
            char[] b = new char[1];
            while (s.Length < 2048)
            {
                int n = await p.StandardOutput.ReadAsync(b);
                if (n == 0)
                    break;
                if (b[0] == '\n')
                    return s.ToString().TrimEnd('\r');
                s.Append(b[0]);
            }

            throw new Exception("CHILD_PROTOCOL_LIMIT_OR_EOF");
        }

        return Read().WaitAsync(TimeSpan.FromSeconds(15)).GetAwaiter().GetResult();
    }

    private static void KillOwned(Process p)
    {
        if (!p.HasExited)
            p.Kill(entireProcessTree: true);
        Assert(p.WaitForExit(5000), "OWNED_CHILD_EXIT_TIMEOUT");
    }

    private static byte[] BoundedError(Process p)
    {
        async Task<byte[]> Read()
        {
            using var stored = new MemoryStream();
            byte[] buffer = new byte[512];
            int count;
            while ((count = await p.StandardError.BaseStream.ReadAsync(buffer)) > 0)
            {
                if (stored.Length + count > 4096)
                    throw new InvalidDataException("TEST_CHILD_STDERR_LIMIT");
                stored.Write(buffer, 0, count);
            }

            return stored.ToArray();
        }

        return Read().WaitAsync(TimeSpan.FromSeconds(5)).GetAwaiter().GetResult();
    }

    private static int Worker(string[] args)
    {
        if (args is not ["--test-worker", var folder, var id, var amountText, var phase])
            return 90;
        string nonce = Safe.Owned(folder);
        if (Environment.GetEnvironmentVariable("LEDGER_TEST_TOKEN") != nonce || phase is not ("none" or "before-commit" or "after-commit-before-response" or "stderr-overflow"))
            return 91;
        if (!long.TryParse(amountText, System.Globalization.NumberStyles.None, System.Globalization.CultureInfo.InvariantCulture, out long amount))
            return 92;
        if (phase == "stderr-overflow")
        {
            Console.OpenStandardError().Write(new byte[4097]);
            return 0;
        }

        if (phase != "none")
            Store.PhaseForTests = observed =>
            {
                if (observed != phase)
                    return;
                Console.WriteLine(Contract.Serialize(new { schema = "ledger-test-phase-v1", nonce, phase, pid = Environment.ProcessId }));
                Console.Out.Flush();
                Thread.Sleep(Timeout.Infinite); // Excluded test assembly; parent owns/terminates this PID.
            };
        try
        {
            Console.WriteLine(Contract.Serialize(Store.Apply(folder, Demo.Request(nonce, id, amount))));
            return 0;
        }
        catch (ReconciliationLedger.Problem p)
        {
            Console.WriteLine(Contract.Serialize(new { reason = p.Code }));
            return p.Rejected ? 2 : 1;
        }
    }

    public static int Main(string[] args)
    {
        if (args.Length > 0 && args[0] == "--test-worker")
            return Worker(args);
        if (args is not ["--work", var work])
            return 90;
        Root = Safe.Normalize(work);
        Safe.Fresh(Root, Guid.NewGuid().ToString("N"));
        Parsing();
        Journal();
        Comparisons();
        DiscrepancyTests();
        FilesAndCli();
        Processes();
        var receipt = new
        {
            schema = "ledger-tests-v1",
            runtimeVersion = Environment.Version.ToString(),
            providerAssemblyVersion = typeof(SqliteConnection).Assembly.GetName().Version?.ToString(),
            toolBuild = Report.Build,
            passed = Passed,
            failed = Failed,
            skipped = Skipped,
            cases = Results,
            limits = "Fresh synthetic owned fixtures only; process interruption observations, not power loss or financial certification."
        };
        Safe.WriteNew(Path.Combine(Root, "receipt.json"), Bytes(Contract.Serialize(receipt) + "\n"));
        Console.WriteLine($"SUMMARY passed={Passed} failed={Failed} skipped={Skipped}");
        return Failed == 0 ? 0 : 1;
    }

    private static void Parsing()
    {
        string book = new('a', 32), valid = Demo.Request(book, "REQ_1").Canonical;
        Test("post-canonical-sorted-order", () =>
        {
            var p = Demo.Request(book, "REQ_1");
            string reordered = Contract.Serialize(new { splits = p.Splits.Reverse().ToArray(), scale = 2, unit = "LAB", requestId = p.RequestId, bookId = book, profile = Contract.Profile });
            Assert(Post.Parse(Bytes(reordered)).Canonical == valid);
        });
        foreach (var pair in new[]
        {
            ("float", "1.0"),
            ("exponent", "1e0"),
            ("negative", "-1"),
            ("string", "\"1\""),
            ("overflow", "9223372036854775808")
        }

        )
            Test("integer-" + pair.Item1, () => Problem(() => Post.Parse(Bytes(valid.Replace("12345", pair.Item2, StringComparison.Ordinal))), "INTEGER_ENCODING_INVALID"));
        Test("post-unbalanced", () => Problem(() => Post.Parse(Bytes(valid.Replace("\"credit\":12345", "\"credit\":1", StringComparison.Ordinal))), "POST_UNBALANCED"));
        Test("post-zero-only", () => Problem(() => Post.Parse(Bytes(valid.Replace("12345", "0", StringComparison.Ordinal))), "SPLIT_VALUE_INVALID"));
        Test("post-both-debit-credit", () => Problem(() => Post.Parse(Bytes(valid.Replace("\"debit\":0,\"credit\":12345", "\"debit\":1,\"credit\":12345", StringComparison.Ordinal))), "SPLIT_VALUE_INVALID"));
        Test("post-amount-over-cap", () => Problem(() => Demo.Request(book, "REQ", Contract.AmountLimit + 1), "SPLIT_VALUE_INVALID"));
        Test("post-amount-exact-cap", () => Assert(Demo.Request(book, "REQ", Contract.AmountLimit).Total == Contract.AmountLimit));
        Test("post-unknown-account", () => Problem(() => Post.Parse(Bytes(valid.Replace("cash", "unknown", StringComparison.Ordinal))), "SPLIT_VALUE_INVALID"));
        Test("post-duplicate-account", () => Problem(() => Post.Parse(Bytes(valid.Replace("clearing", "cash", StringComparison.Ordinal))), "SPLIT_VALUE_INVALID"));
        Test("post-one-split", () => Problem(() => Post.Parse(Bytes(Contract.Serialize(new { profile = Contract.Profile, bookId = book, requestId = "REQ", unit = "LAB", scale = 2, splits = new[] { new Split("cash", 1, 0) } }))), "SPLIT_COUNT_INVALID"));
        foreach (string field in new[]
        {
            "profile",
            "bookId",
            "requestId",
            "unit",
            "scale",
            "splits"
        }

        )
            Test("post-missing-" + field, () =>
            {
                using var d = JsonDocument.Parse(valid);
                var fields = d.RootElement.EnumerateObject().Where(p => p.Name != field).ToDictionary(p => p.Name, p => p.Value.Clone());
                Problem(() => Post.Parse(Bytes(Contract.Serialize(fields))), "JSON_FIELDS_INVALID");
            });
        Test("post-extra-key", () => Problem(() => Post.Parse(Bytes(valid.Insert(1, "\"extra\":1,"))), "JSON_FIELDS_INVALID"));
        Test("post-duplicate-key", () => Problem(() => Post.Parse(Bytes(valid.Insert(1, "\"unit\":\"LAB\","))), "JSON_DUPLICATE_KEY"));
        Test("post-nested-duplicate", () => Problem(() => Post.Parse(Bytes(valid.Replace("\"account\":\"cash\"", "\"account\":\"cash\",\"account\":\"cash\"", StringComparison.Ordinal))), "JSON_DUPLICATE_KEY"));
        Test("post-wrong-profile", () => Problem(() => Post.Parse(Bytes(valid.Replace(Contract.Profile, "future", StringComparison.Ordinal))), "POST_PROFILE_UNIT_INVALID"));
        Test("post-wrong-unit", () => Problem(() => Post.Parse(Bytes(valid.Replace("LAB", "USD", StringComparison.Ordinal))), "POST_PROFILE_UNIT_INVALID"));
        Test("post-wrong-scale", () => Problem(() => Post.Parse(Bytes(valid.Replace("\"scale\":2", "\"scale\":3", StringComparison.Ordinal))), "POST_PROFILE_UNIT_INVALID"));
        Test("json-byte-cap", () => Problem(() => Post.Parse(new byte[Contract.InputLimit + 1]), "INPUT_BYTE_LIMIT"));
        Test("json-depth-cap", () => Problem(() => Post.Parse(Bytes(new string ('[', 9) + new string (']', 9))), "JSON_INVALID"));
        Test("json-trailing-data", () => Problem(() => Post.Parse(Bytes(valid + "{}")), "JSON_INVALID"));
        Test("json-bom", () => Problem(() => Post.Parse([0xef, 0xbb, 0xbf, ..Bytes(valid)]), "JSON_INVALID"));
        Test("id-all-control-positions", () =>
        {
            foreach (char c in Enumerable.Range(0, 160).Select(i => (char)i).Where(char.IsControl).Concat(new[] { '\u2028', '\u2029', '\ufeff' }))
                foreach (string id in new[]
                {
                    c + "REQ",
                    "RE" + c + "Q",
                    "REQ" + c
                }

                )
                    Problem(() => Contract.Id(id), "REQUEST_ID_INVALID");
        });
        Test("id-length-and-absolute-anchor", () =>
        {
            Problem(() => Contract.Id(new string ('x', 65)));
            Problem(() => Contract.Id("REQ\n"));
            Assert(Contract.Id(new string ('x', 64)).Length == 64);
        });
    }

    private static void Journal()
    {
        Test("journal-precision-replay-conflict", () =>
        {
            var b = Book("precision");
            var p = Demo.Request(b.Id, "R", 999999999999);
            var a = Store.Apply(b.Folder, p);
            var r = Store.Apply(b.Folder, Post.Parse(Bytes(p.Canonical)));
            Assert(a.Receipt == r.Receipt && a.ReceiptSha256 == r.ReceiptSha256 && r.Disposition == "replayed");
            Problem(() => Store.Apply(b.Folder, Demo.Request(b.Id, "R", 1)), "REQUEST_ID_CONFLICT");
            var snapshot = Store.Snapshot(b.Folder);
            Assert(snapshot.Entries.Length == 1 && snapshot.DebitMinusCredit["cash"] == 999999999999 && snapshot.DebitMinusCredit.Values.Sum() == 0);
        });
        Test("journal-reordered-request-exact-receipt", () =>
        {
            var b = Book("reordered-replay");
            var p = Demo.Request(b.Id, "ORDERED", 9);
            var first = Store.Apply(b.Folder, p);
            string input = Contract.Serialize(new { splits = p.Splits.Reverse().ToArray(), scale = 2, unit = "LAB", requestId = p.RequestId, bookId = b.Id, profile = Contract.Profile });
            var replay = Store.Apply(b.Folder, Post.Parse(Bytes(" \n" + input + "\n ")));
            Assert(replay.Receipt == first.Receipt && replay.ReceiptSha256 == first.ReceiptSha256 && Store.Snapshot(b.Folder).LastSequence == 1);
        });
        Test("journal-busy-is-incomplete-no-new-row", () =>
        {
            var b = Book("busy-book");
            string input = Fresh("busy-post.json");
            File.WriteAllText(input, Demo.Request(b.Id, "BUSY").Canonical);
            using (var c = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = Path.Combine(b.Folder, "book.sqlite"), Pooling = false }.ToString()))
            {
                c.Open();
                using var t = c.BeginTransaction(deferred: false);
                var r = Cli("post", b.Folder, input);
                Assert(r.Exit == 1 && !r.Output.GetProperty("complete").GetBoolean());
            }

            Assert(Store.Snapshot(b.Folder).LastSequence == 0);
        });
        Test("journal-three-splits", () =>
        {
            var result = Cli("demo", Fresh("three-split-demo"));
            Assert(result.Exit == 0 && result.Output.GetProperty("entries").GetInt32() == 2);
        });
        Test("journal-wrong-book", () =>
        {
            var b = Book("wrong-book");
            Problem(() => Store.Apply(b.Folder, Demo.Request(new string ('a', 32), "R")), "POST_BOOK_MISMATCH");
            Assert(Store.Snapshot(b.Folder).LastSequence == 0);
        });
        Test("journal-exception-rollback", () =>
        {
            var b = Book("exception-rollback");
            Store.PhaseForTests = _ => throw new IOException("owned probe");
            try
            {
                Store.Apply(b.Folder, Demo.Request(b.Id, "R"));
                throw new Exception("EXPECTED_THROW");
            }
            catch (IOException)
            {
            }

            Store.PhaseForTests = null;
            Assert(Store.Snapshot(b.Folder).LastSequence == 0);
        });
        foreach (string table in new[]
        {
            "meta",
            "journal",
            "splits"
        }

        )
            foreach (string operation in new[]
            {
                "UPDATE",
                "DELETE"
            }

            )
                Test("append-guard-" + table + "-" + operation, () =>
                {
                    var b = Book("guard-" + table + operation);
                    Store.Apply(b.Folder, Demo.Request(b.Id, "R"));
                    string sql = operation == "DELETE" ? "DELETE FROM " + table : table switch
                    {
                        "meta" => "UPDATE meta SET profile=profile",
                        "journal" => "UPDATE journal SET request_id=request_id",
                        _ => "UPDATE splits SET debit=debit"
                    };
                    try
                    {
                        Sql(b.Folder, sql);
                        throw new Exception("EXPECTED_SQL_REJECTION");
                    }
                    catch (SqliteException)
                    {
                    }

                    Assert(Store.Snapshot(b.Folder).LastSequence == 1);
                });
        Test("audit-trigger-identity", () =>
        {
            var b = Book("bad-trigger");
            Sql(b.Folder, "DROP TRIGGER journal_no_update; CREATE TRIGGER journal_no_update BEFORE UPDATE ON journal BEGIN SELECT 1; END");
            Problem(() => Store.Snapshot(b.Folder), "BOOK_SCHEMA_INVALID");
        });
        Test("audit-extra-schema", () =>
        {
            var b = Book("extra-table");
            Sql(b.Folder, "CREATE TABLE injected(x)");
            Problem(() => Store.Snapshot(b.Folder), "BOOK_SCHEMA_INVALID");
        });
        foreach (var change in new[]
        {
            ("canonical", "canonical='{}'"),
            ("request-hash", "request_hash='bad'"),
            ("receipt", "receipt='{}'"),
            ("receipt-hash", "receipt_hash='bad'"),
            ("sequence", "seq=3")
        }

        )
            Test("audit-" + change.Item1, () =>
            {
                var b = Book("audit-" + change.Item1);
                Store.Apply(b.Folder, Demo.Request(b.Id, "R"));
                string trigger = Store.Schema["journal_no_update"];
                if (change.Item1 == "sequence")
                    Sql(b.Folder, "PRAGMA foreign_keys=OFF; DROP TRIGGER journal_no_update; DROP TRIGGER splits_no_update; UPDATE journal SET seq=3; UPDATE splits SET seq=3; " + trigger + "; " + Store.Schema["splits_no_update"]);
                else
                    Sql(b.Folder, "DROP TRIGGER journal_no_update; UPDATE journal SET " + change.Item2 + "; " + trigger);
                Problem(() => Store.Snapshot(b.Folder));
            });
        foreach (var value in new[]
        {
            ("text", "'12345'"),
            ("real", "12345.5"),
            ("blob", "x'3132333435'")
        }

        )
            Test("audit-actual-storage-" + value.Item1, () =>
            {
                var b = Book("storage-" + value.Item1);
                Store.Apply(b.Folder, Demo.Request(b.Id, "R"));
                Sql(b.Folder, "PRAGMA writable_schema=ON; UPDATE sqlite_schema SET sql=replace(sql,'debit INTEGER','debit ANY') WHERE name='splits'; PRAGMA writable_schema=OFF");
                Sql(b.Folder, "DROP TRIGGER splits_no_update; UPDATE splits SET debit=" + value.Item2 + " WHERE account='cash'; " + Store.Schema["splits_no_update"]);
                using (var c = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = Path.Combine(b.Folder, "book.sqlite"), Pooling = false }.ToString()))
                {
                    c.Open();
                    using var cmd = Store.Command(c, null, "SELECT typeof(debit) FROM splits WHERE account='cash'");
                    Assert((string)cmd.ExecuteScalar()! == value.Item1);
                }

                Sql(b.Folder, "PRAGMA writable_schema=ON; UPDATE sqlite_schema SET sql=replace(sql,'debit ANY','debit INTEGER') WHERE name='splits'; PRAGMA writable_schema=OFF");
                Problem(() => Store.Snapshot(b.Folder));
            });
        Test("audit-split-values", () =>
        {
            var b = Book("audit-splits");
            Store.Apply(b.Folder, Demo.Request(b.Id, "R"));
            Sql(b.Folder, "DROP TRIGGER splits_no_update; UPDATE splits SET debit=1 WHERE account='cash'; " + Store.Schema["splits_no_update"]);
            Problem(() => Store.Snapshot(b.Folder), "BOOK_SPLIT_AGREEMENT_INVALID");
        });
        Test("audit-missing-split", () =>
        {
            var b = Book("missing-split");
            Store.Apply(b.Folder, Demo.Request(b.Id, "R"));
            Sql(b.Folder, "DROP TRIGGER splits_no_delete; DELETE FROM splits WHERE account='cash'; " + Store.Schema["splits_no_delete"]);
            Problem(() => Store.Snapshot(b.Folder), "BOOK_SPLIT_AGREEMENT_INVALID");
        });
        Test("audit-foreign-key", () =>
        {
            var b = Book("foreign-key");
            Sql(b.Folder, "PRAGMA foreign_keys=OFF; INSERT INTO splits VALUES(99,'cash',1,0)");
            Problem(() => Store.Snapshot(b.Folder), "BOOK_FOREIGN_KEY_INVALID");
        });
        Test("audit-header-appid", () =>
        {
            var b = Book("appid");
            Sql(b.Folder, "PRAGMA application_id=123");
            Problem(() => Store.Snapshot(b.Folder), "BOOK_HEADER_OR_MODE_INVALID");
        });
        Test("audit-version", () =>
        {
            var b = Book("version");
            Sql(b.Folder, "PRAGMA user_version=9");
            Problem(() => Store.Snapshot(b.Folder), "BOOK_HEADER_OR_MODE_INVALID");
        });
        Test("audit-marker-binding", () =>
        {
            var b = Book("marker-binding");
            File.WriteAllText(Path.Combine(b.Folder, ".ledger-owned"), new string ('b', 32));
            Problem(() => Store.Snapshot(b.Folder), "BOOK_IDENTITY_INVALID");
        });
        Test("capacity-replay-and-new-refusal", () =>
        {
            var b = Book("capacity");
            using (var c = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = Path.Combine(b.Folder, "book.sqlite"), Pooling = false }.ToString()))
            {
                c.Open();
                using var t = c.BeginTransaction();
                for (int seq = 1; seq <= Contract.Capacity; seq++)
                {
                    var p = Demo.Request(b.Id, "REQ_" + seq, seq);
                    string receipt = Store.Receipt(p, seq);
                    Store.Execute(c, t, "INSERT INTO journal VALUES($s,$i,$c,$h,$r,$rh)", ("$s", seq), ("$i", p.RequestId), ("$c", p.Canonical), ("$h", Contract.Hash(p.Canonical)), ("$r", receipt), ("$rh", Contract.Hash(receipt)));
                    foreach (var split in p.Splits)
                        Store.Execute(c, t, "INSERT INTO splits VALUES($s,$a,$d,$c)", ("$s", seq), ("$a", split.Account), ("$d", split.Debit), ("$c", split.Credit));
                }

                t.Commit();
            }

            var replay = Store.Apply(b.Folder, Demo.Request(b.Id, "REQ_1", 1));
            Assert(replay.Disposition == "replayed" && replay.Receipt == Store.Receipt(Demo.Request(b.Id, "REQ_1", 1), 1));
            Problem(() => Store.Apply(b.Folder, Demo.Request(b.Id, "NEW")), "BOOK_CAPACITY_REACHED");
            Assert(Store.Snapshot(b.Folder).LastSequence == Contract.Capacity);
        });
    }

    private static void Comparisons()
    {
        var b = Book("comparison-book");
        Store.Apply(b.Folder, Demo.Request(b.Id, "A", 100));
        Store.Apply(b.Folder, Demo.Request(b.Id, "B", 200));
        var snapshot = Store.Snapshot(b.Folder);
        Test("report-distinguishes-books-at-same-sequence", () =>
        {
            List<JsonElement> reports = [];
            foreach (string suffix in new[]
            {
                "one",
                "two"
            }

            )
            {
                var owned = Book("report-identity-" + suffix);
                Store.Apply(owned.Folder, Demo.Request(owned.Id, "SAME", 100));
                string input = Fresh("identity-" + suffix + ".json"), output = Fresh("identity-report-" + suffix);
                File.WriteAllText(input, StatementJson(owned.Id, 1, new StatementRow("SAME", 100)));
                Assert(Reconcile.Run(owned.Folder, input, output).Outcome == "pass");
                using var d = JsonDocument.Parse(File.ReadAllBytes(Path.Combine(output, "summary.json")));
                var r = d.RootElement;
                Assert(r.GetProperty("bookId").GetString() == owned.Id && r.GetProperty("statementSha256").GetString() == Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(File.ReadAllBytes(input))).ToLowerInvariant());
                reports.Add(r.Clone());
            }

            Assert(reports[0].GetProperty("bookId").GetString() != reports[1].GetProperty("bookId").GetString());
            Assert(reports[0].GetProperty("snapshotReceiptListSha256").GetString() != reports[1].GetProperty("snapshotReceiptListSha256").GetString());
        });
        Test("report-exact-statement-bytes-vs-canonical-snapshot", () =>
        {
            string input = Fresh("byte-bound-statement.json"), json = StatementJson(b.Id, 2, new("A", 100), new("B", 200));
            List<JsonElement> reports = [];
            foreach (int i in new[]
            {
                0,
                1
            }

            )
            {
                File.WriteAllText(input, i == 0 ? json : " \n" + json + "\n");
                string output = Fresh("byte-bound-report-" + i);
                Reconcile.Run(b.Folder, input, output);
                using var d = JsonDocument.Parse(File.ReadAllBytes(Path.Combine(output, "summary.json")));
                reports.Add(d.RootElement.Clone());
            }

            Assert(reports[0].GetProperty("statementSha256").GetString() != reports[1].GetProperty("statementSha256").GetString());
            Assert(reports[0].GetProperty("snapshotReceiptListSha256").GetString() == reports[1].GetProperty("snapshotReceiptListSha256").GetString());
            string list = LiteralSnapshotFrame(snapshot);
            Assert(reports[0].GetProperty("snapshotReceiptListSha256").GetString() == Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(Bytes(list))).ToLowerInvariant());
            Assert(reports[0].GetProperty("snapshotDigestSchema").GetString() == "synthetic-ledger-snapshot-v1");
        });
        Test("comparison-match-limits-visible", () =>
        {
            var r = Reconcile.Compare(snapshot, new(b.Id, "LAB", 2, 2, [new("B", 200), new("A", 100)]));
            Assert(r.Outcome == "pass" && r.Provenance == "UNVERIFIED" && r.Freshness == "NOT_CHECKED" && r.ExternalCompleteness == "NOT_PROVEN");
        });
        Test("comparison-exact-error-counts", () =>
        {
            var r = Reconcile.Compare(snapshot, new(b.Id, "LAB", 2, 2, [new("A", 99), new("X", 1), new("X", 2), new("A", 98)]));
            Assert(r.Complete && r.Outcome == "fail" && r.Duplicates == 2 && r.Unexpected == 2 && r.WrongAmount == 2 && r.Missing == 1);
        });
        Test("comparison-bounded-examples-exact-totals", () =>
        {
            var r = Reconcile.Compare(snapshot, new(b.Id, "LAB", 2, 2, Enumerable.Range(0, 1000).Select(_ => new StatementRow("X", 1)).ToArray()));
            Assert(r.Duplicates == 999 && r.Unexpected == 1000 && r.Missing == 2 && r.DiagnosticCodes.Length == 20);
        });
        Test("comparison-book-unit-scope", () =>
        {
            var r = Reconcile.Compare(snapshot, new(new string ('a', 32), "USD", 3, 1, []));
            Assert(r.BookMismatch && r.UnitMismatch && r.ScopeMismatch && r.Outcome == "fail");
            string input = Fresh("mismatched-book-statement.json"), output = Fresh("mismatched-book-report");
            File.WriteAllText(input, StatementJson(new string ('a', 32), 2, new("A", 100), new("B", 200)));
            Assert(Reconcile.Run(b.Folder, input, output).Outcome == "fail");
            using var doc = JsonDocument.Parse(File.ReadAllBytes(Path.Combine(output, "summary.json")));
            Assert(doc.RootElement.GetProperty("bookId").GetString() == b.Id && doc.RootElement.GetProperty("declaredBookId").GetString() == new string ('a', 32));
        });
        Test("statement-duplicates-preserved", () =>
        {
            var s = Statement.Parse(Bytes(StatementJson(b.Id, 2, new("A", 100), new("A", 100))));
            Assert(s.Rows.Length == 2 && Reconcile.Compare(snapshot, s).Duplicates == 1);
        });
        Test("statement-duplicate-key-file-fatal", () => Problem(() => Statement.Parse(Bytes(StatementJson(b.Id, 2).Insert(1, "\"unit\":\"LAB\","))), "JSON_DUPLICATE_KEY"));
        Test("statement-nested-duplicate-key", () => Problem(() => Statement.Parse(Bytes(StatementJson(b.Id, 2, new StatementRow("A", 100)).Replace("\"amountMinor\":100", "\"amountMinor\":100,\"amountMinor\":100", StringComparison.Ordinal))), "JSON_DUPLICATE_KEY"));
        Test("statement-row-cap", () => Problem(() => Statement.Parse(Bytes(StatementJson(b.Id, 2, Enumerable.Range(0, 1001).Select(_ => new StatementRow("A", 1)).ToArray()))), "STATEMENT_ROW_LIMIT"));
        Test("statement-duplicate-key-cli-incomplete", () =>
        {
            string input = Fresh("duplicate-key-statement.json");
            File.WriteAllText(input, StatementJson(b.Id, 2).Insert(1, "\"unit\":\"LAB\","));
            var r = Cli("reconcile", b.Folder, input, Fresh("invalid-statement-report"));
            Assert(r.Exit == 1 && !r.Output.GetProperty("complete").GetBoolean() && !Directory.Exists(Fresh("invalid-statement-report")));
        });
        Test("statement-float", () => Problem(() => Statement.Parse(Bytes(StatementJson(b.Id, 2, new StatementRow("A", 100)).Replace(":100", ":1e2", StringComparison.Ordinal))), "INTEGER_ENCODING_INVALID"));
        Test("comparison-snapshot-later-append", () =>
        {
            string input = Fresh("snapshot-statement.json");
            File.WriteAllText(input, StatementJson(b.Id, 2, new("A", 100), new("B", 200)));
            Reconcile.SnapshotForTests = () => Store.Apply(b.Folder, Demo.Request(b.Id, "LATER", 1));
            var r = Reconcile.Run(b.Folder, input, Fresh("snapshot-report"));
            Assert(r.Outcome == "pass" && r.SnapshotSequence == 2 && Store.Snapshot(b.Folder).LastSequence == 3);
            using var report = JsonDocument.Parse(File.ReadAllBytes(Path.Combine(Fresh("snapshot-report"), "summary.json")));
            string list = LiteralSnapshotFrame(snapshot);
            Assert(report.RootElement.GetProperty("snapshotReceiptListSha256").GetString() == Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(Bytes(list))).ToLowerInvariant());
            Assert(report.RootElement.GetProperty("bookId").GetString() == snapshot.BookId && report.RootElement.GetProperty("result").GetProperty("snapshotSequence").GetInt32() == 2);
        });
    }

    private static JsonElement ReadJson(string path)
    {
        using var document = JsonDocument.Parse(File.ReadAllBytes(path));
        return document.RootElement.Clone();
    }

    private static string IndependentHash(byte[] bytes) => Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(bytes)).ToLowerInvariant();

    private static string BookFingerprint(string folder) => string.Join("\n", Directory.GetFiles(folder).OrderBy(p => p, StringComparer.Ordinal).Select(p => Path.GetFileName(p) + ":" + IndependentHash(File.ReadAllBytes(p))));

    private static void AssertDetailBinding(string output)
    {
        byte[] bytes = File.ReadAllBytes(Path.Combine(output, "discrepancies.json"));
        Assert(bytes[^1] == 10 && !bytes.AsSpan().StartsWith(new byte[] { 0xef, 0xbb, 0xbf }) && bytes.Length <= 2 * 1024 * 1024);
        var detail = ReadJson(Path.Combine(output, "discrepancies.json"));
        var summary = ReadJson(Path.Combine(output, "summary.json"));
        Assert(detail.EnumerateObject().Select(p => p.Name).SequenceEqual(new[] { "schema", "summarySha256", "bookId", "statementSha256", "snapshotReceiptListSha256", "throughSequence", "issues" }));
        Assert(detail.GetProperty("schema").GetString() == "synthetic-reconciliation-discrepancies-v1");
        Assert(detail.GetProperty("summarySha256").GetString() == IndependentHash(File.ReadAllBytes(Path.Combine(output, "summary.json"))));
        foreach (string field in new[] { "bookId", "statementSha256", "snapshotReceiptListSha256" })
            Assert(detail.GetProperty(field).GetString() == summary.GetProperty(field).GetString());
        Assert(detail.GetProperty("throughSequence").GetInt32() == summary.GetProperty("result").GetProperty("snapshotSequence").GetInt32());
        var issues = detail.GetProperty("issues").EnumerateArray().ToArray();
        foreach (var issue in issues)
            Assert(issue.EnumerateObject().Select(p => p.Name).SequenceEqual(new[] { "code", "requestId", "statementRowIndex", "entrySequence", "expectedAmountMinor", "actualAmountMinor", "firstStatementRowIndex" }));
        foreach (var pair in new[] { ("DUPLICATE_REQUEST_ID", "duplicates"), ("UNEXPECTED_REQUEST_ID", "unexpected"), ("WRONG_AMOUNT", "wrongAmount"), ("MISSING_REQUEST_ID", "missing") })
            Assert(issues.Count(i => i.GetProperty("code").GetString() == pair.Item1) == summary.GetProperty("result").GetProperty(pair.Item2).GetInt32());
        Assert(issues.Length <= 4000);
    }

    private static void DiscrepancyTests()
    {
        var b = Book("m1-book");
        Store.Apply(b.Folder, Demo.Request(b.Id, "A", 100));
        Store.Apply(b.Folder, Demo.Request(b.Id, "B", 200));
        string matching = StatementJson(b.Id, 2, new("B", 200), new("A", 100));
        string negative = StatementJson(b.Id, 2, new("A", 99), new("X", 1), new("X", 2), new("A", 98));
        (int Exit, JsonElement Output, string Folder) Compare(string label, string json)
        {
            string input = Fresh("m1-" + label + ".json"), output = Fresh("m1-" + label + "-report");
            File.WriteAllText(input, json, new UTF8Encoding(false));
            var result = Cli("reconcile", b.Folder, input, output);
            if (File.Exists(Path.Combine(output, "summary.json")))
                AssertDetailBinding(output);
            return (result.Exit, result.Output, output);
        }

        Test("m1-ac01-match-and-empty", () =>
        {
            var r = Compare("match", matching);
            Assert(r.Exit == 0 && ReadJson(Path.Combine(r.Folder, "discrepancies.json")).GetProperty("issues").GetArrayLength() == 0);
            var empty = Book("m1-empty");
            string input = Fresh("m1-empty.json"), output = Fresh("m1-empty-report");
            File.WriteAllText(input, StatementJson(empty.Id, 0));
            Assert(Cli("reconcile", empty.Folder, input, output).Exit == 0);
            AssertDetailBinding(output);
            Assert(ReadJson(Path.Combine(output, "discrepancies.json")).GetProperty("throughSequence").GetInt32() == 0);
        });
        Test("m1-ac02-literal-seven-issues", () =>
        {
            var r = Compare("negative", negative);
            Assert(r.Exit == 2);
            var result = r.Output.GetProperty("result");
            Assert(result.GetProperty("missing").GetInt32() == 1 && result.GetProperty("unexpected").GetInt32() == 2 && result.GetProperty("duplicates").GetInt32() == 2 && result.GetProperty("wrongAmount").GetInt32() == 2);
            const string expected = """
            [{"code":"WRONG_AMOUNT","requestId":"A","statementRowIndex":1,"entrySequence":1,"expectedAmountMinor":100,"actualAmountMinor":99,"firstStatementRowIndex":null},{"code":"UNEXPECTED_REQUEST_ID","requestId":"X","statementRowIndex":2,"entrySequence":null,"expectedAmountMinor":null,"actualAmountMinor":1,"firstStatementRowIndex":null},{"code":"DUPLICATE_REQUEST_ID","requestId":"X","statementRowIndex":3,"entrySequence":null,"expectedAmountMinor":null,"actualAmountMinor":2,"firstStatementRowIndex":2},{"code":"UNEXPECTED_REQUEST_ID","requestId":"X","statementRowIndex":3,"entrySequence":null,"expectedAmountMinor":null,"actualAmountMinor":2,"firstStatementRowIndex":null},{"code":"DUPLICATE_REQUEST_ID","requestId":"A","statementRowIndex":4,"entrySequence":1,"expectedAmountMinor":100,"actualAmountMinor":98,"firstStatementRowIndex":1},{"code":"WRONG_AMOUNT","requestId":"A","statementRowIndex":4,"entrySequence":1,"expectedAmountMinor":100,"actualAmountMinor":98,"firstStatementRowIndex":null},{"code":"MISSING_REQUEST_ID","requestId":"B","statementRowIndex":null,"entrySequence":2,"expectedAmountMinor":200,"actualAmountMinor":null,"firstStatementRowIndex":null}]
            """;
            Assert(ReadJson(Path.Combine(r.Folder, "discrepancies.json")).GetProperty("issues").GetRawText() == expected, "LITERAL_SEVEN_ISSUES");
        });
        Test("m1-ac03-duplicate-overlap-case-and-int64", () =>
        {
            var known = Compare("duplicate-known", StatementJson(b.Id, 2, new("A", 100), new("A", 100), new("B", 200)));
            Assert(known.Exit == 2 && ReadJson(Path.Combine(known.Folder, "discrepancies.json")).GetProperty("issues").GetArrayLength() == 1);
            var unknown = Compare("duplicate-unknown", StatementJson(b.Id, 2, new("X", 1), new("X", 1)));
            Assert(unknown.Exit == 2 && ReadJson(Path.Combine(unknown.Folder, "discrepancies.json")).GetProperty("issues").GetArrayLength() == 5);
            var casing = Compare("case", StatementJson(b.Id, 2, new("a", 100), new("B", 200)));
            Assert(casing.Exit == 2 && casing.Output.GetProperty("result").GetProperty("missing").GetInt32() == 1 && casing.Output.GetProperty("result").GetProperty("unexpected").GetInt32() == 1);
            var edge = Compare("large-amount", StatementJson(b.Id, 2, new("A", 3_000_000_000_000), new("B", 0)));
            Assert(edge.Exit == 2 && ReadJson(Path.Combine(edge.Folder, "discrepancies.json")).GetProperty("issues")[0].GetProperty("actualAmountMinor").GetInt64() == 3_000_000_000_000);
        });
        foreach (var mismatch in new[] { ("book", matching.Replace(b.Id, new string('a', 32)), "bookMismatch"), ("unit", matching.Replace("LAB", "USD"), "unitMismatch"), ("scale", matching.Replace("\"scale\":2", "\"scale\":3"), "unitMismatch"), ("scope", matching.Replace("\"throughSequence\":2", "\"throughSequence\":1"), "scopeMismatch"), ("all", matching.Replace(b.Id, new string('a', 32)).Replace("LAB", "USD").Replace("\"throughSequence\":2", "\"throughSequence\":1"), "scopeMismatch") })
            Test("m1-ac04-scope-" + mismatch.Item1, () =>
            {
                var r = Compare("scope-" + mismatch.Item1, mismatch.Item2);
                Assert(r.Exit == 2 && r.Output.GetProperty("result").GetProperty(mismatch.Item3).GetBoolean());
                Assert(ReadJson(Path.Combine(r.Folder, "discrepancies.json")).GetProperty("issues").GetArrayLength() == 0);
                Assert(ReadJson(Path.Combine(r.Folder, "summary.json")).GetProperty("bookId").GetString() == b.Id);
            });
        string valid = StatementJson(b.Id, 2, new("A", 100), new("B", 200));
        var invalid = new List<(string, string)>
        {
            ("duplicate-key", valid.Insert(1, "\"unit\":\"LAB\",")),
            ("nested-key", valid.Replace("\"amountMinor\":100", "\"amountMinor\":100,\"amountMinor\":100")),
            ("extra-key", valid.Insert(1, "\"extra\":1,")),
            ("missing-key", valid.Replace("\"scale\":2,", "")),
            ("unsupported-schema", valid.Replace("synthetic-statement-v1", "other-v1")),
            ("depth", new string('[', 9) + new string(']', 9)),
            ("bytes", new string(' ', 1024 * 1024 + 1)),
            ("rows", StatementJson(b.Id, 2, Enumerable.Repeat(new StatementRow("A", 100), 1001).ToArray()))
        };
        foreach (string token in new[] { "1e2", "100.0", "\"100\"", "-1", "9223372036854775808", "3000000000001" })
            invalid.Add(("number-" + invalid.Count, valid.Replace("\"amountMinor\":100", "\"amountMinor\":" + token)));
        foreach (var item in invalid)
            Test("m1-ac05-reject-" + item.Item1, () =>
            {
                string before = BookFingerprint(b.Folder);
                var r = Compare("invalid-" + item.Item1, item.Item2);
                Assert(r.Exit == 1 && !r.Output.GetProperty("complete").GetBoolean() && !Directory.Exists(r.Folder));
                Assert(BookFingerprint(b.Folder) == before);
            });
        Test("m1-ac06-repeat-bytes-whitespace-and-culture", () =>
        {
            var first = Compare("repeat-one", negative);
            var previous = System.Globalization.CultureInfo.CurrentCulture;
            try
            {
                System.Globalization.CultureInfo.CurrentCulture = System.Globalization.CultureInfo.GetCultureInfo("fa-IR");
                var second = Compare("repeat-two", negative);
                foreach (string name in new[] { "summary.json", "summary.txt", "discrepancies.json" })
                    Assert(File.ReadAllBytes(Path.Combine(first.Folder, name)).SequenceEqual(File.ReadAllBytes(Path.Combine(second.Folder, name))), name);
            }
            finally { System.Globalization.CultureInfo.CurrentCulture = previous; }
            var changed = Compare("repeat-whitespace", " \n" + negative + "\n");
            var a = ReadJson(Path.Combine(first.Folder, "discrepancies.json"));
            var z = ReadJson(Path.Combine(changed.Folder, "discrepancies.json"));
            Assert(a.GetProperty("statementSha256").GetString() != z.GetProperty("statementSha256").GetString());
            Assert(a.GetProperty("snapshotReceiptListSha256").GetString() == z.GetProperty("snapshotReceiptListSha256").GetString());
            Assert(a.GetProperty("issues").GetRawText() == z.GetProperty("issues").GetRawText());
        });
        Test("m1-ac07-literal-2001-issues", () =>
        {
            var r = Compare("2001", StatementJson(b.Id, 2, Enumerable.Repeat(new StatementRow("X", 1), 1000).ToArray()));
            Assert(r.Exit == 2);
            var result = r.Output.GetProperty("result");
            Assert(result.GetProperty("duplicates").GetInt32() == 999 && result.GetProperty("unexpected").GetInt32() == 1000 && result.GetProperty("missing").GetInt32() == 2 && result.GetProperty("wrongAmount").GetInt32() == 0 && result.GetProperty("diagnosticCodes").GetArrayLength() == 20);
            var issues = ReadJson(Path.Combine(r.Folder, "discrepancies.json")).GetProperty("issues");
            Assert(issues.GetArrayLength() == 2001);
            Assert(issues[0].GetProperty("code").GetString() == "UNEXPECTED_REQUEST_ID");
            for (int row = 2; row <= 1000; row++)
            {
                var duplicate = issues[2 * row - 3];
                var unexpected = issues[2 * row - 2];
                Assert(duplicate.GetProperty("code").GetString() == "DUPLICATE_REQUEST_ID" && duplicate.GetProperty("firstStatementRowIndex").GetInt32() == 1);
                Assert(unexpected.GetProperty("code").GetString() == "UNEXPECTED_REQUEST_ID");
                foreach (var issue in new[] { duplicate, unexpected })
                    Assert(issue.GetProperty("statementRowIndex").GetInt32() == row && issue.GetProperty("requestId").GetString() == "X" && issue.GetProperty("actualAmountMinor").GetInt64() == 1 && issue.GetProperty("expectedAmountMinor").ValueKind == JsonValueKind.Null && issue.GetProperty("entrySequence").ValueKind == JsonValueKind.Null);
            }
            Assert(issues[1999].GetProperty("requestId").GetString() == "A" && issues[1999].GetProperty("expectedAmountMinor").GetInt64() == 100 && issues[1999].GetProperty("entrySequence").GetInt32() == 1);
            Assert(issues[2000].GetProperty("requestId").GetString() == "B" && issues[2000].GetProperty("expectedAmountMinor").GetInt64() == 200 && issues[2000].GetProperty("entrySequence").GetInt32() == 2);
        });
        Test("m1-ac07-1000-posts-and-rows", () =>
        {
            // Existing independent capacity fixture is already at the contract boundary.
            string folder = Fresh("capacity"), id = Safe.Owned(folder);
            string input = Fresh("m1-capacity.json"), output = Fresh("m1-capacity-report");
            File.WriteAllText(input, StatementJson(id, 1000, Enumerable.Range(1, 1000).Select(i => new StatementRow("REQ_" + i, i)).ToArray()));
            string before = BookFingerprint(folder);
            Assert(Cli("reconcile", folder, input, output).Exit == 0 && BookFingerprint(folder) == before);
            AssertDetailBinding(output);
            Assert(ReadJson(Path.Combine(output, "discrepancies.json")).GetProperty("issues").GetArrayLength() == 0);
        });
        Test("m1-ac08-quiescent-book-unchanged", () =>
        {
            string before = BookFingerprint(b.Folder);
            var snapshot = Store.Snapshot(b.Folder);
            Assert(Compare("no-write-pass", matching).Exit == 0);
            Assert(Compare("no-write-fail", negative).Exit == 2);
            Assert(Compare("no-write-malformed", "{").Exit == 1);
            Report.BeforeFileForTests = (_, _) => throw new IOException("CONTROLLED_REPORT_FAILURE");
            Assert(Compare("no-write-report-failure", matching).Exit == 1);
            Report.BeforeFileForTests = null;
            Assert(BookFingerprint(b.Folder) == before, "BOOK_BYTES_OR_INVENTORY_CHANGED");
            var after = Store.Snapshot(b.Folder);
            Assert(after.Entries.Select(e => (e.Sequence, e.Post.Canonical, e.Receipt, e.ReceiptSha256)).SequenceEqual(snapshot.Entries.Select(e => (e.Sequence, e.Post.Canonical, e.Receipt, e.ReceiptSha256))), "LOGICAL_JOURNAL_CHANGED");
        });
        Test("m1-ac09-details-one-snapshot", () =>
        {
            var owned = Book("m1-snapshot");
            Store.Apply(owned.Folder, Demo.Request(owned.Id, "A", 100));
            var snapshot = Store.Snapshot(owned.Folder);
            string input = Fresh("m1-snapshot.json"), output = Fresh("m1-snapshot-report");
            File.WriteAllText(input, StatementJson(owned.Id, 1, new StatementRow("A", 99)));
            Reconcile.SnapshotForTests = () => Store.Apply(owned.Folder, Demo.Request(owned.Id, "LATER", 10));
            Assert(Cli("reconcile", owned.Folder, input, output).Exit == 2);
            AssertDetailBinding(output);
            var detail = ReadJson(Path.Combine(output, "discrepancies.json"));
            Assert(detail.GetProperty("issues").GetArrayLength() == 1 && detail.GetProperty("throughSequence").GetInt32() == 1 && Store.Snapshot(owned.Folder).LastSequence == 2);
            Assert(detail.GetProperty("snapshotReceiptListSha256").GetString() == IndependentHash(Bytes(LiteralSnapshotFrame(snapshot))));
        });
        foreach (string phase in new[] { "write:discrepancies.json", "write:summary.txt", "write:summary.json", "rename:discrepancies.json", "rename:summary.txt", "rename:summary.json" })
            foreach (string fault in new[] { "exception", "collision", "ownership" })
                Test("m1-ac10-" + phase + "-" + fault, () =>
                {
                    string before = BookFingerprint(b.Folder);
                    string? sentinel = null;
                    Report.BeforeFileForTests = (folder, observed) =>
                    {
                        if (observed != phase) return;
                        Assert(!File.Exists(Path.Combine(folder, "summary.json")), "SUMMARY_PUBLISHED_EARLY");
                        if (fault == "exception") throw new IOException("CONTROLLED_WRITE_OR_RENAME_FAILURE");
                        if (fault == "ownership") File.WriteAllText(Path.Combine(folder, ".ledger-owned"), new string('f', 32));
                        else
                        {
                            string name = phase.Split(':')[1];
                            // A final-path directory causes a rename collision without introducing a forged summary file.
                            sentinel = Path.Combine(folder, name + (phase.StartsWith("write:", StringComparison.Ordinal) ? ".pending" : ""));
                            if (phase.StartsWith("write:", StringComparison.Ordinal)) File.WriteAllText(sentinel, "occupied");
                            else { Directory.CreateDirectory(sentinel); File.WriteAllText(Path.Combine(sentinel, "sentinel"), "occupied"); }
                        }
                    };
                    var r = Compare("fault-" + phase.Replace(':', '-') + "-" + fault, matching);
                    Assert(r.Exit == 1 && !r.Output.GetProperty("complete").GetBoolean() && r.Output.GetProperty("outcome").GetString() == "incomplete");
                    Assert(!File.Exists(Path.Combine(r.Folder, "summary.json")) && BookFingerprint(b.Folder) == before);
                    if (sentinel != null) Assert(File.Exists(sentinel) ? File.ReadAllText(sentinel) == "occupied" : File.ReadAllText(Path.Combine(sentinel, "sentinel")) == "occupied");
                    if (fault == "ownership") Assert(File.ReadAllText(Path.Combine(r.Folder, ".ledger-owned")) == new string('f', 32));
                });
        Test("m1-ac10-summary-last-observed", () =>
        {
            List<string> phases = [];
            Report.BeforeFileForTests = (folder, phase) =>
            {
                phases.Add(phase);
                Assert(!File.Exists(Path.Combine(folder, "summary.json")));
                if (phase == "rename:summary.json") Assert(File.Exists(Path.Combine(folder, "discrepancies.json")) && File.Exists(Path.Combine(folder, "summary.txt")));
            };
            Assert(Compare("summary-last", matching).Exit == 0);
            Assert(phases.SequenceEqual(new[] { "write:discrepancies.json", "write:summary.txt", "write:summary.json", "rename:discrepancies.json", "rename:summary.txt", "rename:summary.json" }));
        });
        Test("m1-ac10-output-exists-and-overlap", () =>
        {
            string input = Fresh("m1-existing-input.json"), output = Fresh("m1-existing-output");
            File.WriteAllText(input, matching);
            Directory.CreateDirectory(output);
            File.WriteAllText(Path.Combine(output, "sentinel"), "untouched");
            Assert(Cli("reconcile", b.Folder, input, output).Exit == 1 && File.ReadAllText(Path.Combine(output, "sentinel")) == "untouched");
            Assert(Cli("reconcile", b.Folder, input, Path.Combine(b.Folder, "report")).Exit == 1);
            Assert(Cli("reconcile", b.Folder, input, input).Exit == 1 && File.ReadAllText(input) == matching);
        });
        foreach (bool bytesOverLimit in new[] { false, true })
            Test("m1-ac10-" + (bytesOverLimit ? "byte" : "issue") + "-cap-incomplete", () =>
            {
                var snapshot = Store.Snapshot(b.Folder);
                var issue = new Discrepancy("UNEXPECTED_REQUEST_ID", bytesOverLimit ? new string('x', 2 * 1024 * 1024) : "X", 1, null, null, 1, null);
                // These guards cannot be exceeded by valid bounded input today; exercise the actual serialization boundary directly.
                var issues = Enumerable.Repeat(issue, bytesOverLimit ? 1 : 4001).ToArray();
                string output = Fresh("m1-cap-" + bytesOverLimit);
                Problem(() => Report.Write(output, new { outcome = "fail" }, summary => Discrepancies.Serialize(summary, snapshot, new string('a', 64), new string('b', 64), issues)), bytesOverLimit ? "DISCREPANCY_BYTE_LIMIT" : "DISCREPANCY_ISSUE_LIMIT");
                Assert(!File.Exists(Path.Combine(output, "summary.json")) && !File.Exists(Path.Combine(output, "discrepancies.json")));
                Report.BeforeWriteForTests = _ => Discrepancies.Serialize([], snapshot, "", "", issues);
                var r = Compare("cli-cap-" + bytesOverLimit, matching);
                Assert(r.Exit == 1 && !r.Output.GetProperty("complete").GetBoolean() && r.Output.GetProperty("reason").GetString() == (bytesOverLimit ? "DISCREPANCY_BYTE_LIMIT" : "DISCREPANCY_ISSUE_LIMIT"));
            });
        Test("m1-ac11-summary-and-demo-compatibility", () =>
        {
            var r = Compare("legacy-summary", matching);
            var snapshot = Store.Snapshot(b.Folder);
            string expectedSummary = Contract.Serialize(new { schema = "synthetic-reconciliation-report-v1", version = Contract.Version, toolBuild = Report.Build, bookId = b.Id, declaredBookId = b.Id, statementSha256 = IndependentHash(Bytes(matching)), snapshotDigestSchema = "synthetic-ledger-snapshot-v1", snapshotReceiptListSha256 = IndependentHash(Bytes(LiteralSnapshotFrame(snapshot))), result = Reconcile.Compare(snapshot, Statement.Parse(Bytes(matching))), limits = Report.Limits }) + "\n";
            Assert(File.ReadAllText(Path.Combine(r.Folder, "summary.json")) == expectedSummary);
            Assert(ReadJson(Path.Combine(r.Folder, "summary.json")).EnumerateObject().Select(p => p.Name).SequenceEqual(new[] { "schema", "version", "toolBuild", "bookId", "declaredBookId", "statementSha256", "snapshotDigestSchema", "snapshotReceiptListSha256", "result", "limits" }));
            Assert(r.Output.GetProperty("result").EnumerateObject().Select(p => p.Name).SequenceEqual(new[] { "complete", "outcome", "snapshotSequence", "bookMismatch", "unitMismatch", "scopeMismatch", "missing", "unexpected", "duplicates", "wrongAmount", "diagnosticCodes", "exitCode", "provenance", "freshness", "externalCompleteness" }));
            string expectedText = "Financial Reconciliation Ledger: pass\nVersion " + Contract.Version + "; synthetic LAB scale2 only.\nProvenance UNVERIFIED; freshness NOT_CHECKED; external completeness NOT_PROVEN.\nSee summary.json for exact counts and receipt disposition.\n" + Report.Limits + "\n";
            Assert(File.ReadAllText(Path.Combine(r.Folder, "summary.txt")) == expectedText);
            string demo = Fresh("m1-demo-unchanged");
            Assert(Cli("demo", demo).Exit == 0 && !File.Exists(Path.Combine(demo, "report", "discrepancies.json")));
        });
    }

    private static void FilesAndCli()
    {
        Test("path-all-control-positions", () =>
        {
            foreach (char c in Enumerable.Range(0, 160).Select(i => (char)i).Where(char.IsControl).Concat(new[] { '\u2028', '\u2029', '\ufeff' }))
                foreach (string p in new[]
                {
                    c + "demo",
                    "de" + c + "mo",
                    "demo" + c
                }

                )
                    Problem(() => Safe.Normalize(p), "PATH_UNSUPPORTED");
        });
        Test("path-network-and-length", () =>
        {
            Problem(() => Safe.Normalize(@"\\server\share"));
            Problem(() => Safe.Normalize("//server/share"));
            Problem(() => Safe.Normalize(Fresh(new string ('a', 400))));
        });
        Test("path-root-overlap", () =>
        {
            string p = Safe.Normalize(Fresh("overlap"));
            Problem(() => Safe.Separate(p, Path.GetPathRoot(p)!));
            Problem(() => Safe.Separate(Path.Combine(p, "child"), p));
            Safe.Separate(p + "-sibling", p);
        });
        Test("fresh-refuses-existing", () =>
        {
            var b = Book("existing");
            Problem(() => Store.Init(b.Folder), "OUTPUT_EXISTS");
            Assert(Store.Snapshot(b.Folder).LastSequence == 0);
        });
        Test("owned-marker-short", () =>
        {
            var b = Book("short-marker");
            File.WriteAllText(Path.Combine(b.Folder, ".ledger-owned"), "a");
            Problem(() => Store.Snapshot(b.Folder), "OWNERSHIP_INVALID");
        });
        Test("owned-unexpected-file", () =>
        {
            var b = Book("extra-file");
            File.WriteAllText(Path.Combine(b.Folder, "foreign.txt"), "fixture");
            Problem(() => Store.Snapshot(b.Folder), "BOOK_FILE_UNEXPECTED");
        });
        Test("owned-oversize-book", () =>
        {
            var b = Book("huge-book");
            using (var s = File.OpenWrite(Path.Combine(b.Folder, "book.sqlite")))
                s.SetLength(16 * 1024 * 1024 + 1);
            Problem(() => Store.Snapshot(b.Folder), "BOOK_BYTE_LIMIT");
        });
        Test("input-actual-byte-cap", () =>
        {
            string p = Fresh("huge.json");
            using (var s = File.Create(p))
                s.SetLength(Contract.InputLimit + 1);
            Problem(() => Safe.Read(p), "INPUT_BYTE_LIMIT");
        });
        Test("report-collision-never-pass", () =>
        {
            var b = Book("report-book");
            string input = Fresh("empty-statement.json");
            File.WriteAllText(input, StatementJson(b.Id, 0));
            Report.BeforeWriteForTests = output => File.WriteAllText(Path.Combine(output, "summary.json.pending"), "occupied");
            var r = Cli("reconcile", b.Folder, input, Fresh("collision-report"));
            Assert(r.Exit == 1 && r.Output.GetProperty("outcome").GetString() == "incomplete");
            Assert(!File.Exists(Path.Combine(Fresh("collision-report"), "summary.json")));
        });
        Test("reconcile-output-overlap", () =>
        {
            var b = Book("overlap-book");
            string input = Fresh("overlap-statement.json");
            File.WriteAllText(input, StatementJson(b.Id, 0));
            Assert(Cli("reconcile", b.Folder, input, Path.Combine(b.Folder, "report")).Exit == 1);
        });
        Test("cli-completed-rejection-vs-incomplete", () =>
        {
            var b = Book("cli-rejection");
            string p = Fresh("invalid-post.json");
            File.WriteAllText(p, Demo.Request(b.Id, "R").Canonical.Replace("\"credit\":12345", "\"credit\":1", StringComparison.Ordinal));
            Assert(Cli("post", b.Folder, p).Exit == 2);
            File.WriteAllText(p, "{");
            Assert(Cli("post", b.Folder, p).Exit == 1);
        });
        Test("cli-no-raw-input-or-private-path", () =>
        {
            var r = Cli("post", Fresh("PRIVATE_SECRET_FOLDER"), Fresh("PRIVATE_SECRET_INPUT"));
            Assert(r.Exit == 1 && !r.Output.ToString().Contains("PRIVATE_SECRET", StringComparison.Ordinal) && r.Output.GetProperty("schema").GetString() == "synthetic-ledger-error-v1" && r.Output.GetProperty("version").GetString() == Contract.Version && r.Output.GetProperty("toolBuild").GetString()!.Length > 0);
        });
        Test("cli-no-fault-or-sql-surface", () =>
        {
            foreach (string arg in new[]
            {
                "--test-worker",
                "--sql",
                "--host",
                "--reset",
                "--plugin",
                "--crash",
                "--config"
            }

            )
                Assert(Cli(arg).Exit == 1);
        });
        Test("cli-version", () =>
        {
            var original = Console.Out;
            using var text = new StringWriter();
            try
            {
                Console.SetOut(text);
                Assert(App.Main(["--version"]) == 0);
            }
            finally
            {
                Console.SetOut(original);
            }

            Assert(text.ToString().Contains(Contract.Version, StringComparison.Ordinal));
        });
        try
        {
            string target = Fresh("link-target");
            File.WriteAllText(target, "{}");
            string link = Fresh("input-link");
            File.CreateSymbolicLink(link, target);
            Test("symlink-refused", () => Problem(() => Safe.Read(link), "LINK_UNSUPPORTED"));
        }
        catch (Exception e)when (e is UnauthorizedAccessException or IOException)
        {
            Skipped++;
            Results.Add(new { name = "symlink-refused", outcome = "skip", reason = "LOCAL_SYMLINK_PRIVILEGE" });
        }

        if (OperatingSystem.IsLinux())
            Test("linux-fifo-refused-before-open", () =>
            {
                string p = Fresh("named-pipe");
                using var process = Process.Start(new ProcessStartInfo("mkfifo") { ArgumentList = { p }, UseShellExecute = false })!;
                Assert(process.WaitForExit(3000) && process.ExitCode == 0);
                Problem(() => Safe.Read(p), "REGULAR_FILE_REQUIRED");
            });
        else
        {
            Skipped++;
            Results.Add(new { name = "linux-fifo-refused-before-open", outcome = "skip", reason = "LINUX_ONLY" });
        }
    }

    private static void Processes()
    {
        Test("owned-process-stderr-byte-budget", () =>
        {
            var b = Book("stderr-budget");
            using var child = Child(b.Folder, "NO_POST", 1, "stderr-overflow");
            try
            {
                try
                {
                    BoundedError(child);
                    throw new Exception("EXPECTED_STDERR_BUDGET_FAILURE");
                }
                catch (InvalidDataException e)
                {
                    Assert(e.Message == "TEST_CHILD_STDERR_LIMIT");
                }

                Assert(child.WaitForExit(5000) && child.ExitCode == 0 && Store.Snapshot(b.Folder).LastSequence == 0);
            }
            finally
            {
                KillOwned(child);
            }
        });
        foreach (string phase in new[]
        {
            "before-commit",
            "after-commit-before-response"
        }

        )
            Test("owned-process-" + phase, () =>
            {
                var b = Book("kill-" + phase);
                using var child = Child(b.Folder, "INTERRUPTED", 71, phase);
                try
                {
                    using var d = JsonDocument.Parse(BoundedLine(child));
                    var r = d.RootElement;
                    Contract.Fields(r, "schema", "nonce", "phase", "pid");
                    Assert(r.GetProperty("schema").GetString() == "ledger-test-phase-v1" && r.GetProperty("nonce").GetString() == b.Id && r.GetProperty("phase").GetString() == phase && r.GetProperty("pid").GetInt32() == child.Id);
                    KillOwned(child);
                    Assert(BoundedError(child).Length == 0);
                    var snapshot = Store.Snapshot(b.Folder);
                    int count = phase == "before-commit" ? 0 : 1;
                    Assert(snapshot.LastSequence == count);
                    var retry = Store.Apply(b.Folder, Demo.Request(b.Id, "INTERRUPTED", 71));
                    Assert(retry.Disposition == (count == 0 ? "posted" : "replayed") && Store.Snapshot(b.Folder).LastSequence == 1);
                    if (count == 1)
                        Assert(retry.Receipt == snapshot.Entries[0].Receipt && retry.ReceiptSha256 == snapshot.Entries[0].ReceiptSha256);
                }
                finally
                {
                    KillOwned(child);
                }
            });
        foreach (bool conflict in new[]
        {
            false,
            true
        }

        )
            Test("concurrent-clients-" + (conflict ? "conflict" : "identical"), () =>
            {
                var b = Book("concurrent-" + conflict);
                using var first = Child(b.Folder, "SAME", 100, "none");
                using var second = Child(b.Folder, "SAME", conflict ? 200 : 100, "none");
                try
                {
                    string one = BoundedLine(first), two = BoundedLine(second);
                    Assert(first.WaitForExit(15000) && second.WaitForExit(15000));
                    Assert(BoundedError(first).Length == 0 && BoundedError(second).Length == 0);
                    int[] codes = [first.ExitCode, second.ExitCode];
                    Array.Sort(codes);
                    Assert(codes.SequenceEqual(conflict ? new[] { 0, 2 } : new[] { 0, 0 }));
                    Assert(Store.Snapshot(b.Folder).LastSequence == 1);
                    if (!conflict)
                    {
                        using var a = JsonDocument.Parse(one);
                        using var z = JsonDocument.Parse(two);
                        Assert(a.RootElement.GetProperty("receipt").GetString() == z.RootElement.GetProperty("receipt").GetString());
                    }
                }
                finally
                {
                    KillOwned(first);
                    KillOwned(second);
                }
            });
    }
}
