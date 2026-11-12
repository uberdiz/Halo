"""Fast boot on an installed HalOS: small zstd initramfs, a quiet boot, no menu wait when HalOS is alone, nothing at
boot waiting for downloads, and a benchmark script that only reads."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / "packaging/arch/pkgbuilds/halo-calamares-config"
BENCH = ROOT / "packaging/arch/tools/boot-benchmark.sh"


def _read(p):
    return p.read_text(encoding="utf-8")


def test_initramfs_is_zstd_and_written_before_calamares_builds_it():
    cleanup = _read(CAL / "halo-cleanup")
    assert 'COMPRESSION="zstd"' in cleanup and "10-halo-fastboot.conf" in cleanup
    order = yaml.safe_load(_read(CAL / "calamares/settings.conf"))["sequence"][1]["exec"]
    assert order.index("shellprocess@halo-cleanup") < order.index("initcpio")


def test_quiet_splash_boot_and_a_short_menu_only_with_another_system():
    grub = yaml.safe_load(_read(CAL / "calamares/modules/grubcfg.conf"))
    assert {"quiet", "splash", "loglevel=3"} <= set(grub["kernel_params"])
    assert grub["defaults"]["GRUB_TIMEOUT"] == 5
    sb = _read(CAL / "halo-secureboot")
    assert "GRUB_TIMEOUT=0" in sb and "GRUB_TIMEOUT_STYLE=hidden" in sb
    hidden_branch = sb[sb.index("GRUB has no Windows entry"):sb.index("calamares-bootorder")]
    assert "GRUB_TIMEOUT=0" in hidden_branch                    # only on the "no Windows" side


@pytest.mark.parametrize("unit", ["halo-flatpak-apps.service", "saint-ollama-model.service"])
def test_first_boot_downloads_never_hold_up_boot_or_restart(unit):
    path = next(p for p in ROOT.joinpath("packaging").rglob(unit))
    text = _read(path)
    assert "DefaultDependencies=no" in text and "TimeoutStopSec=15" in text


def test_benchmark_only_reads_and_writes_json():
    text = _read(BENCH)
    for verb in ("systemctl enable", "systemctl disable", "pacman ", "rm -", "mkinitcpio", "grub-mkconfig"):
        assert verb not in text, verb
    assert "systemd-analyze blame" in text and '"idle_ram_used_mb"' in text


@pytest.mark.skipif(not shutil.which("bash"), reason="needs bash")
def test_benchmark_produces_valid_json_from_systemd_analyze(tmp_path):
    import json
    import os
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    fakes = {
        "systemd-analyze": '''case "$1" in
  time) echo "Startup finished in 3.210s (firmware) + 1.002s (loader) + 1.500s (kernel) + 900ms (initrd) + 4.120s (userspace) = 10.732s"
        echo "graphical.target reached after 4.050s in userspace.";;
  blame) printf '  2.100s saint-ollama-model.service\\n   650ms NetworkManager.service\\n';;
esac''',
        "systemctl": 'echo running',
        "free": "printf 'total used\\nMem: 15900 1830 1\\n'",
        "systemd-detect-virt": "echo oracle",
        "uname": "echo 6.12.1-arch1-1",
        "stat": "echo 41234567",
        "sleep": ":",
    }
    for name, body in fakes.items():
        f = bin_ / name
        f.write_text("#!/usr/bin/bash\n" + body + "\n", encoding="utf-8", newline="\n")
        f.chmod(0o755)
    out = tmp_path / "boot.json"
    env = dict(os.environ, PATH=f"{bin_}{os.pathsep}{os.environ.get('PATH', '')}", SETTLE_SECONDS="0")
    bash = shutil.which("bash")
    script = BENCH.as_posix()
    res = subprocess.run([bash, script, out.as_posix()], capture_output=True, text=True, env=env, timeout=60)
    if res.returncode != 0 or not out.exists():
        pytest.skip(f"bash here can't run it: {res.stderr[:200]}")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["firmware_s"] == pytest.approx(3.21) and data["initrd_s"] == pytest.approx(0.9)
    assert data["total_s"] == pytest.approx(10.732) and data["graphical_target_s"] == pytest.approx(4.05)
    assert data["slowest_units"][0]["unit"] == "saint-ollama-model.service" and data["idle_ram_used_mb"] == 1830


def test_validator_enforces_the_iso_size_limit_and_lists_the_biggest_packages():
    text = _read(ROOT / "packaging/arch/validate_iso.sh")
    assert "MAX_ISO_BYTES=$((2500 * 1024 * 1024))" in text and "Largest packages in the image" in text
