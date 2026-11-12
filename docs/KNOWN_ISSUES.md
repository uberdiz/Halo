# Known issues and unverified areas

Updated per release. "Unverified" means code and automated tests exist but nobody has run it on real hardware yet.

## Unverified on real hardware
- End-to-end install from HalOS-Setup.exe, dual boot with Windows, Secure Boot MOK flow.
- NVIDIA open driver on HalOS; AMD/Intel GPUs; laptops (battery, sleep/wake, Wi-Fi, Bluetooth).
- Multiple monitors and display scaling with SAINT's window placement.
- Voice stack (wake word, Whisper, Kokoro) on HalOS audio hardware.
- Migration from a real Windows disk; iPhone import.

## Known limitations
- The 3D SAINT avatar animates blinks, mouth movement (from the voice level; there is no phoneme data) and expressions. VRM spring bones (hair/cloth physics) are not simulated. Imported `.vrm`/`.glb` models show without face animation.
- The 3D avatar needs Qt Quick 3D; without a working GPU driver SAINT falls back to the 2D picture.
- GPU process names may show as a PID on some drivers.
- Legacy BIOS: the live ISO boots in BIOS VMs; installing is tested for UEFI only.
- On HalOS (Wayland) the floating avatar opens mid-screen instead of the bottom-right corner; drag it where you want it (the position is remembered).

The live per-feature table is [../HALOS_STATUS.md](../HALOS_STATUS.md).
