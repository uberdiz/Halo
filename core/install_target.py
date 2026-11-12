"""
core/install_target.py

"Install HalOS to free space": the one install path that can't touch what's already on the disks.

Why not Calamares's own partition page (checked against Calamares 3.3's source):
    * partition.conf can only pre-select a mode (initialPartitioningChoice), never a target, and has no
      "free space" mode. "Replace" can take a free-space region, but it reuses an existing EFI partition.
    * Its EFI list holds every ESP-typed partition, including HALOLIVE (6 GB, full of live files, and mounted
      as the running medium) and the 100 MB one that probably boots Windows.

So the steps are:
    1. ui/install_chooser.py lists the free regions and the user confirms one (nothing is written).
    2. ``start`` (root) re-checks it, saves it to /run/halo, selects settings-freespace.conf, opens Calamares.
    3. Calamares's own "Install now" confirmation comes next, then the "halotarget" job calls ``apply``:
       a NEW 512 MiB ESP and a NEW Btrfs root inside the free region, filesystems on those two only, and the
       partition list every later Calamares module reads (mount, fstab, grubcfg, bootloader).

A dedicated ESP means removing HALOLIVE later, or Windows rewriting its own ESP, can't break HalOS, and no
ESP that already exists is ever mounted, changed or formatted.

Standard library only: Calamares's Python job loads this file by path and runs it outside SAINT's venv.
Every command is an argument list.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

MIB = 1024 ** 2
GIB = 1024 ** 3
MIN_REGION = 30 * GIB
ESP_SIZE = 512 * MIB
ESP_LABEL, ROOT_LABEL = "HalOS-EFI", "HalOS-root"
ESP_FS_LABEL, ROOT_FS_LABEL = "HALOS_EFI", "HalOS"
ESP_TYPE = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"
MSR_TYPE = "e3c9e316-0b5c-4db8-817d-f92df00215ae"
RECOVERY_TYPE = "de94bba4-06d1-4d40-a16a-bfd50179d6ac"
LIVE_MOUNT = "/run/archiso/bootmnt"
LIVE_LABEL = "HALOLIVE"
PLAN_FILE = Path("/run/halo/install-target.json")
CALAMARES_DIR = Path("/etc/calamares")
LSBLK = ["lsblk", "-J", "-b", "-o", "NAME,PATH,TYPE,SIZE,START,LOG-SEC,PTTYPE,FSTYPE,LABEL,UUID,PARTUUID,PARTTYPE,"
                                    "PARTLABEL,MODEL,RM,RO,TRAN,MOUNTPOINTS,FSUSED,FSAVAIL"]
_DISK = re.compile(r"^/dev/(?:sd[a-z]+|vd[a-z]+|nvme\d+n\d+|mmcblk\d+)$")
_SGDISK_ROW = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+[\d.]+\s+\S+\s+([0-9A-Fa-f]{4})\s*(.*)$")


class TargetError(Exception):
    """Why the install target can't be used, in words for the user."""


def block_devices(run: Callable = subprocess.run) -> List[Dict]:
    """lsblk's tree of disks and partitions; [] when lsblk isn't there or fails."""
    try:
        out = run(LSBLK, capture_output=True, text=True, timeout=15).stdout
        return json.loads(out or "{}").get("blockdevices", [])
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


