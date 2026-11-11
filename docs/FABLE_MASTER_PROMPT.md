# HalOS — Fable Master Prompt (v2: the AI OS release)

> Open Claude Code (Fable) at the repo root and paste everything below the line. v2 replaces v1. It keeps v1's
> install/migration work and adds the AI-native OS, AIDE integration, SAINT agent mode, camera presence,
> HalOS-made Settings and Files, new icons and the living wallpaper. The bug list from the `Claude prompts twin`
> Google Doc is in W10.

---

**Use as many subagents as needed. Don't ask questions: this is the refined version of this prompt. Keep going
on your own until the project is finished.** When a choice comes up, make it, add one line to
`docs/DECISIONS.md` saying what you chose and why, and move on. Stop only for actions the safety rules leave to
the user (see §6).

## 1. What HalOS is

HalOS is an **AI operating system**, not an OS with AI features bolted on. It's a **free replacement for Windows
that's faster and smaller** (and a way off macOS), and it installs **as easily as a web browser**. One install
brings over **everything from the old OS**. SAINT, the built-in agent, is how you use the machine: ask in words
or voice and it plans, does the work with deterministic tools, and shows you each step. Classic mouse-and-window
use still works for everything.

Targets (measure each one and record it in `HALOS_STATUS.md`):

| Goal | Target |
|---|---|
| Install as easy as a browser | One download under 20 MB (`HalOS-Setup.exe` / `.dmg`), 5 screens or fewer, no USB, no terminal, under 15 min |
| Keep everything | One wizard, one confirmation, moves at least 95% of user data by size, says what it skipped and why, full undo |
| Faster | Boot from firmware to desktop under 10 s on SSD (measure with `systemd-analyze`), idle RAM under Windows 11 on the same machine; publish the numbers |
| Smaller | ISO 2.5 GB or less; base install 12 GB or less; agents and models downloaded only when chosen |
| Free | No accounts, keys, ads or telemetry; everything open source or freely redistributable |
| AI-native | Every Settings toggle, file action, app install and system change can be done through SAINT, gated by trust level |
| Safe | Windows stays bootable; destructive steps need typed confirmation; every SAINT action is logged and can be undone where possible |

**Reuse, don't rewrite**: Arch + KDE Plasma 6 + archiso, Calamares, SAINT (Python/PySide6), SAINT Store,
`core/health.py`, `core/deps.py`, `core/install_assistant.py`, `core/model_pull.py`, remote desktop, and all
v1 work already merged. Read `CLAUDE.md`, `HALOS_STATUS.md`, `HALOS_ROADMAP.md` and `docs/DECISIONS.md` first,
then only the files each workstream needs.

## 2. How to work

1. Follow `CLAUDE.md`: deterministic code does deterministic work; the LLM handles intent and reasoning only.
2. Work in **waves**. In each wave a `Plan` subagent writes the task list. Independent workstreams run as
   parallel subagents, each in its own git worktree (`isolation: "worktree"`), and two writers never touch the
   same files. A reviewer subagent runs `/code-review` and `/security-review` on each branch before merge.
3. At the start of each workstream, invoke the matching project skill from `.claude/skills/`:
   `halos-installer`, `halos-migration`, `halos-agent-catalog`, `halos-ai-shell`, `halos-desktop-design`,
   `halos-verify`.
4. A feature counts as shipped only with all four: code, a targeted test, a VM or runtime check (see
   `docs/VM_TESTING.md` and memory), and a `HALOS_STATUS.md` line marked ✅ verified or 🔧 needs hardware.
   Never mark ✅ without a run.
5. Commit small and often on `halo/*` branches. Merge to `halos-release` only after tests and the VM check
   pass. Push every wave to `origin` (github.com/uberdiz/Halo), open one PR per workstream, keep `main`
   releasable, and tag `v2.0.0` at the end with a release containing the ISO checksum and setup EXE.
6. Keep `docs/PROGRESS.md` up to date (wave, what landed, what failed). Report failures plainly.
   **Document the whole process on GitHub with screenshots**: `docs/process/` gets one page per wave (what was
   built, how it was tested, before/after screenshots from the VM and the SAINT app under
   `docs/process/screenshots/`), linked from the `README`. Only real screenshots from real runs.
7. When hardware you don't have blocks you (camera, real Secure Boot, Mac, iPhone): build everything up to that
   point, add a mock or VM test, mark it 🔧, and keep going.

