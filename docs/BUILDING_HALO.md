# Building Halo OS (Arch Linux)

Halo OS is SAINT's operating system from v0.2 on: Arch Linux + KDE Plasma 6 (Wayland) + SAINT, built with
archiso. It replaced the Fedora/KIWI SAINTOS build, which was removed from the tree (kept at the tag
`saintos-fedora-0.1.0`). Plan: [plan.md](../plan.md) §2b. "Halo OS" is the name shown to people (boot menu,
os-release, splash, installer, About); packages and files keep the `halo-*` names and `ID=halo`.

## Build

On any x86_64 Linux host with podman or docker and ~25 GB free:

```bash
packaging/arch/build_in_container.sh --workdir /var/tmp/halo-build
```

On Arch itself (as root): `packaging/arch/build_iso.sh --workdir /var/tmp/halo-build`.

Output in `dist/halo/`: `Halo-x86_64.iso`, `SHA256SUMS`, `BUILD_INFO.json`, `Halo-x86_64.packages`,
`AUR_COMMITS`, `VALIDATION.txt`.

Modes (`--mode`):

| Mode | Packages from | Root image | Use |
|---|---|---|---|
| `test` (default) | today's Arch mirrors | zstd -3 | everyday builds |
| `fast` | today's Arch mirrors | lz4 | quickest boot test of a change (bigger ISO) |
| `release` | pinned Arch Linux Archive snapshot (`ARCH_SNAPSHOT`) | zstd -19 | repeatable, smallest ISO |

Other options: `--allow-dirty` (build tracked local changes), `--rebuild-aur` (rebuild paru-bin and
Calamares instead of reusing the last build's; Calamares takes ~30 min), `--no-validate`.

Kept between builds in the workdir: the pacman package cache, uv's Python and wheels (SAINT's ~1 GB
runtime), the AUR packages and paru's clones. Step times are printed at the end and saved in
`BUILD_INFO.json` (`step_seconds`).

## What's where

