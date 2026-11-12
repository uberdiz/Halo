"""
core/recovery.py

Halo's Recovery page (deterministic; every command is a fixed argument list):

    firmware_setup_supported()        can this PC restart straight into its UEFI settings?
    REBOOT_TO_FIRMWARE                systemctl reboot --firmware-setup
    boot_entries()                    the PC's UEFI boot entries (efibootmgr): Windows Boot Manager, Halo, ...
    boot_once(entry)                  next restart only: start that entry (pkexec efibootmgr --bootnext), then
                                      the PC goes back to its normal order (dual boot: "Restart into Windows")
    snapshots() / snapshot_now()      Btrfs snapshots of the system (snapper; one is taken around every
                                      package install by snap-pac); booting an older one is in the GRUB menu
                                      ("Halo snapshots", grub-btrfs)
    restart(entry=None)               restart now (optionally into ``entry`` once) with what the image already
                                      has; returns ok / reason / log, for a plain reason with Retry and Copy log
    explain(detail)                   a tool's error text -> a plain-language reason

Nothing here needs a network or installs anything. Boot entries are read with efibootmgr, or straight from the
firmware's variables when it is missing; restarting falls back from HalOS's helper to systemctl to logind's D-Bus call.
"""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

EFIVARS = Path("/sys/firmware/efi/efivars")
OS_INDICATIONS_SUPPORTED = "OsIndicationsSupported-8be4df61-93ca-11d2-aa0d-00e098032b8c"
REBOOT_TO_FIRMWARE = ["systemctl", "reboot", "--firmware-setup"]
REBOOT = ["systemctl", "reboot"]
EFIBOOT_HELPER = "/usr/lib/halo/halo-efiboot"
# halo-system's restart helper: restarts even while a background setup (first-boot downloads) asks to wait.
RESTART_HELPER = "/usr/lib/halo/halo-restart"
EFI_GLOBAL = "8be4df61-93ca-11d2-aa0d-00e098032b8c"
LOGIND_REBOOT = ["busctl", "call", "org.freedesktop.login1", "/org/freedesktop/login1",
                 "org.freedesktop.login1.Manager", "Reboot", "b", "false"]
# Tool output -> what to tell the person. First match wins; deterministic, no model involved.
_REASONS = [
    (r"inhibit", "Something is still being set up in the background (a download or an update). Wait for it to "
                 "finish, or press Retry to restart anyway."),
    (r"not authorized|authentication (is )?required|access denied|interactive authentication|dismissed"
     r"|error executing command as another user",
     "The password prompt was closed or refused, so nothing was changed."),
    (r"no boot entry|invalid boot|could not prepare boot variable",
     "That start-up entry isn't in this PC's firmware any more. Reopen this page to refresh the list."),
    (r"efi variables are not supported|not uefi",
     "This PC started in legacy BIOS mode, so it has no start-up entries to choose from. Restart and pick the "
     "system in the boot menu."),
    (r"no space left", "The PC's firmware has no room left for start-up settings. Restart and pick the system in "
                       "the boot menu (F12 on most PCs)."),
    (r"read-only file system", "This is a read-only snapshot, so that setting can't be saved. Restart still works."),
    (r"command not found|no such file|errno 2|filenotfounderror",
     "A system tool that HalOS comes with is missing. Restart still works; use the PC's boot menu (F12 on most "
     "PCs) to pick another system."),
    (r"timed out|timeout", "The PC didn't answer in time. Try again."),
]
_ENTRY = re.compile(r"^Boot([0-9A-Fa-f]{4})(\*?)\s+(.+?)(?:\t|\s{2,}|$)")


def is_uefi(efivars: Path = EFIVARS) -> bool:
    return efivars.is_dir()


def firmware_setup_supported(efivars: Path = EFIVARS) -> bool:
    """UEFI firmware that accepts "boot to setup next time" (bit 0 of OsIndicationsSupported)."""
    try:
        data = (efivars / OS_INDICATIONS_SUPPORTED).read_bytes()
    except OSError:
        return False
    return len(data) >= 5 and bool(data[4] & 1)        # 4 bytes of attributes, then the 64-bit value


@dataclass
class BootEntry:
    num: str
    label: str
    active: bool
    current: bool = False

    @property
    def is_windows(self) -> bool:
        return "windows" in self.label.lower()


def efivar_boot_entries(efivars: Path = EFIVARS) -> List[BootEntry]:
    """The same list without efibootmgr. A Boot#### file is 4 bytes of efivarfs attributes, then a 32-bit
    attribute word (bit 0: active), a 16-bit device-path length and the label in UTF-16."""
    def value(name: str) -> bytes:
        try:
            return (efivars / f"{name}-{EFI_GLOBAL}").read_bytes()[4:]
        except OSError:
            return b""
    try:
        names = sorted(f.name for f in efivars.iterdir())
    except OSError:
        return []
    cur = value("BootCurrent")
    current = f"{int.from_bytes(cur[:2], 'little'):04X}" if len(cur) >= 2 else ""
    entries = []
    for name in names:
        m = re.fullmatch(rf"Boot([0-9A-Fa-f]{{4}})-{EFI_GLOBAL}", name)
        data = value(f"Boot{m[1]}") if m else b""
        if len(data) < 8:
            continue
        label = data[6:].decode("utf-16-le", "ignore").split("\x00", 1)[0].strip()
        if label:
            entries.append(BootEntry(m[1].upper(), label, bool(data[0] & 1), m[1].upper() == current))
    return entries


