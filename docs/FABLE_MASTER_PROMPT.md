# HalOS — Fable Master Prompt (v1, refined)

> Paste everything between the lines into Fable (Claude Code) at the repo root. This is the refined version of
> the original bug-list prompt (`Claude prompts twin` Google Doc, folded into Workstream 9 below).

---

**Use as many subagents as needed. Do not ask questions — this is the refined version of this prompt. Continue
autonomously until the project is finished.** Decide, record the decision in `docs/DECISIONS.md` (one line, with
why), and keep moving. Stop only for actions the safety rules reserve for the user (see "Hard limits").

## 1. Product essence

HalOS is a **free, faster, smaller replacement for Windows (and a switch path from macOS)** that anyone can
install as easily as a browser, and that **keeps everything from the old OS in one pass**: files, apps (or their
Linux equivalents), browser data and passwords, settings, wallpapers, history, and AI models. A first-time user
who has never seen Linux must get from "download" to "my desktop, my stuff" with no terminal and no decisions
they don't care about.

Success bar (measure and record each in `HALOS_STATUS.md`):
| Goal | Target |
|---|---|
| Install effort | Download one small installer, click through ≤ 5 screens, ≤ 15 min, no USB required on Windows |
| Faster | Cold boot to desktop and idle RAM both measurably better than Windows 11 on the same VM/hardware; publish numbers |
| Smaller | ISO ≤ 2.5 GB; installed base ≤ 12 GB (optional agents/models downloaded on demand) |
| Free | No accounts, no licence keys, no telemetry; every component open-source or freely redistributable |
| Keep everything | Migration wizard moves ≥ 95% of user data by size and reports exactly what was skipped and why |
| Safe | Windows install stays bootable; every destructive step needs explicit, typed-out confirmation; full undo for migration |

Existing base to **reuse, not rewrite**: Arch + KDE Plasma 6 + archiso, Calamares, SAINT (Python/PySide6),
SAINT Store, `core/health.py`, `core/deps.py`, `core/install_assistant.py`, `core/model_pull.py`, remote
desktop (`docs/REMOTE_DESKTOP.md`). Read `CLAUDE.md`, `HALOS_STATUS.md`, `HALOS_ROADMAP.md` first; read only
the files each workstream needs.

## 2. Operating rules

1. Follow `CLAUDE.md` (efficiency, deterministic code for deterministic work, LLM only for reasoning).
2. Work in **waves**. Per wave: a planner subagent (`Plan`) writes the task list; independent workstreams
   run as parallel subagents in separate git worktrees (`isolation: "worktree"`), never two writers on the
   same files; a reviewer subagent runs `/code-review` and `/security-review` on each branch before merge.
3. Use the project skills in `.claude/skills/` (`halos-installer`, `halos-migration`, `halos-agent-catalog`,
   `halos-verify`). Invoke the matching skill at the start of each workstream.
4. Every feature ships with: code, a targeted test, a VM or runtime check (recipe in memory/`docs/VM_TESTING.md`),
   and a `HALOS_STATUS.md` line marked ✅ verified or 🔧 needs hardware. Never claim ✅ without a run.
5. Commit small and often on `halo/*` branches; merge to `halos-release` only when tests + VM pass; push every
   wave to GitHub (`origin`). Open one PR per workstream; keep `main` releasable.
6. Keep a running `docs/PROGRESS.md` log (wave, what landed, what failed). Report failures plainly.
7. When blocked by hardware you do not have (real Secure Boot, Mac, iPhone), build everything up to the
   hardware boundary, add a mock/VM test, mark 🔧, and continue.

## 3. Workstreams (run in parallel where independent)

### W1 — Browser-easy install (highest priority)
- **Windows-hosted installer** `HalOS-Setup.exe` (small, signed-ready, built from `packaging/windows`): checks
  UEFI/Secure Boot/BitLocker/free space, shrinks C: safely, downloads the ISO with resume + checksum, stages
  it on an ESP/boot entry and reboots into the installer. No USB needed. Fall back to a USB writer for others.
- **Guided Calamares flow** reduced to: language → "Install alongside Windows / Replace Windows / Try first"
  → confirm → done. Auto-detect disks, GPU (nvidia-open path), Wi-Fi, keyboard, time zone. Sensible defaults;
  an "Advanced" drawer for everything else.
- **Recovery that reboots immediately** without dependency installs (fix the known bug: recovery must work
  offline from the image). Installation errors must show a plain-language reason, a "Retry" and a "Copy log" button.
- Live session "Try without installing" with the migration wizard available before install.
- Verify in VMs: UEFI, BIOS, Secure Boot (MOK recipe in memory), 4 GB RAM minimum, dual-boot with a
  Windows VM disk. Fix the Build-16 SBAT/GRUB issue lineage if still open.

### W2 — Migration wizard ("Bring everything", one click)
Skill: `halos-migration`. A single wizard scans every Windows/macOS source (mounted disk, network share, or
a lightweight Windows exporter), shows one summary, and migrates after one confirmation:
- Files (Documents/Desktop/Pictures/Music/Videos/Downloads) into a **shared file layout** so the old Windows
  install, new HalOS and SAINT all see the same folders (symlinks/bind mounts, no duplicate copies by default).
- Browser profiles (Chrome/Edge/Firefox/Brave): bookmarks, history, extensions mapped, saved passwords via
  export file or Apple/Chrome password import; Apple Passwords/iCloud Keychain import path.
- Installed-app inventory → **match to Linux native/Flatpak/AUR/Wine equivalents**, shown in one list with
  filters (works on Linux / needs Wine / no equivalent) and a "install all that work" button; try harder
  than name matching (AppStream IDs, winget/Chocolatey IDs, Flathub search, a curated `data/app_map.json`).
