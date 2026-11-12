// HalOS-Setup.exe: install HalOS from Windows as easily as a browser. Five screens: welcome, checks, choice,
// download, ready. The disk work is done by the tested PowerShell scripts embedded in this EXE
// (prepare_disk_boot.ps1, restart_into_halos.ps1); this program only asks, downloads, verifies and runs them.
//
//   HalOS-Setup.exe               the wizard
//   HalOS-Setup.exe --dry-run     the wizard, but every disk step runs with -WhatIf and nothing restarts
//   HalOS-Setup.exe --self-test   print this PC's checks as JSON and exit (reads only)
//   HalOS-Setup.exe --plan <alongside|try|replace> <installGB> <iso>   print the commands it would run, and exit
//
// Built with the C# 5 compiler in .NET Framework 4 (every Windows 10/11 has it): see build_setup.ps1.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace HalOS.Setup
{
    public static class Config
    {
        public const string IsoUrl = "https://github.com/uberdiz/Halo/releases/latest/download/Halo-x86_64.iso";
        public const string SumsUrl = "https://github.com/uberdiz/Halo/releases/latest/download/SHA256SUMS";
        public const string IsoName = "Halo-x86_64.iso";   // the name build_iso.sh gives it
        public const int LiveGB = 6;            // HALOLIVE: the live system and installer
        public const int MinInstallGB = 30;
        public const int DefaultInstallGB = 100;
        public const long MinRamMB = 4000;
        public static string WorkDir
        {
            get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "HalOS-Setup"); }
        }
    }

    // ------------------------------------------------------------------ checks (read only, no admin needed)
    public class Check
    {
        public string Name; public bool Ok; public bool Blocking; public string Text;
        public Check(string name, bool ok, bool blocking, string text) { Name = name; Ok = ok; Blocking = blocking; Text = text; }
    }

    public static class Checks
    {
        [DllImport("kernel32.dll")] static extern bool GetFirmwareType(out uint type);   // 1 BIOS, 2 UEFI

        [StructLayout(LayoutKind.Sequential)]
        class MEMORYSTATUSEX
        {
            public uint dwLength = (uint)Marshal.SizeOf(typeof(MEMORYSTATUSEX));
            public uint dwMemoryLoad; public ulong ullTotalPhys, ullAvailPhys, ullTotalPageFile, ullAvailPageFile,
                ullTotalVirtual, ullAvailVirtual, ullAvailExtendedVirtual;
        }
        [DllImport("kernel32.dll")] static extern bool GlobalMemoryStatusEx([In, Out] MEMORYSTATUSEX m);

        public static bool Uefi()
        {
            uint t;
            try { return GetFirmwareType(out t) && t == 2; } catch { return false; }
        }

        public static int SecureBoot()   // 1 on, 0 off, -1 unknown
        {
            try
            {
                object v = Microsoft.Win32.Registry.GetValue(
                    @"HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\SecureBoot\State", "UEFISecureBootEnabled", null);
                return v == null ? -1 : ((int)v == 1 ? 1 : 0);
            }
            catch { return -1; }
        }

        public static string BitLocker()  // "on", "off" or "unknown"; Explorer's own property, no admin needed
        {
            string o = Ps.Capture("$p=(New-Object -ComObject Shell.Application).NameSpace('C:').Self.ExtendedProperty('System.Volume.BitLockerProtection'); \"$p\"");
            o = o.Trim();
            if (o == "1" || o == "3" || o == "5") return "on";
            if (o == "2" || o == "4" || o == "6" || o == "0" || o == "") return "off";
            return "unknown";
        }

        public static long FreeGB()
        {
            try { return new DriveInfo("C").AvailableFreeSpace / (1L << 30); } catch { return 0; }
        }

        public static long RamMB()
        {
            var m = new MEMORYSTATUSEX();
            return GlobalMemoryStatusEx(m) ? (long)(m.ullTotalPhys / (1UL << 20)) : 0;
        }

        public static bool Online()
        {
            try
            {
                var r = (HttpWebRequest)WebRequest.Create("https://github.com");
                r.Method = "HEAD"; r.Timeout = 5000;
                using (r.GetResponse()) { return true; }
            }
            catch { return false; }
        }

        public static List<Check> All()
        {
            var list = new List<Check>();
            bool uefi = Uefi();
            list.Add(new Check("uefi", uefi, true, uefi ? "This PC starts in UEFI mode."
                : "This PC starts in legacy BIOS mode. HalOS needs UEFI: switch it on in the firmware settings, or install from a USB stick."));
            int sb = SecureBoot();
            list.Add(new Check("secureboot", true, false, sb == 1 ? "Secure Boot is on. It can stay on: you'll approve HalOS's key once on the first start."
                : sb == 0 ? "Secure Boot is off. That's fine." : "Couldn't tell whether Secure Boot is on. Either way works."));
            string bl = BitLocker();
            list.Add(new Check("bitlocker", bl != "on", true, bl == "on"
                ? "BitLocker is protecting C:. Setup will ask Windows to pause it for the next restarts (keep your recovery key handy)."
                : "C: isn't locked by BitLocker."));
            long free = FreeGB();
            long need = Config.LiveGB + Config.MinInstallGB + 10;
            list.Add(new Check("space", free >= need, true, free >= need
                ? string.Format("{0} GB free on C:. HalOS needs at least {1} GB.", free, need)
                : string.Format("Only {0} GB free on C:. HalOS needs at least {1} GB: free some space and run Setup again.", free, need)));
            long ram = RamMB();
            list.Add(new Check("ram", ram >= Config.MinRamMB, true, ram >= Config.MinRamMB
                ? string.Format("{0:0.#} GB of memory.", ram / 1024.0)
                : string.Format("{0:0.#} GB of memory. HalOS needs 4 GB.", ram / 1024.0)));
            bool online = Online();
            list.Add(new Check("internet", true, false, online ? "Connected to the internet."
                : "No internet connection. You can still use an ISO you've already downloaded."));
            return list;
        }

        // BitLocker isn't a hard stop: Setup suspends it (with consent). So "blocking" means: can't continue at all.
        public static bool CanContinue(List<Check> checks)
        {
            foreach (var c in checks) if (c.Blocking && !c.Ok && c.Name != "bitlocker") return false;
            return true;
        }

        public static string Json(List<Check> checks)
        {
            var sb = new StringBuilder("{\"checks\":[");
            for (int i = 0; i < checks.Count; i++)
            {
                var c = checks[i];
                sb.AppendFormat("{0}{{\"name\":\"{1}\",\"ok\":{2},\"blocking\":{3},\"text\":\"{4}\"}}", i > 0 ? "," : "",
                    c.Name, c.Ok ? "true" : "false", c.Blocking ? "true" : "false", c.Text.Replace("\\", "\\\\").Replace("\"", "\\\""));
            }
            sb.AppendFormat("],\"can_continue\":{0}}}", CanContinue(checks) ? "true" : "false");
            return sb.ToString();
        }
    }

    // ------------------------------------------------------------------ what gets run
    public static class Plan
    {
        // mode: "alongside" (HALOLIVE + installGB free for HalOS), "try" (HALOLIVE only), "replace" (HALOLIVE only:
        // Windows is replaced from inside the installer, which asks again before it erases anything).
        public static List<string[]> Commands(string mode, int installGB, string iso, string scriptsDir, bool dryRun)
        {
            if (mode != "alongside" && mode != "try" && mode != "replace") throw new ArgumentException("mode");
            int gb = mode == "alongside" ? Math.Max(Config.MinInstallGB, installGB) : 0;
            var prepare = new List<string> { "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                Path.Combine(scriptsDir, "prepare_disk_boot.ps1"), "-Iso", iso,
                "-LiveGB", Config.LiveGB.ToString(), "-InstallGB", gb.ToString() };
            var restart = new List<string> { "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                Path.Combine(scriptsDir, "restart_into_halos.ps1"), "-Live" };
            if (dryRun) { prepare.Add("-WhatIf"); restart.Add("-NoRestart"); }
            var cmds = new List<string[]> { prepare.ToArray() };
            if (!dryRun) cmds.Add(restart.ToArray());
            return cmds;
        }

        public static string Confirmation(string mode)
        {
            return mode == "replace" ? "REPLACE" : "INSTALL";
        }
    }

    // ------------------------------------------------------------------ PowerShell
    public static class Ps
    {
        public static string Capture(string command)
        {
            try
            {
                var psi = new ProcessStartInfo("powershell.exe", "-NoProfile -NonInteractive -Command \"" + command.Replace("\"", "\\\"") + "\"");
                psi.UseShellExecute = false; psi.RedirectStandardOutput = true; psi.CreateNoWindow = true;
                using (var p = Process.Start(psi))
                {
                    string o = p.StandardOutput.ReadToEnd();
                    p.WaitForExit(15000);
                    return o;
                }
            }
            catch { return ""; }
        }

        public static string Quote(string a)
        {
            return a.IndexOfAny(new[] { ' ', '\t', '"' }) < 0 && a.Length > 0 ? a : "\"" + a.Replace("\"", "\\\"") + "\"";
        }

        // Runs elevated (one UAC prompt). Output goes to a log file the wizard follows, because an elevated child
        // can't hand its output back directly. Returns the exit code.
        public static int RunElevated(string[] args, string logFile, Action<string> onLine, Func<bool> cancelled)
        {
            var sb = new StringBuilder();
            foreach (var a in args) sb.Append(Quote(a)).Append(' ');
            string inner = string.Format("& {{ Start-Transcript -LiteralPath '{0}' -Force | Out-Null; try {{ & powershell.exe {1}; exit $LASTEXITCODE }} finally {{ Stop-Transcript | Out-Null }} }}",
                logFile.Replace("'", "''"), sb.ToString().Replace("'", "''"));
            var psi = new ProcessStartInfo("powershell.exe", "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command \"" + inner.Replace("\"", "\\\"") + "\"");
            psi.UseShellExecute = true; psi.Verb = "runas"; psi.WindowStyle = ProcessWindowStyle.Hidden;
            Process p;
            try { p = Process.Start(psi); }
            catch (System.ComponentModel.Win32Exception) { onLine("You said no to the administrator prompt, so nothing was changed."); return 1223; }
            long seen = 0;
            while (true)
            {
                bool done = p.WaitForExit(500);
                try
                {
                    if (File.Exists(logFile))
                        using (var fs = new FileStream(logFile, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                        {
                            fs.Seek(seen, SeekOrigin.Begin);
                            using (var r = new StreamReader(fs))
                            {
                                string line;
                                while ((line = r.ReadLine()) != null) onLine(line);
                                seen = fs.Position;
                            }
                        }
                }
                catch (IOException) { }
                if (done) return p.ExitCode;
            }
        }
    }

    // ------------------------------------------------------------------ download with resume and checksum
    public static class Download
    {
        public delegate void Progress(long done, long total, double bytesPerSec);

        public static void Fetch(string url, string dest, Progress progress, Func<bool> cancelled)
        {
            string part = dest + ".part";
            for (int attempt = 1; ; attempt++)
            {
                try { FetchOnce(url, part, progress, cancelled); break; }
                catch (WebException) { if (attempt >= 5 || cancelled()) throw; Thread.Sleep(2000 * attempt); }
                catch (IOException) { if (attempt >= 5 || cancelled()) throw; Thread.Sleep(2000 * attempt); }
            }
            if (File.Exists(dest)) File.Delete(dest);
            File.Move(part, dest);
        }

        static void FetchOnce(string url, string part, Progress progress, Func<bool> cancelled)
        {
            long have = File.Exists(part) ? new FileInfo(part).Length : 0;
            var req = (HttpWebRequest)WebRequest.Create(url);
            req.UserAgent = "HalOS-Setup";
            req.Timeout = 30000; req.ReadWriteTimeout = 60000;
            if (have > 0) req.AddRange(have);
            using (var resp = (HttpWebResponse)req.GetResponse())
            {
                if (have > 0 && resp.StatusCode != HttpStatusCode.PartialContent) have = 0;   // server ignored the range
                long total = resp.ContentLength > 0 ? resp.ContentLength + have : -1;
                using (var input = resp.GetResponseStream())
                using (var output = new FileStream(part, have > 0 ? FileMode.Append : FileMode.Create, FileAccess.Write))
                {
                    var buf = new byte[1 << 20];
                    var clock = Stopwatch.StartNew();
                    long since = have; int n;
                    while ((n = input.Read(buf, 0, buf.Length)) > 0)
                    {
                        if (cancelled()) throw new OperationCanceledException();
                        output.Write(buf, 0, n);
                        have += n;
                        if (clock.ElapsedMilliseconds >= 500)
                        {
                            progress(have, total, (have - since) / clock.Elapsed.TotalSeconds);
                            since = have; clock.Restart();
                        }
                    }
                    progress(have, total, 0);
                }
            }
        }

        public static string Sha256(string file)
        {
            using (var s = File.OpenRead(file))
            using (var h = SHA256.Create())
                return BitConverter.ToString(h.ComputeHash(s)).Replace("-", "").ToLowerInvariant();
        }

        // SHA256SUMS lines: "<hash>  <name>" (or "<hash> *<name>")
        public static string ExpectedHash(string sums, string name)
        {
            foreach (var raw in sums.Split('\n'))
            {
                var line = raw.Trim();
                int sp = line.IndexOf(' ');
                if (sp == 64 && line.Substring(sp).Trim().TrimStart('*') == name) return line.Substring(0, 64).ToLowerInvariant();
            }
            return null;
        }
    }

    // ------------------------------------------------------------------ the wizard
    public class Wizard : Form
    {
        readonly bool dryRun;
        readonly Panel body = new Panel();
        readonly Label title = new Label(), step = new Label();
        readonly Button back = new Button(), next = new Button();
        int page;
        List<Check> checks;
        string mode = "alongside";
        int installGB = Config.DefaultInstallGB;
        string iso;
        bool busy, cancel;
        readonly StringBuilder log = new StringBuilder();
        static readonly Color Accent = Color.FromArgb(0xFE, 0xAA, 0x34), Bg = Color.FromArgb(0x12, 0x13, 0x16),
            Fg = Color.FromArgb(0xEC, 0xEC, 0xEE), Muted = Color.FromArgb(0x9A, 0x9C, 0xA3), Good = Color.FromArgb(0x5C, 0xD6, 0x8A),
            Bad = Color.FromArgb(0xF0, 0x5D, 0x5D);

        public Wizard(bool dryRun)
        {
            this.dryRun = dryRun;
            Text = dryRun ? "HalOS Setup (dry run: nothing will change)" : "HalOS Setup";
            ClientSize = new Size(720, 500); FormBorderStyle = FormBorderStyle.FixedSingle; MaximizeBox = false;
            StartPosition = FormStartPosition.CenterScreen; BackColor = Bg; ForeColor = Fg;
            Font = new Font("Segoe UI", 10f);
            step.SetBounds(32, 22, 600, 20); step.ForeColor = Muted; step.Font = new Font("Segoe UI", 8.5f, FontStyle.Bold);
            title.SetBounds(32, 44, 660, 40); title.Font = new Font("Segoe UI Semibold", 18f);
            body.SetBounds(32, 96, 656, 330);
            Style(back, false); back.Text = "Back"; back.SetBounds(32, 444, 110, 36); back.Click += delegate { Go(page - 1); };
            Style(next, true); next.SetBounds(578, 444, 110, 36); next.Click += delegate { Next(); };
            Controls.AddRange(new Control[] { step, title, body, back, next });
            FormClosing += (s, e) => { if (busy && MessageBox.Show(this, "Setup is still working. Stop it?", "HalOS Setup", MessageBoxButtons.YesNo) == DialogResult.No) e.Cancel = true; else cancel = true; };
            Go(0);
        }

        static void Style(Button b, bool primary)
        {
            b.FlatStyle = FlatStyle.Flat; b.FlatAppearance.BorderSize = primary ? 0 : 1;
            b.FlatAppearance.BorderColor = Color.FromArgb(0x3A, 0x3C, 0x42);
            b.BackColor = primary ? Accent : Color.FromArgb(0x1E, 0x20, 0x24);
            b.ForeColor = primary ? Color.Black : Fg; b.Cursor = Cursors.Hand;
        }

        Label Text_(string text, int y, int h, Color c)
        {
            var l = new Label(); l.Text = text; l.ForeColor = c; l.SetBounds(0, y, 656, h); body.Controls.Add(l); return l;
        }

        void Go(int p)
        {
            if (busy || p < 0) return;
            page = p; body.Controls.Clear(); next.Enabled = true; back.Enabled = p > 0 && p < 4; next.Text = "Next";
            step.Text = string.Format("STEP {0} OF 5", p + 1);
            if (p == 0) PageWelcome(); else if (p == 1) PageChecks(); else if (p == 2) PageChoice(); else if (p == 3) PageDownload(); else PageReady();
        }

        public void Show(int p) { Go(p); }      // --screenshot

        void Next()
        {
            if (page == 3 && iso == null) { StartDownload(); return; }
            if (page == 4) { Install(); return; }
            Go(page + 1);
        }

        void PageWelcome()
        {
            title.Text = "Welcome to HalOS";
            Text_("HalOS is a free operating system with an AI assistant, SAINT, built in. Setup puts it on this PC next to Windows: " +
                  "Windows, your files and your apps stay where they are, and you choose which system to start.", 0, 70, Fg);
            Text_("What happens: Setup checks this PC, downloads HalOS (about 2.5 GB), makes room for it on C:, and restarts into the " +
                  "HalOS installer. There you pick a password, and that's it. Nothing is changed until you confirm on the last screen.", 80, 90, Muted);
            if (dryRun) Text_("Dry run: the disk step only shows its plan, and the PC doesn't restart.", 180, 30, Accent);
        }

        void PageChecks()
        {
            title.Text = "Checking this PC";
            next.Enabled = false;
            Text_("Checking…", 0, 24, Muted);
            ThreadPool.QueueUserWorkItem(delegate
            {
                var found = Checks.All();
                BeginInvoke((Action)delegate
                {
                    if (page != 1) return;
                    checks = found; body.Controls.Clear();
                    int y = 0;
                    foreach (var c in found)
                    {
                        Text_((c.Ok ? "✓  " : (c.Blocking ? "✕  " : "!  ")) + c.Text, y, 44, c.Ok ? Good : (c.Blocking ? Bad : Accent));
                        y += 48;
                    }
                    bool ok = Checks.CanContinue(found);
                    next.Enabled = ok;
                    if (!ok) Text_("Fix the item marked ✕, then run Setup again.", y + 4, 24, Bad);
                });
            });
        }

        void PageChoice()
        {
            title.Text = "How do you want HalOS?";
            long free = Checks.FreeGB();
            int max = (int)Math.Max(Config.MinInstallGB, Math.Min(free - Config.LiveGB - 10, 1024));
            installGB = Math.Min(Math.Max(installGB, Config.MinInstallGB), max);
            var alongside = new RadioButton(); alongside.Text = "Install alongside Windows (recommended)"; alongside.SetBounds(0, 0, 600, 28);
            var size = new TrackBar(); size.SetBounds(24, 30, 460, 40); size.Minimum = Config.MinInstallGB; size.Maximum = max;
            size.TickFrequency = Math.Max(1, (max - Config.MinInstallGB) / 10); size.Value = installGB;
            var sizeText = new Label(); sizeText.SetBounds(496, 34, 160, 24); sizeText.ForeColor = Muted;
            var tryIt = new RadioButton(); tryIt.Text = "Just try it (nothing installed; HalOS runs from a small partition)"; tryIt.SetBounds(0, 90, 640, 28);
            var replace = new RadioButton(); replace.Text = "Replace Windows (everything on this disk is erased)"; replace.SetBounds(0, 128, 640, 28);
            var note = new Label(); note.SetBounds(24, 160, 630, 90); note.ForeColor = Muted;
            Action sync = delegate
            {
                mode = alongside.Checked ? "alongside" : tryIt.Checked ? "try" : "replace";
                installGB = size.Value; size.Enabled = alongside.Checked;
                sizeText.Text = string.Format("{0} GB for HalOS", installGB);
                note.Text = mode == "alongside" ? string.Format("C: shrinks by {0} GB. Windows keeps {1} GB free.", installGB + Config.LiveGB, Math.Max(0, free - installGB - Config.LiveGB))
                    : mode == "try" ? "Only a 6 GB partition is made. You can install from inside HalOS later, or remove it in Disk Management."
                    : "Setup prepares the installer the same way; in the installer you choose \"Replace Windows\", and it asks you again before it erases anything. Copy anything you want to keep first, or use \"Bring everything\" in HalOS afterwards from a backup.";
                note.ForeColor = mode == "replace" ? Bad : Muted;
            };
            alongside.Checked = mode == "alongside"; tryIt.Checked = mode == "try"; replace.Checked = mode == "replace";
            alongside.CheckedChanged += delegate { sync(); }; tryIt.CheckedChanged += delegate { sync(); };
            replace.CheckedChanged += delegate { sync(); }; size.ValueChanged += delegate { sync(); };
            body.Controls.AddRange(new Control[] { alongside, size, sizeText, tryIt, replace, note });
            sync();
        }

        Label status;
        ProgressBar bar;

        void PageDownload()
        {
            title.Text = "Getting HalOS";
            next.Text = iso == null ? "Download" : "Next";
            Text_(iso == null ? "Setup downloads HalOS (about 2.5 GB) and checks it. If the download stops, it carries on from where it was."
                : "HalOS is downloaded and checked.", 0, 50, Muted);
            bar = new ProgressBar(); bar.SetBounds(0, 70, 656, 18); body.Controls.Add(bar);
            status = Text_(iso ?? "", 96, 44, Fg);
            var pick = new LinkLabel(); pick.Text = "Use a HalOS ISO I already have…"; pick.SetBounds(0, 160, 400, 24); pick.LinkColor = Accent;
            pick.Click += delegate
            {
                using (var d = new OpenFileDialog())
                {
                    d.Filter = "HalOS ISO (*.iso)|*.iso";
                    if (d.ShowDialog(this) == DialogResult.OK) { iso = d.FileName; status.Text = "Using " + iso; next.Text = "Next"; }
                }
            };
            body.Controls.Add(pick);
        }

        void StartDownload()
        {
            busy = true; next.Enabled = false; back.Enabled = false; cancel = false;
            Directory.CreateDirectory(Config.WorkDir);
            string dest = Path.Combine(Config.WorkDir, Config.IsoName), sums = Path.Combine(Config.WorkDir, "SHA256SUMS");
            ThreadPool.QueueUserWorkItem(delegate
            {
                string error = null;
                try
                {
                    Ui(delegate { status.Text = "Getting the checksum list…"; });
                    using (var wc = new WebClient()) { wc.Headers.Add("User-Agent", "HalOS-Setup"); wc.DownloadFile(Config.SumsUrl, sums); }
                    string want = Download.ExpectedHash(File.ReadAllText(sums), Config.IsoName);
                    if (want == null) throw new InvalidDataException("The release's checksum list doesn't mention " + Config.IsoName + ".");
                    if (!(File.Exists(dest) && Download.Sha256(dest) == want))
                    {
                        Download.Fetch(Config.IsoUrl, dest, (done, total, speed) => Ui(delegate
                        {
                            if (total > 0) { bar.Value = (int)Math.Min(100, done * 100 / total); }
                            string left = speed > 0 && total > 0 ? string.Format(", about {0} left", Eta((total - done) / speed)) : "";
                            status.Text = string.Format("{0:0.00} of {1:0.00} GB, {2:0.0} MB/s{3}", done / 1e9, total / 1e9, speed / 1e6, left);
                        }), () => cancel);
                        Ui(delegate { status.Text = "Checking the download…"; });
                        string got = Download.Sha256(dest);
                        if (got != want) { File.Delete(dest); throw new InvalidDataException("The download was damaged (its checksum doesn't match). Press Retry to download it again."); }
                    }
                    iso = dest;
                }
                catch (OperationCanceledException) { error = "Stopped."; }
                catch (WebException e) { error = "The download didn't finish: " + e.Message + " Check the connection and press Retry; it carries on from where it stopped."; }
                catch (Exception e) { error = e.Message; }
                Ui(delegate
                {
                    busy = false; back.Enabled = true; next.Enabled = true;
                    if (error == null) { bar.Value = 100; status.Text = "Downloaded and checked: " + iso; next.Text = "Next"; }
                    else { Fail(error); next.Text = "Retry"; }
                });
            });
        }

        static string Eta(double seconds)
        {
            if (seconds > 5400) return string.Format("{0:0.#} hours", seconds / 3600);
            if (seconds > 90) return string.Format("{0:0} minutes", seconds / 60);
            return string.Format("{0:0} seconds", seconds);
        }

        TextBox typed;
        TextBox output;

        void PageReady()
        {
            title.Text = dryRun ? "Ready (dry run)" : "Ready to make room for HalOS";
            next.Text = dryRun ? "Show plan" : "Install";
            string word = Plan.Confirmation(mode);
            Text_(mode == "alongside" ? string.Format("Setup will shrink C: by {0} GB, put the HalOS installer on a small partition, and restart into it. Windows stays the default system.", installGB + Config.LiveGB)
                : mode == "try" ? "Setup will shrink C: by 6 GB, put HalOS on a small partition, and restart into it."
                : "Setup will put the HalOS installer on a small partition and restart into it. Choose \"Replace Windows\" there.", 0, 50, Fg);
            Text_(string.Format("Type {0} to confirm:", word), 56, 24, Muted);
            typed = new TextBox(); typed.SetBounds(0, 82, 200, 28); typed.BackColor = Color.FromArgb(0x1E, 0x20, 0x24); typed.ForeColor = Fg;
            typed.TextChanged += delegate { next.Enabled = dryRun || typed.Text.Trim() == word; };
            output = new TextBox(); output.Multiline = true; output.ReadOnly = true; output.ScrollBars = ScrollBars.Vertical;
            output.SetBounds(0, 120, 656, 170); output.BackColor = Color.FromArgb(0x0C, 0x0D, 0x0F); output.ForeColor = Muted;
            output.Font = new Font("Consolas", 8.5f);
            body.Controls.AddRange(new Control[] { typed, output });
            next.Enabled = dryRun;
        }

        void Install()
        {
            busy = true; next.Enabled = false; back.Enabled = false; typed.Enabled = false; log.Clear();
            string scripts = Path.Combine(Config.WorkDir, "scripts");
            ThreadPool.QueueUserWorkItem(delegate
            {
                string error = null;
                try
                {
                    Directory.CreateDirectory(scripts);
                    foreach (var name in new[] { "prepare_disk_boot.ps1", "restart_into_halos.ps1" })
                        using (var res = typeof(Wizard).Assembly.GetManifestResourceStream(name))
                        using (var f = File.Create(Path.Combine(scripts, name))) res.CopyTo(f);
                    if (!dryRun && Checks.BitLocker() == "on")
                    {
                        Line("Pausing BitLocker on C: for the next 3 restarts…");
                        int rc = Ps.RunElevated(new[] { "-NoProfile", "-Command", "Suspend-BitLocker -MountPoint C: -RebootCount 3" },
                            Path.Combine(Config.WorkDir, "bitlocker.log"), Line, () => cancel);
                        if (rc != 0) throw new Exception("BitLocker couldn't be paused, so nothing was changed.");
                    }
                    int i = 0;
                    foreach (var cmd in Plan.Commands(mode, installGB, iso, scripts, dryRun))
                    {
                        string logFile = Path.Combine(Config.WorkDir, string.Format("step{0}.log", ++i));
                        int rc = Ps.RunElevated(cmd, logFile, Line, () => cancel);
                        if (rc != 0) throw new Exception(Plain(log.ToString(), rc));
                    }
                }
                catch (Exception e) { error = e.Message; }
                Ui(delegate
                {
                    busy = false;
                    if (error != null) { Fail(error); next.Text = "Retry"; next.Enabled = true; back.Enabled = true; typed.Enabled = true; }
                    else if (dryRun) { Line("Dry run finished: nothing was changed."); next.Enabled = false; }
                    else Line("Restarting into HalOS…");
                });
            });
        }

        // A script's own error ("BitLocker protection is ON…", "C: can only shrink by…") is already plain words.
        static string Plain(string text, int rc)
        {
            foreach (var raw in text.Split('\n'))
            {
                var l = raw.Trim();
                if (l.StartsWith("Exception:") || l.Contains("Expected one HALOLIVE") || l.Contains("can only shrink") || l.Contains("BitLocker protection is ON")
                    || l.Contains("already exists") || l.Contains("checksum mismatch") || l.Contains("No firmware boot entry"))
                    return l.Replace("Exception:", "").Trim();
            }
            return rc == 1223 ? "You said no to the administrator prompt, so nothing was changed."
                : string.Format("The disk step stopped (code {0}). Nothing after that point was done. Press Copy log if you report this.", rc);
        }

        void Line(string text)
        {
            log.AppendLine(text);
            Ui(delegate { if (output != null && !output.IsDisposed) output.AppendText(text + Environment.NewLine); });
        }

        void Fail(string reason)
        {
            var d = new Form(); d.Text = "HalOS Setup"; d.ClientSize = new Size(520, 180); d.FormBorderStyle = FormBorderStyle.FixedDialog;
            d.StartPosition = FormStartPosition.CenterParent; d.BackColor = Bg; d.ForeColor = Fg; d.Font = Font;
            var l = new Label(); l.Text = reason; l.SetBounds(20, 20, 480, 100); d.Controls.Add(l);
            var copy = new Button(); copy.Text = "Copy log"; copy.SetBounds(20, 130, 110, 34); Style(copy, false);
            copy.Click += delegate { Clipboard.SetText(reason + Environment.NewLine + Environment.NewLine + log); };
            var close = new Button(); close.Text = "OK"; close.SetBounds(390, 130, 110, 34); Style(close, true); close.Click += delegate { d.Close(); };
            d.Controls.AddRange(new Control[] { copy, close });
            d.ShowDialog(this);
        }

        void Ui(Action a)
        {
            if (IsDisposed) return;
            try { BeginInvoke(a); } catch (InvalidOperationException) { }
        }
    }

    public static class Program
    {
        [STAThread]
        public static int Main(string[] args)
        {
            ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;
            var a = new List<string>(args);
            if (a.Contains("--self-test")) { Console.WriteLine(Checks.Json(Checks.All())); return 0; }
            int plan = a.IndexOf("--plan");
            if (plan >= 0 && a.Count >= plan + 4)
            {
                foreach (var cmd in Plan.Commands(a[plan + 1], int.Parse(a[plan + 2]), a[plan + 3], Path.Combine(Config.WorkDir, "scripts"), a.Contains("--dry-run")))
                    Console.WriteLine("powershell.exe " + string.Join(" ", cmd));
                return 0;
            }
            Application.EnableVisualStyles();
            int shot = a.IndexOf("--screenshot");          // docs only: draws pages 1, 3 and 5 to PNGs, runs nothing
            if (shot >= 0 && a.Count > shot + 1)
            {
                var w = new Wizard(true);
                w.StartPosition = FormStartPosition.Manual; w.Location = new Point(-4000, -4000); w.ShowInTaskbar = false;
                w.Show();                                  // off screen: children only paint once the form is shown
                foreach (var p in new[] { 0, 2, 4 })
                {
                    w.Show(p);
                    Application.DoEvents();
                    using (var bmp = new Bitmap(w.Width, w.Height))
                    {
                        w.DrawToBitmap(bmp, new Rectangle(Point.Empty, w.Size));
                        bmp.Save(Path.Combine(a[shot + 1], string.Format("setup-step{0}.png", p + 1)));
                    }
                }
                return 0;
            }
            Application.Run(new Wizard(a.Contains("--dry-run")));
            return 0;
        }
    }
}
