"""
Live-session clarity, install to free space, drives, OS switching and Windows migration. Disk layouts are this
PC's real one; every command is mocked, and removal runs only on fake Windows trees in tmp_path.
"""

import json
import logging
import os
import re
import sqlite3
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import drives, install_target as target, os_switch, recovery
from core import windows_migration as wm
from core.install_target import ESP_TYPE, GIB, MIB, MSR_TYPE, RECOVERY_TYPE

ROOT = Path(__file__).resolve().parent.parent
CAL = ROOT / "packaging" / "arch" / "pkgbuilds" / "halo-calamares-config"
SYSTEM = ROOT / "packaging" / "arch" / "pkgbuilds" / "halo-system"
DATA_TYPE = "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7"


def part(path, start, size, parttype=DATA_TYPE, fstype=None, label=None, mounts=None, partlabel=None, uuid=None, **kw):
    return {"name": Path(path).name, "path": path, "type": "part", "start": start, "size": size, "parttype": parttype,
            "fstype": fstype, "label": label, "mountpoints": mounts or [None], "partlabel": partlabel,
            "uuid": uuid or Path(path).name.upper(), "partuuid": kw.pop("partuuid", None), "pttype": "gpt", **kw}


def real_layout():
    """Seagate (D:), XF-2TB (C:, HALOLIVE, 200 GB free), ADATA (ESP, old Windows, Recovery)."""
    xf = 2000 * 10 ** 9
    c_size = int(1701.7 * GIB)
    c_start = 2048 + 32768
    live_start = c_start + c_size // 512
    live_size = 6 * GIB
    return [
        {"name": "sda", "path": "/dev/sda", "type": "disk", "size": 932 * GIB, "model": "Seagate", "rm": False, "ro": False,
         "pttype": "gpt", "log-sec": 512, "children": [part("/dev/sda1", 2048, 932 * GIB - 2 * MIB, fstype="ntfs", label="Data")]},
        {"name": "nvme0n1", "path": "/dev/nvme0n1", "type": "disk", "size": c_size + live_size + 200 * GIB + 18 * MIB,
         "model": "XF-2TB", "rm": False, "ro": False, "pttype": "gpt", "log-sec": 512, "children": [
             part("/dev/nvme0n1p1", 2048, 16 * MIB, MSR_TYPE),
             part("/dev/nvme0n1p2", c_start, c_size, fstype="ntfs", label="2nd_M.2"),
             part("/dev/nvme0n1p3", live_start, live_size, ESP_TYPE, "vfat", "HALOLIVE", ["/run/archiso/bootmnt"])]},
        {"name": "nvme1n1", "path": "/dev/nvme1n1", "type": "disk", "size": 477 * GIB, "model": "ADATA", "rm": False, "ro": False,
         "pttype": "gpt", "log-sec": 512, "children": [
             part("/dev/nvme1n1p1", 2048, 100 * MIB, ESP_TYPE, "vfat"),
             part("/dev/nvme1n1p2", 206848, 16 * MIB, MSR_TYPE),
             part("/dev/nvme1n1p3", 239616, 476 * GIB, fstype="ntfs", label="Windows"),
             part("/dev/nvme1n1p4", 239616 + 476 * GIB // 512, 800 * MIB, RECOVERY_TYPE, "ntfs")]},
        {"name": "loop0", "path": "/dev/loop0", "type": "loop", "size": GIB},
    ]


def done(stdout="", rc=0, stderr=""):
    return SimpleNamespace(returncode=rc, stdout=stdout, stderr=stderr)


# --------------------------------------------------------------------------- install to free space
def test_only_the_200_gb_is_offered_on_the_real_layout():
    offers = target.candidates(real_layout())
    assert len(offers) == 1
    c = offers[0]
    assert c.disk == "/dev/nvme0n1" and c.model == "XF-2TB" and not c.reuse
    assert 199 * GIB <= c.size <= 200 * GIB and c.start % MIB == 0 and c.end % MIB == 0
    assert any("HALOLIVE" in e for e in c.existing)      # shown as staying where it is


@pytest.mark.parametrize("change", [{"pttype": "dos"}, {"rm": True}, {"ro": True}])
def test_no_offer_on_mbr_removable_or_read_only(change):
    layout = real_layout()
    layout[1].update(change)
    assert target.candidates(layout) == []


def test_small_gaps_are_not_offered():
    layout = real_layout()
    layout[1]["size"] -= 180 * GIB
    assert target.candidates(layout) == []


def test_validate_refuses_a_layout_that_changed():
    layout = real_layout()
    c = target.candidates(layout)[0]
    target.validate(c, layout)
    layout[1]["children"].append(part("/dev/nvme0n1p4", c.start // 512, 5 * GIB))
    with pytest.raises(target.TargetError, match="changed"):
        target.validate(c, layout)
    with pytest.raises(target.TargetError):
        target.validate(target.Candidate(disk="/dev/sda;rm", model="", start=0, end=0), layout)
    with pytest.raises(target.TargetError, match="isn't free"):
        target.find_candidate("/dev/nvme1n1", 0, 100 * GIB, real_layout())


def test_a_region_overlapping_a_partition_is_refused():
    layout = real_layout()
    c = target.candidates(layout)[0]
    c.start -= 2 * GIB                                   # reaches into HALOLIVE
    with pytest.raises(target.TargetError):
        target.validate(c, layout)


SGDISK_BEFORE = """Disk /dev/nvme0n1: 3907029168 sectors, 1.8 TiB
Number  Start (sector)    End (sector)  Size       Code  Name
   1            2048           34815   16.0 MiB    0C01  Microsoft reserved partition
   2           34816      3568000000   1701.7 GiB  0700  Basic data partition
   3      3568001024      3580000000   1024.0 MiB  EF00  HALOLIVE
"""


def test_sgdisk_table_reads_every_size_format():
    t = target.sgdisk_table("/dev/nvme0n1", lambda *a, **k: done(SGDISK_BEFORE))
    assert t[3] == (3568001024, 3580000000, "EF00", "HALOLIVE") and t[1][2] == "0C01" and set(t) == {1, 2, 3}


class FakeDisk:
    """Answers sgdisk and lsblk like the real tools, and records everything."""

    def __init__(self, layout, corrupt=False, partx_rc=0):
        self.layout, self.corrupt, self.partx_rc = layout, corrupt, partx_rc
        self.table = SGDISK_BEFORE
        self.calls = []

    def __call__(self, argv, **kw):
        self.calls.append(argv)
        if argv[0] == "lsblk" and "-n" in argv:
            label = target.ESP_LABEL if argv[-1].endswith("p4") else target.ROOT_LABEL
            return done(json.dumps({"blockdevices": [{"path": argv[-1], "uuid": f"U-{argv[-1][-2:]}", "partuuid": "P",
                                                      "parttype": "x", "partlabel": label}]}))
        if argv[0] == "lsblk":
            return done(json.dumps({"blockdevices": self.layout}))
        if argv[:2] == ["sgdisk", "--print"]:
            return done(self.table)
        if argv[0] == "sgdisk" and not any(a.startswith(("--pretend", "--backup", "--load-backup")) for a in argv):
            rows = "   4      3600000000      3601048575   512.0 MiB   EF00  HalOS-EFI\n   5      3601048576      3900000000   142.0 GiB   8300  HalOS-root\n"
            self.table += rows
            if self.corrupt:
                self.table = self.table.replace("3568001024", "3568001000")
        if argv[0] == "partx":
            return done(rc=self.partx_rc, stderr="busy" if self.partx_rc else "")
        return done()


def _flat(calls):
    return [" ".join(c) for c in calls]


def test_apply_adds_two_partitions_and_formats_only_those(tmp_path):
    layout = real_layout()
    plan = target.candidates(layout)[0]
    fake = FakeDisk(layout)
    gs = target.apply(plan, run=fake, exists=lambda d: True, sleep=lambda s: None, backup_dir=tmp_path)
    flat = _flat(fake.calls)
    mkfs = [c for c in flat if c.startswith("mkfs")]
    assert mkfs == ["mkfs.fat -F 32 -n HALOS_EFI /dev/nvme0n1p4", "mkfs.btrfs -f -L HalOS /dev/nvme0n1p5"]
    create = next(c for c in flat if c.startswith("sgdisk --new"))
    assert "--typecode=4:ef00" in create and "--typecode=5:8300" in create
    assert f"--new=4:{plan.start // 512}:" in create and f":{plan.end // 512 - 1} " in create
    assert not any(re.search(r"--(?:delete|zap|clear|largest-new|sort|mbrtogpt)", c) for c in flat)
    # The pretend run and the backup come before the real write.
    assert flat.index(next(c for c in flat if "--backup=" in c)) < flat.index(create)
    assert flat.index(next(c for c in flat if "--pretend" in c)) < flat.index(create)
    # A busy disk (HALOLIVE mounted): only the two new partitions are announced to the kernel.
    assert "partx --add --nr 4:4 /dev/nvme0n1" in flat and "partx --add --nr 5:5 /dev/nvme0n1" in flat

    assert gs["firmwareType"] == "efi" and gs["efiSystemPartition"] == "/boot/efi"
    by_mount = {p["mountPoint"]: p for p in gs["partitions"]}
    assert by_mount["/"]["fs"] == "btrfs" and by_mount["/"]["device"] == "/dev/nvme0n1p5"
    assert by_mount["/boot/efi"]["fs"] == "fat32" and by_mount["/boot/efi"]["device"] == "/dev/nvme0n1p4"
    # What Calamares's mount, fstab, initcpiocfg, grubcfg and bootloader index directly.
    for p in gs["partitions"]:
        assert {"device", "fs", "fsName", "mountPoint", "uuid", "claimed"} <= set(p) and p["uuid"]


def test_apply_restores_the_table_if_an_existing_partition_changed(tmp_path):
    layout = real_layout()
    plan = target.candidates(layout)[0]
    fake = FakeDisk(layout, corrupt=True)
    with pytest.raises(target.TargetError, match="restored"):
        target.apply(plan, run=fake, exists=lambda d: True, sleep=lambda s: None, backup_dir=tmp_path)
    flat = _flat(fake.calls)
    assert any("--load-backup=" in c for c in flat) and not any(c.startswith("mkfs") for c in flat)


def test_apply_formats_nothing_if_the_partition_label_is_wrong(tmp_path):
    layout = real_layout()
    plan = target.candidates(layout)[0]
    fake = FakeDisk(layout)
    real = fake.__call__

    def wrong_label(argv, **kw):
        if argv[0] == "lsblk" and "-n" in argv:
            fake.calls.append(argv)
            return done(json.dumps({"blockdevices": [{"partlabel": "Basic data partition"}]}))
        return real(argv, **kw)
    with pytest.raises(target.TargetError, match="nothing was formatted"):
        target.apply(plan, run=wrong_label, exists=lambda d: True, sleep=lambda s: None, backup_dir=tmp_path)
    assert not any(c[0].startswith("mkfs") for c in fake.calls)


def test_an_unfinished_attempt_can_be_retried_without_repartitioning(tmp_path):
    layout = real_layout()
    start = target.candidates(layout)[0].start // 512
    layout[1]["children"] += [part("/dev/nvme0n1p4", start, 512 * MIB, ESP_TYPE, "vfat", partlabel=target.ESP_LABEL),
                              part("/dev/nvme0n1p5", start + 512 * MIB // 512, 199 * GIB, partlabel=target.ROOT_LABEL)]
    offers = target.candidates(layout)
    assert len(offers) == 1 and offers[0].reuse
    fake = FakeDisk(layout)
    target.apply(offers[0], run=fake, exists=lambda d: True, sleep=lambda s: None, backup_dir=tmp_path)
    flat = _flat(fake.calls)
    assert not any(c.startswith("sgdisk") for c in flat) and sum(c.startswith("mkfs") for c in flat) == 2
    layout[1]["children"][-1]["mountpoints"] = ["/somewhere"]
    with pytest.raises(target.TargetError, match="in use"):
        target.validate(offers[0], layout)


def test_plan_file_round_trip_and_settings_swap(tmp_path):
    c = target.candidates(real_layout())[0]
    target.save_plan(c, tmp_path / "run" / "plan.json")
    assert target.load_plan(tmp_path / "run" / "plan.json") == c
    with pytest.raises(target.TargetError):
        target.load_plan(tmp_path / "missing.json")
    (tmp_path / "settings.conf").write_text("standard")
    (tmp_path / "settings-freespace.conf").write_text("free")
    target.select_settings(True, tmp_path)
    assert (tmp_path / "settings.conf").read_text() == "free"
    target.select_settings(False, tmp_path)
    assert (tmp_path / "settings.conf").read_text() == "standard"


def test_freespace_settings_replace_the_partition_and_locale_modules():
    yaml = pytest.importorskip("yaml")
    std = yaml.safe_load((CAL / "calamares" / "settings.conf").read_text(encoding="utf-8"))
    free = yaml.safe_load((CAL / "calamares" / "settings-freespace.conf").read_text(encoding="utf-8"))
    assert "/usr/lib/halo/calamares-modules" in free["modules-search"]
    # The simple path also drops the Location and Keyboard pages: halo-autolocale writes them from the live session.
    dropped = ("partition", "locale", "keyboard")
    assert free["sequence"][0]["show"] == [m for m in std["sequence"][0]["show"] if m not in dropped]
    swapped = {"partition": "halotarget", "bootloader": "halobootloader@halo", "locale": None, "keyboard": None,
               "localecfg": "shellprocess@halo-autolocale"}
    expected = [swapped.get(m, m) for m in std["sequence"][1]["exec"]]
    assert free["sequence"][1]["exec"] == [m for m in expected if m]
    # Calamares won't start a sequence with its own bootloader module and no partition module (found booting the ISO).
    assert {"id": "halo", "module": "halobootloader", "config": "bootloader.conf"} in free["instances"]
    boot = yaml.safe_load((CAL / "halobootloader.desc").read_text(encoding="utf-8"))
    assert boot == {"type": "job", "name": "halobootloader", "interface": "python", "script": "main.py"}
    assert free["prompt-install"] is True                 # Calamares still asks before anything is written
    desc = yaml.safe_load((CAL / "halotarget.desc").read_text(encoding="utf-8"))
    assert desc == {"type": "job", "name": "halotarget", "interface": "python", "script": "main.py", "noconfig": True}


def test_calamares_job_runs_on_the_standard_library_alone():
    src = (ROOT / "core" / "install_target.py").read_text(encoding="utf-8")
    imports = set(re.findall(r"^(?:from|import) (\w+)", src, re.M))
    assert imports <= {"json", "os", "re", "shutil", "subprocess", "sys", "time", "dataclasses", "pathlib", "typing"}
    job = (CAL / "halotarget.py").read_text(encoding="utf-8")
    assert "/opt/saint/app/core/install_target.py" in job and "globalstorage.insert" in job
    pkg = (CAL / "PKGBUILD").read_text(encoding="utf-8")
    assert "calamares-modules/halotarget/module.desc" in pkg and "calamares-modules/halotarget/main.py" in pkg


def test_install_launcher_and_clean_install():
    assert "Exec=/usr/lib/halo/install-halo" in (CAL / "install-halo.desktop").read_text(encoding="utf-8")
    launcher = (CAL / "install-halo").read_text(encoding="utf-8")
    assert "-m ui.install_chooser" in launcher and "exec sudo -E /usr/bin/calamares" in launcher
    # The installed system comes from the squashfs, not the live overlay holding the live user and its rules.
    assert "airootfs.sfs" in (CAL / "calamares" / "modules" / "unpackfs.conf").read_text(encoding="utf-8")
    live = (ROOT / "packaging/arch/profile/airootfs/usr/local/lib/halo/live-setup").read_text(encoding="utf-8")
    assert "only to the live overlay" in live.replace("\n# ", " ") or "Writes only to the live overlay" in live
    airootfs = ROOT / "packaging/arch/profile/airootfs"
    for leftover in ("etc/sudoers.d/10-halo-live", "etc/sddm.conf.d/zz-halo-live.conf", "etc/polkit-1/rules.d/49-halo-live.rules"):
        assert not (airootfs / leftover).exists()
    users = (CAL / "calamares" / "modules" / "users.conf").read_text(encoding="utf-8")
    assert "doAutologin: false" in users and "setRootPassword: false" in users
    validate = (ROOT / "packaging/arch/validate_iso.sh").read_text(encoding="utf-8")
    assert "49-halo-live.rules" in validate and "halotarget/main.py" in validate
    grub = (CAL / "calamares" / "modules" / "grubcfg.conf").read_text(encoding="utf-8")
    assert "GRUB_DISABLE_OS_PROBER: false" in grub


def test_mok_password_screen_only_with_secure_boot_on():
    sb = (CAL / "halo-secureboot").read_text(encoding="utf-8")
    assert sb.index("mokutil --sb-state") < sb.index("mokutil --import")
    assert "SecureBoot enabled" in sb


def test_chooser_commands_and_text(monkeypatch):
    pytest.importorskip("PySide6")
    from ui import install_chooser as ic
    c = target.candidates(real_layout())[0]
    argv = ic.start_argv(c)
    assert argv[:4] == ["sudo", "-E", "/usr/bin/python3", "-I"] and argv[-4:] == ["start", c.disk, str(c.start), str(c.end)]
    assert ic.start_argv()[-1] == "standard"
    assert "200 GB" in ic.describe(c) or "199 GB" in ic.describe(c) or "21" in ic.describe(c)


# --------------------------------------------------------------------------- drives
def test_volumes_flag_the_real_layout():
    vols = {v.device: v for v in drives.volumes(devices=real_layout())}
    assert "/dev/nvme0n1p1" not in vols and "/dev/nvme1n1p2" not in vols      # MSR
    assert vols["/dev/nvme0n1p3"].is_live_medium and vols["/dev/nvme0n1p3"].protected
    assert vols["/dev/nvme1n1p1"].is_esp and vols["/dev/nvme1n1p1"].protected
    assert vols["/dev/nvme1n1p4"].is_recovery and vols["/dev/nvme1n1p4"].protected
    assert vols["/dev/nvme1n1p3"].label == "Windows" and vols["/dev/nvme1n1p3"].model == "ADATA"
    assert vols["/dev/sda1"].is_ntfs and not vols["/dev/sda1"].protected


def test_unlocked_bitlocker_shows_what_is_inside():
    layout = real_layout()
    layout[0]["children"][0].update(fstype="BitLocker", children=[
        {"name": "x", "path": "/dev/mapper/x", "type": "crypt", "fstype": "ntfs", "label": "Inside", "size": 5, "uuid": "I"}])
    v = next(x for x in drives.volumes(devices=layout) if x.label == "Inside")
    assert v.device == "/dev/mapper/x" and not v.locked


class FakeUdisks:
    def __init__(self, mountpoint, rw_error="", ro_error=""):
        self.mountpoint, self.rw_error, self.ro_error = str(mountpoint), rw_error, ro_error
        self.calls = []

    def __call__(self, argv, **kw):
        self.calls.append(argv)
        if argv[1] == "unmount":
            return done("Unmounted.")
        if "rw" in argv and self.rw_error:
            return done(rc=1, stderr=self.rw_error)
        if "ro" in argv and self.ro_error:
            return done(rc=1, stderr=self.ro_error)
        return done(f"Mounted {argv[3]} at {self.mountpoint}\n")


def _fake_windows(root: Path, users=("seb",), hiber=False):
    (root / "Windows" / "System32" / "config").mkdir(parents=True)
    (root / "Windows" / "System32" / "config" / "SOFTWARE").write_bytes(b"x")
    (root / "Windows" / "explorer.exe").write_bytes(b"e" * 100)
    for u in users:
        (root / "Users" / u).mkdir(parents=True)
        (root / "Users" / u / "NTUSER.DAT").write_bytes(b"n")
    (root / "Users" / "Public").mkdir(exist_ok=True)
    if hiber:
        (root / "hiberfil.sys").write_bytes(b"HIBR" + b"\0" * 8)
    return root


def _ntfs(device="/dev/sda1", **kw):
    return drives.Volume(device=device, label=kw.pop("label", "Data"), fstype="ntfs", uuid=kw.pop("uuid", "ABC"), **kw)


def test_data_ntfs_ends_up_writable(tmp_path):
    fake = FakeUdisks(tmp_path)
    res = drives.mount(_ntfs(), run=fake)
    assert res.ok and not res.read_only and res.mountpoint == str(tmp_path)
    assert fake.calls[0][-2:] == ["-o", "ro"] and fake.calls[-1][-2:] == ["-o", "rw"]


def test_windows_system_volume_stays_read_only_unless_asked(tmp_path):
    _fake_windows(tmp_path)
    fake = FakeUdisks(tmp_path)
    v = _ntfs(uuid="WIN")
    res = drives.mount(v, run=fake)
    assert res.read_only and "read-only" in res.message and v.is_windows
    assert not any("rw" in c for c in fake.calls)
    fake2 = FakeUdisks(tmp_path)
    res = drives.mount(_ntfs(uuid="WIN"), write=True, run=fake2)
    assert not res.read_only and fake2.calls[-1][-2:] == ["-o", "rw"]


def test_fast_startup_is_explained_from_hiberfil(tmp_path):
    _fake_windows(tmp_path, hiber=True)
    fake = FakeUdisks(tmp_path)
    res = drives.mount(_ntfs(), write=True, run=fake)
    assert res.ok and res.read_only and res.code == "fast_startup" and "Turn off Fast Startup" in res.message
    assert not any("rw" in c for c in fake.calls)


@pytest.mark.parametrize("err", ["mount: wrong fs type, bad option", "volume is dirty and \"force\" flag is not set!",
                                 "Windows is hibernated, refused to mount"])
def test_a_refused_writable_mount_falls_back_with_the_reason(tmp_path, err):
    fake = FakeUdisks(tmp_path, rw_error=err)
    res = drives.mount(_ntfs(), run=fake)
    assert res.ok and res.read_only and res.code == "fast_startup" and "Fast Startup" in res.message


def test_mount_refuses_protected_and_explains_bitlocker():
    called = []
    run = lambda *a, **k: called.append(a) or done()
    for v in (drives.Volume("/dev/x", is_esp=True, fstype="vfat"), drives.Volume("/dev/x", is_recovery=True, fstype="ntfs"),
              drives.Volume("/dev/x", is_live_medium=True, fstype="vfat")):
        assert drives.mount(v, run=run).code == "protected"
    res = drives.mount(drives.Volume("/dev/x", fstype="BitLocker"), run=run)
    assert res.code == "bitlocker" and "recovery key" in res.message
    assert not called


def test_bitlocker_key_goes_over_stdin_and_is_never_logged(caplog):
    key = "111111-222222-333333-444444-555555-666666-777777-888888"
    seen = {}

    def fake(argv, **kw):
        seen.update(argv=argv, input=kw.get("input"))
        return done(rc=1, stderr="wrong")
    with caplog.at_level(logging.DEBUG):
        res = drives.unlock(drives.Volume("/dev/sda1", fstype="BitLocker"), key, run=fake)
    assert not res.ok and key not in res.message and key not in caplog.text
    assert seen["input"] == key and key not in " ".join(seen["argv"]) and "--key-file" in seen["argv"]
    ok = drives.unlock(drives.Volume("/dev/sda1", fstype="BitLocker"), key,
                       run=lambda a, **k: done("Unlocked /dev/sda1 as /dev/dm-0.\n"))
    assert ok.ok and ok.mountpoint == "/dev/dm-0"


def test_unmount_says_when_busy():
    res = drives.unmount(_ntfs(), run=lambda a, **k: done(rc=1, stderr="target is busy"))
    assert not res.ok and res.code == "busy" and "in use" in res.message


def test_live_status_labels_ram_and_the_free_space(tmp_path):
    layout = real_layout()
    usage = lambda p: SimpleNamespace(total=50 * 10 ** 9, free=25 * 10 ** 9)
    run = lambda argv, **k: done(json.dumps({"blockdevices": layout}))
    s = drives.live_status(archiso=tmp_path, usage=usage, run=run)
    assert s.live and "25.0 GB free is RAM, not your disk" in s.message and "nothing here is kept" in s.message
    assert "unallocated" in s.install_hint and "/dev/nvme0n1" in s.install_hint and "XF-2TB" in s.install_hint
    assert not drives.live_status(archiso=tmp_path / "nope").live


# --------------------------------------------------------------------------- OS switching
EFIBOOT = """BootCurrent: 0001
Timeout: 1 seconds
BootOrder: 0001,0000,0002
Boot0000* Windows Boot Manager\tHD(1,GPT,aaaaaaaa-0000-0000-0000-000000000001,0x800,0x32000)/File(\\EFI\\MICROSOFT\\BOOT\\BOOTMGFW.EFI)
Boot0001* HalOS\tHD(4,GPT,bbbbbbbb-0000-0000-0000-000000000002,0x800,0x100000)/File(\\EFI\\Halo\\shimx64.efi)
Boot0002* UEFI: PXE IPv4\tPciRoot(0x0)
"""


def _efi_run(calls):
    def run(argv, **kw):
        calls.append(argv)
        return done(EFIBOOT if argv[0] == "efibootmgr" else "")
    return run


def test_restart_into_windows_uses_only_listed_entries(monkeypatch):
    monkeypatch.setattr(os_switch, "available", lambda: (True, ""))
    calls = []
    res = os_switch.restart_into("windows", run=_efi_run(calls))
    assert res["ok"] and res["entry"] == "0000"
    assert calls[-1] == ["systemctl", "reboot"] and calls[-2][0] == "pkexec" and calls[-2][-1] == "0000"
    calls.clear()
    assert not os_switch.restart_into("0009", run=_efi_run(calls))["ok"]
    assert not os_switch.restart_into("0000; rm -rf /", run=_efi_run(calls))["ok"]
    assert not os_switch.restart_into("0001", run=_efi_run(calls))["ok"]      # the running system
    assert not any(c[0] == "pkexec" for c in calls)


def test_a_refused_bootnext_doesnt_reboot(monkeypatch):
    monkeypatch.setattr(os_switch, "available", lambda: (True, ""))
    calls = []

    def run(argv, **kw):
        calls.append(argv)
        return done(EFIBOOT) if argv[0] == "efibootmgr" else done(rc=126, stderr="Not authorized")
    res = os_switch.restart_into("windows", run=run)
    assert not res["ok"] and "Not authorized" in res["message"] and ["systemctl", "reboot"] not in calls


def test_helper_when_installed_and_argument_checks(monkeypatch, tmp_path):
    helper = tmp_path / "halo-efiboot"
    helper.write_text("")
    monkeypatch.setattr(recovery, "EFIBOOT_HELPER", str(helper))
    cmds = recovery.boot_once(recovery.BootEntry("0000", "Windows", True))
    assert cmds[0] == ["pkexec", str(helper), "next", "0000"]
    with pytest.raises(ValueError):
        os_switch.remove_entry_argv("00; x")


def test_helper_and_polkit_rule_are_narrow():
    helper = (SYSTEM / "halo-efiboot").read_text(encoding="utf-8")
    assert "^[0-9A-F]{4}$" in helper and 'efibootmgr --quiet --bootnext "$num"' in helper
    assert "export PATH=/usr/bin" in helper and "eval" not in helper
    rules = (SYSTEM / "50-halo-drives.rules").read_text(encoding="utf-8")
    pattern = re.search(r"/\^(.+?)\$/", rules)[1].replace("\\/", "/")
    assert re.fullmatch(pattern, "/usr/lib/halo/halo-efiboot next 0000")
    assert not re.fullmatch(pattern, "/usr/lib/halo/halo-efiboot delete 0000")
    assert not re.fullmatch(pattern, "/usr/lib/halo/halo-efiboot next 0000 x")
    assert "format" not in rules.split("polkit.addRule")[2].replace("Formatting", "")
    policy = (SYSTEM / "org.halos.efiboot.policy").read_text(encoding="utf-8")
    assert "<allow_active>auth_admin</allow_active>" in policy and "/usr/lib/halo/halo-efiboot" in policy
    pkg = (SYSTEM / "PKGBUILD").read_text(encoding="utf-8")
    assert "usr/share/polkit-1/rules.d/50-halo-drives.rules" in pkg


def test_voice_restart_always_asks(monkeypatch):
    from core.permissions import ALWAYS_CONFIRM
    from modules.agent import winctl_intents as w
    from modules.agent.autonomy.policy import ALWAYS_ASK
    assert "system.restart_into" in ALWAYS_CONFIRM and "system.restart_into" in ALWAYS_ASK
    monkeypatch.setattr(w, "os", SimpleNamespace(name="posix"))
    for said in ("restart into windows", "reboot to windows", "switch to windows", "restart my pc into windows"):
        assert w.parse_winctl(said).name == "system.restart_into", said
    assert w.parse_winctl("restart") is None or w.parse_winctl("restart").name == "system.power"
    from modules.automation.tools import ToolRegistry
    reg = ToolRegistry()
    os_switch.register_os_switch_tools(reg)
    tool = reg.get("system.restart_into")
    assert tool is not None and not tool.llm_exposed


def _bcd(*partuuids):
    import uuid
    return b"regf" + b"".join(b"\0" * 8 + uuid.UUID(p).bytes_le for p in partuuids)


OLD_V, MAIN_V = "11111111-0000-0000-0000-00000000000a", "22222222-0000-0000-0000-00000000000b"
ESP_A, ESP_B = "aaaaaaaa-0000-0000-0000-000000000001", "cccccccc-0000-0000-0000-000000000003"
TWO_ENTRIES = (f"Boot0000* Windows Boot Manager\tHD(1,GPT,{ESP_A},0x800,0x1)/File(\\EFI\\Microsoft\\Boot\\bootmgfw.efi)\n"
               f"Boot0003* Windows Boot Manager\tHD(1,GPT,{ESP_B},0x800,0x1)/File(\\EFI\\Microsoft\\Boot\\bootmgfw.efi)\n")


def test_one_windows_entry_is_never_offered_for_removal():
    # This PC: one entry, on the ADATA ESP, that may boot the current Windows.
    res = os_switch.stale_windows_entry(OLD_V, MAIN_V, lambda p: _bcd(OLD_V), run=lambda a, **k: done(EFIBOOT))
    assert res["entry"] is None and "only one" in res["reason"]


@pytest.mark.parametrize("bcds,expected", [
    ({ESP_A: _bcd(OLD_V), ESP_B: _bcd(MAIN_V)}, "0000"),         # proven: A only starts the old one
    ({ESP_A: _bcd(OLD_V, MAIN_V), ESP_B: _bcd(MAIN_V)}, None),   # A also starts the main one
    ({ESP_A: _bcd(OLD_V), ESP_B: _bcd(OLD_V)}, None),            # nothing proves the main one still boots
    ({ESP_A: None, ESP_B: _bcd(MAIN_V)}, None),                  # couldn't read one
])
def test_stale_boot_entry_needs_proof(bcds, expected):
    res = os_switch.stale_windows_entry(OLD_V, MAIN_V, lambda p: bcds[p], run=lambda a, **k: done(TWO_ENTRIES))
    assert (res["entry"]["num"] if res["entry"] else None) == expected


# --------------------------------------------------------------------------- migration: fixtures
@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    data = tmp_path / "_data"
    data.mkdir()
    monkeypatch.setattr(wm, "data_path", lambda *p: data.joinpath(*p))
    return data


def make_link(link: Path, to: Path):
    """A directory link this OS lets a test make: a symlink, or on Windows without the privilege, a junction."""
    try:
        os.symlink(to, link, target_is_directory=True)
    except OSError:
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(to)], check=True, capture_output=True)
    assert drives.is_link(link)


def fake_symlink(src, dst, target_is_directory=False):
    """Stands in for os.symlink where the host doesn't allow it: records a home-folder link as a text file."""
    if "_data" not in Path(dst).parts:         # the stable mount link is re-pointed each time; nothing to record
        Path(dst).write_text(str(src), encoding="utf-8")


def install_at(root: Path, **kw) -> wm.WindowsInstall:
    inst = wm.probe_root(root)
    assert inst is not None
    inst.device = kw.get("device", "/dev/nvme1n1p3")
    inst.label = kw.get("label", "Windows")
    inst.uuid = kw.get("uuid", "OLD-UUID")
    inst.partuuid = kw.get("partuuid", OLD_V)
    return inst


def rw_mount(root, source="/dev/nvme1n1p3"):
    return lambda r: wm.MountInfo(str(root), "ntfs3", source, "rw,relatime")


def full_windows(root: Path) -> Path:
    """E: as it really is: system folders, Users, boot files, and a neighbour that isn't on any list."""
    _fake_windows(root)
    for d in ("Program Files/App", "Program Files (x86)/App", "ProgramData/Thing", "$Recycle.Bin/S-1", "Windows.old/old",
              "PerfLogs", "Boot", "EFI", "Recovery", "System Volume Information", "My Own Stuff"):
        (root / d).mkdir(parents=True, exist_ok=True)
    (root / "Program Files" / "App" / "app.exe").write_bytes(b"a" * 1000)
    (root / "My Own Stuff" / "keep.txt").write_text("mine")
    (root / "Users" / "seb" / "Documents").mkdir()
    (root / "Users" / "seb" / "Documents" / "thesis.doc").write_text("precious")
    for f in ("pagefile.sys", "swapfile.sys", "bootmgr", "BOOTNXT"):
        (root / f).write_bytes(b"p" * 10)
    (root / "Boot" / "BCD").write_bytes(b"bcd")
    return root


@pytest.fixture
def old_and_main(tmp_path):
    old = full_windows(tmp_path / "E")
    main = full_windows(tmp_path / "C")
    return (install_at(old), install_at(main, device="/dev/nvme0n1p2", label="2nd_M.2", uuid="MAIN-UUID", partuuid=MAIN_V))


# --------------------------------------------------------------------------- detection
def test_detection_and_main_is_the_most_recently_used(tmp_path):
    e = _fake_windows(tmp_path / "E", users=("old",))
    c = _fake_windows(tmp_path / "C", users=("seb", "guest"))
    (tmp_path / "D" / "Movies").mkdir(parents=True)
    os.utime(e / "Windows/System32/config/SOFTWARE", (1000, 1000))
    os.utime(e / "Users/old/NTUSER.DAT", (2000, 2000))
    os.utime(c / "Users/seb/NTUSER.DAT", (9000, 9000))
    os.utime(c / "Users/guest/NTUSER.DAT", (3000, 3000))
    os.utime(c / "Windows/System32/config/SOFTWARE", (5000, 5000))
    assert wm.probe_root(tmp_path / "D") is None
    installs = [wm.probe_root(e), wm.probe_root(c)]
    assert wm.pick_main(installs).root == c and installs[1].last_used == 9000
    assert installs[1].users == ["guest", "seb"]         # Public isn't a person
    assert wm.pick_main([]) is None


def test_detect_installs_looks_read_only_and_lets_data_drives_go(tmp_path):
    c = _fake_windows(tmp_path / "C")
    data = tmp_path / "D"
    data.mkdir()
    calls = []

    def run(argv, **kw):
        calls.append(argv)
        if argv[1] == "unmount":
            return done()
        return done(f"Mounted {argv[3]} at {c if argv[3] == '/dev/c' else data}\n")
    vols = [drives.Volume("/dev/c", fstype="ntfs", uuid="C1"), drives.Volume("/dev/d", fstype="ntfs", uuid="D1"),
            drives.Volume("/dev/esp", fstype="ntfs", is_esp=True), drives.Volume("/dev/b", fstype="BitLocker", label="Locked")]
    found = wm.detect_installs(vols, run=run)
    assert [i.device for i in found["installs"]] == ["/dev/c"] and [v.device for v in found["locked"]] == ["/dev/b"]
    assert all(c_[-2:] == ["-o", "ro"] for c_ in calls if c_[1] == "mount")
    assert ["udisksctl", "unmount", "-b", "/dev/d"] in calls and not any("/dev/esp" in c_ for c_ in calls)


def test_linux_home_detection(tmp_path):
    (tmp_path / "old" / "home" / "me" / ".config").mkdir(parents=True)
    (tmp_path / "old" / "home" / "me" / "Documents").mkdir()
    (tmp_path / "old" / "home" / "lost+found").mkdir()
    v = drives.Volume("/dev/sdb2", fstype="ext4", mountpoint=str(tmp_path / "old"), uuid="L1")
    homes = wm.linux_homes([v, drives.Volume("/dev/x", fstype="ntfs")], running=set())
    assert homes[0].users == ["me"] and homes[0].kind == "linux"
    assert [c.name for c in wm.plan_folders(homes[0], "me")] == ["Documents"]
    assert wm.linux_homes([v], running={os.stat(tmp_path / "old").st_dev}) == []      # the running system


# --------------------------------------------------------------------------- files
def test_folders_skip_junctions_and_prefer_onedrive_when_moved(tmp_path):
    root = _fake_windows(tmp_path / "C")
    profile = root / "Users" / "seb"
    (profile / "Documents").mkdir()
    (profile / "Downloads").mkdir()
    (profile / "Downloads" / "a.zip").write_text("a")
    (profile / "OneDrive" / "Pictures").mkdir(parents=True)
    (tmp_path / "elsewhere").mkdir()
    make_link(profile / "Music", tmp_path / "elsewhere")
    choices = {c.name: c for c in wm.plan_folders(install_at(root), "seb")}
    assert set(choices) == {"Documents", "Downloads", "Pictures"} and "Music" not in choices
    assert "OneDrive" in str(choices["Pictures"].source) and choices["Downloads"].mode == "link"
    with pytest.raises(ValueError):
        wm.profile_dir(install_at(root), "../..")


def test_link_replaces_an_empty_folder_and_never_a_full_one(tmp_path):
    root = _fake_windows(tmp_path / "C")
    src = root / "Users" / "seb" / "Documents"
    src.mkdir()
    (root / "Users" / "seb" / "Pictures").mkdir()
    home = tmp_path / "home"
    (home / "Documents").mkdir(parents=True)
    (home / "Pictures").mkdir()
    (home / "Pictures" / "mine.png").write_text("mine")
    inst = install_at(root)
    r = wm.link_folder("Documents", src, inst, home, fake_symlink)
    assert r["path"] == str(home / "Documents") and r["target"].endswith(os.path.join("Users", "seb", "Documents"))
    assert str(wm.stable_path("OLD-UUID")) in r["target"]        # survives the mount point moving
    r = wm.link_folder("Pictures", root / "Users/seb/Pictures", inst, home, fake_symlink)
    assert r["path"] == str(home / "Pictures" / "From Windows") and (home / "Pictures" / "mine.png").exists()


def test_stable_path_refuses_odd_ids():
    with pytest.raises(ValueError):
        wm.stable_path("../../etc")


def test_copy_skips_appdata_and_links_and_never_overwrites(tmp_path):
    src = tmp_path / "src"
    (src / "AppData" / "Local").mkdir(parents=True)
    (src / "AppData" / "Local" / "secret").write_text("no")
    (src / "sub").mkdir()
    (src / "sub" / "a.txt").write_text("new")
    (src / "desktop.ini").write_text("no")
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "private.txt").write_text("outside")
    make_link(src / "link", tmp_path / "outside")
    home = tmp_path / "home"
    existing = home / "Documents" / "From Windows" / "sub" / "a.txt"
    existing.parent.mkdir(parents=True)
    existing.write_text("different content")
    r = wm.copy_folder("Documents", src, home)
    dest = home / "Documents" / "From Windows"
    assert existing.read_text() == "different content"
    assert (dest / "sub" / "a (from Windows).txt").read_text() == "new"
    assert not (dest / "AppData").exists() and not (dest / "desktop.ini").exists() and not (dest / "link").exists()
    assert r["copied"] == 1


def test_copy_refuses_when_there_is_no_room(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "big").write_text("x")
    r = wm.copy_folder("Videos", src, tmp_path / "home", usage=lambda p: SimpleNamespace(free=10))
    assert r["failed"] and "Link it instead" in r["note"]


def test_run_files_records_and_refuses_paths_off_the_volume(tmp_path, monkeypatch):
    root = _fake_windows(tmp_path / "C")
    (root / "Users/seb/Documents").mkdir()
    inst = install_at(root)
    outside = wm.FolderChoice("Music", tmp_path, "copy")
    home = tmp_path / "home"
    home.mkdir()
    res = wm.run_files(inst, "seb", [outside], home=home, symlink=fake_symlink)
    assert res[0]["failed"] and not wm.migration_ran(inst.uuid)
    res = wm.run_files(inst, "seb", wm.plan_folders(inst, "seb"), home=home, symlink=fake_symlink)
    assert not res[0].get("failed") and wm.migration_ran(inst.uuid)
    auto = (home / ".config/autostart/saint-migrated-drives.desktop").read_text(encoding="utf-8")
    assert "core.windows_migration login-mount" in auto and wm._load_state()["mounts"]["OLD-UUID"] == {"write": False}


def test_login_mount_uses_udisks_and_repoints(tmp_path, monkeypatch):
    wm._save_state({"mounts": {"U1": {"write": False}, "GONE": {"write": False}}})
    pointed = []
    monkeypatch.setattr(wm, "_point_stable", lambda u, m, symlink=None: pointed.append((u, m)))
    monkeypatch.setattr(wm.drives, "volumes", lambda run: [drives.Volume("/dev/x", fstype="ntfs", uuid="U1")])
    monkeypatch.setattr(wm.drives, "mount", lambda v, write=False, run=None: drives.Result(True, mountpoint="/run/media/me/C"))
    assert wm.login_mount() == {"U1": True, "GONE": False}
    assert pointed == [("U1", "/run/media/me/C")]


# --------------------------------------------------------------------------- browser and settings
def _browser_profile(root: Path) -> Path:
    profile = root / "Users" / "seb"
    chrome = profile / "AppData/Local/Google/Chrome/User Data/Default"
    chrome.mkdir(parents=True)
    (chrome / "Bookmarks").write_text(json.dumps({"roots": {
        "bookmark_bar": {"children": [
            {"type": "url", "name": "Example <b>", "url": "https://example.com/?a=1&b=2"},
            {"type": "url", "name": "evil", "url": "javascript:alert(1)"},
            {"type": "folder", "name": "Work", "children": [{"type": "url", "name": "Git", "url": "https://git.example"}]}]},
        "other": {"children": []}}}), encoding="utf-8")
    (chrome / "Login Data").write_text("SECRET-PASSWORD")
    (chrome / "Cookies").write_text("SECRET-COOKIE")
    fx = profile / "AppData/Roaming/Mozilla/Firefox/Profiles/abc.default"
    fx.mkdir(parents=True)
    (fx / "logins.json").write_text("SECRET-LOGIN")
    con = sqlite3.connect(fx / "places.sqlite")
    con.executescript("CREATE TABLE moz_places(id INTEGER PRIMARY KEY, url TEXT);"
                      "CREATE TABLE moz_bookmarks(id INTEGER PRIMARY KEY, type INT, fk INT, parent INT, title TEXT);"
                      "INSERT INTO moz_places VALUES (1,'https://mozilla.example'),(2,'place:sort=8');"
                      "INSERT INTO moz_bookmarks VALUES (1,2,NULL,0,'menu'),(2,1,1,1,'Moz'),(3,1,2,1,'Recent');")
    con.close()
    return profile


def test_bookmarks_are_read_escaped_and_no_secrets_cross(tmp_path):
    root = _fake_windows(tmp_path / "C")
    _browser_profile(root)
    home = tmp_path / "home"
    res = wm.import_bookmarks(install_at(root), "seb", home, run=lambda *a, **k: done())
    assert res["by_browser"] == {"Chrome": 2, "Firefox": 1} and res["errors"] == []
    page = Path(res["file"]).read_text(encoding="utf-8")
    assert "javascript:" not in page and "place:" not in page
    assert "Example &lt;b&gt;" in page and "https://example.com/?a=1&amp;b=2" in page and "Bookmarks bar / Work" in page
    for f in home.rglob("*"):
        if f.is_file():
            data = f.read_text(encoding="utf-8", errors="ignore")
            assert "SECRET" not in data, f
    assert res["firefox"] == "manual"                    # no Firefox profile could be made here


def test_firefox_takes_the_file_only_when_it_has_no_bookmarks(tmp_path):
    home = tmp_path / "home"
    prof = home / ".mozilla" / "firefox" / "x.default-release"
    prof.mkdir(parents=True)
    (home / ".mozilla/firefox/profiles.ini").write_text("[Profile0]\nName=default\nIsRelative=1\nPath=x.default-release\nDefault=1\n")
    page = tmp_path / "b.html"
    page.write_text("<html>")
    res = wm.install_into_firefox(page, home)
    assert res["firefox"] == "next_start" and (prof / "bookmarks.html").exists()
    assert "importBookmarksHTML" in (prof / "prefs.js").read_text() and not (prof / "user.js").exists()
    (prof / "places.sqlite").write_text("has bookmarks")
    (prof / "prefs.js").unlink()
    assert wm.install_into_firefox(page, home)["firefox"] == "manual" and not (prof / "prefs.js").exists()


def test_wallpaper_vscode_steam_and_values(tmp_path):
    root = _fake_windows(tmp_path / "C")
    profile = root / "Users/seb"
    themes = profile / "AppData/Roaming/Microsoft/Windows/Themes"
    themes.mkdir(parents=True)
    (themes / "TranscodedWallpaper").write_bytes(b"\xff\xd8\xff\xe0 jpeg")
    home = tmp_path / "home"
    inst = install_at(root)
    r = wm.import_wallpaper(inst, "seb", home, run=lambda *a, **k: done())
    assert r["ok"] and r["path"].endswith("Windows wallpaper.jpg")
    (themes / "TranscodedWallpaper").write_bytes(b"not a picture")
    assert not wm.import_wallpaper(inst, "seb", home)["ok"]

    code = profile / "AppData/Roaming/Code/User"
    (code / "snippets").mkdir(parents=True)
    (code / "settings.json").write_text('{"a": 1}')
    (code / "snippets" / "py.json").write_text("{}")
    ext = profile / ".vscode/extensions"
    (ext / "ms-python.python-2024.1.0-win32-x64").mkdir(parents=True)
    (ext / "bad name; rm").mkdir()
    existing = home / ".config/Code/User/keybindings.json"
    existing.parent.mkdir(parents=True)
    existing.write_text("mine")
    (code / "keybindings.json").write_text("theirs")
    r = wm.import_vscode(inst, "seb", home)
    assert r["extensions"] == ["ms-python.python"] and "settings.json" in r["copied"] and "keybindings.json" not in r["copied"]
    assert existing.read_text() == "mine"

    steam = root / "Program Files (x86)/Steam/steamapps"
    steam.mkdir(parents=True)
    (steam / "libraryfolders.vdf").write_text('"libraryfolders" { "0" { "path" "D:\\\\SteamLibrary" } }')
    assert wm.steam_libraries(inst) == ["D:\\SteamLibrary"]

    (root / "Windows/System32/config/SYSTEM").write_bytes(b"regf")

    class Hive:
        def __init__(self, path): self.path = path
        def root(self): return "root"
        def node_get_child(self, node, name): return f"{node}/{name}"
        def node_get_value(self, node, name): return (node, name)
        def value_string(self, v): return "SEB-PC" if v[1] == "ComputerName" else "Eastern Standard Time"
    values = wm.windows_values(inst, hive=Hive)
    assert values["Computer name"] == "SEB-PC" and values["Time zone"] == "Eastern Standard Time"
    assert wm.windows_values(inst, hive=lambda p: (_ for _ in ()).throw(ImportError("no hivex")))["Accounts"] == "seb"
    assert "can't run on Linux" in wm.SETTINGS_NOTICE


# --------------------------------------------------------------------------- apps
def test_collect_app_names(tmp_path):
    root = _fake_windows(tmp_path / "C")
    for d in ("Common Files", "Windows Defender", "Microsoft Update Health Tools", "Mozilla Firefox", "VideoLAN", "NVIDIA Corporation"):
        (root / "Program Files" / d).mkdir(parents=True)
    menu = root / "ProgramData/Microsoft/Windows/Start Menu/Programs"
    (menu / "Discord Inc").mkdir(parents=True)
    (menu / "Discord Inc" / "Discord.lnk").write_bytes(b"lnk")
    (menu / "Uninstall Foo.lnk").write_bytes(b"lnk")

    class Hive:
        def __init__(self, path): pass
        def root(self): return "r"
        def node_get_child(self, node, name): return "uninstall" if name == "Uninstall" else "x"
        def node_children(self, node): return ["a"] if node == "uninstall" else []
        def node_get_value(self, node, name): return name
        def value_string(self, v): return "Blender 4.2"
    names = wm.collect_app_names(install_at(root), hive=Hive)
    assert {"Mozilla Firefox", "VideoLAN", "Discord", "Blender"} <= set(names)
    assert not any(re.search("Common Files|Defender|Update Health|NVIDIA|Uninstall", n) for n in names)


def test_match_apps_prefers_linux_then_wine():
    from core.store import Result
    code = Result("featured", "vscode", "Visual Studio Code")
    npp = Result("windows", "Notepad++.Notepad++", "Notepad++")
    wrong = Result("repo", "firefox", "firefox")

    def search(q, sources=()):
        if "featured" in sources:
            return {"vscode": [code], "python": [wrong]}.get(q, [])
        return {"notepad++": [npp]}.get(q, [])
    out = {m.windows_name: m for m in wm.match_apps(["Microsoft VS Code", "Visual Studio Code", "Notepad++", "Obscure Tool", "Python 3"], search)}
    assert out["Microsoft VS Code"].result is code and out["Microsoft VS Code"].kind == "native"
    assert "Visual Studio Code" not in out                # one row per app
    assert out["Notepad++"].kind == "wine" and out["Obscure Tool"].kind == "none"
    assert out["Python 3"].result is None                 # a search hit that isn't this app isn't a match


def test_match_apps_survives_a_failing_search():
    def search(q, sources=()):
        raise OSError("offline")
    assert [m.kind for m in wm.match_apps(["Steam"], search)] == ["none"]


def test_wine_matches_install_through_the_stores_path():
    from core import store
    from core.store import Result
    steps = store.plan(Result("repo", "blender", "blender"))
    assert steps[0].argv[:2] == ["pkexec", "pacman"]


# --------------------------------------------------------------------------- removing the old Windows
def _plan(old, main, root=None, **kw):
    return wm.build_removal(old, main, mount_info=kw.pop("mount_info", rw_mount(root or old.root, old.device)),
                            running=kw.pop("running", set()), **kw)


def _remove(plan, main, typed=None, **kw):
    return wm.execute_removal(plan, main, plan.token if typed is None else typed,
                              mount_info=kw.pop("mount_info", rw_mount(plan.install.root, plan.install.device)),
                              running=kw.pop("running", set()), **kw)


def _names(root: Path):
    return sorted(p.name for p in root.iterdir())


def test_plan_lists_exact_folders_and_keeps_users_and_boot_files(old_and_main):
    old, main = old_and_main
    plan = _plan(old, main)
    assert plan.allowed and plan.token == "Windows"
    names = {Path(i.path).name for i in plan.items}
    assert names == {"Windows", "Program Files", "Program Files (x86)", "ProgramData", "$Recycle.Bin", "Windows.old",
                     "PerfLogs", "pagefile.sys", "swapfile.sys"}
    assert plan.size >= 1100


def test_removal_deletes_only_the_list(old_and_main):
    old, main = old_and_main
    root = Path(old.root)
    res = _remove(_plan(old, main), main)
    assert res["ok"] and res["freed"] >= 1000 and not res["dry_run"]
    assert _names(root) == sorted(["BOOTNXT", "Boot", "EFI", "My Own Stuff", "Recovery", "System Volume Information",
                                   "Users", "bootmgr"], key=str)
    assert (root / "My Own Stuff/keep.txt").read_text() == "mine"
    assert (root / "Users/seb/Documents/thesis.doc").read_text() == "precious"
    assert (root / "Boot/BCD").exists() and (Path(main.root) / "Windows").exists()
    log = Path(wm.data_path(wm.LOG_NAME)).read_text(encoding="utf-8")
    assert "removal start" in log and "Program Files" in log and "removal done" in log


def test_dry_run_deletes_nothing(old_and_main):
    old, main = old_and_main
    before = sorted(str(p) for p in Path(old.root).rglob("*"))
    res = _remove(_plan(old, main), main, dry_run=True)
    assert res["ok"] and res["dry_run"] and res["freed"] >= 1000
    assert sorted(str(p) for p in Path(old.root).rglob("*")) == before
    assert "DRY RUN" in Path(wm.data_path(wm.LOG_NAME)).read_text(encoding="utf-8")


def test_refuses_the_main_install_by_any_identity(old_and_main):
    old, main = old_and_main
    assert any("main" in r for r in _plan(main, main, root=main.root).refusals)
    for same in ("uuid", "partuuid", "device"):
        twin = install_at(Path(old.root), device="/dev/a", uuid="A", partuuid="B", label="Windows")
        setattr(twin, same, getattr(old, same))
        assert any("main" in r for r in wm.check_removal(old, twin, mount_info=rw_mount(old.root, old.device), running=set())), same
    assert any("main Windows first" in r for r in wm.check_removal(old, None, mount_info=rw_mount(old.root), running=set()))


def _assert_refused_and_intact(plan, main, **kw):
    root = Path(plan.install.root)
    before = sorted(str(p) for p in root.rglob("*"))
    res = _remove(plan, main, **kw)
    assert not res["ok"] and res["refused"] and res["freed"] == 0
    assert sorted(str(p) for p in root.rglob("*")) == before


def test_refuses_read_only_volume(old_and_main):
    old, main = old_and_main
    ro = lambda r: wm.MountInfo(str(old.root), "ntfs3", old.device, "ro,relatime")
    plan = _plan(old, main, mount_info=ro)
    assert not plan.allowed and any("read-write" in r for r in plan.refusals)
    _assert_refused_and_intact(plan, main, mount_info=ro)


@pytest.mark.parametrize("info,why", [
    (lambda r: None, "mounted volume"),                                               # not a mount point
    (lambda r: wm.MountInfo(str(r), "vfat", "/dev/nvme1n1p3", "rw"), "isn't NTFS"),   # an ESP-like filesystem
    (lambda r: wm.MountInfo(str(r), "ntfs3", "/dev/sdz9", "rw"), "not /dev/"),        # another device mounted there
])
def test_refuses_unexpected_mounts(old_and_main, info, why):
    old, main = old_and_main
    plan = _plan(old, main, mount_info=info)
    assert any(why in r for r in plan.refusals)
    _assert_refused_and_intact(plan, main, mount_info=info)


def test_refuses_the_volume_hosting_the_running_os(old_and_main):
    old, main = old_and_main
    running = {os.stat(old.root).st_dev}
    plan = _plan(old, main, running=running)
    assert any("running" in r for r in plan.refusals)
    _assert_refused_and_intact(plan, main, running=running)


def test_default_running_devices_include_this_process():
    assert os.stat(os.sys.executable).st_dev in wm._running_devices()


@pytest.mark.parametrize("parttype", [ESP_TYPE, MSR_TYPE, RECOVERY_TYPE])
def test_refuses_esp_msr_and_recovery(old_and_main, parttype):
    old, main = old_and_main
    old.parttype = parttype
    assert any("never touched" in r for r in _plan(old, main).refusals)


def test_refuses_a_volume_without_windows_or_hibernated(tmp_path, old_and_main):
    old, main = old_and_main
    (tmp_path / "plain").mkdir()
    fake = wm.WindowsInstall(tmp_path / "plain", "/dev/nvme1n1p3", "X", "Z", "Y")
    assert any("doesn't hold a Windows" in r for r in wm.check_removal(fake, main, mount_info=rw_mount(fake.root), running=set()))
    (Path(old.root) / "hiberfil.sys").write_bytes(b"HIBR1234")
    plan = _plan(old, main)
    assert any("hibernated" in r for r in plan.refusals)


def test_linux_home_cant_be_removed(old_and_main):
    old, main = old_and_main
    old.kind = "linux"
    assert any("Only an old Windows" in r for r in _plan(old, main).refusals)


@pytest.mark.parametrize("typed", ["", "windows", "Windows ", "E:", "yes"])
def test_needs_the_exact_name_typed(old_and_main, typed):
    old, main = old_and_main
    _assert_refused_and_intact(_plan(old, main), main, typed=typed)


def test_label_less_volume_uses_the_device_name(old_and_main):
    old, main = old_and_main
    old.label = ""
    assert _plan(old, main).token == "nvme1n1p3"


def test_a_tampered_plan_cant_reach_outside_the_list(tmp_path, old_and_main):
    old, main = old_and_main
    root = Path(old.root)
    outside = tmp_path / "outside.txt"
    outside.write_text("safe")
    for path in (str(outside), str(root / "My Own Stuff"), str(root / "Users"), str(root / "Boot"),
                 str(root / "Windows" / ".." / ".." / "outside.txt"), str(root / "bootmgr"),
                 str(root / "Recovery"), str(root / "EFI")):
        plan = _plan(old, main)
        plan.items.append(wm.RemovalItem(path, "dir"))
        _assert_refused_and_intact(plan, main)
    assert outside.read_text() == "safe"


def test_top_level_link_is_not_followed_or_listed(tmp_path, old_and_main):
    old, main = old_and_main
    root = Path(old.root)
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "precious.txt").write_text("keep")
    (root / "PerfLogs").rmdir()
    make_link(root / "PerfLogs", victim)
    plan = _plan(old, main)
    assert str(root / "PerfLogs") in plan.skipped
    assert "PerfLogs" not in {Path(i.path).name for i in plan.items}
    assert _remove(plan, main)["ok"]
    assert (victim / "precious.txt").read_text() == "keep" and drives.is_link(root / "PerfLogs")


def test_a_link_swapped_in_after_planning_is_refused(tmp_path, old_and_main):
    old, main = old_and_main
    root = Path(old.root)
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "precious.txt").write_text("keep")
    plan = _plan(old, main)
    (root / "PerfLogs").rmdir()
    make_link(root / "PerfLogs", victim)
    res = _remove(plan, main)
    assert res["refused"] and (victim / "precious.txt").read_text() == "keep" and (root / "Windows").exists()


def test_links_inside_are_removed_as_links_never_entered(tmp_path, old_and_main):
    old, main = old_and_main
    root = Path(old.root)
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "precious.txt").write_text("keep")
    make_link(root / "ProgramData" / "Application Data", victim)
    res = _remove(_plan(old, main), main)
    assert res["ok"], res["errors"]
    assert (victim / "precious.txt").read_text() == "keep" and not (root / "ProgramData").exists()


def test_size_measure_doesnt_follow_links(tmp_path, old_and_main):
    old, main = old_and_main
    root = Path(old.root)
    victim = tmp_path / "big"
    victim.mkdir()
    (victim / "huge.bin").write_bytes(b"x" * 500000)
    make_link(root / "ProgramData" / "out", victim)
    assert _plan(old, main).size < 500000


def test_user_files_need_a_finished_migration_and_no_links(old_and_main):
    old, main = old_and_main
    plan = _plan(old, main, include_users=True)
    assert any("Files step" in r for r in plan.refusals)
    _assert_refused_and_intact(plan, main)
    wm._record_migration(old.uuid, "files")
    wm._remember_mount(old, False)
    assert any("still links" in r for r in _plan(old, main, include_users=True).refusals)
    state = wm._load_state()
    state["mounts"] = {}
    wm._save_state(state)
    plan = _plan(old, main, include_users=True)
    assert plan.allowed and "Users" in {Path(i.path).name for i in plan.items}
    assert _remove(plan, main)["ok"] and not (Path(old.root) / "Users").exists()
    assert (Path(old.root) / "Boot" / "BCD").exists() and (Path(main.root) / "Users").exists()


def test_stopping_part_way_keeps_the_rest(old_and_main):
    import threading
    old, main = old_and_main
    cancel = threading.Event()
    cancel.set()
    res = _remove(_plan(old, main), main, cancel=cancel)
    assert res["cancelled"] and (Path(old.root) / "Windows").exists()


def test_mount_info_parser(tmp_path):
    root = tmp_path / "mnt with space"
    root.mkdir()
    real = os.path.realpath(root).replace(" ", "\\040")
    f = tmp_path / "mountinfo"
    f.write_text(f"36 35 8:1 / {real} rw,nosuid shared:1 - ntfs3 /dev/sdb3 rw,uid=1000\n"
                 "37 35 8:2 / /other ro - ext4 /dev/sda1 rw\n", encoding="utf-8")
    info = wm.read_mount_info(root, str(f))
    assert info.fstype == "ntfs3" and info.source == "/dev/sdb3" and "rw" in info.options.split(",")
    assert wm.read_mount_info(tmp_path, str(f)) is None
    assert wm.read_mount_info(root, str(tmp_path / "missing")) is None


def test_removal_code_has_no_shell_or_disk_tools():
    src = (ROOT / "core" / "windows_migration.py").read_text(encoding="utf-8")
    for banned in ("shell=True", "rmtree", "os.system", "sgdisk", "parted", "mkfs", "wipefs", "bcdedit", "efibootmgr"):
        assert banned not in src, banned


def test_offered_once(monkeypatch):
    monkeypatch.setattr(wm, "os", SimpleNamespace(name="posix", replace=os.replace))
    monkeypatch.setattr(wm.drives, "is_live", lambda: False)
    assert wm.should_offer()
    wm.mark_offered()
    assert not wm.should_offer()


# --------------------------------------------------------------------------- pages
@pytest.fixture
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_live_banner_says_it_and_is_hidden_when_installed(qapp, monkeypatch):
    from ui.components.live_banner import LiveBanner
    banner = LiveBanner()
    assert banner.isHidden()
    status = drives.LiveStatus(True, 25 * 10 ** 9, 50 * 10 ** 9, target.candidates(real_layout()))
    banner.show_status(status)
    assert not banner.isHidden() and "RAM, not your disk" in banner.message.text() and "unallocated" in banner.hint.text()
    assert banner.install_btn.text() == "Install HalOS"
    launched = []
    monkeypatch.setattr(drives, "launch_installer", lambda: launched.append(1) or "")
    banner.install_btn.click()
    assert launched
    banner.show_status(drives.LiveStatus(False))
    assert banner.isHidden()


def test_launch_installer_reports_a_missing_installer(tmp_path):
    assert "isn't on this system" in drives.launch_installer(path=str(tmp_path / "no"))


def test_storage_labels_the_live_row_as_ram(qapp):
    from PySide6.QtWidgets import QLabel
    from ui.pages.storage import StorageCard
    card = StorageCard()
    card._set_drives([{"name": "Live session", "kind": "live", "drive": "/", "label": "in memory", "percent": 50.0,
                       "free": 25 * 10 ** 9, "total": 50 * 10 ** 9}])
    assert any("in RAM, not on disk" in w.text() for w in card.findChildren(QLabel))


def test_drives_panel_rows(qapp, tmp_path):
    from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton
    from ui.components.drives_panel import DrivesPanel
    panel = DrivesPanel()
    vols = [drives.Volume("/dev/a", label="Data", fstype="ntfs", size=10 ** 12),
            drives.Volume("/dev/b", label="Old", fstype="ntfs", mountpoint=str(tmp_path), is_windows=True, read_only=True),
            drives.Volume("/dev/c", fstype="BitLocker"), drives.Volume("/dev/d", fstype="vfat", is_esp=True)]
    panel.show_volumes(vols)
    buttons = {b.text() for b in panel.findChildren(QPushButton)}
    assert {"Mount", "Open in Dolphin", "Unmount", "Unlock…"} <= buttons
    assert [c.isChecked() for c in panel.findChildren(QCheckBox)] == [False]    # read-only by default
    assert any("Left alone" in w.text() for w in panel.findChildren(QLabel))


def test_os_switch_card_confirms_first(qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox, QPushButton
    from ui.components import drives_panel as dp
    card = dp.OsSwitchCard()
    card.show_entries([recovery.BootEntry("0000", "Windows Boot Manager", True)])
    calls = []
    monkeypatch.setattr(dp.os_switch, "restart_into", lambda n: calls.append(n) or {"message": "x"})
    monkeypatch.setattr(dp, "run_async", lambda fn, ok=None, err=None: ok(fn()))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    button = card.findChildren(QPushButton)[0]
    assert button.text() == "Restart into Windows Boot Manager"
    button.click()
    assert not calls
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    button.click()
    assert calls == ["0000"]


def test_settings_pages_are_discovered_and_build(qapp, monkeypatch):
    from ui import settings_pages
    from ui.settings_pages import migrate_windows
    titles = [m.TITLE for m in settings_pages.discover()]
    assert "Drives & OS" in titles and "Migrate from Windows" in titles
    assert migrate_windows.build() is not None


def test_wizard_end_to_end_on_a_fake_install(qapp, old_and_main, monkeypatch):
    from ui.settings_pages import migrate_windows as mw
    old, main = old_and_main
    main.last_used, old.last_used = 9000, 1000
    page = mw.MigratePage()
    monkeypatch.setattr(mw, "run_async", lambda fn, ok=None, err=None: ok(fn()))
    page.go(1)
    assert page.stack.currentIndex() == 0                  # no source yet: can't move on
    page.show_installs([old, main])
    assert page.main is main and page.source() is main and page.user_box.currentText() == "seb"
    page.go(1)
    assert [c.name for c in page.choices] == ["Documents"]
    page.go(4)
    assert page.old_box.count() == 1 and page.old_box.currentData() is old and not page.users_box.isEnabled()
    assert not page.remove_btn.isEnabled()
    monkeypatch.setattr(wm, "read_mount_info", rw_mount(old.root, old.device))
    plan = wm.build_removal(old, main, mount_info=rw_mount(old.root, old.device), running=set())
    page.show_plan(plan)
    assert "Type Windows" in page.remove_info.text() and not page.remove_btn.isEnabled()
    page.confirm_edit.setText("Windows")
    assert page.remove_btn.isEnabled() and page.dry_btn.isEnabled()
    page.confirm_edit.setText("windows")
    assert not page.remove_btn.isEnabled()
    refused = wm.build_removal(main, main, mount_info=rw_mount(main.root, main.device), running=set())
    page.show_plan(refused)
    page.confirm_edit.setText(refused.token)
    assert not page.remove_btn.isEnabled() and "can't go ahead" in page.remove_info.text()
    assert not page.boot_box.isChecked() and page.boot_box.isHidden()   # the boot entry option is off and hidden


def test_app_checklist_ticks_linux_versions_only(qapp):
    from PySide6.QtCore import Qt
    from core.store import Result
    from ui.settings_pages import migrate_windows as mw
    page = mw.MigratePage()
    page.show_matches([wm.AppMatch("VS Code", Result("featured", "vscode", "VS Code"), "native"),
                       wm.AppMatch("Notepad++", Result("windows", "n", "Notepad++"), "wine"), wm.AppMatch("Obscure")])
    states = [page.app_list.item(i).checkState() for i in range(3)]
    assert states[:2] == [Qt.Checked, Qt.Unchecked] and "no Linux or Wine" in page.app_list.item(2).text()
    assert page.install_btn.isEnabled()


def test_welcome_offers_migration_once(qapp, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QPushButton
    from ui import saintos_center as sc
    monkeypatch.setattr(wm, "should_offer", lambda: True)
    marked = []
    monkeypatch.setattr(wm, "mark_offered", lambda: marked.append(1))
    win = sc.build_window("Welcome")
    button = [b for b in win.findChildren(QPushButton) if "from Windows" in b.text()]
    assert len(button) == 1 and marked == [1]
    button[0].click()
    assert win._stack.currentWidget().__class__.__name__ == "MigratePage"