| Path | Role |
|---|---|
| `packaging/arch/VERSION` | Halo version (also every Halo package's `pkgver`) |
| `packaging/arch/ARCH_SNAPSHOT` | Arch Linux Archive date the image and the AUR builds use |
| `packaging/arch/profile/` | archiso profile: boot entries (BIOS syslinux, UEFI systemd-boot, no menu), package list, live-only files |
| `packaging/arch/pkgbuilds/saint` | `/opt/saint`: the app, a uv-managed CPython 3.12 and a venv from `saint-runtime.lock` |
| `packaging/arch/pkgbuilds/halo-branding` | os-release (applied by a pacman hook), artwork, Plymouth, Plasma and SDDM defaults |
| `packaging/arch/pkgbuilds/halo-system` | NVIDIA driver choice at boot, preinstalled Flathub apps (Spotify) |
| `packaging/arch/pkgbuilds/halo-calamares-config` | the installer: Btrfs subvolumes, GRUB + os-prober, live cleanup |
| `packaging/arch/build_iso.sh` | builds the `[halo]` repo (ours + `paru-bin` and `calamares` from the AUR) and runs mkarchiso |
| `packaging/arch/validate_iso.sh` | structural checks of an ISO (root) |
| `tests/test_halo_image.py`, `tests/test_halo_decisions.py` | static checks that run anywhere, in the normal test suite |

## Live session and installed system

- The live ISO logs `liveuser` (no password) straight into Plasma. That user, its autologin, NOPASSWD
  sudo and polkit rule are created at boot by `halo-live.service`, only when the kernel command line has
  `archisobasedir=`; none of it is in the image, so the installer can't copy it to a disk.
- "Install Halo OS" (desktop and menu) runs Calamares. Its last steps remove the live tools, write Arch's
  normal kernel preset, create the pacman keyring and install GRUB with os-prober (dual boot). The
  installed system is a copy of the image, so everything below (NVIDIA, apps, theme) carries over.

## NVIDIA

The image ships `nvidia-open`, `nvidia-utils`, `lib32-nvidia-utils` ([multilib] is on, in the build and on
installed systems) and `nvidia-settings`. `halo-gpu-detect.service` runs at every boot before udev loads
GPU drivers and writes `/run/modprobe.d/halo-gpu.conf`:

| This PC | Result (`/run/halo/gpu`) |
|---|---|
| NVIDIA GPU nvidia-open drives (Turing / GTX 16 / RTX 20 and newer, incl. RTX 50) | `nvidia`: nouveau blacklisted, nvidia + nvidia_drm loaded with `modeset=1 fbdev=1` |
| older NVIDIA GPU (Maxwell, Pascal, Volta) | `nouveau`: the nvidia modules blacklisted |
| no NVIDIA GPU | `none`: the nvidia modules blacklisted |

`halo.nvidia=0` / `halo.nvidia=1` on the kernel command line override it ("basic graphics" boot entries use
`=0`). nvidia-utils' own file that blacklists nouveau everywhere is replaced by `/etc/modprobe.d/nvidia-utils.conf`.
No GPU driver may be in the initramfs before that choice: the live initramfs has no `kms` hook, and on
installed PCs with an NVIDIA GPU `/etc/mkinitcpio.conf.d/zz-halo-gpu.conf` drops `kms` (PCs without one keep
early KMS). Until the driver loads (about a second), the boot splash uses the firmware framebuffer.

## Preinstalled apps and defaults

- Taskbar: Firefox, Dolphin, Konsole, SAINT, VS Code (Arch's `code`, Code - OSS), Spotify.
- **Spotify comes from Flathub** (`com.spotify.Client`), not the AUR: Spotify's licence doesn't allow
  shipping its binaries in an ISO, and Flathub's package downloads them from Spotify at install time.
  `halo-flatpak-apps.service` installs the apps in `/etc/halo/flatpak-apps` once in the background on an
  installed system (retrying until there is a network). Until then — and in the live session — the pinned
  icon is Halo's placeholder launcher with the same desktop ID, which installs Spotify on first click;
  Flathub's own launcher takes its place once installed.
- Claude Code CLI (`claude`, AUR `claude-code` built into [halo], with `nodejs`/`npm`) for SAINT's Evolve.
- EFI partition: an existing one as small as Windows' 100 MB can be kept (mounted at `/boot/efi`, not
  formatted). Kernels and initramfs live in `/boot` on the Btrfs root; the ESP gets only shim, MokManager and
  GRUB (~15 MB).
- Theme: Halo Dark (colour scheme and look-and-feel `org.saintos.desktop`); Halo Light is selectable.
- Ollama: `saint-ollama-model.service` pulls `HALO_OLLAMA_MODEL` from `/etc/halo/ollama-model`
  (`llama3.1:8b`, ~5 GB) once on an installed system, or `HALO_OLLAMA_SMALL_MODEL` (`llama3.2:3b`) on PCs with
  less than 12 GB RAM and no NVIDIA GPU. The model pulled is the first line of `/var/lib/ollama/.saint-model-ready`.
- Window animations (`saint-star`): follow Plasma's animation speed; "Instant" turns them off, and
  `kwriteconfig6 --file kwinrc --group Effect-saint-star --key ReducedMotion true` keeps only a short fade.

## Known gaps

- **Secure Boot:** Microsoft-signed shim + Halo's MOK key (untested on hardware). The nvidia modules are
  not signed with that key; Arch's kernel doesn't enforce module signatures, but this needs a hardware check.
- **Ollama on the GPU:** Arch's `ollama` package runs on the CPU; GPU inference needs `ollama-cuda`
  (several GB, not in the ISO) — a candidate for SAINT's dependency manager on NVIDIA PCs.
- **Updates:** installed systems follow Arch's live mirrors; SAINT and the branding come from the ISO
  until a hosted `[halo]` repository exists.
- **AUR packages** (`paru-bin`, `calamares` and its AUR dependencies) are built from the AUR's current
  PKGBUILDs; the commits used are recorded in `AUR_COMMITS` and `BUILD_INFO.json`.