def _int(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def mounts_of(node: Dict) -> List[str]:
    return [m for m in node.get("mountpoints") or [node.get("mountpoint")] if m]


def is_live_medium(part: Dict) -> bool:
    return LIVE_MOUNT in mounts_of(part) or (part.get("label") or "").upper() == LIVE_LABEL


def _is_real_disk(d: Dict) -> bool:
    return d.get("type") == "disk" and not str(d.get("name", "")).startswith(("loop", "zram", "sr", "ram"))


def _partitions(disk: Dict) -> List[Dict]:
    return [c for c in disk.get("children") or [] if c.get("type") == "part"]


def free_regions(disk: Dict) -> List[Dict]:
    """Gaps between partitions as {start, end} in bytes (end exclusive), aligned to 1 MiB, keeping 1 MiB clear
    at each end of the disk for the GPT. lsblk's START is always in 512-byte units."""
    size = _int(disk.get("size"))
    used = sorted((_int(p.get("start")) * 512, _int(p.get("start")) * 512 + _int(p.get("size")))
                  for p in _partitions(disk))
    regions, pos = [], MIB
    for start, end in used + [(size - MIB, size - MIB)]:
        a = (pos + MIB - 1) // MIB * MIB
        b = start // MIB * MIB
        if b > a:
            regions.append({"start": a, "end": b})
        pos = max(pos, end)
    return regions


@dataclass
class Candidate:
    disk: str
    model: str
    start: int                     # bytes
    end: int                       # bytes, exclusive
    sector: int = 512
    reuse: bool = False            # an earlier unfinished attempt's two HalOS partitions, to be formatted again
    esp_device: str = ""
    root_device: str = ""
    existing: List[str] = field(default_factory=list)      # what's already on that disk, for the confirmation

    @property
    def size(self) -> int:
        return self.end - self.start


def _describe(part: Dict) -> str:
    return " ".join(str(x) for x in (part.get("path"), part.get("label") or "", part.get("fstype") or "",
                                     f"{_int(part.get('size')) / GIB:.1f} GiB") if x)


def candidates(devices: Optional[List[Dict]] = None, min_size: int = MIN_REGION,
               run: Callable = subprocess.run) -> List[Candidate]:
    """Where HalOS can go without touching anything: internal GPT disks' free regions, largest first."""
    out = []
    for d in (devices if devices is not None else block_devices(run)):
        if not _is_real_disk(d) or d.get("rm") or d.get("ro") or (d.get("pttype") or "") != "gpt":
            continue
        parts = _partitions(d)
        existing = [_describe(p) for p in parts]
        common = dict(disk=d.get("path") or f"/dev/{d.get('name')}", model=(d.get("model") or "").strip(),
                      sector=_int(d.get("log-sec")) or 512, existing=existing)
        for r in free_regions(d):
            if r["end"] - r["start"] >= min_size:
                out.append(Candidate(start=r["start"], end=r["end"], **common))
        esp = [p for p in parts if p.get("partlabel") == ESP_LABEL]
        root = [p for p in parts if p.get("partlabel") == ROOT_LABEL]
        if len(esp) == 1 and len(root) == 1 and not mounts_of(esp[0]) and not mounts_of(root[0]):
            start = _int(esp[0].get("start")) * 512
            out.append(Candidate(start=start, end=_int(root[0].get("start")) * 512 + _int(root[0].get("size")),
                                 reuse=True, esp_device=esp[0]["path"], root_device=root[0]["path"], **common))
    return sorted(out, key=lambda c: (c.reuse, -c.size))


def validate(plan: Candidate, devices: List[Dict]) -> None:
    """Raises TargetError unless ``plan`` is still only free space on an internal GPT disk (or, for a retry,
    still exactly the two earlier HalOS partitions, unmounted)."""
    if not _DISK.match(plan.disk or ""):
        raise TargetError(f"{plan.disk!r} isn't a disk HalOS can install to.")
    disk = next((d for d in devices if d.get("path") == plan.disk), None)
    if disk is None or not _is_real_disk(disk):
        raise TargetError(f"{plan.disk} isn't there any more.")
    if disk.get("rm") or disk.get("ro"):
        raise TargetError(f"{plan.disk} is removable or read-only.")
    if (disk.get("pttype") or "") != "gpt":
        raise TargetError(f"{plan.disk} doesn't use a GPT partition table.")
    parts = _partitions(disk)
    if plan.reuse:
        found = {p.get("path"): p for p in parts}
        for dev, label in ((plan.esp_device, ESP_LABEL), (plan.root_device, ROOT_LABEL)):
            p = found.get(dev)
            if not p or p.get("partlabel") != label:
                raise TargetError(f"{dev} isn't HalOS's earlier partition ({label}).")
            if mounts_of(p) or is_live_medium(p):
                raise TargetError(f"{dev} is in use.")
        return
    if plan.size < MIN_REGION or plan.start % MIB or plan.end % MIB:
        raise TargetError("That free space is too small or not aligned.")
    if not any(r["start"] <= plan.start and plan.end <= r["end"] for r in free_regions(disk)):
        raise TargetError(f"The free space on {plan.disk} has changed. Nothing was written.")


def part_device(disk: str, number: int) -> str:
    return f"{disk}p{number}" if disk[-1].isdigit() else f"{disk}{number}"


def sgdisk_table(disk: str, run: Callable = subprocess.run) -> Dict[int, tuple]:
    """number -> (first sector, last sector, type code, name), straight from the GPT on disk."""
    res = run(["sgdisk", "--print", disk], capture_output=True, text=True, timeout=30)
    if res.returncode != 0:
        raise TargetError(f"Couldn't read the partition table of {disk}: {(res.stderr or res.stdout).strip()}")
    table, in_rows = {}, False
    for line in res.stdout.splitlines():
        if line.strip().startswith("Number"):
            in_rows = True
        elif in_rows:
            m = _SGDISK_ROW.match(line)
            if m:
                table[int(m[1])] = (int(m[2]), int(m[3]), m[4].upper(), m[5].strip())
    return table


def create_args(plan: Candidate, table: Dict[int, tuple]) -> tuple:
    """The sgdisk arguments that add the two new partitions, on the first two unused numbers."""
    free = [n for n in range(1, 129) if n not in table]
    if len(free) < 2:
        raise TargetError(f"{plan.disk}'s partition table is full.")
    n1, n2 = free[:2]
    s = plan.sector
    esp_end = plan.start + ESP_SIZE
    args = [f"--new={n1}:{plan.start // s}:{esp_end // s - 1}", f"--typecode={n1}:ef00", f"--change-name={n1}:{ESP_LABEL}",
            f"--new={n2}:{esp_end // s}:{plan.end // s - 1}", f"--typecode={n2}:8300", f"--change-name={n2}:{ROOT_LABEL}"]
    return n1, n2, args


def _check(run: Callable, argv: List[str], what: str, timeout: int = 120) -> None:
    res = run(argv, capture_output=True, text=True, timeout=timeout)
    if res.returncode != 0:
        raise TargetError(f"{what} failed: {(res.stderr or res.stdout or '').strip()[:400]}")


def create_partitions(plan: Candidate, run: Callable = subprocess.run, backup_dir: Path = PLAN_FILE.parent) -> tuple:
    """Adds the two partitions. Everything already in the GPT must read back identical, or the backup taken
    seconds earlier goes back and the install stops."""
    before = sgdisk_table(plan.disk, run)
    n1, n2, args = create_args(plan, before)
    backup = str(Path(backup_dir) / f"gpt-backup-{Path(plan.disk).name}.bin")
    _check(run, ["sgdisk", f"--backup={backup}", plan.disk], "Backing up the partition table")
    _check(run, ["sgdisk", "--pretend", *args, plan.disk], "Checking the new partitions")
    _check(run, ["sgdisk", *args, plan.disk], "Creating the partitions")
    after = sgdisk_table(plan.disk, run)
    changed = {n: row for n, row in before.items() if after.get(n) != row}
    if changed or set(after) - set(before) != {n1, n2}:
        _check(run, ["sgdisk", f"--load-backup={backup}", plan.disk], "Restoring the partition table")
        raise TargetError(f"The partition table of {plan.disk} didn't read back as expected; it was restored and "
                          "nothing else was changed.")
    # A disk with a mounted partition (HALOLIVE) can't re-read its table as a whole; partx adds just these two.
    for n in (n1, n2):
        res = run(["partx", "--add", "--nr", f"{n}:{n}", plan.disk], capture_output=True, text=True, timeout=30)
        if res.returncode != 0:
            run(["partprobe", plan.disk], capture_output=True, text=True, timeout=30)
    run(["udevadm", "settle", "--timeout=15"], capture_output=True, text=True, timeout=30)
    return part_device(plan.disk, n1), part_device(plan.disk, n2)


def _wait_for(devices: List[str], exists: Callable = os.path.exists, sleep: Callable = time.sleep) -> None:
    for _ in range(20):
        if all(exists(d) for d in devices):
            return
        sleep(0.5)
    raise TargetError(f"The new partitions ({', '.join(devices)}) didn't appear. Restart and try again: the free "
                      "space is safe, and the installer will offer those partitions.")


def _describe_node(device: str, run: Callable) -> Dict:
    res = run(["lsblk", "-J", "-b", "-n", "-o", "PATH,UUID,PARTUUID,PARTTYPE,PARTLABEL,FSTYPE", device],
              capture_output=True, text=True, timeout=15)
    try:
        return json.loads(res.stdout or "{}").get("blockdevices", [{}])[0]
    except (ValueError, IndexError):
        return {}


def partition_entry(device: str, mount_point: str, fs: str, node: Dict) -> Dict:
    """One item of Calamares's "partitions" global (the keys its partition module's FillGlobalStorageJob writes)."""
    return {"device": device, "mountPoint": mount_point, "fs": fs, "fsName": fs, "uuid": node.get("uuid") or "",
            "partuuid": node.get("partuuid") or "", "partlabel": node.get("partlabel") or "",
            "parttype": node.get("parttype") or "", "partattrs": 0, "features": {}, "claimed": True}


def apply(plan: Candidate, efi_mount: str = "/boot/efi", run: Callable = subprocess.run,
          exists: Callable = os.path.exists, sleep: Callable = time.sleep,
          backup_dir: Path = PLAN_FILE.parent) -> Dict:
    """Runs at install time, as root: partitions, filesystems, and the globals Calamares's later jobs read."""
    validate(plan, block_devices(run))
    if plan.reuse:
        esp, root = plan.esp_device, plan.root_device
    else:
        esp, root = create_partitions(plan, run, backup_dir)
    _wait_for([esp, root], exists, sleep)
    # The only two mkfs calls in HalOS's installer path, both on partitions identified by the name given above.
    for dev, label in ((esp, ESP_LABEL), (root, ROOT_LABEL)):
        for _ in range(10):                # udev may still be reading the new partition
            if _describe_node(dev, run).get("partlabel") == label:
                break
            sleep(0.5)
        else:
            raise TargetError(f"{dev} isn't the partition HalOS just created ({label}); nothing was formatted.")
    _check(run, ["mkfs.fat", "-F", "32", "-n", ESP_FS_LABEL, esp], "Formatting HalOS's EFI partition")
    _check(run, ["mkfs.btrfs", "-f", "-L", ROOT_FS_LABEL, root], "Formatting HalOS's partition", timeout=300)
    run(["udevadm", "settle", "--timeout=15"], capture_output=True, text=True, timeout=30)
    return {"partitions": [partition_entry(root, "/", "btrfs", _describe_node(root, run)),
                           partition_entry(esp, efi_mount, "fat32", _describe_node(esp, run))],
            "firmwareType": "efi", "efiSystemPartition": efi_mount, "bootLoader": {"installPath": plan.disk},
            "filesystem_use": {}, "partitionChoices": {"swap": "none"}}


def save_plan(plan: Candidate, path: Path = PLAN_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(plan)), encoding="utf-8")


