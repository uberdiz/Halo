# Installing Halo next to Windows on this PC

A checklist for the owner's desktop. **No Halo or SAINT script partitions, formats or changes boot
entries for you** — you do every step, and you can stop at any checkpoint. Do the VM test first
(`packaging\windows-host\boot_test.ps1`, UEFI + BIOS PASS) and only use an ISO whose SHA-256 matches.

## This PC (read from Windows, 2026-11-04)

| | |
|---|---|
| Board | Gigabyte B450M DS3H WIFI · **Del** = UEFI setup · **F12** = boot menu |
| CPU / RAM / GPU | Ryzen 9 5900XT · 48 GB · NVIDIA RTX 5060 Ti |
| Firmware | **UEFI, Secure Boot on** (`UEFISecureBootEnabled=1`) |
| Fast Startup | **on** (`HiberbootEnabled=1`) — turn off in step 1.2 |
| Disk 0 | Seagate ST1000DM010 1 TB HDD · GPT · `D:` (data) |
| Disk 1 | XF-2TB 2280 NVMe 2 TB · GPT · **`C:` Windows, ~617 GB free** — Halo goes here |
| Disk 2 | ADATA SX6000LNP 512 GB NVMe · GPT · **EFI System Partition (100 MB)** · `E:` · Windows Recovery |

So Windows' boot files (the ESP) live on the **ADATA** disk, not on the disk with `C:`. Halo will be
installed into free space on the 2 TB disk and must put its boot loader on that **existing ADATA ESP**.
Re-check with `Get-Disk; Get-Partition` before you start — disk numbers can change when drives are
added or moved.

## 1. Prepare Windows (nothing on disk changes yet)

