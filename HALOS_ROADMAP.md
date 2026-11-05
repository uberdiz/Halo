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
- ⏳ Ollama: verify service + model pull + a real inference in the VM; surface pull progress in SAINT
- ⏳ Health dashboard: one `core/health.py` with Working / Degraded / Missing / Failed / Not tested per subsystem (Ollama inference, Kokoro synthesis, Whisper transcription, Flatpak remote, pacman, network, GPU, storage), each backed by a real check
- ☐ Dependency manager: per-subsystem dependency manifests, detect → install → verify → test

## Priority 2 — universal app experience
- ☐ Store cards: icon, publisher, screenshots from AppStream/Flathub metadata (no invented ratings)
- ☐ Filters: installed status, compatibility, app type
- ☐ Universal installation assistant (URL / GitHub release / package file → plan → approve → install → verify launch), history, uninstall/repair
- ☐ Heroic + one app per source installed and launched in the VM (test matrix)

## Priority 3 — desktop
- 🔧 Halo Dark / Halo Light (Plasma colour schemes generated from SAINT's palette) — build 7
- 🔧 SAINT Task Manager app + Ctrl+Shift+Esc — build 7 (verified on Windows data; Linux pages need the VM)
- 🔧 Floating Halo widget, SAINT Music widget (MPRIS via playerctl) — build 7 (QML syntax-checked only)
- 🔧 Star close animation (`saint-star` KWin effect exists) — review against the brief, reduced-motion, test transitions

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
- ☐ Extend `core/evolve.py`: repository index, skill registry cache, worktree isolation, plan/approve/test/rollback

## Priority 7 — release
- ☐ Merge A + B into `halos-release`, full test matrix, ISO + checksums + install guide

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
