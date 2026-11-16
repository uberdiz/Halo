# HalOS 2.3.0-beta.2: Evolve from your PC, linked PCs share Evolve, avatar and desktop fixes

Install: [INSTALL_GUIDE.md](INSTALL_GUIDE.md). **Another computer:** download HalOS-Setup.exe and the three
`Halo-x86_64.iso.part*` files below (Setup joins and checks them), or join them yourself:
`copy /b Halo-x86_64.iso.part1+Halo-x86_64.iso.part2+Halo-x86_64.iso.part3 Halo-x86_64.iso` and compare the
SHA-256 with SHA256SUMS. Already on HalOS? HalOS-Setup.exe → *Update HalOS*.

## Evolve
- Everything Evolve built on the HalOS PC is in: the new Evolve app (notes in sections with search and
  deselect-all, saved chats + History, usage ring, a movable activity widget, local models), Meta+N drag-to-
  screenshot notes, Meta+S (SAINT), Meta+A (AIDE), "how is Evolve doing?" and "note this for Evolve".
- One Meta+N launcher (two tools both held Meta+N). Missing Alt+` / Meta+N / Meta+A are added and work at once.

**Test:** Meta+N → drag over something → write a note → it's in Evolve's Notes. Alt+`, Meta+S, Meta+A.

## Linked PCs share Evolve
- SAINT Link now also syncs SAINT Vault (notes, Fix notes with screenshots, Evolve runs and lessons) and Evolve's
  saved chats between your own PCs.

**Test:** link two PCs (Devices), write a Meta+N note on one → it appears in Evolve's Notes on the other.

## Avatar
- Dropped on a window in front of a bigger one, she stays on the one you dropped her on (no floating off-screen).
- Her eyes follow the pointer on Wayland.
- "Come over here", "go to my window", "go back to your corner".

## Desktop
- The Halo lights the whole border while SAINT is active, on every monitor.
- Mini player follows any app (YouTube in a browser, VLC, mpv, Spotify): the one playing longest, or the one you
  pick in its dropdown; play/pause/skip/volume.
- Settings → Desktop → Taskbar: height and edge.
- The login screen runs on KWin Wayland: no black gap between the login screen and the desktop.
- Installer's last page names the disk and the free space HalOS goes into.
- "Download and install X. It may be …" installs X (several apps: one question) instead of a long reply.

## Phone from anywhere
- Tailscale is in the ISO and SAINT Store; TeamViewer via Devices → *Screen via TeamViewer*.
  Steps: [REMOTE_DESKTOP.md](REMOTE_DESKTOP.md#test-your-pc-screen-on-your-phone-from-anywhere-teamviewer--tailscale).

Left for Evolve (open notes in SAINT Vault › Fix): mini player above fullscreen apps, seasonal outfits, camera,
smart lights, Alt+Tab speed, Sober cursor, YouTube chat taken as a command, clipboard button, Windows history merge.