1. **BitLocker.** In an administrator PowerShell: `manage-bde -status`.
   - If any volume shows *Protection On* (or "Fully Encrypted"), first save the recovery key
     (Settings → Privacy & security → Device encryption, or https://account.microsoft.com/devices/recoverykey),
     then suspend it: `manage-bde -protectors -disable C: -RebootCount 3`.
   - Suspending is needed because changing boot entries makes the TPM ask for the recovery key.
2. **Fast Startup off**: Control Panel → Power Options → *Choose what the power buttons do* → *Change
   settings that are currently unavailable* → untick **Turn on fast startup**. (Or, admin:
   `powercfg /h off`.) Otherwise Windows leaves its disks half-mounted and Linux sees them read-only.
3. **Back up** anything you can't lose on `C:`. Shrinking is safe, but a backup makes it boring.
4. **ESP free space**: GRUB + shim need about 10 MB on the 100 MB ESP. Admin PowerShell:
   `mountvol S: /s; Get-PSDrive S; mountvol S: /d` — "Free" should be at least 30 MB.

## 2. Make room on the 2 TB disk (Disk Management)

1. Win+X → **Disk Management**. Find **Disk 1** (the ~1.9 TB one) and its `C:` partition.
2. Right-click `C:` → **Shrink Volume…** → amount: **204800** MB (200 GB) → Shrink.
3. You now have **200 GB "Unallocated"** after `C:`. **Leave it unallocated. Do not create or format a
   volume there** — the installer uses it.
4. If Windows offers less than 200 GB (unmovable files), run `defrag C: /O` and turn off the page file /
   hibernation temporarily, then try again; or accept a smaller size (Halo needs ≥ 40 GB).

## 3. Boot the USB stick

Write the stick as in `packaging\windows-host\write_usb.md` (Rufus, DD mode). Restart, press **F12** at
the Gigabyte logo and pick **UEFI: <USB stick>**. Leave Secure Boot **on**.

**First boot of the stick with Secure Boot — MOK enrolment (once per key).** Halo boots through the
Microsoft-signed shim; the stick's boot loader and kernel are signed with Halo's build key, which the
PC doesn't know yet, so shim shows a blue *MOK management* screen:

1. *Press any key to perform MOK management* → **Enroll key from disk**.
2. Pick the USB stick → **`HALO-MOK.cer`** (in the stick's root) → **Continue** → **Yes**.
3. **Reboot** and pick the stick again (F12). It now boots with Secure Boot on.
   If you miss the 10-second prompt, the PC reboots and shows it again.

## 4. Install (Calamares)

1. In the live desktop, open **Install Halo**. Language, keyboard, time zone as usual.
2. Partitions: choose **Manual partitioning** (the automatic choices may create a second ESP on the
   2 TB disk, which works but is not what we want here).
3. On the **2 TB disk**, select the 200 GB *Free Space* → **Create**: file system **btrfs**, mount point
   **/**, use all of it. (No swap partition needed; with 48 GB RAM pick "No swap", or "Swap to file".)
4. On the **ADATA disk**, select the existing **100 MB FAT32 EFI partition** → **Edit**:
   - Content: **Keep** (do **not** tick Format — that would erase Windows' boot loader),
   - Mount point: **/boot/efi**, flags: **boot** (already set).
   Calamares may warn that this EFI partition is smaller than its 300 MB recommendation. That is a
   warning only; GRUB + shim fit. Continue.
5. Do **not** touch `C:`, the Windows Recovery partition, `D:` or `E:`.
6. The summary must list exactly: *create btrfs on the free space of the 2 TB disk* and *mount
   the existing EFI partition at /boot/efi without formatting*. If it says anything else (format,
   delete, resize), go **Back**.
7. **Boot loader**: leave the default (GRUB on the ESP). Install, then restart and remove the stick.

## 5. After installing

- **First restart: a second MOK screen.** The installer made a key for *this PC only*
  (`/etc/secureboot/halo/`) and queued it. Shim's MokManager asks once: **Enroll MOK** → **Continue** →
  **Yes** → password **`halo`** → Reboot.
- The firmware boots **GRUB** with *Halo* and *Windows Boot Manager* entries (found by os-prober); GRUB
  remembers the last choice. SAINT's "Restart into Windows" does a one-time boot into Windows.
- Turn BitLocker protection back on in Windows if you suspended it (`manage-bde -protectors -enable C:`).
- Halo snapshots its root with snapper; the Recovery page in SAINT lists them.

## Recovery

**GRUB doesn't list Windows.** Boot Halo, open Konsole:

```bash
sudo pacman -S --needed os-prober ntfs-3g
grep -q '^GRUB_DISABLE_OS_PROBER=false' /etc/default/grub || \
  echo 'GRUB_DISABLE_OS_PROBER=false' | sudo tee -a /etc/default/grub
sudo grub-mkconfig -o /boot/grub/grub.cfg       # should print "Found Windows Boot Manager on /dev/..."
```

If it still doesn't find it, check the ESP is the ADATA one: `findmnt /boot/efi` and
`ls /boot/efi/EFI/Microsoft/Boot/bootmgfw.efi`.

**The PC boots straight into Windows (no GRUB).** F12 → pick **Halo**, or in the
UEFI setup (Del) → Boot → *Boot Option #1* = **Halo**. From Halo you can also fix the order with
`sudo efibootmgr` (list) and `sudo efibootmgr -o XXXX,YYYY` (Halo first).

**"Verification failed: (0x1A) Security Violation".** The key wasn't enrolled. On the stick: enrol
`HALO-MOK.cer` (step 3). `HALO-MOK.cer` only starts the live system. The installed system has its own key for this PC: in MokManager use
**Enroll key from disk** and pick `EFI/Halo/HalOS-this-PC.cer`. On installs made before that file existed, start HALOLIVE,
mount the installed Btrfs partition at `/mnt/h` and run `sudo mokutil --import /mnt/h/@/etc/secureboot/halo/MOK.cer`
(choose a one-time password), restart, then **Enroll MOK** with that password.

**Windows asks for the BitLocker recovery key.** Type the key you saved in step 1.1, then suspend and
resume protection once in Windows so the TPM learns the new boot path.

**Undo everything.** In Windows: Disk Management → delete the Halo btrfs partition (back to
Unallocated) → extend `C:`. Admin PowerShell: `mountvol S: /s`, delete `S:\EFI\Halo` (and only that
folder), `bcdedit /enum firmware` to find Halo's entry, `bcdedit /delete {id}`, `mountvol S: /d`.
Windows' own `EFI\Microsoft` folder is untouched by all of the above.
