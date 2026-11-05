# Writing the Halo ISO to a USB stick (Windows)

You need: `dist\halo\Halo-x86_64.iso` and `dist\halo\SHA256SUMS` from `build_iso.ps1`, and a USB stick of
8 GB or more. **Everything on the stick is erased** (Rufus), or the stick is reformatted once (Ventoy).

## 1. Verify the ISO first

A truncated copy writes fine and then fails to boot (build 7, see `HALOS_TEST_RESULTS.md`). Always compare:

```powershell
Get-FileHash -Algorithm SHA256 dist\halo\Halo-x86_64.iso
Get-Content dist\halo\SHA256SUMS
```

The two hex strings must be identical. `build_iso.ps1` and `boot_test.ps1` already do this check.

## 2a. Rufus (simplest, one ISO per stick)

1. `winget install -e --id Rufus.Rufus`, start Rufus.
2. **Device**: the USB stick. Check the size; it must not be one of your internal disks.
3. **Boot selection**: SELECT → `Halo-x86_64.iso`.
4. Partition scheme **GPT**, target system **UEFI (non CSM)** (this PC boots UEFI).
5. START. When Rufus asks *"ISOHybrid image detected"*, choose **Write in DD Image mode**.
   (ISO mode copies files and can break the archiso/shim boot; DD writes the image byte for byte.)
6. Confirm the "all data will be destroyed" warning, wait for READY, then eject the stick in Explorer.

## 2b. Ventoy (keeps several ISOs on one stick)

1. `winget install -e --id Ventoy.Ventoy`, run `Ventoy2Disk.exe`.
2. Option → Partition Style → **GPT**; Option → **Secure Boot Support** on (this PC has Secure Boot on).
3. Pick the USB stick, **Install** (erases it once). Later updates use **Update** and keep your ISOs.
4. Copy `Halo-x86_64.iso` onto the big Ventoy partition like a normal file, then eject.
5. First boot with Secure Boot: Ventoy shows its own MOK enrolment screen once
   (Enroll key → `ENROLL_THIS_KEY_IN_MOKMANAGER.cer` on the stick → reboot). Halo's own shim then asks
   for its key on the first Halo boot as well (`HALO-MOK.cer`; see `docs/INSTALL_ON_THIS_PC.md`).

If Ventoy misbehaves with Halo (menu loops, black screen), write the stick with Rufus DD mode instead:
that is the tested path.

## 3. Verify the stick (optional, Rufus DD only)

Read the image back and compare the hash of the first *ISO-size* bytes. In an **administrator**
PowerShell, with `N` the stick's disk number from `Get-Disk` (check twice: FriendlyName and size):

```powershell
$iso = "dist\halo\Halo-x86_64.iso"; $len = (Get-Item $iso).Length; $N = 3
$in = [IO.File]::OpenRead("\\.\PhysicalDrive$N"); $sha = [Security.Cryptography.SHA256]::Create()
$buf = New-Object byte[] (4MB); $left = $len
while ($left -gt 0) { $n = $in.Read($buf, 0, [Math]::Min($buf.Length, $left)); if ($n -le 0) { break }
  [void]$sha.TransformBlock($buf, 0, $n, $null, 0); $left -= $n }
[void]$sha.TransformFinalBlock($buf, 0, 0); $in.Close()
-join ($sha.Hash | ForEach-Object { $_.ToString("x2") })      # must equal SHA256SUMS
```

This only reads the stick. (Raw disk reads must be whole sectors; ISO images are a multiple of 2048
bytes, so every read above stays aligned.)

## 4. Boot it

Restart, press **F12** at the Gigabyte logo (boot menu; **Del** opens the setup), choose the entry
**UEFI: <your USB stick>** (not the one without "UEFI"). Continue with `docs/INSTALL_ON_THIS_PC.md`.
