// HalOS-Setup.exe: install HalOS from Windows as easily as a browser. Five screens: welcome, checks, choice,
// download, ready. The disk work is done by the tested PowerShell scripts embedded in this EXE
// (prepare_disk_boot.ps1, restart_into_halos.ps1); this program only asks, downloads, verifies and runs them.
//
//   HalOS-Setup.exe               the wizard
//   HalOS-Setup.exe --dry-run     the wizard, but every disk step runs with -WhatIf and nothing restarts
//   HalOS-Setup.exe --self-test   print this PC's checks as JSON and exit (reads only)
//   HalOS-Setup.exe --plan <alongside|try|replace|update> <installGB> <iso>   print the commands it would run, and exit
//   HalOS-Setup.exe --release     print the newest release's ISO part URLs and checksum URL, and exit
//
// Built with the C# 5 compiler in .NET Framework 4 (every Windows 10/11 has it): see build_setup.ps1.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Net;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;

namespace HalOS.Setup
{
    public static class Config
    {
        // Newest first, pre-releases included (releases/latest skips them, and a 2 GB+ ISO is uploaded in parts).
        public const string ReleasesApi = "https://api.github.com/repos/uberdiz/Halo/releases?per_page=5";
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
            // An update reuses HALOLIVE and the old HalOS's partitions: it only needs room for the download (parts + ISO).
            long need = Plan.HasLivePartition() ? 12 : Config.LiveGB + Config.MinInstallGB + 10;
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
        // Windows is replaced from inside the installer, which asks again before it erases anything), "update"
        // (the new build goes on the existing HALOLIVE; C: isn't shrunk; the installer then offers to replace the
        // HalOS already installed, and Windows isn't touched).
        public static List<string[]> Commands(string mode, int installGB, string iso, string scriptsDir, bool dryRun)
        {
            if (mode != "alongside" && mode != "try" && mode != "replace" && mode != "update") throw new ArgumentException("mode");
            int gb = mode == "alongside" ? Math.Max(Config.MinInstallGB, installGB) : 0;
            var prepare = new List<string> { "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                Path.Combine(scriptsDir, "prepare_disk_boot.ps1"), "-Iso", iso,
                "-LiveGB", Config.LiveGB.ToString(), "-InstallGB", gb.ToString() };
            if (mode == "update") prepare.Add("-Refresh");
            var restart = new List<string> { "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                Path.Combine(scriptsDir, "restart_into_halos.ps1"), "-Live" };
            if (dryRun) { prepare.Add("-WhatIf"); restart.Add("-NoRestart"); }
            var cmds = new List<string[]> { prepare.ToArray() };
            if (!dryRun) cmds.Add(restart.ToArray());
            return cmds;
        }

        public static string Confirmation(string mode)
        {
            return mode == "replace" ? "REPLACE" : mode == "update" ? "UPDATE" : "INSTALL";
        }

        // An earlier Setup left a HALOLIVE partition: the new build can go on it, without shrinking C: again.
        public static bool HasLivePartition()
        {
            // The same test prepare_disk_boot.ps1 -Refresh makes: 1-16 GB, after C:, labelled HALOLIVE or typed as an
            // ESP (Setup leaves it as one, and Windows shows no label for an ESP). Windows' own ESP comes before C:.
            return Ps.Capture("$c = Get-Partition -DriveLetter C; [bool](Get-Partition -DiskNumber $c.DiskNumber | Where-Object { " +
                "$_.Offset -gt $c.Offset -and $_.Size -gt 1GB -and $_.Size -lt 16GB -and ($_.GptType -eq '{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}' " +
                "-or (($_ | Get-Volume -ErrorAction SilentlyContinue).FileSystemLabel -eq 'HALOLIVE')) })").Trim() == "True";
        }
    }

    // ------------------------------------------------------------------ the newest release on GitHub
    public static class Release
    {
        // From the releases list (newest first): the first release's ISO, as one file or as its .part1, .part2, ...
        // in order, and its SHA256SUMS. Only that release's own download links count.
        public static void Assets(string json, out List<string> isoParts, out string sumsUrl)
        {
            var tag = Regex.Match(json, "\"tag_name\"\\s*:\\s*\"([^\"]+)\"");
            if (!tag.Success) throw new InvalidDataException("No HalOS release was found on GitHub.");
            string mine = "/releases/download/" + tag.Groups[1].Value + "/";
            string whole = null; sumsUrl = null;
            var parts = new SortedDictionary<int, string>();
            foreach (Match m in Regex.Matches(json, "\"browser_download_url\"\\s*:\\s*\"([^\"]+)\""))
            {
                string u = m.Groups[1].Value;
                if (!u.Contains(mine)) continue;
                string name = u.Substring(u.LastIndexOf('/') + 1);
                int n;
                if (name == Config.IsoName) whole = u;
                else if (name == "SHA256SUMS") sumsUrl = u;
                else if (name.StartsWith(Config.IsoName + ".part") && int.TryParse(name.Substring(Config.IsoName.Length + 5), out n)) parts[n] = u;
            }
            isoParts = new List<string>();
            if (whole != null) isoParts.Add(whole);
            else { int i = 1; foreach (var kv in parts) { if (kv.Key != i++) { isoParts.Clear(); break; } isoParts.Add(kv.Value); } }
            if (isoParts.Count == 0 || sumsUrl == null)
                throw new InvalidDataException("The newest HalOS release (" + tag.Groups[1].Value + ") has no complete ISO or no checksum list.");
        }

