"""
core/drives.py

Every drive on the PC, for people: what it is, how full, whether it's mounted, and what's special about it
(a Windows system volume, Fast Startup, BitLocker). Mounting goes through udisksctl, so no root.

    volumes()                         every partition (lsblk)
    mount(vol, write=...)             NTFS is first mounted read-only to look inside: a Windows system volume
                                      stays read-only unless asked otherwise; a data volume comes back writable
    unmount(vol)  unlock(vol, key)    the key goes to udisksctl over stdin and is never kept or logged
    live_status()                     the live session's numbers: RAM, not disk, and the free space to install to
"""

import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from core import install_target as target

log = logging.getLogger("saint.drives")

ARCHISO = Path("/run/archiso")
INSTALLER = "/usr/lib/halo/install-halo"
NTFS = {"ntfs", "ntfs3", "ntfs-3g", "fuseblk"}
FAST_STARTUP = ("Windows didn't fully shut down (Fast Startup or hibernate), so this drive can only be read safely. "
                "Turn off Fast Startup in Windows to write here: Control Panel > Power Options > Choose what the "
                "power buttons do > untick \"Turn on fast startup\", then shut Windows down.")
BITLOCKER = ("This drive is locked with BitLocker. Unlock it with your recovery key (48 digits, at "
             "account.microsoft.com/devices/recoverykey). You type it each time: HalOS never stores it.")
SYSTEM_READ_ONLY = ("This is a Windows system drive, so it's mounted read-only to keep Windows safe. "
                    "Turn on writing only if you mean to change files there.")
_MOUNTED_AT = re.compile(r"Mounted \S+ at (.+)")
_UNLOCKED_AS = re.compile(r"Unlocked \S+ as (\S+?)\.?\s*$", re.M)
_DIRTY = re.compile(r"dirty|unclean|hibernat|metadata kept in windows|wrong fs type|force", re.I)

_windows_seen: Dict[str, bool] = {}          # uuid -> holds \Windows, learned the first time it's mounted


@dataclass
class Volume:
    device: str
    disk: str = ""
    model: str = ""
    label: str = ""
    fstype: str = ""
    size: int = 0
    used: int = 0
    free: int = 0
    mountpoint: str = ""
    uuid: str = ""
    partuuid: str = ""
    parttype: str = ""
    removable: bool = False
    is_esp: bool = False
    is_recovery: bool = False
    is_live_medium: bool = False
    is_windows: Optional[bool] = None        # None: not known until it has been mounted once
    read_only: bool = False

    @property
    def locked(self) -> bool:
        return self.fstype.lower() == "bitlocker"

    @property
    def is_ntfs(self) -> bool:
        return self.fstype.lower() in NTFS

    @property
    def protected(self) -> bool:
        """EFI, Recovery and the live medium: listed, never mounted from a button."""
        return self.is_esp or self.is_recovery or self.is_live_medium

    @property
    def name(self) -> str:
        return self.label or Path(self.device).name

    @property
    def kind(self) -> str:
        if self.is_live_medium:
            return "HalOS live medium"
        if self.is_esp:
            return "EFI system partition"
        if self.is_recovery:
            return "Windows Recovery"
        if self.locked:
            return "BitLocker (locked)"
        if self.is_windows:
            return "Windows system"
        return "External" if self.removable else "Data"


@dataclass
class Result:
    ok: bool
    message: str = ""
    mountpoint: str = ""
    read_only: bool = False
    code: str = ""                 # "fast_startup", "bitlocker", "protected", "busy", "error"


def ci_child(parent, name: str) -> Optional[Path]:
    """``parent``'s child called ``name``, ignoring case (NTFS keeps Windows's case; Linux compares exactly)."""
    parent = Path(parent)
    exact = parent / name
    if os.path.lexists(exact):
        return exact
    try:
        with os.scandir(parent) as it:
            for e in it:
                if e.name.lower() == name.lower():
                    return parent / e.name
    except OSError:
        pass
    return None


def is_link(path) -> bool:
    """A symlink or junction: never walked into. (NTFS junctions show up as symlinks on Linux.)"""
    return os.path.islink(path) or os.path.isjunction(path)


def real_dir(path) -> bool:
    return path is not None and not is_link(path) and os.path.isdir(path)


def is_windows_root(root) -> bool:
    """A real \\Windows\\System32 directly under this volume's root."""
    win = ci_child(root, "Windows")
    if not real_dir(win):
        return False
    return real_dir(ci_child(win, "System32"))