## 3. Workstreams

### W1 — Install as easy as a browser (`halos-installer`)
- `HalOS-Setup.exe` (and a macOS `.dmg` helper): a small stub that checks UEFI, Secure Boot, BitLocker
  (suspend with consent) and free space, safely shrinks C:, streams the ISO with resume and checksum, adds a
  boot entry and reboots into install. Keep the USB writer as a fallback.
- Calamares cut down to: language → "Alongside Windows / Replace / Try first" → confirm → done. Detect the
  rest automatically (GPU through the nvidia-open path, Wi-Fi, keyboard, time zone) and put everything else in
  an "Advanced" drawer.
- Every error shows a plain-language reason with Retry and Copy log buttons. Recovery boots and reboots offline
  with no dependency installs.
- Fast boot: zstd initramfs with only the needed modules (`mkinitcpio` autodetect), systemd-boot or a trimmed
  GRUB with a 0 s timeout when only one OS is present, services parallel or socket-activated, Plymouth with the
  HalOS logo. Record `systemd-analyze blame` before and after.
- Verify in VMs: UEFI, BIOS, Secure Boot with MOK, 4 GB RAM, dual boot with Windows. Keep the SBAT/GRUB fixes
  from Build 16.

### W2 — Bring everything (`halos-migration`)
A single wizard that runs before or after install, shows one summary and asks for one confirmation:
- Files go into one **shared layout** that the old Windows install, HalOS and SAINT all see (bind mounts or
  links, no duplicate copies). An AI pass suggests merges only; deterministic code does the moving, and
  nothing moves without the user's approval.
- Browsers (Chrome/Edge/Firefox/Brave): bookmarks, history, extensions, passwords. Import Apple
  Passwords/iCloud Keychain through an export file.
- Apps: inventory the old OS, then match each app to a native/Flatpak/AUR/Wine equivalent using AppStream,
  winget and Chocolatey IDs, Flathub search and `data/app_map.json` (Antigravity, for example, has a Linux
  build). Show the list with filters (works / needs Wine / no equivalent) and an "Install all that work" button.
- Settings: Wi-Fi, default OS choice, default apps, fonts, locale, accounts, wallpapers (Wallpaper Engine
  through Steam, or a large free catalogue of animated wallpapers).
- SAINT/Claude history, usage and settings from Windows, plus **local models reused from the Windows disk** (no
  re-download on slow Wi-Fi).
- iPhone: photo transfer, and access to PC photos from the phone while the PC is online.
- Full undo, and a report of what moved and what was skipped.

### W3 — Agents matched to the hardware (`halos-agent-catalog`)
Detect CPU, RAM, GPU and VRAM, then recommend a tier (none / small / 8B / larger) with a size and speed estimate
and one-click install through `core/model_pull.py`. Claude Code is the default cloud agent (no API key needed);
local Ollama models are the offline fallback. Show download progress in the universal download tray (W9).

### W4 — SAINT agent mode, on par with Antigravity (`halos-ai-shell`)
- The SAINT app becomes an agent workspace like Google Antigravity, **driven by Claude Code** (`claude -p` in
  headless/stream-json mode with the user's subscription, no API key). It has a task list, live per-step
  progress, diffs and artifacts, and a review/approve flow for each step.
- Token thrift: premade skills, cached context, short summaries of what Claude did so earlier work isn't
  re-sent, and deterministic tools wherever code can do the job.
- **Integrate AIDE 2.0**, the user's AI-native IDE at `C:\SAINTxAIDE\AIDEv2.0` (in the VM or on Linux, copy or
  mount it). It's a rebranded VSCodium 1.107 workbench plus the built-in `extensions/aide-core` extension
  (provider routing, agents, MCP, context engine, change review and checkpoints, workflows). Read its
  `README.md` and `docs/` first. Build AIDE for **linux-x64** (VSCodium Linux runtime instead of the
  `runtime/AIDE.exe` setup; adapt `scripts/setup-runtime.mjs`), package it for HalOS (pacman package or
  Flatpak), and ship it preinstalled as the HalOS "Code" app. SAINT and aide-core should share one agent
  backend (Claude Code), history, skills and usage limits. Use AIDE's agent/change-review UI as the model for
  SAINT agent mode instead of building a second one. Its `vitest` tests must pass on Linux. Treat AIDE's own
  repo as a dependency: commit AIDE changes there, not copied into HalOS.
