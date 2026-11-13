# Prompt: finish the SAINT/HalOS polish pass (branch `feat/saint-os-polish`)

Paste everything below the line into Claude Code, opened in a checkout of `github.com/uberdiz/Halo` with the
branch `feat/saint-os-polish` checked out (it is based on `halo/roadmap-2026-11`, which is 37 commits ahead of `main`
and holds HalOS 2.1, the 3D VRM avatar and the Visual Shop).

---

You're continuing work on the Halo repo (HalOS: Arch + KDE Plasma 6 on Wayland, with the SAINT assistant; Python 3.12 +
PySide6). Branch: `feat/saint-os-polish`. Follow CLAUDE.md: read only what you need, reuse existing code, make real
changes, keep AI for intent and deterministic code for execution.

## Hard constraints
- **Do NOT build anything**: no ISO, no makepkg, no Docker, no build VM, no AIDE build. Verify only with
  `python -m py_compile` on changed files, targeted `pytest` (tests/; the KWin/Plasma JS tests run under node), and
  headless imports (`QT_QPA_PLATFORM=offscreen`). The person runs the build on their main PC.
- Commit in small logical commits on `feat/saint-os-polish`, push it, and open (or update) a PR into
  `halo/roadmap-2026-11`. Never force-push; never touch `main`.
- Add a HALOS_CHANGELOG.md entry and update HALOS_STATUS.md. Anything that needs HalOS/hardware to verify goes in
  HALOS_STATUS.md as 🔧 "unverified", never silently skipped.
- Pick up the "Already done" section below as working code: extend it, don't redo it.

## Already done on this branch (commit 1)
- **Avatar couldn't be dragged** (root causes): the 3D `QQuickWidget` covered the whole window in full-body view and
  ate every mouse press, and on Wayland `QWidget.move()` is a no-op. Fixed in `ui/avatar/__init__.py`: the scene is
  transparent to mouse; on Wayland a press calls `windowHandle().startSystemMove()`; the window is placed with
  `ui/placement.wayland_place(..., "SAINT Avatar")` (which also sets skipTaskbar/keepAbove through the KWin script).
- **KWin `saint-shell` script reports back over D-Bus** (`core/saint_dbus.py`): `PlacedMoved("name|x,y")` when a SAINT
  helper window is dropped (the avatar remembers its position), `ActiveWindow("class|x,y,w,h")` on focus changes.
  Both arrive as Qt signals on `core.saint_dbus.desktop_events` (`placed_moved`, `active_window`).
- **Animation clips** `core/avatar/clips.py`: JSON keyframe clips that override parts of the body pose (arms, head,
  spine, hips turn, legs, hop, scale), 24 built-in primitives (wave, nod, bow, stretch, yawn, cheer, clap, point,
  hop, spin, dance, think, shrug, typing, sit, sit-swing, climb, peek, pop-in, sleepy ...), `compose()` to build a
  new clip from primitive names, validation/clamping, save/load in `<data_dir>/avatar_clips/`.
- `core/avatar/body.py`: `BodyDriver.step(..., clip_pose=...)`, leg bones and hip turn.
- `AvatarView.play_clip(name|dict)` / `stop_clip()`; right-click menu on the avatar: Play animation ▸ (every clip),
  Stop, Customize avatar… (opens `saint --page Avatar`), Hide.
- **Behaviour engine** `core/avatar/behavior.py` (not wired into the UI yet): `BehaviorEngine.next(Context)` →
  `Beat(clip, anchor, seconds, reason, new_clip)`; anchors stay/titlebar/edge/peek/corner/hidden;
  `anchor_point()` turns an anchor + focused-window geometry into a screen position; it builds its own clips now and
  then via `clips.compose`. Deterministic per seed.
- Tests: `tests/test_avatar_clips_behavior.py` (155 avatar/desktop/D-Bus tests pass).

## Findings you can rely on (already investigated)
- Visual Shop install of the living wallpapers works (sha256s match the LF files). The failure is in **apply**:
  `ui/settings_pages/wallpaper.py plasma_script()` writes config but never calls `d.reloadConfig()`, and `apply()`
  swallows qdbus' stderr so the user only sees "Plasma didn't accept". Also Install doesn't apply: the person expects
  installing a wallpaper to show it.