def load_plan(path: Path = PLAN_FILE) -> Candidate:
    try:
        return Candidate(**json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError) as e:
        raise TargetError(f"The chosen install location couldn't be read ({e}). Close the installer and start again.")


def select_settings(free_space: bool, conf_dir: Path = CALAMARES_DIR) -> None:
    """Calamares reads /etc/calamares/settings.conf; in the live session that's in the RAM overlay, so swapping
    it changes nothing on disk."""
    current, standard = conf_dir / "settings.conf", conf_dir / "settings-standard.conf"
    if not standard.exists():
        shutil.copyfile(current, standard)
    shutil.copyfile(conf_dir / "settings-freespace.conf" if free_space else standard, current)


def find_candidate(disk: str, start: int, end: int, devices: List[Dict]) -> Candidate:
    """The user's choice must still be one the live layout offers; nothing from the command line is trusted."""
    for c in candidates(devices):
        if (c.disk, c.start, c.end) == (disk, start, end):
            validate(c, devices)
            return c
    raise TargetError(f"That location on {disk} isn't free any more. Nothing was written.")


def main(argv: List[str]) -> int:
    """install_target.py list | start <disk> <start> <end> | standard   (start and standard run as root)."""
    if argv[:1] == ["list"]:
        print(json.dumps([asdict(c) for c in candidates()]))
        return 0
    try:
        if argv[:1] == ["standard"]:
            select_settings(False)
        elif argv[:1] == ["start"] and len(argv) == 4:
            plan = find_candidate(argv[1], int(argv[2]), int(argv[3]), block_devices())
            save_plan(plan)
            select_settings(True)
        else:
            print(main.__doc__, file=sys.stderr)
            return 64
    except (TargetError, OSError, ValueError) as e:
        print(f"halos-install: {e}", file=sys.stderr)
        return 1
    return run_installer()


