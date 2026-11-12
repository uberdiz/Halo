# Known issues and unverified areas

Updated per release. "Unverified" means code and automated tests exist but nobody has run it on real hardware yet.

## Unverified on real hardware
- End-to-end install from HalOS-Setup.exe, dual boot with Windows, Secure Boot MOK flow.
- NVIDIA open driver on HalOS; AMD/Intel GPUs; laptops (battery, sleep/wake, Wi-Fi, Bluetooth).
- Multiple monitors and display scaling with SAINT's window placement.
- Voice stack (wake word, Whisper, Kokoro) on HalOS audio hardware.
- Migration from a real Windows disk; iPhone import.

## Known limitations
- The default SAINT avatar is 2D until the 3D SAINT model is finished; you can import your own `.vrm`/`.glb`.
- GPU process names may show as a PID on some drivers.
- Legacy BIOS boot is not supported (UEFI only).

The live per-feature table is [../HALOS_STATUS.md](../HALOS_STATUS.md).