- Audio: `packaging/arch/profile/packages.x86_64` has pipewire/-pulse/-alsa/wireplumber/sof-firmware but **no
  `alsa-ucm-conf`** (SOF/UCM cards then show only "Dummy Output") and no `alsa-utils`.
- AIDE branding: AIDE is built from `uberdiz/AIDE` (aide-2.0) by `packaging/arch/pkgbuilds/aide/PKGBUILD`. The
  extension's activity-bar icon `extensions/aide-core/media/aide-activity.svg` is literally an "A" and a "+"; the
  title-bar logo is VSCodium's `resources/app/out/media/code-icon.svg` (also `letterpress-*.svg`,
  `resources/app/resources/linux/code.png`). Fix in the PKGBUILD's `package()` (find + replace those files with
  AIDE art, e.g. `extensions/aide-core/media/AIDE.svg` / `AIDE_Logo.png`, and a monochrome `currentColor` mark for
  the activity bar), or note that the proper fix belongs in the AIDE repo.
- Recovery: `core/recovery.py` already lists every UEFI entry (`boot_entries`) and has firmware restart; the
  SAINT Recovery page is in `ui/saintos_center.py` (~line 860). The GRUB menu has no "boot another device" entry.
- Close animation: the KWin scripted effect `packaging/linux/rootfs/usr/share/kwin/effects/saint-star/contents/code/main.js`
  can only animate scale/opacity/brightness/rotation; its built-ins must stay equal to `core/window_anim.py`
  (checked by `tests/test_halos_desktop.py`).
- Downloads: `core/downloads.py` already detects model pulls, pacman/paru/flatpak, browser partial files and
  Steam; it has no ETA, no live UI view of its own and no toasts.
- Secrets already go through `keyring` (KWallet / Secret Service): see `core/config.py` and `core/paths.py`.
- `saint` (no args) sends `show` to the running SAINT (`app.py`, `ui/main_window.py` ~line 400, with the Wayland
  activation token); verify why clicking the SAINT launcher doesn't bring the window up on Plasma.

## What's left, in this order

### Bug fixes
1. **Avatar ↔ wallpaper voice visual overlap**: when both the avatar and the living wallpaper (source "saint") react
   to SAINT's voice, keep them apart: the avatar avoids the wallpaper logo's rectangle (LogoX/LogoY/LogoScale from the
   wallpaper settings) when placed or dropped, or the wallpaper hides its visualizer while the avatar is on screen.
   Add a test.
2. **No audio**: add `alsa-ucm-conf alsa-utils alsa-firmware` to `packages.x86_64` (and a `validate_iso.sh` check);
   add `core/audio_doctor.py` run once at SAINT start on Linux: `wpctl status`/`pactl` → if the default sink is
   missing or "Dummy Output", restart `wireplumber pipewire pipewire-pulse` (user units); unmute and raise a 0%
   default sink; prefer a real analog/HDMI sink with an available port. Expose as action `audio.repair`. Tests with
   faked command output.
3. **AIDE branding** (see findings).
4. **Visual Shop**: `d.reloadConfig()` in the plasma script; surface qdbus stderr; Install also applies wallpapers
   and living wallpapers when it can. **Wallpaper Engine integration**: new `core/wallpaper_engine.py` that finds
   Steam Wallpaper Engine workshop items (`~/.local/share/Steam/steamapps/workshop/content/431960/<id>/project.json`:
   title, preview, type scene/video/web), lists them in the Visual Shop (own category/tab with previews), and applies
   one through the KDE plugin `com.github.catsout.wallpaperEngineKde` (AUR `wallpaper-engine-kde-plugin`, Plasma 6)
   via the same plasmashell script mechanism, or `linux-wallpaperengine` as a fallback; a clear message + an
   "Install support" button (through the existing package queue, `core/pkg_queue.py`) when neither is installed.
   Video wallpapers (.mp4/.webm) without Wallpaper Engine: Plasma's own video wallpaper if present.