# --------------------------------------------------------------------------- #
# Running Calamares, and saying why when it fails
# --------------------------------------------------------------------------- #
INSTALL_LOG = PLAN_FILE.parent / "install.log"          # what "Copy log" copies; readable by the live user
# Calamares's log text -> a plain reason. First match wins; searched in the failure's own message and details
# first, so a harmless warning earlier in the log can't be blamed.
_FAILURES = [
    (r"no space left on device", "The place HalOS was being installed to filled up. Choose a larger free space "
                                 "(30 GB or more) and try again."),
    (r"input/output error|i/o error|medium error", "The disk reported a read or write error. Check the drive's "
                                                   "health before trying again; the live system itself may also be a bad copy."),
    (r"unsquashfs|failed to unpack|unpackfs|rsync", "HalOS's files couldn't be copied from the live system. The "
                                                     "download or the HALOLIVE copy is probably damaged: get the ISO again and check it."),
    (r"device or resource busy|is mounted|target is busy", "A partition the installer needed was in use. Close file "
                                                           "managers and other windows using that disk, then try again."),
    (r"mkfs|formatting halos", "A new HalOS partition couldn't be formatted. Restart the live system and try again; "
                               "the free space is still there."),
    (r"efibootmgr|could not prepare boot variable|efi variables", "The PC's firmware refused the new start-up entry. "
                                                                   "HalOS's files are installed: restart, open the boot menu (F12 on most PCs) "
                                                                   "and pick the HalOS disk, or try the install again."),
    (r"grub-install|grub-mkconfig|bootloader", "The boot loader couldn't be set up, so HalOS wouldn't start from "
                                               "this install. Windows and your files weren't changed by this step. Try again."),
    (r"mkinitcpio|initcpio", "HalOS's start-up files couldn't be built. Try the install again."),
    (r"sgdisk|partition table|partx", "The disk's partition table couldn't be changed. Nothing else was written."),
    (r"could not mount|failed to mount|mount:", "A HalOS partition couldn't be opened after it was created. "
                                                "Restart the live system and try again."),
    (r"users?:|useradd|passwd|chpasswd", "Your account couldn't be created. Use a simple user name (lowercase "
                                         "letters and digits) and try again."),
]


