"""
core/wallpapers.py

What the HalOS Wallpapers app (ui/wallpapers_app.py) lists and applies, as one list of items:

    living   SAINT's living wallpaper (org.halos.living), always there: built into HalOS
    engine   Wallpaper Engine wallpapers from Steam's workshop: HalOS's Steam libraries and the Steam libraries on
             mounted Windows drives (core/wallpaper_engine.py, applied through its plugin or fallbacks)
    image    pictures: Plasma's wallpaper packages (/usr/share/wallpapers), ~/Pictures/Wallpapers and ~/Pictures

Applying goes through the same plasmashell script as the Wallpaper settings page (desktop_script), one monitor
or all. No model, no network.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Callable, List, Optional

from core import wallpaper_engine as we

log = logging.getLogger("saint.wallpapers")

LIVING = "org.halos.living"
IMAGE_PLUGIN = "org.kde.image"
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".avif", ".jxl", ".bmp")
SYSTEM_WALLPAPERS = Path("/usr/share/wallpapers")
MAX_PICTURES = 300                  # per folder: ~/Pictures can hold thousands; the app lists the first ones


def living_item() -> dict:
    return {"kind": "living", "id": "saint-living", "title": "SAINT living wallpaper", "type": "living",
            "source": "halos", "preview": None,
            "about": "Built into HalOS: a colour or gradient with the SAINT logo, glowing and moving with SAINT's "
                     "voice, your music or the microphone."}


def _package_image(d: Path) -> Optional[Path]:
    """A Plasma wallpaper package's picture: the biggest one in contents/images."""
    try:
        pics = [p for p in (d / "contents/images").iterdir() if p.suffix.lower() in IMAGE_EXT and p.is_file()]
    except OSError:
        return None
    return max(pics, key=lambda p: p.stat().st_size, default=None)


def image_items(home: Optional[Path] = None, system: Path = SYSTEM_WALLPAPERS) -> List[dict]:
    home = Path(home or Path.home())
    out, seen = [], set()

    def add(path: Path, title: str, source: str):
        key = str(path)
        if key not in seen:
            seen.add(key)
            out.append({"kind": "image", "id": key, "title": title, "type": "picture", "source": source,
                        "file": path, "preview": path})
    try:
        for d in sorted(system.iterdir()):
            pic = _package_image(d) if d.is_dir() else (d if d.suffix.lower() in IMAGE_EXT else None)
            if pic:
                add(pic, d.name if d.is_dir() else d.stem, "plasma")
    except OSError:
        pass
    for folder in (home / "Pictures/Wallpapers", home / "Pictures"):
        try:
            files = sorted(f for f in folder.iterdir() if f.suffix.lower() in IMAGE_EXT and f.is_file())
        except OSError:
            continue
        for f in files[:MAX_PICTURES]:
            add(f, f.stem, "pictures")
    return out


def catalog(home: Optional[Path] = None, run: Callable = subprocess.run, system: Path = SYSTEM_WALLPAPERS,
            windows: Optional[List[Path]] = None) -> List[dict]:
    """Everything the app shows: SAINT's wallpaper first, then Wallpaper Engine, then pictures."""
    mounts = we.windows_mounts(run) if windows is None else windows
    engine = [{**it, "kind": "engine"} for it in we.items(home, mounts)]
    return [living_item()] + engine + image_items(home, system)


def apply(item: dict, screen: int = -1, run: Callable = subprocess.run) -> str:
    """Put ``item`` on the desktop. Returns what happened; raises we.EngineError with the reason it didn't."""
    from ui.settings_pages.wallpaper import desktop_script, run_script
    kind = item.get("kind")
    if kind == "engine":
        return we.apply(item, screen, run)
    if kind == "living":
        # No values: Plasma keeps the living wallpaper's own settings (Settings > Wallpaper) per desktop.
        script = desktop_script(LIVING, {}, screen)
        done = "SAINT's living wallpaper is on."
    elif kind == "image":
        try:
            script = desktop_script(IMAGE_PLUGIN, {"Image": Path(item["file"]).as_uri()}, screen)
        except ValueError:
            raise we.EngineError("This picture's path has a character Plasma's script can't take.")
        done = f"{item['title']} is your wallpaper now."
    else:
        raise we.EngineError("That isn't a wallpaper HalOS knows how to show.")
    why = run_script(script, run)
    if why:
        raise we.EngineError(why)
    log.info("wallpapers.applied %s", kind)
    return done


def can_apply(item: dict, home: Optional[Path] = None) -> str:
    """"" when ``item`` can be applied here, else why not (a Wallpaper Engine item without its plugin)."""
    if item.get("kind") != "engine":
        return ""
    if we.support(home) or item["type"] == "video" and item.get("file") and we.video_plugin(home):
        return ""
    return we.missing_text()
