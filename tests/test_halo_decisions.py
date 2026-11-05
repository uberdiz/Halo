"""
Halo OS image, decisions of 2026-11-04 (HALOS_ROADMAP.md): the name "Halo OS", NVIDIA (nvidia-open only
where it drives the GPU), the 8B Ollama default with a small fallback, the preinstalled and pinned apps,
Halo Dark, and reduced motion in the saint-star KWin effect. Static checks plus the boot-time shell
scripts run against a fake /sys.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ARCH = ROOT / "packaging" / "arch"
PROFILE = ARCH / "profile"
AIROOTFS = PROFILE / "airootfs"
CAL = ARCH / "pkgbuilds" / "halo-calamares-config" / "calamares"
SYSTEM = ARCH / "pkgbuilds" / "halo-system"
FS = ROOT / "packaging" / "linux" / "rootfs"


def _read(p):
    return p.read_text(encoding="utf-8")


def _packages():
    return [l.strip() for l in _read(PROFILE / "packages.x86_64").splitlines()
            if l.strip() and not l.lstrip().startswith("#")]


def _bash():
    bash = shutil.which("bash")
    git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    if os.name == "nt" and (not bash or "system32" in bash.lower()):   # not WSL's launcher: Git Bash
        bash = str(git_bash) if git_bash.exists() else None
    if not bash:
        pytest.skip("no bash")
    return bash


def _fake_pci(tmp_path, devices):
    root = tmp_path / "sys" / "bus" / "pci" / "devices"
    root.mkdir(parents=True)
    for i, (vendor, cls, dev) in enumerate(devices):
        d = root / f"0000.0{i}.00.0"                 # real names have colons, which Windows paths can't
        d.mkdir()
        (d / "vendor").write_text(vendor + "\n")
        (d / "class").write_text(cls + "\n")
        (d / "device").write_text(dev + "\n")
    return tmp_path / "sys"


def _env(**kw):
    return {"PATH": os.environ.get("PATH", ""), **{k: (v.as_posix() if isinstance(v, Path) else v) for k, v in kw.items()}}


# --------------------------------------------------------------------------- name
def test_halo_os_is_the_name_people_read():
    for e in (PROFILE / "efiboot" / "loader" / "entries").glob("*.conf"):
        assert re.search(r"^title +Start Halo OS", _read(e), re.M), e.name
    assert _read(PROFILE / "syslinux" / "syslinux.cfg").count("MENU LABEL Start Halo OS") == 2
    desc = _read(CAL / "branding" / "halo" / "branding.desc")
    for key in ("productName", "shortProductName", "versionedName", "bootloaderEntryName"):
        assert re.search(rf'^ +{key}: +"Halo OS"$', desc, re.M), key
    assert "keepDistributor: false" in _read(CAL / "modules" / "grubcfg.conf")   # GRUB_DISTRIBUTOR = "Halo OS"
    branding = _read(ARCH / "pkgbuilds" / "halo-branding" / "PKGBUILD")
    assert 'PRETTY_NAME="Halo OS $pkgver"' in branding and "Name=Halo OS" in branding
    assert "etc/xdg/kcm-about-distrorc" in branding
    assert "Name=Install Halo OS" in _read(ARCH / "pkgbuilds/halo-calamares-config/install-halo.desktop")
    lf = FS / "usr/share/plasma/look-and-feel"
    assert '"Name": "Halo Dark"' in _read(lf / "org.saintos.desktop/metadata.json")
    assert '"Name": "Halo Light"' in _read(lf / "org.saintos.desktop.light/metadata.json")
    assert '"HALO OS"' in _read(lf / "org.saintos.desktop/contents/splash/Splash.qml")
    prof = _read(PROFILE / "profiledef.sh")
    assert 'iso_name="Halo"' in prof and re.search(r'^iso_label="HALO_', prof, re.M)   # file names, volume id
    assert 'iso_application="Halo OS ' in prof


# --------------------------------------------------------------------------- NVIDIA
def test_nvidia_open_ships_with_multilib():
    pkgs = _packages()
    for p in ("nvidia-open", "nvidia-utils", "lib32-nvidia-utils", "nvidia-settings", "halo-system"):
        assert p in pkgs, p
    assert re.search(r"^\[multilib\]\nServer = @SERVER@$", _read(PROFILE / "pacman.conf"), re.M)
    assert "multilib" in _read(ARCH / "pkgbuilds" / "halo-branding" / "apply-branding")
    build = _read(ARCH / "build_iso.sh")
    assert "for p in saint halo-branding halo-system halo-calamares-config" in build
    assert "sysinit.target.wants/halo-gpu-detect.service" in build
    assert "multi-user.target.wants/halo-flatpak-apps.service" in build
    validate = _read(ARCH / "validate_iso.sh")
    for word in ("nvidia-open", "lib32-nvidia-utils", "halo-gpu-detect.service", "modeset=1 fbdev=1", "[multilib]"):
        assert word in validate, word


def test_nouveau_never_reaches_an_initramfs_before_the_gpu_choice():
    live = _read(AIROOTFS / "etc" / "mkinitcpio.conf.d" / "halo-live.conf")
    assert "kms" not in re.search(r"HOOKS=\(([^)]*)\)", live).group(1).split()
    dropin = _read(SYSTEM / "zz-halo-gpu.mkinitcpio.conf")
    assert "0x10de" in dropin and "== kms" in dropin
    pkg = _read(SYSTEM / "PKGBUILD")
    assert "etc/mkinitcpio.conf.d/zz-halo-gpu.conf" in pkg and "etc/modprobe.d/nvidia-utils.conf" in pkg
    mp = _read(SYSTEM / "nvidia-utils.modprobe.conf")
    assert "options nvidia_drm modeset=1 fbdev=1" in mp and not re.search(r"^blacklist", mp, re.M)
    unit = _read(SYSTEM / "halo-gpu-detect.service")
    assert "DefaultDependencies=no" in unit
    assert re.search(r"^Before=.*systemd-udev-trigger\.service.*systemd-modules-load\.service", unit, re.M)
    # Calamares copies the image (with the enabled unit and these files); its cleanup leaves them alone.
    cal = _read(ARCH / "pkgbuilds/halo-calamares-config/halo-cleanup") + _read(ARCH / "pkgbuilds/halo-calamares-config/halo-secureboot")
    assert "nvidia" not in cal and "zz-halo-gpu" not in cal and "modprobe.d" not in cal


def test_mkinitcpio_dropin_drops_kms_only_with_an_nvidia_gpu(tmp_path):
    bash = _bash()
    script = _read(SYSTEM / "zz-halo-gpu.mkinitcpio.conf").replace("/sys/", "$FAKESYS/")
    (tmp_path / "dropin").write_text(script, encoding="utf-8", newline="\n")
    for devices, keeps_kms in (([("0x10de", "0x030000", "0x2b85")], False), ([("0x1002", "0x030000", "0x744c")], True)):
        sysfs = _fake_pci(tmp_path / str(keeps_kms), devices)
        res = subprocess.run([bash, "-c", 'HOOKS=(base udev autodetect microcode modconf kms keyboard block filesystems); '
                              f'. "{(tmp_path / "dropin").as_posix()}"; echo "${{HOOKS[*]}}"'],
                             capture_output=True, text=True, env=_env(FAKESYS=sysfs))
        assert res.returncode == 0, res.stderr
        assert ("kms" in res.stdout.split()) == keeps_kms
        assert "modconf keyboard" in res.stdout or keeps_kms


@pytest.mark.parametrize("devices, cmdline, gpu, nvidia", [
    ([("0x10de", "0x030000", "0x2b85")], "", "nvidia", True),                                    # RTX 5090 (Blackwell)
    ([("0x8086", "0x030000", "0xa780"), ("0x10de", "0x030200", "0x2860")], "", "nvidia", True),  # laptop + Ada dGPU
    ([("0x10de", "0x030000", "0x1e84")], "", "nvidia", True),                                    # RTX 2070 Super (Turing)
    ([("0x10de", "0x030000", "0x1b80")], "", "nouveau", False),                                  # GTX 1080 (Pascal)
    ([("0x1002", "0x030000", "0x744c")], "", "none", False),                                     # AMD only
    ([("0x10de", "0x040300", "0x22ba")], "", "none", False),                                     # NVIDIA HDMI audio only
    ([("0x10de", "0x030000", "0x2b85")], "quiet halo.nvidia=0", "nouveau", False),
    ([("0x10de", "0x030000", "0x1b80")], "halo.nvidia=1", "nvidia", True),
])
def test_gpu_detect_picks_the_driver(tmp_path, devices, cmdline, gpu, nvidia):
    bash = _bash()
    sysfs = _fake_pci(tmp_path, devices)
    run = tmp_path / "run"
    (tmp_path / "cmdline").write_text(cmdline + "\n")
    res = subprocess.run([bash, (SYSTEM / "gpu-detect").as_posix()], capture_output=True, text=True,
                         env=_env(HALO_SYSFS=sysfs, HALO_RUNDIR=run, HALO_CMDLINE=tmp_path / "cmdline"))
    assert res.returncode == 0, res.stderr
    assert (run / "halo" / "gpu").read_text().strip() == gpu
    conf = (run / "modprobe.d" / "halo-gpu.conf").read_text()
    assert ("blacklist nouveau" in conf) == nvidia                 # nouveau blacklisted only with nvidia-open
    assert ("blacklist nvidia\n" in conf) == (not nvidia)
    assert (run / "modules-load.d" / "halo-nvidia.conf").exists() == nvidia
    if nvidia:
        assert "options nvidia_drm modeset=1 fbdev=1" in conf


# --------------------------------------------------------------------------- Ollama
def test_ollama_model_is_one_setting_with_a_small_fallback():
    conf = _read(FS / "etc" / "halo" / "ollama-model")
    assert re.search(r"^HALO_OLLAMA_MODEL=llama3\.1:8b$", conf, re.M)
    assert re.search(r"^HALO_OLLAMA_SMALL_MODEL=llama3\.2:3b$", conf, re.M)
    unit = _read(FS / "usr/lib/systemd/system/saint-ollama-model.service")
    assert "EnvironmentFile=-/etc/halo/ollama-model" in unit
    assert re.search(r"^ExecStart=/usr/libexec/saintos/ollama-model( auto)?$", unit, re.M)       # no model hard-coded
    saint = _read(ARCH / "pkgbuilds" / "saint" / "PKGBUILD")
    assert '"$pkgdir/etc/halo/ollama-model"' in saint and "backup=(etc/halo/ollama-model)" in saint


@pytest.mark.parametrize("ram_gb, nvidia, env_model, model", [
    (32, False, "", "llama3.1:8b"), (16, False, "", "llama3.1:8b"), (8, False, "", "llama3.2:3b"),
    (8, True, "", "llama3.1:8b"), (32, False, "qwen3:8b", "qwen3:8b"),
])
def test_ollama_model_choice(tmp_path, ram_gb, nvidia, env_model, model):
    bash = _bash()
    sysfs = _fake_pci(tmp_path, [("0x10de", "0x030000", "0x2b85")] if nvidia else [("0x8086", "0x030000", "0xa780")])
    (tmp_path / "meminfo").write_text(f"MemTotal:       {ram_gb * 1024 * 1024 - 400000} kB\n")
    env = _env(HALO_SYSFS=sysfs, HALO_MEMINFO=tmp_path / "meminfo", HALO_OLLAMA_CONF=FS / "etc/halo/ollama-model",
               HALO_OLLAMA_DRY_RUN="1")
    if env_model:
        env["HALO_OLLAMA_MODEL"] = env_model
    res = subprocess.run([bash, (FS / "usr/libexec/saintos/ollama-model").as_posix()], capture_output=True, text=True, env=env)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == model


# --------------------------------------------------------------------------- apps, theme, motion
def test_taskbar_pins_and_preinstalled_apps():
    js = _read(FS / "usr/share/plasma/shells/org.kde.plasma.desktop/contents/updates/saintos-defaults.js")
    pins = re.search(r"var pins = \[(.*?)\];", js, re.S).group(1)
    assert re.findall(r'"applications:([^"]+)"', pins) == [
        "firefox.desktop", "org.kde.dolphin.desktop", "org.kde.konsole.desktop", "saint.desktop",
        "code-oss.desktop", "com.spotify.Client.desktop"]
    pkgs = _packages()
    assert all(p in pkgs for p in ("firefox", "dolphin", "konsole", "code", "saint", "flatpak"))
    assert "visual-studio-code-bin" not in pkgs
    # Spotify from Flathub (it may not be redistributed in an ISO): installed once in the background, and a
    # placeholder launcher with the same desktop ID (shadowed by Flathub's once installed) installs on click.
    assert _read(SYSTEM / "flatpak-apps.list").count("com.spotify.Client") == 1
    placeholder = _read(SYSTEM / "com.spotify.Client.desktop")
    assert "Exec=/usr/lib/halo/flatpak-apps --launch com.spotify.Client" in placeholder
    unit = _read(SYSTEM / "halo-flatpak-apps.service")
    assert "ConditionKernelCommandLine=!archisobasedir" in unit and "Restart=on-failure" in unit
    pkg = _read(SYSTEM / "PKGBUILD")
    assert "usr/share/applications/com.spotify.Client.desktop" in pkg and "etc/halo/flatpak-apps" in pkg


def test_flatpak_apps_list_parsing(tmp_path):
    bash = _bash()
    lst = tmp_path / "apps"
    lst.write_text("# comment\ncom.spotify.Client   # music\n\nbad id!\norg.example.App\n")
    script = _read(SYSTEM / "flatpak-apps")
    fn = re.search(r"^apps\(\) \{.*\}$", script, re.M).group(0)
    res = subprocess.run([bash, "-c", f'LIST="{lst.as_posix()}"; {fn}; apps'], capture_output=True, text=True, env=_env())
    assert res.stdout.split() == ["com.spotify.Client", "org.example.App"]


def test_halo_dark_is_the_default_look():
    kdeglobals = _read(FS / "etc/xdg/kdeglobals")
    assert "ColorScheme=HaloDark" in kdeglobals and "LookAndFeelPackage=org.saintos.desktop" in kdeglobals
    assert "Theme=org.saintos.desktop" in _read(FS / "etc/xdg/ksplashrc")


def test_claude_code_cli_ships_in_the_image():
    pkgs = _packages()
    assert all(p in pkgs for p in ("nodejs", "npm", "claude-code"))
    assert re.search(r"^AUR_PKGS=\(.*\bclaude-code\b.*\)$", _read(ARCH / "build_iso.sh"), re.M)
    assert "/usr/bin/claude --version" in _read(ARCH / "validate_iso.sh")


def test_a_100_mb_windows_efi_partition_can_be_reused():
    """The owner's ESP is 100 MB on another disk: Calamares must accept it, mount it at /boot/efi without
    formatting, and only boot loaders may go on it (kernels + nvidia-sized initramfs stay in /boot on Btrfs)."""
    yaml = pytest.importorskip("yaml")
    part = yaml.safe_load(_read(CAL / "modules" / "partition.conf"))
    mib = lambda s: int(re.fullmatch(r"(\d+)MiB", s).group(1))
    assert part["efi"]["mountPoint"] == "/boot/efi"
    assert mib(part["efi"]["minimumSize"]) <= 100 * 10**6 // 2**20 - 16   # 100 MB is 95 MiB; Windows' ESP passes
    assert part["allowManualPartitioning"] is True              # "Replace/keep" an existing ESP by hand too
    boot = yaml.safe_load(_read(CAL / "modules" / "bootloader.conf"))
    assert boot["kernelSearchPath"] == "/boot" and boot["efiBootLoader"] == "grub"
    mounts = yaml.safe_load(_read(CAL / "modules" / "mount.conf"))
    assert {"mountPoint": "/", "subvolume": "/@"} in mounts["btrfsSubvolumes"]
    assert not any(m["mountPoint"].startswith("/boot") for m in mounts["btrfsSubvolumes"])   # /boot is in @
    # Kernels and initramfs are written to /boot (the root), never to the ESP.
    assert 'ALL_kver="/boot/vmlinuz-linux"' in _read(ARCH / "pkgbuilds/halo-calamares-config/halo-cleanup")
    sb = _read(ARCH / "pkgbuilds/halo-calamares-config/halo-secureboot")
    assert re.search(r"^ESP=/boot/efi$", sb, re.M) and re.search(r"^ESP_NEEDS_MB=(\d+)$", sb, re.M)
    assert int(re.search(r"^ESP_NEEDS_MB=(\d+)$", sb, re.M).group(1)) <= 30
    written = re.findall(r'"\$(?:ESP|D)/[^"]*"', sb)
    assert written and all(w.lower().endswith('.efi"') or w in ('"$ESP/EFI/Halo"', '"$ESP/EFI/BOOT"') for w in written), written
    assert "vmlinuz" not in "".join(l for l in sb.splitlines() if "$ESP" in l or "$D/" in l)
    assert "--efi-directory=\"$ESP\"" in sb and "--boot-directory" not in sb   # GRUB's modules/config stay in /boot/grub


def test_saint_star_respects_reduced_motion():
    path = FS / "usr/share/kwin/effects/saint-star/contents/code/main.js"
    js = _read(path)
    assert "animationTime(BASE_MS)" in js                     # Plasma's animation speed slider scales it
    assert "saintStar.duration > 0 &&" in js                  # "Instant": no animation and no window grab
    assert 'effect.readConfig("ReducedMotion"' in js          # fade only: no spin, zoom or flash
    assert "if (saintStar.reduced || saintStar.duration <= 0)" in js
    assert "effect.configChanged.connect(saintStar.loadConfig)" in js and "saintStar.loadConfig();" in js
    node = shutil.which("node")
    if node:
        res = subprocess.run([node, "--check", path.as_posix()], capture_output=True, text=True)
        assert res.returncode == 0, res.stderr


def test_dual_boot_keeps_windows_fallback_loader():
    """A shared Windows EFI partition keeps Windows' EFI/BOOT/BOOTX64.EFI."""
    cal = ARCH / "pkgbuilds" / "halo-calamares-config"
    assert re.search(r"^installEFIFallback: false$", _read(cal / "calamares" / "modules" / "bootloader.conf"), re.M)
    sb = _read(cal / "halo-secureboot")
    guard = sb.index('EFI/Microsoft/Boot/bootmgfw.efi')
    assert guard < sb.index('"$ESP/EFI/BOOT/BOOTX64.EFI"\n')