def calamares_logs(home: Optional[str] = None) -> List[Path]:
    """Where Calamares writes its session log: the invoking user's cache (sudo -E keeps HOME) or root's."""
    homes = [home or os.environ.get("HOME") or "", "/root"]
    return [Path(h) / ".cache/calamares/session.log" for h in dict.fromkeys(homes) if h]


def calamares_failure(log: str) -> Optional[Dict[str, str]]:
    """The failed job's message and details from Calamares's log, with a plain reason; None when it didn't fail."""
    m = re.search(r"Installation failed:?\s*(.*)", log)
    if not m:
        return None
    tail = log[m.start():]
    msg = re.search(r"- message:\s*(.*)", tail)
    det = re.search(r"- details:\s*(.*?)(?=^\d{4}-\d\d-\d\d - |\Z)", tail, re.S | re.M)
    message = (msg[1] if msg else m[1]).strip().strip('"')
    details = (det[1] if det else "").strip().strip('"')
    return {"message": message, "details": details, "reason": explain_failure(message, details)}


def explain_failure(message: str, details: str = "") -> str:
    if "free space" in message:                 # halotarget's errors (TargetError) are already written for people
        return f"{message}: {details}".rstrip(": ")
    low = f"{message}\n{details}".lower()
    for pattern, reason in _FAILURES:
        if re.search(pattern, low):
            return reason
    step = message or "an installer step"
    return f"The install stopped at: {step}. Try again; if it stops at the same place, copy the log and report it."


def run_installer(run: Callable = subprocess.run, logs: Optional[List[Path]] = None,
                  out: Path = INSTALL_LOG) -> int:
    """Start Calamares and wait. A failed or crashed install ends with ``halos-install: <plain reason>`` on
    stderr (ui/install_chooser.py shows it with Retry and Copy log) and the full log in /run/halo/install.log."""
    logs = calamares_logs() if logs is None else logs
    before = {p: p.stat().st_mtime_ns for p in logs if p.exists()}
    try:
        rc = run(["/usr/bin/calamares"]).returncode
    except OSError as e:
        print(f"halos-install: The installer couldn't start ({e}). Restart the live system and try again.",
              file=sys.stderr)
        return 1
    text = ""
    for p in logs:                              # only a log this run wrote
        try:
            if p.stat().st_mtime_ns != before.get(p):
                text = p.read_text(encoding="utf-8", errors="replace")
                break
        except OSError:
            continue
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text or f"Calamares left no log (exit code {rc}).\n", encoding="utf-8")
        out.chmod(0o644)
    except OSError:
        pass
    failure = calamares_failure(text)
    if failure:
        print(f"halos-install: {failure['reason']}", file=sys.stderr)
        return 1
    if rc != 0:
        print(f"halos-install: The installer closed unexpectedly (code {rc}) before it finished. Nothing more was "
              "written after that. Try again.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