- Settings: Wi-Fi networks, default apps, wallpapers (incl. Wallpaper Engine → Steam Workshop or free
  animated alternatives with a large catalogue), fonts, keyboard/locale, mail/calendar accounts.
- SAINT/Claude history and usage from the Windows install merged into the HalOS history store;
  all installs sharing a machine/account sync history (deduplicated, conflict-safe).
- **Reuse Windows-side AI models** (Ollama/LM Studio GGUF) in place instead of re-downloading (low bandwidth).
- AI-assisted *plan*, deterministic *execution*: an LLM only proposes which duplicate/stale files to merge;
  code applies it, with a dry-run diff and one-click undo (manifest of every change).
- Real visual feedback: per-step progress, ETA, current item, and a final report. Never a silent button.

### W3 — Fast, smart universal search
Local index (inotify/USN-style incremental, SQLite FTS5 + small embeddings model, runs locally) for files,
apps, settings, mail, browser history, and clipboard. Natural queries ("the app for claude", "that invoice from
March") resolve to apps/files/settings with ranked, previewed results in < 100 ms for hot queries. Used by
Halo, the Store, and SAINT. Benchmark and record numbers.

### W4 — Hardware-aware agent installer ("Agents" app)
Skill: `halos-agent-catalog`. Detect CPU/RAM/GPU/VRAM/disk/network, then recommend and one-click install
local AI agents and models that fit: tiers (≤8 GB RAM CPU-only → small quantized models; 16 GB+ → 8B;
GPU ≥ 12 GB VRAM → larger), with size, speed estimate, and offline-first behaviour. Catalogue lives in
`data/agent_catalog.json` (id, role, min specs, source, checksum, licence). Includes: assistant (Ollama),
voice (Kokoro/Whisper), coding agent (Claude Code), file-organizer, photo-tagger, download/update watcher.
Install through `core/deps.py` (detect → confirm → install → verify with `core/health.py`).
**Claude Code autonomy**: SAINT drives `claude` (Claude Code CLI) for heavy tasks so no API credits are needed,
streams progress updates, summarises results compactly to save tokens, and uses pre-made skills.

### W5 — Phone and cross-device
iPhone photo transfer (and PC-hosted photo access while the PC is online) via the existing remote/relay
design; Apple Passwords import; clear pairing UX. Build the PC side fully; mark phone side 🔧 where no device.

### W6 — Universal download/update detector
One panel showing every active download and pending update (pacman, Flatpak, AUR, models, ISO/Windows
downloads, browser downloads) with progress, ETA, pause/cancel, and notifications. Event-driven, not polling.

### W7 — Store polish
Visual feedback on every search/install step; fix "pacman is busy" by queueing and showing "waiting for
other install" with automatic retry; apps filter default "Works on HalOS"; try harder to resolve apps
(e.g. Antigravity) via Flathub/AUR/AppImage/Wine.

### W8 — Desktop quality (SAINT/Halo shell)
Window-close/open animations that animate the **window itself** (pull-in then burst), not the logo; do not
replay animations on tab/fullscreen changes; Animations settings tab fully working (scale, profiles,
Preview, "Try on real windows"). Halo ring on the primary screen (or spanning extended screens); clicking the
SAINT dock icon opens the SAINT app, not the Halo. Screenshots: no phantom clicks, copy/save never closes
the editor early, saved shots appear in the Screenshots folder. Performance pass: idle RAM, boot time,
service start-up (disable/lazy-start what is not needed), zram, fast kernel/initramfs settings.

### W9 — Original prompt backlog (from the Google Doc; all must be covered above or done here)
Linux commands by asking SAINT (deterministic tool layer with allow-list + confirmation, never raw LLM shell);
Claude usage/history imported and installed by default; Step-5 feedback; app-store feedback; "pacman busy";
shared history across installs; faster accurate search; default-OS picker from a drive scan.

### W10 — Release, docs, GitHub
`README.md` rewritten as a product page (what/why/download/how-to-install, screenshots, comparison table
vs Windows/macOS); `docs/INSTALL.md` beginner guide; `CONTRIBUTING.md`; GitHub Actions to build the ISO and
installer, run tests, and attach artifacts + SHA256 to GitHub Releases; issue templates; roadmap project.
Publish to the `origin` repo; tag releases `halos-0.x`.

## 4. Order of work
Wave 0: audit + plan (read status files, write `docs/PROGRESS.md`, decide target numbers).
Wave 1 (parallel): W1 installer, W2 migration core, W3 search index, W4 hardware detector + catalogue.
Wave 2 (parallel): W5, W6, W7, W8, remaining W2 matchers.
Wave 3: integration on `halos-release`, full ISO build, VM matrix, performance benchmarks, W10 docs/CI.
Wave 4: fix everything the VM matrix found; repeat Wave 3 until the success bar is met or only hardware-bound
items remain. Then tag a release and push.

## 5. Hard limits (do not cross even autonomously)
- Never delete or overwrite the user's Windows partition or personal files without the typed confirmation flow;
  the migration and installer default to non-destructive.
- Never enter passwords/keys on the user's behalf, move money, or publish secrets. No credentials in the repo.
- Ship only freely redistributable software; no pirated assets, no bundled proprietary Windows/macOS code.
- No telemetry. No bypassing Secure Boot/BitLocker protections; use the supported MOK/recovery-key flows.
- Do not force-push `main`. Do not run unreviewed downloaded scripts.

## 6. Definition of done
Success-bar table filled with measured numbers; fresh-VM install from the downloadable installer to a
migrated desktop passes unattended on the VM matrix; all tests green; `HALOS_STATUS.md` honest (no ✅ without
a run); README/INSTALL published; release tagged and pushed. Then write the final report: CHANGED / FIXED /
TESTED / REMAINING.

---