def hibernated(root) -> bool:
    """hiberfil.sys holds a live image (Fast Startup or hibernate) when it starts with "hibr"."""
    f = ci_child(root, "hiberfil.sys")
    if f is None or is_link(f):
        return False
    try:
        with open(f, "rb") as fh:
            return fh.read(4).lower() == b"hibr"
    except OSError:
        return False


def _to_volume(node: Dict, disk: Dict) -> Volume:
    mounts = target.mounts_of(node)
    fsused, fsavail = target._int(node.get("fsused")), target._int(node.get("fsavail"))
    uuid = node.get("uuid") or ""
    parttype = (node.get("parttype") or "").lower()
    v = Volume(device=node.get("path") or f"/dev/{node.get('name')}", disk=disk.get("path") or "",
               model=(disk.get("model") or "").strip(), label=node.get("label") or "",
               fstype=node.get("fstype") or "", size=target._int(node.get("size")), used=fsused, free=fsavail,
               mountpoint=mounts[0] if mounts else "", uuid=uuid, partuuid=node.get("partuuid") or "",
               parttype=parttype, removable=bool(disk.get("rm")), is_esp=parttype == target.ESP_TYPE,
               is_recovery=parttype == target.RECOVERY_TYPE, is_live_medium=target.is_live_medium(node),
               read_only=bool(node.get("ro")) or (bool(mounts) and _mount_read_only(mounts[0])))
    if v.mountpoint and v.is_ntfs:
        v.is_windows = _windows_seen[uuid] = is_windows_root(v.mountpoint)
    elif v.is_ntfs:
        v.is_windows = _windows_seen.get(uuid)
    return v


def volumes(run: Callable = subprocess.run, devices: Optional[List[Dict]] = None) -> List[Volume]:
    """Every partition with something on it, skipping MSR and the like. An unlocked BitLocker volume shows up
    as what's inside it."""
    out = []
    for d in (devices if devices is not None else target.block_devices(run)):
        if not target._is_real_disk(d):
            continue
        for p in target._partitions(d):
            if (p.get("parttype") or "").lower() == target.MSR_TYPE or not p.get("fstype"):
                continue
            inner = [c for c in p.get("children") or [] if c.get("type") == "crypt" and c.get("fstype")]
            out.append(_to_volume(inner[0], d) if inner else _to_volume(p, d))
    return out


def _udisks(args: List[str], run: Callable, stdin: Optional[str] = None) -> subprocess.CompletedProcess:
    return run(["udisksctl", *args], input=stdin, capture_output=True, text=True, timeout=120)


def _do_mount(device: str, options: str, run: Callable) -> tuple:
    try:
        res = _udisks(["mount", "-b", device, *(["-o", options] if options else [])], run)
    except (OSError, subprocess.SubprocessError) as e:
        return "", str(e)
    if res.returncode != 0:
        return "", (res.stderr or res.stdout or "").strip()
    m = _MOUNTED_AT.search(res.stdout or "")
    path = m[1].strip() if m else ""
    # Older udisks ends the sentence with a full stop; a label may too, so ask the filesystem.
    if path.endswith(".") and not os.path.isdir(path):
        path = path[:-1]
    return path, ""


def _do_unmount(device: str, run: Callable) -> str:
    try:
        res = _udisks(["unmount", "-b", device], run)
    except (OSError, subprocess.SubprocessError) as e:
        return str(e)
    return "" if res.returncode == 0 else (res.stderr or res.stdout or "").strip()


def mount(vol: Volume, write: bool = False, run: Callable = subprocess.run) -> Result:
    """Mount a volume. ``write=True`` is the deliberate toggle for a Windows system volume (data volumes are
    writable anyway). A Windows that didn't shut down stays read-only, with the reason."""
    if vol.protected:
        return Result(False, f"{vol.kind}: HalOS leaves this one alone.", code="protected")
    if vol.locked:
        return Result(False, BITLOCKER, code="bitlocker")
    if not vol.is_ntfs:
        if vol.mountpoint:
            return Result(True, "", vol.mountpoint, vol.read_only)
        path, err = _do_mount(vol.device, "", run)
        return Result(bool(path), "" if path else f"Couldn't mount {vol.name}: {err}", path, code="" if path else "error")

    # NTFS: look inside first, read-only, so a Windows volume is never writable by accident.
    path = vol.mountpoint
    if not path:
        path, err = _do_mount(vol.device, "ro", run)
        if not path:
            return Result(False, f"Couldn't mount {vol.name}: {err}", code="error")
    is_win = is_windows_root(path)
    if vol.uuid:
        _windows_seen[vol.uuid] = is_win
    vol.is_windows = is_win
    if is_win and not write:
        ro = not vol.mountpoint or _mount_read_only(path)
        return Result(True, SYSTEM_READ_ONLY if ro else "", path, ro)
    if hibernated(path):
        return Result(True, FAST_STARTUP, path, True, "fast_startup")
    if vol.mountpoint and not vol.read_only and not _mount_read_only(path):
        return Result(True, "", path, False)          # already writable
    err = _do_unmount(vol.device, run)
    if err:
        return Result(True, f"Mounted read-only: {err}", path, True, "busy")
    rw, err = _do_mount(vol.device, "rw", run)
    if rw:
        return Result(True, "", rw, False)
    ro, ro_err = _do_mount(vol.device, "ro", run)
    if _DIRTY.search(err):
        log.info("drives.rw_refused device=%s: %s", vol.device, err)
        return Result(bool(ro), FAST_STARTUP, ro, True, "fast_startup")
    return Result(bool(ro), f"Couldn't mount {vol.name} for writing: {err or ro_err}", ro, True, "error")