        public static void Latest(out List<string> isoParts, out string sumsUrl)
        {
            using (var wc = new WebClient())
            {
                wc.Headers.Add("User-Agent", "HalOS-Setup");
                Assets(wc.DownloadString(Config.ReleasesApi), out isoParts, out sumsUrl);
            }
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
            catch (System.ComponentModel.Win32Exception) { onLine("You said no to the administrator prompt."); return 1223; }
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
        bool? hasLive;          // null until the choice page first asks Windows
        bool choiceShown;
        int installGB = Config.DefaultInstallGB;
        string iso;
        bool busy, cancel;
        readonly StringBuilder log = new StringBuilder();
        static readonly Color Accent = Color.FromArgb(0xFE, 0xAA, 0x34), Bg = Color.FromArgb(0x12, 0x13, 0x16),
            Fg = Color.FromArgb(0xEC, 0xEC, 0xEE), Muted = Color.FromArgb(0x9A, 0x9C, 0xA3), Good = Color.FromArgb(0x5C, 0xD6, 0x8A),
            Bad = Color.FromArgb(0xF0, 0x5D, 0x5D);
        // The welcome screen: soft colour orbs (blue, green, peach) drifting on a light background, like ui/orbs.py.
        static readonly Color Light = Color.FromArgb(0xF7, 0xF8, 0xFB), Ink = Color.FromArgb(0x13, 0x14, 0x17),
            InkMuted = Color.FromArgb(0x5E, 0x62, 0x6B);
        static readonly float[][] Orbs = {          // r, g, b, cx, cy, drift x, drift y, radius, speed, phase
            new float[] { 0x7F, 0xB0, 0xFF, 0.22f, 0.30f, 0.10f, 0.08f, 0.55f, 0.11f, 0.0f },
            new float[] { 0x8F, 0xE0, 0xB4, 0.78f, 0.25f, 0.08f, 0.10f, 0.48f, 0.09f, 2.1f },
            new float[] { 0xFF, 0xC3, 0xA0, 0.60f, 0.82f, 0.12f, 0.07f, 0.52f, 0.13f, 4.2f },
            new float[] { 0xA9, 0xC8, 0xFF, 0.05f, 0.95f, 0.06f, 0.06f, 0.35f, 0.07f, 1.3f } };
        readonly System.Windows.Forms.Timer orbTimer = new System.Windows.Forms.Timer();
        readonly Stopwatch clock = Stopwatch.StartNew();

        protected override CreateParams CreateParams
        {
            get { var cp = base.CreateParams; cp.ExStyle |= 0x02000000; return cp; }   // WS_EX_COMPOSITED: no flicker
        }

        protected override void OnPaintBackground(PaintEventArgs e)
        {
            if (page != 0) { base.OnPaintBackground(e); return; }
            var g = e.Graphics;
            g.Clear(Light);
            g.SmoothingMode = SmoothingMode.AntiAlias;
            // Animation effects off in Windows: one still frame.
            double t = SystemInformation.UIEffectsEnabled ? clock.Elapsed.TotalSeconds : 0;
            float w = ClientSize.Width, h = ClientSize.Height, side = Math.Max(w, h);
            foreach (var o in Orbs)
            {
                float x = (o[3] + o[5] * (float)Math.Sin(t * o[8] + o[9])) * w;
                float y = (o[4] + o[6] * (float)Math.Cos(t * o[8] * 0.8 + o[9])) * h;
                float r = o[7] * side * (1 + 0.06f * (float)Math.Sin(t * o[8] * 1.7 + o[9]));
                using (var path = new GraphicsPath())
                {
                    path.AddEllipse(x - r, y - r, 2 * r, 2 * r);
                    using (var b = new PathGradientBrush(path))
                    {
                        b.CenterColor = Color.FromArgb(150, (int)o[0], (int)o[1], (int)o[2]);
                        b.SurroundColors = new[] { Color.FromArgb(0, (int)o[0], (int)o[1], (int)o[2]) };
                        b.SetSigmaBellShape(1f, 1f);       // a soft, blurred falloff
                        g.FillPath(b, path);
                    }
                }
            }
        }

        public Wizard(bool dryRun)
        {
            this.dryRun = dryRun;
            DoubleBuffered = true;
            orbTimer.Interval = 33;                        // ~30 fps, only while the welcome page is on screen
            orbTimer.Tick += delegate
            {
                if (page == 0 && Visible && WindowState != FormWindowState.Minimized && SystemInformation.UIEffectsEnabled)
                    Invalidate(true);
            };
            orbTimer.Start();
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
            bool welcome = p == 0;                         // light, with the orbs; the other pages stay dark
            step.BackColor = title.BackColor = Color.Transparent;
            body.BackColor = welcome ? Color.Transparent : Bg;
            title.ForeColor = welcome ? Ink : Fg; step.ForeColor = welcome ? InkMuted : Muted;
            back.Visible = !welcome;
            Invalidate(true);
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
                  "Windows, your files and your apps stay where they are, and you choose which system to start.", 0, 70, Ink);
            Text_("What happens: Setup checks this PC, downloads HalOS (about 2.5 GB), makes room for it on C:, and restarts into the " +
                  "HalOS installer. There you pick a password, and that's it. Nothing is changed until you confirm on the last screen.", 80, 90, InkMuted);
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
            var update = new RadioButton(); update.Text = "Update HalOS: replace the older HalOS or SAINT OS, keep Windows"; update.Visible = false;
            if (hasLive == null) hasLive = Plan.HasLivePartition();
            if (hasLive == true)
            {
                // Setup ran here before: updating is the likely wish, and it's listed first.
                update.Visible = true; update.SetBounds(0, 0, 640, 28);
                foreach (Control c in new Control[] { alongside, size, sizeText, tryIt, replace }) c.Top += 38;
                note.Top += 38;
                if (!choiceShown) mode = "update";
            }
            choiceShown = true;
            Action sync = delegate
            {
                mode = update.Checked ? "update" : alongside.Checked ? "alongside" : tryIt.Checked ? "try" : "replace";
                installGB = size.Value; size.Enabled = alongside.Checked;
                sizeText.Text = string.Format("{0} GB for HalOS", installGB);
                note.Text = mode == "update" ? "The new HalOS goes on the HALOLIVE partition Setup made before; C: isn't shrunk again. After the restart, the installer offers \"Replace the HalOS already installed\": that erases only the old HalOS (and its Home files). Windows and its files stay."
                    : mode == "alongside" ? string.Format("C: shrinks by {0} GB. Windows keeps {1} GB free.", installGB + Config.LiveGB, Math.Max(0, free - installGB - Config.LiveGB))
                    : mode == "try" ? "Only a 6 GB partition is made. You can install from inside HalOS later, or remove it in Disk Management. Also the way to replace an older HalOS when its HALOLIVE partition was removed: the installer offers it."
                    : "Setup prepares the installer the same way; in the installer you choose \"Replace Windows\", and it asks you again before it erases anything. Copy anything you want to keep first, or use \"Bring everything\" in HalOS afterwards from a backup.";
                note.ForeColor = mode == "replace" ? Bad : Muted;
            };
            if (mode == "update" && hasLive != true) mode = "alongside";
            update.Checked = mode == "update"; alongside.Checked = mode == "alongside"; tryIt.Checked = mode == "try"; replace.Checked = mode == "replace";
            alongside.CheckedChanged += delegate { sync(); }; tryIt.CheckedChanged += delegate { sync(); }; update.CheckedChanged += delegate { sync(); };
            replace.CheckedChanged += delegate { sync(); }; size.ValueChanged += delegate { sync(); };
            body.Controls.AddRange(new Control[] { update, alongside, size, sizeText, tryIt, replace, note });
            sync();
        }

