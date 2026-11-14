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
    assert 'mode == "replace" ? "REPLACE" : mode == "update" ? "UPDATE" : "INSTALL"' in SOURCE
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
def test_update_reuses_halolive_and_never_shrinks_c(exe):
    out = subprocess.run([str(exe), "--plan", "update", "200", "x.iso"], capture_output=True, text=True,
                         timeout=30).stdout.strip().splitlines()
    assert out[0].endswith("-InstallGB 0 -Refresh") and out[1].endswith("restart_into_halos.ps1 -Live")


def _release(tag, *names):
    return {"tag_name": tag, "prerelease": True, "assets": [
        {"name": n, "browser_download_url": f"https://github.com/uberdiz/Halo/releases/download/{tag}/{n}"} for n in names]}


@needs_csc
def test_newest_release_is_found_including_pre_releases_and_split_isos(exe, tmp_path):
    f = tmp_path / "releases.json"
    f.write_text(json.dumps([_release("v2.0.0-beta.2", "SHA256SUMS", "Halo-x86_64.iso.part2", "Halo-x86_64.iso.part1",
                                      "Halo-x86_64.iso.part10", "HalOS-Setup.exe", *[f"Halo-x86_64.iso.part{i}" for i in range(3, 10)]),
                             _release("v1.0.0", "Halo-x86_64.iso", "SHA256SUMS")]))
    out = subprocess.run([str(exe), "--release", str(f)], capture_output=True, text=True, timeout=30).stdout.split()
    assert [u.rsplit("/", 1)[1] for u in out] == [f"Halo-x86_64.iso.part{i}" for i in range(1, 11)] + ["SHA256SUMS"]
    assert all("/v2.0.0-beta.2/" in u for u in out)
    f.write_text(json.dumps([_release("v3", "SHA256SUMS", "Halo-x86_64.iso.part1", "Halo-x86_64.iso.part3")]))
    res = subprocess.run([str(exe), "--release", str(f)], capture_output=True, text=True, timeout=30)
    assert res.returncode == 2 and "no complete ISO" in res.stdout                     # a missing part is refused


@needs_csc
def test_unknown_mode_is_refused(exe):
    res = subprocess.run([str(exe), "--plan", "wipe-everything", "100", "x.iso"], capture_output=True, text=True, timeout=30)
    assert res.returncode != 0 and "prepare_disk_boot" not in res.stdout


def test_live_entry_is_one_time_only_and_windows_stays_first():
    # 2.1.0-beta.2: a `bcdedit /copy {bootmgr}` entry for HALOLIVE sat first and the PC started HalOS instead of
    # Windows. 2.2.0-beta.1 made no entry at all, and firmware that doesn't list HALOLIVE in F12 (the real PC) then
    # had no way into the live system. Now: an entry that is taken out of the boot order, used only as BootNext.
    root = Path(__file__).resolve().parents[1] / "packaging" / "windows-host"
    text = (root / "prepare_disk_boot.ps1").read_text(encoding="utf-8")
    fn = text[text.index("function Add-LiveBootEntry"):]
    fn = fn[:fn.index("\n}\n")]
    assert "bcdedit /copy '{bootmgr}'" in fn
    assert "displayorder $guid /remove" in fn and "/addlast" not in fn and "/addfirst\" $guid" not in fn
    assert fn.index("displayorder $guid /remove") < fn.index("displayorder '{bootmgr}' /addfirst")
    for call in ("Remove-LiveBootCopies\n        Add-LiveBootEntry $dst", "Remove-LiveBootCopies\nAdd-LiveBootEntry $dst"):
        assert call in text.replace("\r\n", "\n")                       # old copies go first, in both modes
    restart = (root / "restart_into_halos.ps1").read_text(encoding="utf-8")
    assert "bootsequence $guid" in restart and "HALOLIVE-READY" in restart


def test_every_page_is_dark_and_the_rays_only_run_on_the_welcome_page():
    assert "Light" not in SOURCE and "Orbs" not in SOURCE                     # the light orb welcome page is gone
    assert "DwmSetWindowAttribute(f.Handle, 20, ref on, 4)" in SOURCE         # dark title bar
    assert "d.HandleCreated += delegate { DarkTitle(d); }" in SOURCE           # the error dialog too
    assert "rayTimer.Enabled = welcome;" in SOURCE                            # no timer on the other pages
    assert "new ProgressBar()" not in SOURCE                                  # the light system bar is replaced


@needs_csc
def test_screenshots_cover_all_five_pages_and_a_ray_frame_is_cheap(exe, tmp_path):
    res = subprocess.run([str(exe), "--screenshot", str(tmp_path)], capture_output=True, text=True, timeout=120)
    assert sorted(p.name for p in tmp_path.glob("setup_step*.png")) == [f"setup_step{i}.png" for i in range(1, 6)]
    ms = float(re.search(r"rays frame: ([\d.]+) ms", res.stdout).group(1))
    assert ms < 8, res.stdout                                                 # ~2.5 ms: under 10% of a core at 30 fps
