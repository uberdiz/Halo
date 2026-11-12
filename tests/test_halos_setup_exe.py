"""HalOS-Setup.exe: builds with the compiler every Windows has, stays tiny, reads only in its self-test, and hands
all disk work to the tested PowerShell scripts with the right arguments (and -WhatIf in a dry run)."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "packaging/windows-host/setup"
SOURCE = (SETUP / "HalOSSetup.cs").read_text(encoding="utf-8")
CSC = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
needs_csc = pytest.mark.skipif(os.name != "nt" or not CSC.exists(), reason="needs Windows with .NET Framework 4")


@pytest.fixture(scope="module")
def exe(tmp_path_factory):
    out = tmp_path_factory.mktemp("setup") / "HalOS-Setup.exe"
    res = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                          str(SETUP / "build_setup.ps1"), "-Out", str(out)], capture_output=True, text=True, timeout=180)
    assert res.returncode == 0 and out.exists(), res.stdout + res.stderr
    return out


def test_no_disk_command_is_in_the_exe_itself():
    """Shrinking, formatting and boot entries stay in prepare_disk_boot.ps1 (reviewed, -WhatIf-able)."""
    for word in ("diskpart", "Format-Volume", "New-Partition", "Resize-Partition", "bcdedit", "Set-Partition"):
        assert word not in SOURCE, word
    assert "Suspend-BitLocker -MountPoint C: -RebootCount 3" in SOURCE        # the only system change, with consent


def test_iso_name_matches_what_the_build_produces():
    build = (ROOT / "packaging/arch/build_iso.sh").read_text(encoding="utf-8")
    name = re.search(r'IsoName = "([^"]+)"', SOURCE).group(1)
    assert f'ISO="$DIST/{name}"' in build and f"sha256sum {name} > SHA256SUMS" in build


def test_destructive_choices_need_typed_confirmation():
    assert 'mode == "replace" ? "REPLACE" : "INSTALL"' in SOURCE
    assert 'next.Enabled = dryRun || typed.Text.Trim() == word' in SOURCE


@needs_csc
def test_it_is_small(exe):
    assert exe.stat().st_size < 20 * 1024 * 1024
    assert exe.stat().st_size < 200 * 1024                                  # in practice about 50 KB


@needs_csc
def test_self_test_reports_this_pc_without_changing_anything(exe):
    res = subprocess.run([str(exe), "--self-test"], capture_output=True, text=True, timeout=90)
    data = json.loads(res.stdout)
    names = [c["name"] for c in data["checks"]]
    assert names == ["uefi", "secureboot", "bitlocker", "space", "ram", "internet"]
    assert all(c["text"] and c["text"].rstrip().endswith(".") for c in data["checks"])   # whole sentences
    assert isinstance(data["can_continue"], bool)


@needs_csc
@pytest.mark.parametrize("mode, gb, want_gb", [("alongside", 120, "120"), ("alongside", 5, "30"), ("try", 120, "0"),
                                               ("replace", 500, "0")])
def test_plan_passes_the_right_arguments(exe, mode, gb, want_gb):
    out = subprocess.run([str(exe), "--plan", mode, str(gb), r"D:\HalOS\Halo-x86_64.iso"], capture_output=True,
                         text=True, timeout=30).stdout.strip().splitlines()
    assert len(out) == 2
    assert "prepare_disk_boot.ps1 -Iso D:\\HalOS\\Halo-x86_64.iso -LiveGB 6 -InstallGB " + want_gb in out[0]
    assert out[1].endswith("restart_into_halos.ps1 -Live")


@needs_csc
def test_dry_run_only_shows_the_plan_and_never_restarts(exe):
    out = subprocess.run([str(exe), "--plan", "alongside", "100", "x.iso", "--dry-run"], capture_output=True,
                         text=True, timeout=30).stdout.strip().splitlines()
    assert len(out) == 1 and out[0].endswith("-InstallGB 100 -WhatIf")


@needs_csc
def test_unknown_mode_is_refused(exe):
    res = subprocess.run([str(exe), "--plan", "wipe-everything", "100", "x.iso"], capture_output=True, text=True, timeout=30)
    assert res.returncode != 0 and "prepare_disk_boot" not in res.stdout
