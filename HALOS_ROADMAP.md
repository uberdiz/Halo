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
- ⏳ Host: portal ScreenCast/RemoteDesktop + GStreamer WebRTC, authenticated by SAINT Link device keys
- ⏳ Relay/signaling (self-hostable) + TURN fallback
- ⏳ Browser client, then desktop client (same protocol)
- ⏳ iOS: native remote-desktop screen in `mobile/ios` (WebRTC), pairing reuse, reconnection

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

## Priority 7 — release
- ☐ Merge A + B into `halos-release`, full test matrix, ISO + checksums + install guide