- Shared history across every SAINT install on the same machine or account (Windows ↔ HalOS sync).

### W5 — AI that can manage the whole OS
- A typed **action registry** (settings, files, packages, services, windows, network, power, users) that both
  the GUI and SAINT call. The LLM picks actions; code checks and runs them.
- **Trust levels**, set per category: Ask every time / Ask for risky / Trusted. Risky actions (delete, sudo,
  network, credentials) always show a preview first. Everything goes to an action log with undo where possible.
- Multi-step commands appear as a **visual plan**: a step list with live status, a highlight on the screen
  element being acted on, and a progress HUD around the SAINT halo.
- **Parallel tasks tile automatically**: each running task gets its own window in a KWin split layout.
- **Works without stealing focus**: keyboard and mouse automation runs in a nested or headless session
  (separate virtual desktop, Xvfb/wlroots headless output, or `ydotool` on a virtual seat) so the user's own
  focus, desktop and typing are never interrupted. Results are shown when they're done.

### W6 — Camera presence (opt-in, off by default)
Local-only vision with no frames leaving the machine and a visible camera-in-use indicator. It wakes the PC when
the user sits down, dims and sleeps when they leave, pauses media when they look away, and offers optional
gesture shortcuts and a "focus mode" nudge. One switch in Settings turns it all off.

### W7 — HalOS Settings and HalOS Files (`halos-desktop-design`)
- **HalOS Settings**: a new app with simple categories and SAINT search ("make the text bigger"), built on the
  action registry from W5. KDE modules open only behind "Advanced".
- **HalOS Files**: a new file explorer with instant indexed search (a local index plus a semantic layer) that
  infers intent as you type ("the app for claude" → Claude Code), quick previews, and the shared Windows/HalOS
  folders from W2.

### W8 — Look and feel (`halos-desktop-design`)
- Redesign **every icon except the main HalOS/Orbit logo** as one consistent set (SVG, light and dark), and
  ship it as the default icon theme.
- **Living wallpaper**: by default a solid colour the user picks, plus the SAINT logo, which the user can move,
  resize and position on any monitor. The logo works as a **visualizer** (mic, desktop audio, or idle
  breathing animation). Settings cover colour or gradient, logo size, position, glow, reactivity, sensitivity,
  per-monitor layout and an FPS cap. GPU use stays under 2% when idle.
- Keep the existing design language consistent across Settings, Files, SAINT and the Store.

### W9 — System quality
- A universal download detector and tray: pacman, Flatpak, browsers, Steam, model pulls and app updates, all in
  one place.
- A pacman queue so "pacman is busy" never reaches the user; the Store queues and shows progress instead.
- Visual feedback on every button that starts work.

### W10 — Bug list from the Google Doc (fix first, in wave 1)
- Close animation: the window itself should pull inward and then burst outward, not just the logo. It must not
  play on new-tab or fullscreen changes. The Animations tab needs to work (scale, profiles, preview, "Try on
  real windows").
- The halo isn't the SAINT app: the taskbar SAINT icon opens the app, and the halo belongs on the primary
  screen or spans both screens.
- Screenshots: no stray clicks; copy and save must not flash the editor; saved files must land in Screenshots.
- Migration step 5 needs visual feedback. The Store needs search feedback and has the pacman-busy error.
- The install error and the recovery reboot bug (also covered in W1).
- SAINT runs Linux commands on request (under W5 trust levels), with Apple Passwords integration.

## 4. Wave order
1. W10 bugs, the W5 action registry and the W1 installer core (everything else builds on these).
2. W2, W3, W4 and W7 in parallel.
3. W5 UI (plans, tiling, background sessions), W6, W8, W9.
4. Hardening: full VM matrix, boot and RAM benchmarks, docs (`README`, `docs/GUIDE.md`), release `v2.0.0`.

## 5. Done means
Every row of the §1 table is measured and met (or marked 🔧 with the reason), every workstream is merged with
✅ or 🔧 status, the release is pushed and tagged on GitHub, and `docs/PROGRESS.md` ends with a short summary of
what shipped and what's left.

## 6. Hard limits
Never enter real passwords, keys or financial data; never wipe a disk without typed confirmation in a VM;
never push secrets; never send camera frames, files or history off the machine without explicit opt-in.
