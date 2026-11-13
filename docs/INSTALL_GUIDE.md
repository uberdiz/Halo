# HalOS install guide (2.2)

Step by step, from a Windows PC to a running HalOS, then keeping it up to date without reinstalling.
Short version of the requirements: 64-bit UEFI PC, 8 GB RAM (16 GB for the 8B model), **30 GB free** disk space.
Back up anything important first: HalOS is a beta. Full requirements: [INSTALL.md](INSTALL.md).

## 1. One-click install from Windows (recommended)

1. Download **HalOS-Setup.exe** from the newest release: <https://github.com/uberdiz/Halo/releases>.
2. Run it and click **Yes** on the Windows admin prompt.
3. Setup checks the PC (UEFI, Secure Boot, BitLocker, free space, RAM, internet) and says plainly if something has to change first.
4. Pick one:
   - **Install alongside Windows**: makes room in free space only. Windows and its files stay untouched.
   - **Update HalOS**: refreshes an existing HalOS (your `/home` is kept).
5. Setup downloads the image in parts, checks every SHA-256 and resumes if the network drops. Leave it running.
6. Click **Restart now**. The PC starts into the HalOS installer.
7. **Secure Boot on?** A blue *MOK management* screen shows once. Pick *Enroll MOK* → *Continue* → *Yes*, type
   the password `halo`, then *Reboot*. (If you miss it, nothing breaks: it comes back on the next start.)
8. The installer runs by itself: language, keyboard, your name and password. About 10 minutes.
9. After the restart, the boot menu lists **HalOS** and **Windows**. HalOS is the default; Windows is one arrow key away.

## 2. Install from a USB stick

1. From the release, download every `HalOS-*.iso.part*` and `SHA256SUMS`.
2. Join them: `copy /b HalOS-*.iso.part1 + HalOS-*.iso.part2 HalOS.iso` (Windows) or `cat HalOS-*.iso.part* > HalOS.iso`.
3. Check: `sha256sum -c SHA256SUMS` (or `certutil -hashfile HalOS.iso SHA256` and compare).
4. Write it with Rufus (**DD mode**), Ventoy, or `dd`. Details: [write_usb.md](../packaging/windows-host/write_usb.md).
5. Boot from the stick (F12 / F8 / Esc for the boot menu), try the live desktop, then open **Install HalOS**.

## 3. First start

1. SAINT greets you and the **What's new** tour opens once. Each card has **Try it**.
2. Settings → **Migrate from Windows** brings files, browsers, wallpapers and apps over (optional).
3. Settings → **Agents** picks a local AI model that fits your GPU/RAM.
4. If you hear nothing, say "fix the sound" (or Settings → Sound → Repair).

## 4. Updates without reinstalling

HalOS updates SAINT and the HalOS apps in place, from GitHub. The previous version is kept, so you can go back in one click.

- **Settings → Updates → SAINT**: *Check now*, then *Install*. SAINT restarts by itself (about 15 s).
- **Channel**: `beta` (default: every HalOS release, pre-releases included), `stable` (full releases only) or `dev` (the newest commit of a branch; for testing).
- **Daily check**: on by default. A notice appears when something new is out.
- **Go back**: *Settings → Updates → Go back* swaps back to the copy that was running before the last update.
- **The rest of the system** (kernel, Plasma, drivers): *Update the system now* runs `pacman -Syu` in a terminal.
- By voice: "check for updates", "update SAINT".

An image update (new kernel, boot or installer changes) still goes through HalOS-Setup.exe → **Update HalOS**, or the USB stick.

## 5. Developer hot-patch (no rebuild)

Push the code in your checkout to a running HalOS over SSH and restart SAINT there:

```powershell
tools\hotpatch.ps1 -Host 192.168.1.50 -Port 22 -User root -Key $HOME\.ssh\id_ed25519
```

```bash
tools/hotpatch.sh -H 192.168.1.50 -p 22 -u root -i ~/.ssh/id_ed25519
```

Defaults point at the test VM (`127.0.0.1:2224`). The target needs SSH as root or a user with passwordless sudo.
Files land in `/opt/saint/app`; SAINT is back about 15 s later. A later in-place update or image update replaces them.

## 6. If something goes wrong

- Boot menu → **Start from another device** lists USB sticks and Windows on every disk, plus *UEFI firmware settings*.
- SAINT → Settings → **Recovery** lists every boot device and can restart straight into one.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md), [RECOVERY.md](RECOVERY.md), [KNOWN_ISSUES.md](KNOWN_ISSUES.md).
