# HalOS 2.2.0-beta.1: what's new and how to test it

Install: [INSTALL_GUIDE.md](INSTALL_GUIDE.md) (HalOS-Setup.exe → *Install alongside Windows* or *Update HalOS*).
Already on HalOS 2.2? Settings → Updates → SAINT → *Check now* gets later versions without reinstalling.

Each section ends with **Test:** steps. Tick them off and report anything odd with Settings → About → *Copy log*.

## Look and feel: fluid, not rigid
- Floating, rounded panel with blur. Menus and KRunner are blurred and slightly see-through. Window borders are gone;
  the soft shadow is the edge (you can still resize at the edges).
- Inter for text, JetBrains Mono for code, softer shadows, animations about 15% quicker.
- **Accent follows the wallpaper**: the accent colour across Plasma and SAINT is picked from your wallpaper
  (grey wallpapers keep the SAINT amber). Switch: Wallpaper page → *Use the glow colour as the accent everywhere*.
- **Slideshows**: Wallpaper page → *Slideshow from a folder…*, with cross-fades.
- New close animation **Fold away**: the window swells a little, then turns and shrinks away with a bright flash.
  (Supernova is still in Settings → Animations.)
- Smooth wheel scrolling in SAINT's pages.

**Test:** open and close a few windows; open the app menu and KRunner (Alt+Space), check blur; set a colourful
wallpaper and check the accent (buttons, selection) changes; try a slideshow folder; check both light and dark themes.

## Wallpapers and the Visual Shop
- Living wallpapers apply straight away (they used to need a re-login); if Plasma refuses, you see its own error.
- Installing a wallpaper also applies it.
- **Wallpaper Engine**: a new tab lists your Steam Wallpaper Engine items with previews. *Apply* uses the KDE plugin;
  *Install support* installs it if missing. Plain .mp4/.webm wallpapers play through Plasma's video wallpaper.
- The living wallpaper's visualizer is now **bars** (a mirrored row under the logo, smooth rise/decay); *ring* is
  still there (Wallpaper page → Style).

**Test:** Visual Shop → install a living wallpaper → it shows at once; switch Style bars/ring and talk to SAINT;
with Steam + Wallpaper Engine items, open the Wallpaper Engine tab → Apply.

## SAINT's avatar: a companion on the desktop
- Drag her anywhere; she remembers the spot and stays off the taskbar.
- **Desktop behaviour**: she sits on the focused window's title bar, peeks from edges, climbs, gets sleepy late at
  night or on low battery, dances with music, and invents her own moves now and then. Never over games or fullscreen.
- **Pop-in**: in *pop* mode she appears only while SAINT is doing something, next to the window it's working on,
  with a gesture that fits (typing for files, nod for sound, shrug when something fails).
- **Idle animations** every 20–60 s, **shy mode** (moves aside when the cursor comes close), glance on notifications.
- **Outfits** (midnight, sakura, forest, halo, mono, casual or your own) and the **avatar menu**: size, presence,
  behaviours, voice indicator (glow / ring / bars / off), and an animation library where you string moves together.
- She keeps clear of the living wallpaper's logo when both react to SAINT's voice.
- Say: "wave", "dance for me", "put on the sakura outfit", "make a new animation called hello with wave, nod and
  bow", "only pop in when you're doing something", "make the avatar bigger".

**Test:** drag her, log out/in (same spot); focus different apps and watch where she goes; start a game (she hides);
Settings → Avatar: change outfit, size, presence = pop, build and save an animation; try the phrases above.

## Apps
- **Files**: tabs (Ctrl+T / Ctrl+W / Ctrl+Tab, drag to reorder, middle-click closes), back/forward, a clickable
  breadcrumb (Ctrl+L to type a path), every drive in the sidebar with a capacity bar (click to mount), Details / List
  / Icons, folder sizes calculated in the background, Recent files, Space for a quick look, drag between tabs.
- **Task Manager**: processes grouped into Apps / Background / SAINT / System with totals, sortable columns, usage
  bars, *End process tree*, right-click menu, CPU and memory sparklines.
- **Downloads**: one live page for every download (browsers, Steam, models, pacman, Flatpak, Store, Visual Shop) with
  speed and time left, plus a quiet notification when a long download starts and finishes. Ask "what's downloading?".
- **Passwords** (new app): a vault kept only in the system keyring. Import from Apple Passwords (File → Export All
  Passwords → CSV), Chrome, Firefox or Bitwarden; HalOS spots a new export in Downloads, offers to import it and to
  delete the plain-text file. Copy (clipboard clears after 20 s, not kept in history), *Fill in*, 2FA codes,
  strength and reuse badges, a generator. Live iCloud Keychain sync isn't possible from Linux; re-export to refresh.
  SAINT can find a login for you but never reads out or sends a password.

**Test:** Files: open 3 tabs, drag a file between them, plug in a USB stick and open it from the sidebar.
Task Manager: sort by memory, end a test app's process tree. Download something big in the browser and watch the
Downloads page. Passwords: export from your iPhone/Mac, put the CSV in Downloads, import, copy a password, wait 20 s.

## System
- **Sound fix**: missing ALSA UCM/firmware packages added (laptops showed only "Dummy Output"). At start SAINT checks
  sound and repairs it (restarts PipeWire, picks a real output, unmutes). Say "fix the sound".
- **Updates without reinstalling**: Settings → Updates → SAINT (check, install, go back), daily check, channels.
- **Start from another device**: a GRUB submenu lists USB sticks and Windows loaders on every disk, plus firmware
  settings; SAINT's Recovery page lists every boot device with an icon. Say "boot from the USB stick" (always asks).
- **SAINT launcher**: clicking SAINT's icon now brings the window up on Plasma; helper windows stay off the taskbar.
- **AIDE** shows AIDE's own logo instead of VSCodium's.
- **What's new** tour on the first start after an update (also in SAINT's menu, or say "what's new").
- New install-screen background: soft drifting colour light.

**Test:** Settings → Sound: unplug/replug headphones and say "fix the sound"; Settings → Updates → Check now;
reboot and open *Start from another device* in the boot menu (Esc if the menu is hidden); SAINT → Recovery → list.

## Known limits in this beta
- Rounded window corners need a third-party KWin effect that breaks on KWin updates; not included yet.
- A real page-curl close effect needs a C++/GLSL KWin effect; *Fold away* uses scale, turn and brightness.
- Wallpaper Engine support depends on the community KDE plugin (AUR); some scene wallpapers may not render.
- On Secure Boot PCs, *Start from another device* can only start signed loaders.
- See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) and [../HALOS_STATUS.md](../HALOS_STATUS.md) for what's verified on real hardware.
