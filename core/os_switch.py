"""
core/os_switch.py

Restart into another OS, one time only: the next boot goes to that UEFI entry, then the normal order returns.
Boot entries and commands come from core/recovery.py; privilege is the narrow helper it uses
(/usr/lib/halo/halo-efiboot, polkit action org.halos.efiboot).
"""

import logging
import os
import re
import subprocess
import uuid as uuidlib
from typing import Callable, Dict, List, Optional

from core import recovery
from core.recovery import BootEntry

log = logging.getLogger("saint.os_switch")

_LOADER = re.compile(r"^Boot([0-9A-Fa-f]{4})\*?\s+(.+?)\s*\tHD\(\d+,GPT,([0-9a-fA-F-]{36})", re.I)


def available() -> tuple:
    if os.name == "nt":
        return False, "Switching to another OS from here only works on HalOS."
    if not recovery.is_uefi():
        return False, "This PC didn't start in UEFI mode, so its boot entries can't be changed from here."
    return True, ""


def others(run: Callable = subprocess.run) -> List[BootEntry]:
    """Boot entries worth restarting into: active operating systems, not this one, not firmware or USB rows."""
    skip = re.compile(r"^(?:uefi|usb|pxe|network|ipv[46]|cd|dvd|hard drive|ubuntu pxe|shell)\b|firmware|setup", re.I)
    return [e for e in recovery.boot_entries(run) if e.active and not e.current and not skip.search(e.label)]


def find(target: str, entries: List[BootEntry]) -> Optional[BootEntry]:
    """By number ("0003"), or by name ("windows"), when exactly one entry fits."""
    t = (target or "").strip()
    if re.fullmatch(r"[0-9A-Fa-f]{4}", t):
        return next((e for e in entries if e.num == t.upper()), None)
    hits = [e for e in entries if t and t.lower() in e.label.lower()]
    return hits[0] if len(hits) == 1 else None


def restart_into(target: str, run: Callable = subprocess.run, reboot: bool = True) -> Dict:
    """The one action. ``target`` must be an entry efibootmgr lists right now."""
    ok, why = available()
    if not ok:
        return {"ok": False, "message": why}
    entries = others(run)
    entry = find(target, entries)
    if entry is None:
        names = ", ".join(e.label for e in entries) or "none"
        return {"ok": False, "message": f"I can't tell which OS \"{target}\" is. Boot entries here: {names}."}
    for argv in recovery.boot_once(entry, then_restart=reboot):
        res = run(argv, capture_output=True, text=True, timeout=120)
        if res.returncode != 0:
            detail = (res.stderr or "").strip()[:200]
            log.warning("os_switch.failed argv=%s: %s", argv, detail)
            return {"ok": False, "message": f"Couldn't set {entry.label} for the next restart: {detail or 'it was refused'}"}
    return {"ok": True, "message": f"Restarting into {entry.label}.", "entry": entry.num, "label": entry.label}


def remove_entry_argv(num: str) -> List[str]:
    if not re.fullmatch(r"[0-9A-F]{4}", num or ""):
        raise ValueError(f"not a boot entry number: {num!r}")
    return ["pkexec", recovery.EFIBOOT_HELPER, "delete", num]


def loader_entries(run: Callable = subprocess.run) -> List[Dict]:
    """From ``efibootmgr -v``: every entry stored on a GPT partition, with which partition that is."""
    try:
        out = run(["efibootmgr", "-v"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    rows = []
    for line in out.splitlines():
        m = _LOADER.match(line)
        if m:
            rows.append({"num": m[1].upper(), "label": m[2], "partuuid": m[3].lower(),
                         "windows": "bootmgfw" in line.lower() or "windows" in m[2].lower()})
    return rows


def _bcd_mentions(bcd: bytes, partuuid: str) -> bool:
    """BCD stores a Windows loader's partition GUID in binary. A plain byte search: no false "absent" for a
    device element, and any doubt below means the entry is kept."""
    try:
        return uuidlib.UUID(partuuid).bytes_le in bcd
    except ValueError:
        return False


def stale_windows_entry(old_partuuid: str, main_partuuid: str, read_bcd: Callable[[str], Optional[bytes]],
                        run: Callable = subprocess.run) -> Dict:
    """Is there a boot entry that can only start the removed Windows? Offered only when proven:
    its own BCD names the old volume and not the main one, and a different Windows entry's BCD names the main
    one. One shared "Windows Boot Manager" (the usual case) is never offered: it may well boot the main Windows.
    ``read_bcd(esp_partuuid)`` returns that ESP's EFI/Microsoft/Boot/BCD, or None if it can't be read."""
    rows = [r for r in loader_entries(run) if r["windows"]]
    keep = {"entry": None}
    if len(rows) < 2:
        return {**keep, "reason": "There's only one Windows boot entry, and it may boot your main Windows. It stays."}
    bcds = {r["num"]: read_bcd(r["partuuid"]) for r in rows}
    if any(b is None for b in bcds.values()):
        return {**keep, "reason": "An EFI partition couldn't be read to check, so every boot entry stays."}
    main_rows = [r for r in rows if _bcd_mentions(bcds[r["num"]], main_partuuid)]
    stale = [r for r in rows if _bcd_mentions(bcds[r["num"]], old_partuuid)
             and not _bcd_mentions(bcds[r["num"]], main_partuuid)]
    if not main_rows:
        return {**keep, "reason": "No boot entry could be proven to start your main Windows, so they all stay."}
    if len(stale) != 1:
        return {**keep, "reason": "No entry could be proven to start only the old Windows, so they all stay."}
    return {"entry": stale[0], "reason": f"\"{stale[0]['label']}\" only starts the removed Windows."}


# ---------------------------------------------------------------------- SAINT tool
def _tool_restart(target: str = "windows") -> Dict:
    from modules.automation.tools import ToolError
    res = restart_into(target)
    if not res["ok"]:
        raise ToolError(res["message"], "OS_SWITCH")
    return res


def register_os_switch_tools(registry):
    from modules.automation.tools import P, PermissionLevel, Tool
    # Always asks first (core/permissions.ALWAYS_CONFIRM).
    registry.register(Tool("system.restart_into", "Restart the PC into another installed OS, such as Windows, for one boot",
                           {"target": "string"}, PermissionLevel.HIGH, _tool_restart,
                           parameters={"target": P("string", "the OS to start, such as windows")},
                           category="system", availability=available))
