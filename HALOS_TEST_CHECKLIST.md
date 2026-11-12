# HalOS build 12 — what to test on the real PC

Build 12: `dist/halo/build12/Halo-x86_64.iso`, commit 1b78dc6, SHA-256 `93be857e…ec47c22`.
Tick each line; anything that fails goes into "Prompts for Claude" at the bottom, with what you saw.

## 1. Install (from the live system on HALOLIVE)
- [ ] Restart, F12, pick HALOLIVE / "HalOS (live)". Live desktop appears with no password prompt and one "Welcome to HalOS" window.
- [ ] Double-click **Install HalOS** on the desktop. The chooser offers the 200 GB free space on XF-2TB and lists C: and HALOLIVE as untouched.
- [ ] Continue, choose your name, login and password (remember it: that is the only password), Install, "All done", restart.
- [ ] The PC starts **Windows** by default (nothing to press).
- [ ] With Secure Boot on, the first F12 → **HalOS** shows the blue MokManager screen: **Enroll MOK** → Continue → Yes → password `halo` → Reboot. Not `HALO-MOK.cer`: that key is only for the live system.

## 2. Getting into HalOS while Windows stays the default
- [ ] F12 at power-on, pick **HalOS**: GRUB, then the login screen with your account; your password works.
- [ ] From Windows (Administrator PowerShell): `powershell -ExecutionPolicy Bypass -File packaging\windows-host\restart_into_halos.ps1` restarts straight into HalOS once; the restart after that is Windows again.
- [ ] In HalOS, ask SAINT "restart into Windows" (or Settings › Drives & OS): it asks, then restarts into Windows.

## 3. First login
- [ ] One Welcome window only; HalOS (Orbit) icon at the bottom-left launcher; no green dots on window icons.
- [ ] Settings › AI: the device setup picked a model for the RTX 5060 Ti with CUDA; `nvidia-smi` in Konsole shows the GPU.
- [ ] The model download finishes (notification); ask SAINT something and get an answer.
- [ ] Settings › AI: add a Claude API key; it isn't shown again in plain text.
- [ ] Voice: choose your microphone, say "Hey SAINT", hear the Kokoro voice answer.

## 4. Desktop
- [ ] Close a window: the **Supernova** close animation (never tested on real graphics before). Settings › Animations: presets, editor, preview.
- [ ] Four desktops: Ctrl+Meta+Left/Right, Meta+1..4, Meta+mouse wheel, the Pager in the panel.
- [ ] Alt+` opens SAINT's overlay; the screen-edge trigger is off until you set one in Settings › Desktop.
- [ ] Widget explorer: a HalOS category with SAINT's widgets; the SAINT widget shows the right status.
- [ ] Settings › Startup apps: add, remove and toggle an app; it survives a restart.

## 5. Store
- [ ] SAINT Store opens as its own app; home shows the full catalogue and a big featured image (Blender).
- [ ] Search is quick; results have preview images; an app page shows similar apps.
- [ ] Install something small, then Open and Uninstall; no "Installing…" left over afterwards.

## 6. Drives, Windows, migration
- [ ] Settings › Drives & OS: C:, D: and E: listed; open D: without a password; Windows system volumes read-only.
- [ ] Settings › Migrate from Windows: preview files, browser data and matched apps (Files & drives, Browser & app data, Match installed apps).
- [ ] Old Windows on E: removal: only look at the review screen. Don't confirm until you have checked what it lists.

## 7. Evolve (the OS agent)
Ask SAINT things like these and check that it shows a plan, asks before changing anything, and can undo it:
- "Add a KWin shortcut Meta+T that opens Konsole."
- "Make the panel transparent and move the clock to the left."
- "Create a startup script that mounts D: at login."
- "Install a dark color scheme with orange accents and switch to it."
- "Add a plasmoid that shows my GPU temperature."
- "Turn off the screen lock after idle." (kscreenlockerrc is not on the allowed list; it should say so or ask)
- "Change the HalOS store so the featured banner rotates every 10 seconds." (source change: worktree, plan, tests, keep or roll back)
It must refuse: sudoers, passwd/shadow, PAM, polkit, ssh and pacman configuration.

## Prompts for Claude (known issues to fix next)
- "Add a 'Start HalOS by default' switch in Settings › Drives & OS that moves HalOS before Windows in the UEFI boot order (and back)."
- "The Calamares summary page doesn't say which disk/free space HalOS goes to; show the target from the chooser."
- "AUR app pages show the source chip twice ('AUR AUR'); fix the chips in the store details/tiles."
- "The settings rail header says 'HALOS' in capitals; it should read 'HalOS'."
- "The EFI folder/boot loader id is 'Halo' while the boot entry says 'HalOS'; make them consistent without breaking installed systems."
- "airootfs.sfs is 4.13 GB, close to FAT32's 4 GiB file limit on HALOLIVE; add a build check and slim the image."
- Plus anything that failed above, with exactly what you clicked and what happened.
