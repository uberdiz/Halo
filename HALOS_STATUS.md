# Halo OS (HalOS) — status

Last updated: 2026-11-12 · branch `halo/roadmap-2026-11` · HalOS v2 in progress

## HalOS v2 (the AI OS release): where each part stands

✅ means a test or run actually exercised it on the development PC. 🔧 means the code and its tests are done
but it still needs a run on HalOS itself (VM or hardware). By decision, no ISO is built until every wave is coded,
so nothing below has run on HalOS yet. Details per item: [docs/PROGRESS.md](docs/PROGRESS.md); write-ups with
screenshots: [docs/process/](docs/process/).

| Part | State | Evidence |
|---|---|---|
| HalOS-Setup.exe (5 screens, 50 KB, resumable verified download) | ✅ built and run (self-test, plan, dry run) on Windows · 🔧 end-to-end install | tests/test_halos_setup_exe.py |
| 3-page install, time zone/keyboard from the live session | 🔧 | tests/test_install_flow.py |
| Recovery restart offline; plain install errors with Retry/Copy log | 🔧 | tests/test_recovery.py, test_install_failures.py |
| Fast boot (zstd initramfs, quiet splash, no menu wait alone) + benchmark | 🔧 boot time and idle RAM not measured yet | tests/test_fast_boot.py |
| OS action registry: 45 actions, trust levels, log, undo | ✅ logic · 🔧 Linux command lines | tests/test_actions_*.py |
| SAINT plain-phrase OS control; plan panel; What SAINT may do | ✅ | tests/test_os_intents.py, test_plan_panel.py, test_ai_control_page.py |
| SAINT agent mode on Claude Code (subscription, no API key) | ✅ with a faked Claude Code · 🔧 real sign-in on HalOS | tests/test_claude_agent.py |
| AIDE 2.0: claude-code provider, Linux builds, ships as the Code app | ✅ 94 AIDE tests · 🔧 Linux build in the ISO build | uberdiz/AIDE aide-2.0 |
| AI agents matched to hardware; reuse of Windows models | ✅ rated on the dev PC's hardware | tests/test_agent_catalog.py |
| Package queue (no "pacman is busy"); Store feedback; download detector | ✅ logic · 🔧 on pacman | tests/test_pkg_queue.py, test_downloads.py |
| Migration: app matching (302 apps), filters, SAINT/Claude history, exporters, Wi-Fi, duplicates, iPhone | ✅ logic · 🔧 a real Windows disk, a real iPhone | tests/test_app_match.py, test_migrate_ai.py, test_halos_export.py, test_merge_plan.py, test_iphone_photos.py |
| Quick settings; HalOS Files (2-8 ms search on 20,000 files) | ✅ measured on the dev PC · 🔧 on Plasma | tests/test_quick_settings.py, test_file_index.py, test_files_app.py |
| Living wallpaper; HalOS icon theme | ✅ preview, QML lint · 🔧 in Plasma | tests/test_living_wallpaper.py, test_halos_icons.py |
| Background desktop (no focus stolen); window tiling | ✅ with faked Xvfb/xdotool · 🔧 real | tests/test_background_and_tiling.py |
| Camera presence (opt-in) | ✅ state machine · 🔧 real webcam | tests/test_presence.py |
| UI bug list from the notes (animation, halo, screenshots) | 🔧 | tests/test_w10_*.py |
| 2.1: NVIDIA detail (NVML via nvidia-smi), per-process VRAM, SAINT GPU answers | ✅ live on RTX 5060 Ti (Windows) · 🔧 HalOS | tests/test_gpu_intel.py |
| 2.1: System Overview (per-core, NVIDIA panel, history Live–7d, failed units), system.snapshot, can_run_model | ✅ Windows run + screenshots · 🔧 HalOS | tests/test_overview_system.py |
| 2.1: Home widgets (reminders w/ snooze, tasks, PC summary, quick actions) | ✅ offscreen/test window · 🔧 full app | tests/test_home_widgets.py |
| 2.1: Model pull checks (no duplicates, fits-this-PC, real inference, CUDA vs CPU) | ✅ live smollm2:360m on CUDA | tests/test_model_verify.py |
| 2.1: SAINT avatar: your VRoid SAINT (VRM 1.0) in 3D, full body; face (blink, speech, expressions) and body animation per activity, task props, optional hologram; safe VRM/GLB/PNG import | ✅ rendered and animated on Windows (screenshots) · 🔧 on HalOS (Qt Quick 3D on the VM/GPU) | tests/test_avatar_*.py |
| 2.1: Visual Shop (10 HalOS-made items, SHA256, file allowlist, install/apply) | ✅ Windows · 🔧 Plasma apply paths | tests/test_visual_shop.py |

