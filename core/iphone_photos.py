"""
core/iphone_photos.py

Import photos and videos from an iPhone plugged in by USB (libimobiledevice + ifuse, both in the HalOS image).

    status()               -> {"connected", "paired", "name", "message"}
    import_photos(dest)    -> {"copied", "skipped", "dest", "message"}  new photos only; nothing on the phone changes

The phone shows "Trust this computer?" the first time; until it's accepted, status() says so in plain words. The
phone is mounted read-only in a private folder, its DCIM folder copied into Pictures/iPhone/<year-month>/, and
unmounted again. A photo already imported (same name and size) is skipped, so running it again only brings new
ones.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable, Dict, Optional

MEDIA = {".jpg", ".jpeg", ".heic", ".heif", ".png", ".gif", ".mov", ".mp4", ".m4v", ".dng", ".aae"}


def _run(run: Callable, argv, timeout: float = 20):
    try:
        return run(argv, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        return type("R", (), {"returncode": 127, "stdout": "", "stderr": str(e)})()


def status(run: Callable = subprocess.run) -> Dict:
    ids = _run(run, ["idevice_id", "-l"])
    if ids.returncode == 127:
        return {"connected": False, "paired": False, "name": "",
                "message": "iPhone support isn't installed (libimobiledevice)."}
    udids = [l.strip() for l in (ids.stdout or "").splitlines() if l.strip()]
    if not udids:
        return {"connected": False, "paired": False, "name": "", "message": "No iPhone is plugged in. Connect it with a cable and unlock it."}
    pair = _run(run, ["idevicepair", "-u", udids[0], "validate"])
    name = (_run(run, ["ideviceinfo", "-u", udids[0], "-k", "DeviceName"]).stdout or "iPhone").strip() or "iPhone"
    if pair.returncode != 0:
        _run(run, ["idevicepair", "-u", udids[0], "pair"])
        return {"connected": True, "paired": False, "name": name, "udid": udids[0],
                "message": f"Unlock {name} and tap Trust on it, then try again."}
    return {"connected": True, "paired": True, "name": name, "udid": udids[0], "message": f"{name} is connected."}


def _month(path: Path) -> str:
    return time.strftime("%Y-%m", time.localtime(path.stat().st_mtime))


def copy_new(dcim: Path, dest: Path, progress: Optional[Callable[[int, int], None]] = None) -> Dict[str, int]:
    files = [p for p in dcim.rglob("*") if p.is_file() and p.suffix.lower() in MEDIA]
    copied = skipped = 0
    for i, f in enumerate(sorted(files)):
        target = dest / _month(f) / f.name
        if target.exists() and target.stat().st_size == f.stat().st_size:
            skipped += 1
        else:
            if target.exists():                          # same name, different photo (IMG_0001 again after a reset)
                target = target.with_name(f"{target.stem}-{f.stat().st_size}{target.suffix}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
            copied += 1
        if progress:
            progress(i + 1, len(files))
    return {"copied": copied, "skipped": skipped}


def import_photos(dest: Optional[Path] = None, run: Callable = subprocess.run,
                  progress: Optional[Callable[[int, int], None]] = None) -> Dict:
    st = status(run)
    if not st.get("paired"):
        return {"copied": 0, "skipped": 0, "dest": "", "message": st["message"]}
    if dest is None:
        from modules.link.photos import pictures_dir
        dest = pictures_dir() / "iPhone"
    mnt = Path(tempfile.mkdtemp(prefix="halos-iphone-"))
    try:
        mount = _run(run, ["ifuse", "-u", st["udid"], "-o", "ro", str(mnt)], timeout=60)
        if mount.returncode != 0:
            return {"copied": 0, "skipped": 0, "dest": "",
                    "message": f"{st['name']} couldn't be opened: {(mount.stderr or '').strip()[:160] or 'unlock it and try again'}."}
        dcim = mnt / "DCIM"
        if not dcim.is_dir():
            return {"copied": 0, "skipped": 0, "dest": "", "message": f"No photos found on {st['name']}."}
        result = copy_new(dcim, Path(dest), progress)
    finally:
        _run(run, ["fusermount", "-u", str(mnt)], timeout=30)
        try:
            os.rmdir(mnt)
        except OSError:
            pass
    result["dest"] = str(dest)
    result["message"] = (f"Imported {result['copied']} new photos and videos from {st['name']} into {dest}."
                         + (f" {result['skipped']} were already here." if result["skipped"] else ""))
    return result
