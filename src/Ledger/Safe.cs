using System.Runtime.InteropServices;
using System.Buffers.Binary;
using System.Text;

namespace ReconciliationLedger;

internal static class Safe
{
    // Adapted from the author's public MIT Release Doctor statx/path guard.
    [StructLayout(LayoutKind.Explicit, Size = 256)]
    private struct Statx { [FieldOffset(0)] public uint Mask; [FieldOffset(28)] public ushort Mode; }
    [DllImport("libc", EntryPoint = "statx", SetLastError = true)]
    private static extern int LinuxStatx(int dirfd, [MarshalAs(UnmanagedType.LPUTF8Str)] string path, int flags, uint mask, out Statx result);
    public static void Regular(string path)
    {
        NoLinks(path);
        if ((File.GetAttributes(path) & (FileAttributes.Directory | FileAttributes.Device | FileAttributes.ReparsePoint)) != 0) throw new Problem("REGULAR_FILE_REQUIRED");
        if (OperatingSystem.IsLinux() && (LinuxStatx(-100, path, 0x100, 1, out var s) != 0 || (s.Mask & 1) == 0 || (s.Mode & 0xf000) != 0x8000)) throw new Problem("REGULAR_FILE_REQUIRED");
    }
    public static void NoLinks(string path)
    {
        string? p = Path.GetFullPath(path);
        while (p != null)
        {
            FileSystemInfo f = Directory.Exists(p) ? new DirectoryInfo(p) : new FileInfo(p);
            if (f.LinkTarget != null || f.Exists && (f.Attributes & FileAttributes.ReparsePoint) != 0) throw new Problem("LINK_UNSUPPORTED");
            p = Path.GetDirectoryName(p);
        }
    }
    public static string Normalize(string path)
    {
        if (string.IsNullOrEmpty(path) || path.Any(c => char.IsControl(c) || c is '\u2028' or '\u2029' or '\ufeff') || path.StartsWith("//") || path.StartsWith(@"\\") || !OperatingSystem.IsWindows() && path.Contains('\\')) throw new Problem("PATH_UNSUPPORTED");
        string full = Path.TrimEndingDirectorySeparator(Path.GetFullPath(path));
        if (full.StartsWith(@"\\") || full.Length > 384) throw new Problem("PATH_UNSUPPORTED");
        if (OperatingSystem.IsWindows() && new DriveInfo(Path.GetPathRoot(full)!).DriveType == DriveType.Network) throw new Problem("NETWORK_PATH_UNSUPPORTED");
        NoLinks(full); return full;
    }
    public static bool Nested(string a, string b)
    {
        var comparison = OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
        string prefix = Path.EndsInDirectorySeparator(b) ? b : b + Path.DirectorySeparatorChar;
        return a.Equals(b, comparison) || a.StartsWith(prefix, comparison);
    }
    public static void Separate(string output, string input)
    {
        if (Nested(output, input) || Nested(input, output)) throw new Problem("OUTPUT_OVERLAPS_INPUT");
    }
    public static void Fresh(string path, string nonce)
    {
        Contract.Nonce(nonce); NoLinks(path);
        if (File.Exists(path) || Directory.Exists(path)) throw new Problem("OUTPUT_EXISTS");
        Directory.CreateDirectory(path); NoLinks(path);
        using var f = new FileStream(Path.Combine(path, ".ledger-owned"), FileMode.CreateNew, FileAccess.Write); f.Write(Encoding.ASCII.GetBytes(nonce));
    }
    public static string Owned(string path)
    {
        path = Normalize(path); string marker = Path.Combine(path, ".ledger-owned");
        byte[] bytes = Read(marker, 32); if (bytes.Length != 32) throw new Problem("OWNERSHIP_INVALID");
        return Contract.Nonce(Encoding.ASCII.GetString(bytes));
    }
    public static byte[] Read(string path, int cap = Contract.InputLimit)
    {
        path = Normalize(path); Regular(path); var before = new FileInfo(path); long length = before.Length, ticks = before.LastWriteTimeUtc.Ticks;
        if (length > cap) throw new Problem("INPUT_BYTE_LIMIT");
        using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read); using var memory = new MemoryStream(); byte[] b = new byte[8192]; int n;
        while ((n = stream.Read(b)) > 0) { if (memory.Length + n > cap) throw new Problem("INPUT_BYTE_LIMIT"); memory.Write(b, 0, n); }
        var after = new FileInfo(path); Regular(path);
        if (memory.Length != length || after.Length != length || after.LastWriteTimeUtc.Ticks != ticks) throw new Problem("INPUT_CHANGED");
        return memory.ToArray();
    }
    public static void BookFiles(string folder)
    {
        NoLinks(folder); int count = 0; long sidecars = 0;
        foreach (string path in Directory.EnumerateFileSystemEntries(folder))
        {
            if (++count > 5) throw new Problem("BOOK_FILE_LIMIT"); Regular(path); string name = Path.GetFileName(path); long size = new FileInfo(path).Length;
            if (name == ".ledger-owned") { if (size != 32) throw new Problem("OWNERSHIP_INVALID"); }
            else if (name == "book.sqlite") { if (size > 16 * 1024 * 1024) throw new Problem("BOOK_BYTE_LIMIT"); }
            else if (name is "book.sqlite-journal" or "book.sqlite-wal" or "book.sqlite-shm") { if ((sidecars += size) > 32 * 1024 * 1024) throw new Problem("SIDECAR_BYTE_LIMIT"); }
            else throw new Problem("BOOK_FILE_UNEXPECTED");
        }
        Regular(Path.Combine(folder, "book.sqlite"));
    }
    public static void Header(string folder)
    {
        string path = Path.Combine(folder, "book.sqlite"); Regular(path);
        using var f = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        byte[] header = new byte[100]; f.ReadExactly(header);
        if (!header.AsSpan(0, 16).SequenceEqual("SQLite format 3\0"u8) || BinaryPrimitives.ReadInt32BigEndian(header.AsSpan(68, 4)) != Store.ApplicationId || BinaryPrimitives.ReadInt32BigEndian(header.AsSpan(60, 4)) != 1) throw new Problem("BOOK_HEADER_OR_MODE_INVALID");
    }
    public static void WriteNew(string path, byte[] bytes)
    {
        NoLinks(path); using var f = new FileStream(path, FileMode.CreateNew, FileAccess.Write); f.Write(bytes);
    }
}