        Label status;
        ProgressBar bar;

        void PageDownload()
        {
            title.Text = "Getting HalOS";
            next.Text = iso == null ? "Download" : "Next";
            Text_(iso == null ? "Setup downloads the newest HalOS (about 4.5 GB) and checks it. If the download stops, it carries on from where it was."
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
                    Ui(delegate { status.Text = "Finding the newest HalOS…"; });
                    List<string> urls; string sumsUrl;
                    Release.Latest(out urls, out sumsUrl);
                    using (var wc = new WebClient()) { wc.Headers.Add("User-Agent", "HalOS-Setup"); wc.DownloadFile(sumsUrl, sums); }
                    string want = Download.ExpectedHash(File.ReadAllText(sums), Config.IsoName);
                    if (want == null) throw new InvalidDataException("The release's checksum list doesn't mention " + Config.IsoName + ".");
                    if (!(File.Exists(dest) && Download.Sha256(dest) == want))
                    {
                        // Each part resumes on its own; a finished part (renamed from .part) isn't fetched again.
                        var files = new List<string>();
                        for (int i = 0; i < urls.Count; i++)
                        {
                            string file = urls.Count == 1 ? dest : dest + ".p" + (i + 1);
                            files.Add(file);
                            if (urls.Count > 1 && File.Exists(file)) continue;
                            string label = urls.Count > 1 ? string.Format("Part {0} of {1}: ", i + 1, urls.Count) : "";
                            Download.Fetch(urls[i], file, (done, total, speed) => Ui(delegate
                            {
                                if (total > 0) { bar.Value = (int)Math.Min(100, done * 100 / total); }
                                string left = speed > 0 && total > 0 ? string.Format(", about {0} left", Eta((total - done) / speed)) : "";
                                status.Text = string.Format("{0}{1:0.00} of {2:0.00} GB, {3:0.0} MB/s{4}", label, done / 1e9, total / 1e9, speed / 1e6, left);
                            }), () => cancel);
                        }
                        if (files.Count > 1)
                        {
                            Ui(delegate { status.Text = "Joining the parts…"; });
                            using (var output = File.Create(dest))
                                foreach (var f in files) using (var input = File.OpenRead(f)) input.CopyTo(output, 1 << 20);
                        }
                        Ui(delegate { status.Text = "Checking the download…"; });
                        string got = Download.Sha256(dest);
                        foreach (var f in files) if (f != dest) File.Delete(f);
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
            Text_(mode == "update" ? "Setup will put the new HalOS on the HALOLIVE partition (nothing else on the disk changes) and restart into it. There, choose \"Replace the HalOS already installed\"."
                : mode == "alongside" ? string.Format("Setup will shrink C: by {0} GB, put the HalOS installer on a small partition, and restart into it. Windows stays the default system.", installGB + Config.LiveGB)
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
                        // Step 1 put HalOS on HALOLIVE; a failed restart step doesn't undo that.
                        if (rc != 0 && i > 1) throw new Exception("HalOS is on HALOLIVE and ready, but Setup couldn't restart into it ("
                            + (rc == 1223 ? "you said no to the administrator prompt" : Plain(log.ToString(), rc)) + "). Restart yourself, press F12 (or your PC's boot-menu key) and pick HALOLIVE or 'HalOS (live)'.");
                        if (rc != 0) throw new Exception(Plain(log.ToString(), rc));
                    }
                }
                catch (Exception e) { error = e.Message; }
                Ui(delegate
                {
                    busy = false;
                    if (error != null) { Fail(error); next.Text = "Retry"; next.Enabled = true; back.Enabled = true; typed.Enabled = true; }
                    else if (dryRun) { Line("Dry run finished: nothing was changed."); next.Enabled = false; }
                    else if (log.ToString().Contains("HALOLIVE-READY")) Done("HalOS is ready on HALOLIVE. Restart, press your PC's boot-menu key (F12 on most PCs) and pick HALOLIVE. Windows stays the default.");
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

        void Done(string text)
        {
            Line(text);
            MessageBox.Show(this, text, "HalOS Setup", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }

        void Fail(string reason)
        {
            var d = new Form(); d.Text = "HalOS Setup"; d.ClientSize = new Size(520, 180); d.FormBorderStyle = FormBorderStyle.FixedDialog;
            d.StartPosition = FormStartPosition.CenterParent; d.BackColor = Bg; d.ForeColor = Fg; d.Font = Font;
            var l = new Label(); l.Text = reason; l.SetBounds(20, 20, 480, 100); d.Controls.Add(l);
            var copy = new Button(); copy.Text = "Copy log"; copy.SetBounds(20, 130, 110, 34); Style(copy, false);
            copy.Click += delegate
            {
                // Another program can hold the clipboard open; say so instead of crashing.
                try { Clipboard.SetText(reason + Environment.NewLine + Environment.NewLine + log); copy.Text = "Copied"; }
                catch (System.Runtime.InteropServices.ExternalException) { copy.Text = "Busy, retry"; }
            };
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
            if (a.Contains("--release"))
            {
                List<string> urls; string sums;
                int r = a.IndexOf("--release");                // "--release <file>" parses a saved releases list (tests)
                try
                {
                    if (a.Count > r + 1) Release.Assets(File.ReadAllText(a[r + 1]), out urls, out sums);
                    else Release.Latest(out urls, out sums);
                }
                catch (InvalidDataException e) { Console.WriteLine(e.Message); return 2; }
                foreach (var u in urls) Console.WriteLine(u);
                Console.WriteLine(sums);
                if (a.Count == r + 1) Console.WriteLine("HALOLIVE here: " + Plan.HasLivePartition());
                return 0;
            }
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
