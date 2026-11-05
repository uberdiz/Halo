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
- ☐ Extend `core/evolve.py`: repository index, skill registry cache, worktree isolation, plan/approve/test/rollback

## Priority 7 — release
- ☐ Merge A + B into `halos-release`, full test matrix, ISO + checksums + install guide