def _mount_read_only(path: str) -> bool:
    try:
        return bool(os.statvfs(path).f_flag & os.ST_RDONLY)
    except (OSError, AttributeError):
        return False


def unmount(vol: Volume, run: Callable = subprocess.run) -> Result:
    err = _do_unmount(vol.device, run)
    if not err:
        return Result(True)
    if re.search(r"busy|target is busy", err, re.I):
        return Result(False, f"{vol.name} is in use. Close the windows and apps using it, then try again.", code="busy")
    return Result(False, f"Couldn't unmount {vol.name}: {err}", code="error")


def unlock(vol: Volume, key: str, run: Callable = subprocess.run) -> Result:
    """Unlock BitLocker with what the user just typed. The key goes over stdin, never on a command line, into a
    log or to disk."""
    if not vol.locked:
        return Result(False, f"{vol.name} isn't locked.", code="error")
    key = (key or "").strip()
    if not key:
        return Result(False, "Type the recovery key first.", code="bitlocker")
    try:
        res = _udisks(["unlock", "-b", vol.device, "--key-file", "/dev/stdin"], run, stdin=key)
    except (OSError, subprocess.SubprocessError):
        return Result(False, "udisks couldn't be reached to unlock the drive.", code="error")
    finally:
        del key
    if res.returncode != 0:
        log.info("drives.unlock_failed device=%s", vol.device)     # never the key, nor udisks's echo of the attempt
        return Result(False, "That key didn't unlock the drive. Check it and try again.", code="bitlocker")
    m = _UNLOCKED_AS.search(res.stdout or "")
    return Result(True, "Unlocked.", m[1] if m else "")


def open_in_files(path: str, popen: Callable = subprocess.Popen) -> Result:
    if not path or not os.path.isdir(path):
        return Result(False, "Mount it first.", code="error")
    argv = ["dolphin", path] if shutil.which("dolphin") else ["xdg-open", path]
    try:
        popen(argv, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        return Result(False, f"Couldn't open the file manager: {e}", code="error")
    return Result(True)


# ---------------------------------------------------------------------- live session
def is_live(archiso: Path = ARCHISO) -> bool:
    return Path(archiso).is_dir()


@dataclass
class LiveStatus:
    live: bool
    ram_free: int = 0
    ram_total: int = 0
    free_space: List[target.Candidate] = field(default_factory=list)

    @property
    def message(self) -> str:
        return (f"Running live from memory: nothing here is kept after a restart. "
                f"{self.ram_free / 1e9:.1f} GB free is RAM, not your disk.")

    @property
    def install_hint(self) -> str:
        if not self.free_space:
            return "HalOS isn't installed yet. No free space of 30 GB or more was found on an internal disk."
        c = self.free_space[0]
        return (f"HalOS isn't installed yet. Detected {c.size / 1e9:.0f} GB of unallocated space on {c.disk}"
                f"{' (' + c.model + ')' if c.model else ''}, ready for it.")


def live_status(archiso: Path = ARCHISO, usage: Callable = shutil.disk_usage,
                run: Callable = subprocess.run) -> LiveStatus:
    if not is_live(archiso):
        return LiveStatus(False)
    try:
        u = usage("/")
        total, free = u.total, u.free
    except OSError:
        total = free = 0
    return LiveStatus(True, free, total, [c for c in target.candidates(run=run) if not c.reuse])


def launch_installer(popen: Callable = subprocess.Popen, path: str = INSTALLER) -> str:
    """Opens the installer. Returns why it couldn't, or ""."""
    if not os.path.exists(path):
        return "The installer isn't on this system."
    try:
        popen([path], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        return f"The installer didn't start: {e}"
    return ""
