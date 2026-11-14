# Halo OS changelog

## 2026-11-14 — HalOS 2.3.0-beta.1: SAINT comes alive (avatar, sound, smarter chat, no interruptions)

What's new, with test steps: [docs/RELEASE_NOTES_2.3.md](docs/RELEASE_NOTES_2.3.md).

- The Halo is its own app (halos-halo): the SAINT taskbar icon opens SAINT.
- Avatar: animations hold, pop-in, "Hey SAINT" rise from the taskbar, sits on windows, dances on music, walks, cursor/typing gaze, habits, head-and-shoulders framing, menu view toggle, ~20 s wake-free follow-up.
- Never steals focus (KWin hand-back, desktop guard); chat via Claude Haiku when signed in, better local knowledge, fresh conversations, no transient memories.
- Sound: NVIDIA HDMI/DP kept on, Bluetooth A2DP defaults, Settings › Sound mixer, a repair that really repairs.
- Evolve: prompt on stdin, Claude Code sign-in, Obsidian preinstalled, SAINT Vault.
- SAINT star open/close fixed, animation profiles with Save/Revert, honest What's New with a popup, living wallpaper packaged, SAINT Visualizer widget, HalOS Wallpapers app.
- Migration file picker, custom Quick add, keep-going with Retry, Wallpaper Engine; Print drags a region; Downloads & Trash in Files; readable Task Manager; dark Setup.exe with animated rays.

## 2026-11-14 — HalOS 2.2.0-beta.1: the polish pass (fluid look, avatar companion, new apps, live updates)

What's new, with test steps: [docs/RELEASE_NOTES_2.2.md](docs/RELEASE_NOTES_2.2.md). Install: [docs/INSTALL_GUIDE.md](docs/INSTALL_GUIDE.md).

- Look: floating blurred panel, blurred translucent menus, borderless windows with soft shadows, Inter/JetBrains Mono,
  quicker animations, accent picked from the wallpaper, wallpaper slideshows, "Fold away" close animation (default).
- Wallpapers: living wallpapers apply at once (reloadConfig) and show Plasma's own error; Install applies; Wallpaper
  Engine tab (KDE plugin, linux-wallpaperengine fallback, Install support); bar-style visualizer (default) or ring.
- Avatar: behaviour engine wired to the window (title bars, edges, climbing, sleepy, music, games/fullscreen hide),
  pop-in on actions with gestures, idle animations, shy mode, outfits, one avatar menu with an animation library,
  keeps off the wallpaper logo; actions avatar.play / avatar.create_animation / avatar.set.
- Files: tabs, breadcrumb + typed paths, every drive with capacity and mount, views, background folder sizes, quick
  look, drag between tabs, single window. Task Manager: grouped, sortable, usage bars, End process tree, sparklines.
  Downloads: ETA, live page, Store/Flathub/Visual Shop sources, rare toasts.
- Passwords app: keyring-only vault, Apple/Chrome/Firefox/Bitwarden CSV import and merge, Downloads watcher, fill in,
  TOTP, strength/reuse badges, generator; SAINT finds logins but never reads passwords.
- System: alsa-ucm-conf/alsa-utils/alsa-firmware + audio doctor (audio.repair); in-place SAINT updates with rollback
  (beta channel default) and dev hot-patch (tools/hotpatch.*); GRUB "Start from another device" + every boot device
  in Recovery; SAINT launcher raises the window on Wayland; AIDE logos; installer welcome background; What's new tour.
- SAINT 0.5.0.

## 2026-11-13 — SAINT avatar: drag, animations, desktop behaviour (`feat/saint-os-polish`, part 1)

- The avatar can be dragged again: the 3D scene no longer swallows clicks, and on Wayland the drag is KWin's own
  move; the saint-shell script reports where she landed (D-Bus `PlacedMoved`) so the spot is remembered. She's
  placed through the script, so she no longer shows up on the taskbar.
- Animation clips: 24 built-in moves (wave, nod, stretch, climb, sit, dance, peek, pop-in, ...) and a builder that
  strings them into new animations; right-click the avatar → Play animation.
- Behaviour engine (core only, not wired to the window yet): picks what she does from the focused app, time of day,
  idle time and music, and builds her own moves now and then.