def boot_entries(run: Callable = subprocess.run, efivars: Path = EFIVARS) -> List[BootEntry]:
    try:
        out = run(["efibootmgr"], capture_output=True, text=True, timeout=10).stdout or ""
    except (OSError, subprocess.TimeoutExpired):
        out = ""
    if not re.search(r"^Boot[0-9A-Fa-f]{4}", out, re.M):
        return efivar_boot_entries(efivars)             # efibootmgr missing or failing: read the firmware directly
    current = re.search(r"^BootCurrent:\s*([0-9A-Fa-f]{4})", out, re.M)
    entries = []
    for line in out.splitlines():
        m = _ENTRY.match(line)
        if m:
            entries.append(BootEntry(m[1].upper(), m[3].strip(), m[2] == "*",
                                     bool(current) and current[1].upper() == m[1].upper()))
    return entries


def boot_once(entry: BootEntry, then_restart: bool = True) -> List[List[str]]:
    """Commands: start ``entry`` on the next restart only (the normal order comes back after that)."""
    if not re.fullmatch(r"[0-9A-F]{4}", entry.num):
        raise ValueError(f"not a boot entry number: {entry.num!r}")
    # The narrow helper asks no password for this one thing; without it (not HalOS), efibootmgr as admin.
    argv = [EFIBOOT_HELPER, "next", entry.num] if Path(EFIBOOT_HELPER).exists() else ["efibootmgr", "--bootnext", entry.num]
    cmds = [["pkexec", *argv]]
    if then_restart:
        cmds.append(reboot_argv())
    return cmds


def reboot_argv() -> List[str]:
    """The restart command the Recovery page runs: HalOS's helper (which has its own fallbacks), else systemctl."""
    return [RESTART_HELPER] if Path(RESTART_HELPER).exists() else list(REBOOT)


def restart_alternatives() -> List[List[str]]:
    """Ways to restart, most polite first. All are in the base system: nothing to install, no network."""
    ways = [[RESTART_HELPER]] if Path(RESTART_HELPER).exists() else []
    return ways + [list(REBOOT), ["systemctl", "reboot", "-i"], list(LOGIND_REBOOT)]


def explain(detail: str) -> str:
    """A plain-language reason for a failed recovery or restart command."""
    low = (detail or "").lower()
    for pattern, reason in _REASONS:
        if re.search(pattern, low):
            return reason
    return "That didn't work, and the PC didn't say why. Copy the log if you report this."


def restart(entry: Optional[BootEntry] = None, run: Callable = subprocess.run) -> dict:
    """Restart now; with ``entry``, into that system once. An entry that can't be set stops here (the PC would
    restart into the wrong system); the restart itself tries every way the image has.
    Returns {"ok", "reason", "log"}: reason is for the person, log is what Copy log copies."""
    log: List[str] = []

    def attempt(argv: List[str]) -> bool:
        try:
            res = run(argv, capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as e:
            log.append(f"$ {' '.join(argv)}\n{type(e).__name__}: {e}")
            return False
        out = ((getattr(res, "stderr", "") or "") + (getattr(res, "stdout", "") or "")).strip()
        log.append(f"$ {' '.join(argv)}\nexit {res.returncode}" + (f"\n{out}" if out else ""))
        return res.returncode == 0

    if entry is not None and not attempt(boot_once(entry, then_restart=False)[0]):
        return {"ok": False, "reason": f"Couldn't choose {entry.label} for the next start. {explain(log[-1])}",
                "log": "\n".join(log)}
    for argv in restart_alternatives():
        if attempt(argv):
            return {"ok": True, "reason": f"Restarting{' into ' + entry.label if entry else ''}…",
                    "log": "\n".join(log)}
    return {"ok": False, "reason": "The PC didn't restart. " + explain("\n".join(log)), "log": "\n".join(log)}


@dataclass
class Snapshot:
    number: int
    date: str
    description: str


def snapshots(run: Callable = subprocess.run) -> Optional[List[Snapshot]]:
    """The system's snapshots, newest first; None when snapper isn't set up (not Btrfs, or not installed)."""
    try:
        res = run(["snapper", "--csvout", "-c", "root", "list", "--columns", "number,date,description"],
                  capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if res.returncode != 0:
        return None
    rows = [l.split(",", 2) for l in res.stdout.splitlines()[1:] if l.strip()]
    snaps = [Snapshot(int(n), d, desc) for n, d, desc in rows if n.isdigit() and n != "0"]
    return sorted(snaps, key=lambda s: -s.number)


def snapshot_now(description: str) -> List[str]:
    desc = re.sub(r"[^\w .,:()'-]", "", description)[:80] or "SAINT snapshot"
    return ["pkexec", "snapper", "-c", "root", "create", "--cleanup-algorithm", "number", "--description", desc]