5. **SAINT not in the taskbar, launcher opens SAINT**: the background SAINT must not show a taskbar entry (check every
   top-level SAINT window that's visible at login: the avatar is now fixed; check the Halo frame, overlay, toasts on
   Wayland where `Qt.Tool` doesn't hide from the taskbar); clicking the SAINT icon (taskbar pin / launcher /
   `saint.desktop`) must bring the main window up. Find why `show` doesn't raise it on Plasma Wayland and fix.
6. **Task manager** (`ui/taskmanager.py`, ~860 lines): readability — larger row height, clear column headers,
   grouped (Apps / Background / SAINT / System), sortable, aligned numbers with units, usage bars in CPU/RAM columns,
   better contrast in both themes. Keep the existing actions.

### Features
7. **Close animation** "enlarge, then shrink while the edges curl and fold in": a new preset in saint-star + matching
   `core/window_anim.py` default (grow ~1.06 then shrink to ~0 with rotation and a brightness edge flash). A real
   page-curl/fold needs a C++ KWin effect or a GLSL-capable effect: note it in HALOS_STATUS as follow-up.
8. **Wallpaper visualizer as classic bars `||||||||`**: in
   `packaging/linux/rootfs/usr/share/plasma/wallpapers/org.halos.living/contents/ui/main.qml` add a `BarStyle`
   config ("bars" default: a row of vertical bars mirrored around a baseline under the logo; "ring": today's radial
   one), declare it in `contents/config/main.xml`, `clean()` it in `ui/settings_pages/wallpaper.py`, and offer it on the
   Wallpaper settings page and in the preview.
9. **File manager** (`ui/files_app.py`): Windows-Explorer-like. Tabs (QTabWidget; Ctrl+T/Ctrl+W/Ctrl+Tab, reorder,
   middle-click close), back/forward/up + breadcrumb bar, sidebar with Quick access + **every drive** (internal,
   removable, plugged-in; `core/drives.volumes()`, refreshed on udisks changes or a timer) with capacity bars and
   mount on click, details/list/large-icons views, **folder sizes** computed in a QThreadPool with a cache (never
   blocking the UI), richer icons (HalOS icon theme), keep the preview pane and the search and keep every change going
   through `core/actions` `files.*`.
10. **Recovery**: in SAINT's Recovery page show every boot device (not only "other systems"), with icons for
    USB/disk/network/Windows, plus "Restart into UEFI settings" (exists). In GRUB (installed system,
    `halo-calamares-config`) add a `/etc/grub.d/42_halo_devices` submenu "Start from another device" that at boot
    lists `(*)/EFI/BOOT/BOOTX64.EFI` and `(*)/EFI/Microsoft/Boot/bootmgfw.efi` with `insmod regexp` and chainloads the
    chosen one, plus `fwsetup`. Same in the live ISO's GRUB config.
11. **Universal download detector**: add ETA and a live Downloads window/panel (2 s refresh while open), toasts when a
    download starts/finishes (low frequency, deduplicated), Flathub progress via `flatpak` output, the Visual Shop and
    Store installs as sources, and `downloads.summary()` for SAINT.
12. **Installer welcome background** like the ChatGPT desktop welcome screen: soft, blurred colour orbs (blue,
    green, peach) slowly drifting on a light background — not literal sunrays. Add it to `ui/install_chooser.py`
    and the install assistant screens (QPainter radial gradients, ~30 fps, paused when hidden, still frame with
    reduce motion). If HalOS-Setup.exe (`packaging/windows-host/setup/HalOSSetup.cs`, WinForms) can get it cheaply,
    do it there too.

### Avatar / SAINT overhaul (build on what's done)
13. **Wire the behaviour engine** into `FloatingAvatar`: a timer runs `BehaviorEngine.next()` with context from
    `desktop_events.active_window`, the hour, idle time (KDE idle via `org.freedesktop.ScreenSaver` GetSessionIdleTime
    or `kwin` idle), music playing (`ui_bus.now_playing()`), game mode (`core.game_mode`), SAINT busy state. Move to the
    beat's anchor with `anchor_point()` (animate the move in ~15 steps through `_set_pos`; climbing = walk `progress`
    0→1 while the "climb" clip plays), play the beat's clip, keep new clips SAINT built. Setting `avatar.behaviors`
    (default on) and never during games/fullscreen.