- The rest of the pass is written up as a ready prompt: `docs/NEXT_PROMPT_saint_os_polish.md`.

## 2026-11-09 — Secure Boot, found on the real PC (build 13)

- MokManager's prompt waits for you: when its 10 seconds ran out, shim dropped the queued key and every later start
  ended in 0x1A.
- The install leaves this PC's public key at `EFI/Halo/HalOS-this-PC.cer` for **Enroll key from disk**, and the installer
  says `HALO-MOK.cer` is only for the live system.

## 2026-11-07 — found by a clean install test of build 11

- The SAINT widget and the Halo widget show SAINT's own status ("Microphone off") instead of "SAINT isn't
  running" when SAINT runs without a microphone.
- No automatic model download in the live session (it went into RAM); installed systems still download.
- Two fallback pacman mirrors next to geo.mirror.pkgbuild.com, live and installed.
- `prepare_disk_boot.ps1 -Refresh` finds the ESP-typed HALOLIVE partition and checks its label before formatting.
- Windows stays the default after installing HalOS (Windows Boot Manager first, HalOS second in the firmware's
  boot order); HalOS starts from the boot menu (F12) or `packaging/windows-host/restart_into_halos.ps1` (one-time).

## 2026-11-06 — desktop behaviour (`halos/desktop`)

- The screen edge that opens SAINT's overlay is off by default; any edge or corner plus a hover delay in Control
  Center's Desktop page, live. The top-edge tab no longer appears on Linux.
- Four desktops, Ctrl+Meta+Left/Right, Meta+1..4, Meta+wheel, a Pager in the panel.
- Animations page: presets for open, close, minimize, desktop switch, sliders, preview, custom JSON animations.
  Default close is Supernova. `ReducedMotion` now really works: `saint-star` had no `config/main.xml`, without
  which KWin's `readConfig` ignores kwinrc.
- Startup apps page; SAINT's widgets are under their own HalOS category in the widget explorer.
## 2026-11-06 — install to free space, drives, OS switching, Windows migration (`halos/migration`)

- **Live session:** a banner on Storage and Overview says the free space is RAM and nothing is kept, shows the detected
  unallocated space and has an Install HalOS button. The Storage row reads "free in RAM, not on disk".
- **Install to free space** (`core/install_target.py`, `ui/install_chooser.py`, Calamares job `halotarget`): a new 512 MiB
  EFI partition and a Btrfs root in the free region; existing partitions and EFI partitions are never touched.
- **Drives** (`core/drives.py`, Storage, settings page Drives & OS): every partition with Open, Mount and Unmount through
  udisks; Windows system volumes read-only by default; Fast Startup and BitLocker explained.
- **Restart into Windows** (`core/os_switch.py`, helper `halo-efiboot`, polkit action `org.halos.efiboot`, voice tool
  `system.restart_into`, which always asks).
- **Migrate from Windows** (`core/windows_migration.py`, wizard settings page): files linked or copied, bookmarks,
  wallpaper, VS Code, app matching, and a separate final step removing an old Windows.
- Secure Boot's one-time MOK password screen now only appears when Secure Boot is on.
## 2026-11-06 — settings and AI for this PC (`halos/settings-ai`)

- **One settings window**: one rail with a HalOS group and a SAINT group, behind both sidebar items and `saintos-control`,
  with search across every page. The duplicate AI, Voice and permission controls are gone (their functions moved to the
  one remaining page). KDE System Settings stays KDE's, linked from Plasma settings.
- **Models for this PC** (`core/device_profile.py`, `core/provision.py`): at first boot online, in the installed system
  only, HalOS picks an Ollama model, Whisper model and compute type for the hardware and free disk, and downloads them
  (resumable, retries without a network). Settings you changed stay yours.
- **CUDA at first boot, NVIDIA PCs only**: `ollama-cuda` + `cuda` (3 GB download, 6.1 GB installed) and Whisper's CUDA 12
  libraries (1.4 GB download, ~3 GB). The ISO keeps the 20 MB CPU `ollama`. Kokoro stays on the CPU by design. Health's
  "AI on the GPU" proves each engine by running it; a failed setup falls back to the CPU and says why.
- **Claude**: native provider (streaming, tools), API key on the AI page (masked, Test, Remove, secret store only).
  Evolve uses the saved key for Claude Code when you aren't signed in.