Test totals at this update: HalOS 2,413 passed, 6 skipped, 0 failed (Windows host, .venv); AIDE 94 passed.

---

## Before v2 (2026-11-04)

This file says what works, what is broken and what is missing, from the source code and from tests that
actually ran. "Verified" means a test or a run on real/VM hardware; "implemented" means code exists but has
not been exercised on a running Halo system yet.

## Architecture (from the code, 2026-11-02)

| Layer | What it is | Where |
|---|---|---|
| Base | **Arch Linux** (snapshot 2026/10/28) + KDE Plasma 6 on Wayland, built with **archiso**. Rebased from Fedora 44/KIWI on 2026-10-30 (user decision recorded in `plan.md` §14). The Fedora pipeline was removed on 2026-11-04 (tag `saintos-fedora-0.1.0`). User-visible name: **Halo OS**. | `packaging/arch/` |
| Packages | `[halo]` local repo built per ISO: `saint`, `halo-branding`, `halo-system` (NVIDIA choice, Flathub apps), `halo-calamares-config`, plus AUR `paru-bin`, `calamares`, `shim-signed` | `packaging/arch/pkgbuilds/` |
| GPU | `nvidia-open` + `nvidia-utils` + `lib32-nvidia-utils` + `nvidia-settings`; `halo-gpu-detect.service` loads nvidia only for Turing+ NVIDIA GPUs and blacklists nouveau only then | `packaging/arch/pkgbuilds/halo-system` |
| Installer | Calamares (Btrfs subvolumes, GRUB + os-prober for dual boot) | `halo-calamares-config` |
| Secure Boot | shim-signed (AUR) + MOK enrolment (commit f655c53); untested on hardware | `build_iso.sh` |
| SAINT | Python 3.12 (uv-managed) + PySide6 6.12 venv in `/opt/saint`, user systemd service, single instance, D-Bus `org.saintos.Saint` | `app.py`, `core/`, `modules/`, `ui/` |
| AI | Ollama (Arch `ollama` package; `saint-ollama-model.service` pulls the model in `/etc/halo/ollama-model`: `llama3.1:8b`, or `llama3.2:3b` with < 12 GB RAM and no NVIDIA GPU) or OpenAI-compatible | `modules/ai/providers.py` |
| Voice | Kokoro-82M on onnxruntime (TTS), faster-whisper base.en (STT), ONNX wake word | `modules/voice/` |
| SAINT Store (its own app, `saint-store`) | One search over SAINT's picks, Arch repos, Flathub, AUR (paru) and Windows apps (Wine); the whole catalogue to browse; an app page per app | `core/store.py`, `core/store_browse.py`, `core/store_art.py`, `core/saintos_apps.py`, `ui/store_app.py`, `ui/pages/store.py` |
| Desktop integration | KWin script `saint-shell` (Wayland placement, optional screen edge), KWin effect `saint-star`, Plasma wallpaper + widget, KGlobalAccel Alt+` | `packaging/linux/rootfs/usr/share/` |
| Phone / remote | SAINT Link (Noise IK/XXpsk3 over TCP 8765, UPnP, Tailscale addresses), iOS app `mobile/ios` (SwiftUI, ~13.7k lines), KDE Connect, KRdp | `modules/link`, `mobile/` |
| Build host | VirtualBox VM `SAINTOS-build` (Fedora live, podman, SSH 127.0.0.1:2223, repo shared in); boot tests in VMs `Halo`, `SAINTOS-*` | `packaging/linux/vm/` |
| Tests / CI | ~1,540 pytest tests (Windows host); GitHub workflows `halo-image`, `windows-release`, `mobile-ios` | `tests/`, `.github/workflows/` |

## ISO readiness

| Image | Built | Boot-tested | Result |
|---|---|---|---|
| SAINTOS 0.1 (Fedora 44) `dist/SAINTOS-x86_64.iso` | 2026-10-30 | UEFI + BIOS VM | Boots to Plasma. **This is the image that shows "SAINTOS" at boot and lacks KDE Connect** — it predates Halo. |
| Halo 0.2 `dist/halo/Halo-x86_64.iso` | 2026-10-30 16:27 | UEFI VM | **Stopped at a `systemd-firstboot` timezone prompt** (screenshot `dist/boot-test-Halo-uefi/screen-0606s.png`). Fixed in commit 818423a; not rebuilt/retested since. |
| Halo 0.2 `dist/halo/Halo-x86_64-preview.iso` | 2026-10-30 17:17 | not tested | — |
| Halo 0.2 from this branch | building — see `HALOS_TEST_RESULTS.md` | — | — |

## Reported problems: cause found in the code and state

| Problem | Cause (from the source) | State |
|---|---|---|
| Boot shows SAINTOS | Fedora 0.1 image. Halo image is branded Halo (os-release, Plymouth, boot entries). | Halo branding exists; verify on next boot test |
| SAINT says Kokoro, voice is robotic | Kokoro model files were **not in the image**; SAINT downloaded them in the background and meanwhile spoke with **espeak-ng**, while the Control Center printed the *configured* backend ("kokoro"). | **Fixed (implemented):** model ships in `/opt/saint` with pinned SHA-256; the package build fails unless Kokoro really synthesises; Voice page reports the engine actually speaking + Test buttons |
| Health checks report things installed that aren't | Voice line read config only. Ollama detection already queries the live API (`detect_ollama`). | Voice fixed; full dashboard audit is remaining work |
| `flatpak install --user` fails (Heroic) | Live ISO's write overlay is archiso's default **256 MB**; Heroic + its runtimes need ~1 GB → "No space left". Error message gave no reason. | **Fixed (implemented):** `cow_spacesize=50%`; every failed step now says why (space, network, not found, password prompt, lock, signature) in the log, the Store and the notification. Heroic install on Halo still to verify in VM |
| Store search needs Enter; clearing doesn't reset | `returnPressed` only | **Fixed:** live debounced search (350 ms), instant reset on clear, stale results discarded |
| Apps flashes Easy Install then jumps to Store | Halo page redirected the "Apps" row to the Store | **Fixed:** Apps stays on Easy Install, with a "Search every app in the Store…" button |
| Menu inside a menu | SAINT sidebar + Halo's own list side by side | **Fixed:** SAINT's sidebar folds to icons while Halo is open; Back button at the top |
| Notifications in the middle of the screen | `ActionNotice` used `move()`, which Wayland ignores, so KWin centred it | **Fixed (implemented):** placed through the `saint-shell` KWin script like the Halo |
| Halo is a cross in the middle | Halo = 4 thin edge windows placed with `move()`; on Wayland unplaced windows are centred, so they overlap into a cross | **Fixed (implemented):** on Wayland one click-through, screen-sized window per monitor paints only the edge bands (verified offscreen: centre pixel transparent) |
| Alt+` acts like Windows-Tab / does nothing | Plasma binds Alt+` to KWin "Walk Through Windows of Current Application"; KWin holds the key so SAINT's binding is dropped | **Fixed (implemented):** image ships `/etc/xdg/kglobalshortcutsrc` releasing it to SAINT; ISO validation checks it |
| Storage numbers wrong | On Linux every psutil mount was listed: the live RAM overlay as `/`, the ISO, each Btrfs subvolume again, all labelled "/:"; no unallocated space | **Fixed:** each filesystem once (by device), images/RAM filesystems skipped, live session labelled, reserved space and unallocated disk space (lsblk) shown separately |
| KDE Connect missing | Fedora 0.1 image. Halo ships `kdeconnect`. | Verify in Halo VM |
| Ollama missing | Fedora 0.1 image did not install it. Halo ships `ollama` + a model-pull service. | Verify service + inference in Halo VM |

## Not built yet (from the request)

Universal installation assistant (URL/GitHub → plan → verify), browser/desktop/iOS remote desktop
(Workstream B — design in `docs/REMOTE_DESKTOP.md`), Halo Light/Dark theme pair for Plasma, SAINT Task
Manager app (Ctrl+Shift+Esc), floating Halo widget, music widget (a Spotify mini player exists), first-run
wizard beyond the installer, OS Expansion Agent upgrades (an "Evolve" page exists: `core/evolve.py`),
dependency manager with declared per-subsystem dependencies. See `HALOS_ROADMAP.md`.

## Known limitations

- Nothing in this list has been tested on physical hardware; Secure Boot/MOK and dual boot with BitLocker need the user's laptop.
- iPhone notification mirroring of *other apps* is not possible through Apple's public APIs (ANCS over BLE is the only route and is experimental on Linux).
- iOS builds need macOS (GitHub Actions `mobile-ios.yml`); this Windows host can't compile Swift.
