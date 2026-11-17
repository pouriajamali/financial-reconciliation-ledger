# v0.1.0-preview.3 — .NET 11 maintenance

The synthetic ledger now uses SDK 11.0.100, net11.0, stable C# 15 and the
self-contained 11.0.0 runtime. No AOT, trimming or ReadyToRun is enabled.
Microsoft.Data.Sqlite/Core 10.0.15 and SQLitePCLRaw 2.1.13 keep the same exact
package versions and content hashes. Actual SDK-generated portable and RID
locks replace the old TFM locks. NuGet repository signatures are required and
vulnerability auditing remains enabled.

Local original suites: Windows 143 passed / 0 failed / 2 explicit skips;
Ubuntu 24.04 on WSL2 145 passed / 0 failed / 0 skipped, runtime 11.0.0.
The Windows skips are Linux-only FIFO and unavailable local symlink privilege.
Each matching-OS native archive must pass the original 22 extracted checks and
14 bidirectional preview.2 compatibility cases. VALIDATION.json and native
BUILD-MANIFEST.json identify the actual tested source/artifacts and boundaries.
Execution is serial with CPU2/2GiB and actual Windows Job/Linux cgroup limits.
GitHub Actions CI was not run, by direct owner instruction; local package/signing
checks and direct publication replace that delivery mechanism.

Saved canonical receipts, schemas, integer amounts, snapshot/statement hashes,
discrepancy order/nulls/counts/overlap, exit codes and quiescent no-post behavior
retain the prior contract. The compatibility comparison permits only named outer
version/build metadata and its directly bound summary digest to differ.

Windows was tested on 26H2 build 26300.9974. Microsoft's current .NET 11 OS table
does not list 26H2; vendor support remains unconfirmed. Linux evidence is from an
existing Ubuntu 24.04 WSL2 installation. x64 execution requires x86-64-v2 and
existing native OS prerequisites. No clean-machine, production, real-money,
power-loss durability, performance or security certification is claimed.

Windows ZIP, Linux tar.gz, exact source ZIP, VALIDATION.json, SHA256SUMS.txt,
its SSH signature and the public signing key belong to the same versioned release.
Verify the [known-key provenance](../PROVENANCE.md) before extraction/execution.
Old tags/assets/signatures and all MIT/upstream attribution remain unchanged.