## 2026-11-02 — build 7 features (`halo/arch-rebase`)

- **SAINT Task Manager** (`saint-taskmgr`, Ctrl+Shift+Esc, menu: System): Processes (search, sort, end task /
  end now, warning before ending a process the desktop or system needs), Performance (CPU model, speed,
  temperature; memory and swap; each GPU through nvidia-smi or the kernel's DRM files; each disk's activity;
  each network adapter's throughput), App history (CPU time since each app started), Startup apps
  (enable/disable for your user), Users, Services (systemd; system services ask for the password), System
  information (OS, kernel, board, firmware, uptime, battery health, disk SMART health when readable).
  Runs as its own small process, refreshes only the visible page.
- **Halo widget** (`org.saintos.halo`): a movable, resizable animated ring for the desktop; opacity,
  thickness, speed, animation on/off (also still when Plasma's animations are off); follows SAINT's state
  when SAINT runs; click to talk.
- **SAINT Music widget** (`org.saintos.music`): any MPRIS player (Spotify, Firefox, VLC…) through playerctl:
  artwork, track, artist, album, progress with seeking, volume, play/pause/previous/next. On the default
  desktop under the SAINT widget.
- **Halo Dark (default) and Halo Light**: Plasma colour schemes generated from SAINT's own palette
  (`packaging/linux/branding/make_color_schemes.py`), a light/dark look-and-feel pair wired to Plasma's
  light/dark switch, and SAINT following the desktop theme on Linux.
- ISO validation checks the shortcut, launcher, widgets and themes.
- **Halo apps redesign** (frontend-design pass, SAINT's palette kept): one shared left rail for Task Manager and
  Control Center/Halo (icons, current page marked in orange); Task Manager processes heatmap (busy CPU/memory/
  disk cells tinted), column totals in the header, monospace numbers; Performance as device tiles with
  sparklines plus a large gridded graph and stat grid; Voice status shown as a sheet with state marks.


## 2026-11-02 — audit and Priority 1 repairs (`halo/arch-rebase`)

Voice
- Kokoro-82M (onnxruntime) model files ship in the `saint` package with pinned SHA-256; the package build
  fails unless Kokoro synthesises speech from the packaged files. First boot speaks with Kokoro, not espeak-ng.
- New `core/voice_check.py`: the engine actually speaking, model path, runtime, audio output, microphone,
  Whisper model, last test results. Halo → Voice shows it and has **Test Kokoro voice** (synthesise + play)
  and **Test Whisper** (record 4 s + transcribe). A result is "passed" only when that happened.

Store and installs
- Live search as you type (debounced), clearing the box restores the picks at once, older results can't
  overwrite newer ones, filters only re-filter real search results.
- Every failed install step says why (out of space, network, unknown app, password prompt cancelled,
  pacman busy, permission, signature, conflict) in the log, the Store, Easy Install and the notification.
- Live ISO write overlay raised from archiso's 256 MB default to 50 % of RAM (`cow_spacesize`), which is
  what made Flatpak installs such as Heroic fail in the live session.

Desktop
- Halo on Wayland: one click-through window per screen paints only the edge bands, so it can't end up as a
  cross in the middle when KWin ignores client positions.
- SAINT's action notifications are placed through the `saint-shell` KWin script on Wayland (bottom centre),
  instead of `move()`, which Wayland ignores.
- Alt+` is released from KWin's "Walk Through Windows of Current Application" in the image
  (`/etc/xdg/kglobalshortcutsrc`), so it opens SAINT's overlay instead of switching windows.

SAINT UI
- Halo section: Back button at the top, SAINT's sidebar folds to icons so Halo's list is the only left
  navigation, Apps no longer jumps to the Store (Easy Install stays, with a link to the full Store).

Storage
- Linux: each mounted filesystem once (Btrfs subvolumes share a device), no ISO/EROFS/RAM filesystems, live
  session labelled "in memory", reserved space in the tooltip, unallocated disk space (lsblk) listed
  separately from free space.

Docs
- `HALOS_STATUS.md`, `HALOS_ROADMAP.md`, `HALOS_TEST_RESULTS.md`, `docs/REMOTE_DESKTOP.md` (Workstream B design).
