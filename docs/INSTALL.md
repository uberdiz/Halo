# Installing HalOS

> HalOS is **beta**. Back up anything important first. See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for what has not been verified.

## Requirements
| | Minimum | Recommended |
|---|---|---|
| Firmware | UEFI (64-bit) | UEFI with Secure Boot (shim + MOK enrolment) |
| CPU | x86-64, 4 cores | 8 cores |
| RAM | 8 GB (3B local model) | 16 GB+ (8B local model) |
| Disk | **30 GB free** unallocated or shrinkable (installer refuses less) | 100 GB+ for local models and games |
| GPU | any (CPU inference works, slower) | NVIDIA Turing (RTX 20) or newer, 8 GB+ VRAM |

Local AI needs no account. Cloud features (Claude Code agent mode) need your own Claude subscription sign-in. See [PRIVACY.md](PRIVACY.md).

## Option A — from Windows: HalOS-Setup.exe
1. Download `HalOS-Setup.exe` from the latest GitHub release.
2. Run it. It downloads the ISO parts, joins them and checks every SHA256 (resumable).
3. Choose **Install alongside Windows** (shrinks free space only; never touches the Windows or EFI partitions' contents) or **Update** an existing HalOS (keeps `/home`).
4. Restart. If Secure Boot is on, the blue MOK screen appears once: *Enroll MOK → Continue → Yes*, password `halo`.

## Option B — USB stick
1. Download the ISO parts and `SHA256SUMS` from the release; join: `copy /b HalOS-*.iso.part* HalOS.iso` (Windows) or `cat HalOS-*.iso.part* > HalOS.iso`.
2. Check: `sha256sum -c SHA256SUMS`.
3. Write with Rufus (DD mode), Ventoy, or `dd`. See [packaging/windows-host/write_usb.md](../packaging/windows-host/write_usb.md).
4. Boot from USB, try the live desktop, then run **Install HalOS**.

If something fails: [TROUBLESHOOTING.md](TROUBLESHOOTING.md) and [RECOVERY.md](RECOVERY.md).
