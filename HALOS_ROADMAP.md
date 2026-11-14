# Halo OS roadmap

Order follows the master brief's priorities. Two workstreams run in parallel on separate branches:

| Workstream | Branch | Scope |
|---|---|---|
| A — Halo OS | `halo/arch-rebase` (established OS branch; merges to `main` after VM tests) | OS, SAINT, Store, desktop, ISO |
| B — Remote access + iPhone | `saint-mobile` (worktree) | remote desktop host/relay/clients, `mobile/ios` |
| Release | `halos-release` (created at integration) | tested merges of A + B |

Status key: ✅ done and verified · 🔧 implemented, needs VM/hardware verification · ⏳ next · ☐ not started

## Priority 0 — audit and architecture
- ✅ Repository audit → `HALOS_STATUS.md`
- ✅ Keep Arch + archiso (the repo's current base since 2026-10-30; the brief's "Fedora" predates that decision)
- ✅ Remote-access design and shared protocol → `docs/REMOTE_DESKTOP.md`

## Priority 1 — critical fixes
- 🔧 Kokoro ships in the image; honest voice status; Test Kokoro / Test Whisper buttons
- 🔧 Flatpak installs in the live session (`cow_spacesize`), failure reasons everywhere
- ✅ Store live search, clear resets, stale results dropped
- ✅ Halo navigation: Back button, one level of nav, Apps no longer redirects
- 🔧 Notifications at the bottom on Wayland
- 🔧 Alt+` released from KWin's window switcher
- 🔧 Halo perimeter on Wayland (one screen-sized click-through frame)
- ✅ Storage: real filesystems once each, unallocated space separate
- ⏳ Rebuild ISO, boot test UEFI + BIOS, verify each 🔧 item in the VM
- 🔧 Ollama: default `llama3.1:8b` (`llama3.2:3b` when < 12 GB RAM and no GPU; same rule in `core/config.py` and `ollama-model auto`); pull progress streamed from `/api/pull` into the System page, Halo › AI "Download model" and notifications (`core/model_pull.py`). Still to verify in the VM: service + pull + a real inference
- 🔧 Health dashboard: `core/health.py` — Working / Degraded / Missing / Failed / Not tested for Ollama (real reply), Kokoro (synthesis), Whisper (transcribes a Kokoro clip), Flathub remote, pacman (lock/keyring), network, GPU (nvidia-smi/lspci/driver), storage; each with a timeout and a reason; on the System page with "Run full check" (full run verified on Windows; Linux checks need the VM)
- 🔧 Dependency manager: `core/deps.py` manifests per subsystem, detect → confirm → install (pacman/systemctl/pip via pkexec, Flathub, model downloads; through `saintos_apps.run_plan`) → verify → test with `core/health.py`; "Repair" on the System page (needs the VM)

## Priority 2 — universal app experience
- 🔧 Store cards: icon, publisher, summary; a details view with licence, homepage and up to 4 screenshots, from Flathub's AppStream API, falling back to the system's own AppStream data (`appstreamcli dump`, offline / Arch packages); cached on disk; no ratings (`core/store_art.py`, `ui/components/store_tiles.py`). The `appstreamcli` path is mock-tested only
- 🔧 Filters on search results: compatibility (Native / Flatpak / AUR / Windows (Wine) / Won't work, with the reason), installed / not installed (checked with `flatpak info` / `pacman -Q`), type (apps / games / developer tools / libraries & system) (`core/store.py`)
- 🔧 Universal installation assistant (`core/install_assistant.py`, Store → "From a file or link"): URL, GitHub release (picks the best asset; GitHub's digest or a checksum file in the release), Flathub link/id, `.pkg.tar.zst`, `.flatpakref`, `.AppImage`, `.deb` (debtap), `.exe`/`.msi` (Wine) → plan with steps, risk, source, checksum → approve → the Store's queue/`run_plan` → verify (installed + process appears) → history ("Installed by SAINT": repair, uninstall). Store installs are recorded too. A Windows app / .deb with a Store version gets that offered first; kernel anti-cheat refused. Mock-tested on Windows; needs the VM
- ⏳ Heroic + one app per source installed and launched in the VM — matrix in `HALOS_TEST_RESULTS.md` ("Installation assistant VM matrix", not run)

## Priority 3 — desktop
- 🔧 Halo Dark / Halo Light (Plasma colour schemes generated from SAINT's palette) — build 7
- 🔧 SAINT Task Manager app + Ctrl+Shift+Esc — build 7 (verified on Windows data; Linux pages need the VM)
- 🔧 Floating Halo widget, SAINT Music widget (MPRIS via playerctl) — build 7 (QML syntax-checked only)
- 🔧 Star close animation (`saint-star` KWin effect) — reduced motion done 2026-11-04: follows Plasma's animation speed, "Instant" disables it entirely (no window grab), `[Effect-saint-star] ReducedMotion=true` keeps a fade only; transitions still to be watched in the VM
- 🔧 Halo Dark is the default look (colour scheme + look-and-feel "Halo Dark"), Halo Light selectable

## Priority 4–5 — remote access and iPhone (Workstream B)
- 🔧 Host: portal ScreenCast/RemoteDesktop + GStreamer WebRTC, authenticated by SAINT Link device keys — logic tested
  (pytest: auth, sessions, input, files, pipeline, multi-monitor selection); relay keepalive + redial; the media path
  (`media.py`) still needs a Plasma Wayland session (VM), incl. switching screens on a multi-monitor setup
- 🔧 Relay/signaling (self-hostable) + TURN fallback — relay tested on localhost (pytest + Node); Docker compose
  (relay + coturn + Caddy) and a systemd unit + no-Docker guide in `server/relay/README.md`; not yet run on a VPS,
  TURN across networks not tried
- ✅ Browser client — tested end to end in Chromium against the fake host (video, input, clipboard, files, stats,
  screen picker, reconnect back to the same screen); Safari/iPad not tried
- ✅ Desktop client = SAINT's desktop app (`ui/remote_desktop.py`, Qt WebEngine around the shared viewer) — ran on
  Windows against the local relay + fake host
- 🔧 iOS: native remote-desktop screen in `mobile/ios` (stasel/WebRTC SPM), Link pairing reused, reconnection
  (5 s unstable → retry, back to the same screen), screen picker — written, **not compiled here** (no macOS); first
  compile is `mobile-ios.yml` on GitHub Actions

## Priority 6 — OS Expansion Agent
- 🔧 Extend `core/evolve.py`: repository index (files, symbols, summaries cached by content hash), skill registry
  cache, isolated git worktree per change, plan (Claude Code `-p`, read-only) → approve → Btrfs snapshot
  (snapper or `btrfs subvolume snapshot` via pkexec) → apply (scoped allowed tools) → targeted tests → keep
  (fast-forward) or rollback (worktree removed + `snapper undochange`); `claude` missing / not signed in is
  reported with the fix. Evolve page: "SAINT / Halo itself" mode. Tests with mocks (`tests/test_evolve_source.py`);
  needs a real run in the VM with a signed-in `claude`
- ☐ Image ships the `claude` CLI (needs `nodejs`/`npm` + `@anthropic-ai/claude-code` in packaging/arch)
- 🔧 Windows-host tooling (`packaging/windows-host/`): `build_iso.ps1` (WSL2 + podman, verified `.part` copy-back),
  `boot_test.ps1` (VirtualBox UEFI + BIOS, ISO SHA-256 check first), `write_usb.md`, `tools/dev_check.ps1`,
  `docs/INSTALL_ON_THIS_PC.md`. Checked on this PC up to the missing WSL2/VirtualBox messages

## Image decisions of 2026-11-04 — applied (🔧 until the next ISO is built and boot-tested)
- 🔧 Name **Halo OS** in os-release (`NAME`/`PRETTY_NAME`), boot menus (syslinux, systemd-boot), GRUB distributor
  (Calamares `bootloaderEntryName`), Plymouth, login splash, Calamares, About this System (`kcm-about-distrorc`),
  firmware boot entry label, SAINT's Control Center. Packages/files stay `halo-*`, `ID=halo`, ISO volume `HALO_*`.
- 🔧 NVIDIA: `nvidia-open`, `nvidia-utils`, `lib32-nvidia-utils` ([multilib] on), `nvidia-settings`;
  `halo-gpu-detect.service` (before udev) blacklists nouveau and loads nvidia (`modeset=1 fbdev=1`) only on
  Turing+ NVIDIA GPUs; no GPU driver in the initramfs on NVIDIA PCs; `halo.nvidia=0/1` override.
- 🔧 Ollama default `llama3.1:8b` from `/etc/halo/ollama-model`, `llama3.2:3b` with < 12 GB RAM and no NVIDIA GPU
  (SAINT's own Python default is updated separately). ☐ Pull progress in SAINT; ☐ `ollama-cuda` for GPU inference.
- 🔧 Taskbar: Firefox · Dolphin · Konsole · SAINT · VS Code (Arch `code`) · Spotify (Flathub `com.spotify.Client`,
  installed at first boot by `halo-flatpak-apps.service`; the pinned placeholder installs it on first click).
- 🔧 Claude Code CLI in the image (`nodejs`, `npm`, AUR `claude-code` built into [halo]); validate_iso runs `claude --version`.
- 🔧 Reusing a 100 MB Windows EFI partition: Calamares ESP minimum 64 MiB, mounted at `/boot/efi` (kept, not
  formatted); kernels/initramfs stay in `/boot` on Btrfs; only shim + MokManager + GRUB (~15 MB) go on the ESP,
  and halo-secureboot checks for 20 MB free first.
- ✅ Fedora pipeline removed (`packaging/linux/image`, Anaconda install test, its docs); CI workflow is now `halo-image.yml`.

## Priority 7 — release
- ☐ Merge A + B into `halos-release`, full test matrix, ISO + checksums + install guide

## Later — HalOS moves onto the big partition, old Windows files kept (design note, 2026-11-14; not started)
The wish: eventually run Linux and keep all files on the large partition (today Windows C:, ~1.7 TB) while the
old Windows files stay readable. Sketch, reusing what exists:
1. **Free space without losing files.** The migration wizard already links or copies the Windows folders and
   lists failures with Retry (core/windows_migration.py). Before any resize, everything the user wants is either
   copied to HalOS or confirmed as "keep on Windows". Fast Startup/hibernation and BitLocker must be off
   (drives.py already detects both) and `ntfsresize --info` must pass.
2. **Shrink NTFS, grow HalOS.** Shrink the Windows partition with `ntfsresize` (never below used + 10 %), then
   either move the Btrfs root into the freed space (`btrfs device add` the new partition + `btrfs device
   remove` the old one: online, no copy by hand) or create a new Btrfs partition and `btrfs replace`. The
   HALOLIVE/recovery entries and the ESP stay untouched; GRUB/shim are reinstalled only if the root UUID changes.
3. **Keep the old Windows files.** Either keep the shrunk NTFS partition read-only (links stay valid via the
   stable `~/.local/share/saint/windows/<uuid>` paths), or — when Windows is retired — copy `Users/` into a Btrfs
   subvolume `@windows-files` (deduplicated with `cp --reflink` where possible) and point the links there, then
   `execute_removal` frees the rest.
4. **Safety.** Dry run first with the exact commands shown; a snapshot of `@` and `@home` before; never touch
   EFI/Recovery (install_target rules); do it from the live system, not the running root, with power checked.
   Needs real-hardware testing on a copy of the disk layout in a VM before it's offered.

## Decisions — 2026-11-04 (answers to plan.md §14 and new questions)

| Topic | Decision |
|---|---|
| Name | **Halo OS** in user-visible places (boot menu, os-release `NAME`/`PRETTY_NAME`, Plymouth, installer, About). Package/file names stay `halo-*`. |
| Install target (owner's PC) | Dual boot; shrink Windows `C:` (2 TB NVMe) by **200 GB**, leave it unallocated; Calamares "Install alongside / use free space". EFI partition is on the ADATA disk — keep it, GRUB + os-prober adds Windows. |
| Secure Boot | Microsoft-signed shim + one-time MOK enrolment (already implemented; verify on hardware). |
| GPU | Ship **nvidia-open** (+ nvidia-utils, lib32-nvidia-utils) in the image; loaded only when an NVIDIA GPU is detected; nouveau blacklisted then. Needed for RTX 50-series (Blackwell). |
| Ollama default model | **8B class (~5 GB)**, pulled in the background after install, progress shown in SAINT. Small model only as fallback on machines with < 12 GB RAM and no GPU. |
| Preinstalled / pinned apps | Firefox · Dolphin · Konsole · SAINT · **VS Code** · **Spotify** (Flatpak or AUR, whichever installs cleanly offline-first). |
| Default theme | **Halo Dark**; Halo Light selectable. |
| Fedora pipeline | Tag `saintos-fedora-0.1.0`, then delete `packaging/linux/image` from main. |
| Evolve (OS Expansion Agent) | **Claude Code with the user's own account**; plan → approve → Btrfs snapshot → apply → test → rollback. |
| Scope | Full roadmap including Workstream B and iOS (iOS verified only by GitHub Actions on macOS). |
| Git | Work on branches, push to `uberdiz/Halo`. |