14. **Pop-in on actions**: setting `avatar.presence` = "always" | "pop". On `ACTION_STARTED` / `TOOL_STARTED` /
    `PLAN_STARTED` the avatar pops in (the "pop-in" clip + window fade) near the action's target (`ACTION_TARGET`
    gives the window), plays a gesture per action category (audio.* → nod, files.* / code → typing,
    apps.* → point, power.* → wave, failures → shrug), then fades out after a few seconds in "pop" mode.
15. **Idle animations**: when nothing else plays, a random idle clip every 20–60 s (stretch, look around, sit-swing,
    yawn at night), setting `avatar.idle_animations`.
16. **Outfits + customization menu**: `avatar.outfit` with presets in `data/avatars/outfits.json` (tints for VRoid
    material groups CLOTH/Tops/Bottoms/Shoes/HAIR/Accessory, hide accessories), applied in `ui/avatar/avatar3d.qml`
    (store each material's original `baseColor`, multiply the tint); the Visual Shop's "outfit" category applies an
    outfit .json or an outfit .vrm. Extend `ui/settings_pages/avatar.py` into the central menu: outfit, size (raise
    SIZE_MAX), presence, desktop behaviours, idle animations, voice indicator style (glow/ring/bars/off), animation
    library (play, delete, create from primitives in order, save). Add the new keys to `core/avatar.settings()` with
    clamping and to `core/config.py` defaults.
17. **SAINT capabilities**: register actions (`core/actions/sets/*.py`, `register(registry)`, with risk levels so the
    existing approval flow applies) and plain-phrase intents for: `avatar.play` (clip), `avatar.create_animation`
    (name + primitive list → compose + save: the model only picks names), `avatar.set` (outfit/size/placement/
    presence/behaviours), `files.open` (path, new tab), `downloads.list`, `wallpaper.apply_engine`,
    `recovery.boot_device` (DESTRUCTIVE, always asks), `recovery.firmware_settings` (DESTRUCTIVE), `audio.repair`,
    `taskmgr.open`, `passwords.*` (below). Update `docs/ACTIONS.md`.

### New: Passwords app (asked for later)
18. **HalOS Passwords** (`ui/passwords_app.py`, `core/passwords.py`, launcher `halos-passwords.desktop`, icon):
    - Vault stored only in the system keyring (`keyring` → KWallet/Secret Service, like `core/config.py` secrets):
      one JSON blob under a dedicated service, never written to disk in plain text, never logged.
    - **Sync from Apple Passwords**: Apple has no Linux/Windows sync API. Implement a repeatable import of Apple's
      export (Passwords app → File → Export All Passwords → CSV; columns Title, URL, Username, Password, Notes,
      OTPAuth) that merges by (site, username): adds new, updates changed, keeps local-only ones, reports counts.
      Watch Downloads for a new `Passwords*.csv` and offer to import it, then offer to delete the CSV (it's plain
      text). Also accept Chrome/Firefox/Bitwarden CSV. Say plainly in the UI that live iCloud Keychain sync isn't
      possible from Linux; on Windows, iCloud for Windows' Passwords app is the live option.
    - Easy input: search box, list with site icons, "Copy username", "Copy password" (clipboard cleared after 20 s,
      marked `x-kde-passwordManagerHint: secret` so Klipper keeps no history), "Fill in" (types username, Tab,
      password into the previously focused window through the existing desktop typing helper,
      `modules/desktop/controller.type_text`), TOTP codes from OTPAuth, reveal on demand only.
    - SAINT actions `passwords.find` (returns site/username only, never the password), `passwords.fill` (RISKY,
      asks), `passwords.import` (path). SAINT never speaks or sends a password to a model.
    - Tests: CSV parsing (quotes, commas, BOM), merge rules, the keyring store with a fake keyring.

## Output
Push the branch, open/update the PR into `halo/roadmap-2026-11`, then reply with: CHANGED / FIXED / TESTED /
REMAINING (what needs a HalOS build or hardware to verify, and why).
