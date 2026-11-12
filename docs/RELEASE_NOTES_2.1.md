# HalOS 2.1.0-beta.1

Beta. Read [KNOWN_ISSUES.md](KNOWN_ISSUES.md) before installing.

## New
- **SAINT in 3D.** SAINT is now an animated 3D character (VRM 1.0) that blinks, moves her mouth while speaking and shows
  how she's doing (listening, thinking, success, warning, error, offline). Floating or corner widget, drag to move,
  scroll to resize, reduce-motion option. Optional **hologram** look in your accent colour. Import your own `.vrm`,
  `.glb` or picture in Settings › SAINT › Avatar (validated, never executed).
- **Visual Shop** for wallpapers, themes, accent palettes and avatars, with SHA-256 checks and a strict file-type
  allowlist; import your own packs.
- **System Overview**: per-core CPU, full NVIDIA panel (VRAM, load, power, clocks, temperature, throttling, processes),
  history graphs (live to 7 days), failed services.
- **Ask SAINT about your hardware**: "what's using my GPU?", "is Ollama on my GPU?", "can my computer run a 14B model?"
  are answered from real sensor data, without calling a language model.
- **Home** shows reminders (snooze, dismiss, quick add), SAINT tasks, a PC summary and your quick actions.
- **Model downloads** refuse duplicates and models too big for the PC, then run a short real test and report CUDA or CPU.
- Public docs: install, troubleshooting, recovery, privacy, contributing, issue templates.

## Verified
- 2,408 automated tests pass (Windows host).
- The ISO boots to the desktop with SAINT running in UEFI and BIOS VMs.

## Not verified yet
Installing to real hardware, dual boot, Secure Boot on a real PC, laptops, multi-monitor — see KNOWN_ISSUES.md.
