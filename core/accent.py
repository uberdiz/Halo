"""
core/accent.py

One accent colour for the whole OS, taken from the wallpaper with plain arithmetic (no model):

    from_image(path)     the wallpaper's dominant vivid hue, made bright enough to read on the dark theme
    current_wallpaper()  what the first desktop shows: ("image", path) | ("living", "#rrggbb") | ("", "")
    apply(color)         Plasma's accent (plasma-apply-colorscheme --accent-color) and SAINT's (appearance.accent)
    sync()               all three in one go, for the action and the wallpaper pages

A wallpaper with no colour to speak of (grey, black and white) keeps the HalOS amber.
"""

from __future__ import annotations

import colorsys
import logging
import re
import subprocess
from pathlib import Path
from typing import Callable, Optional, Tuple
from urllib.parse import urlparse
from urllib.request import url2pathname

log = logging.getLogger("saint.accent")

DEFAULT = "#feaa34"
_HEX = re.compile(r"#[0-9a-fA-F]{6}")
BINS = 36


def pick(pixels) -> str:
    """The accent for an iterable of (r, g, b) 0-255: the hue bin with the most saturated, bright weight, averaged
    and lifted to a readable brightness. Deterministic: same pixels, same colour."""
    weight = [0.0] * BINS
    sums = [[0.0, 0.0, 0.0] for _ in range(BINS)]
    total = 0
    for r, g, b in pixels:
        total += 1
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s < 0.25 or v < 0.2:
            continue
        w = s * s * v                                  # vivid beats merely bright
        i = int(h * BINS) % BINS
        weight[i] += w
        sums[i][0] += r * w
        sums[i][1] += g * w
        sums[i][2] += b * w
    best = max(range(BINS), key=lambda i: (weight[i], -i))
    if not total or weight[best] < total * 0.004:     # under ~1% clearly coloured: nothing to follow
        return DEFAULT
    r, g, b = (c / weight[best] for c in sums[best])
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    r, g, b = colorsys.hsv_to_rgb(h, min(0.9, max(0.55, s)), min(1.0, max(0.88, v)))
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def from_image(path, size: int = 64) -> str:
    """The accent for an image file (downscaled to size x size first; any format Qt reads)."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage
    img = QImage(str(path))
    if img.isNull():
        return DEFAULT
    img = img.scaled(size, size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(QImage.Format_RGB32)
    return pick((c.red(), c.green(), c.blue()) for c in
                (img.pixelColor(x, y) for y in range(img.height()) for x in range(img.width())))


_READ = """var d = desktops()[0];
d.currentConfigGroup = ['Wallpaper', d.wallpaperPlugin, 'General'];
print(d.wallpaperPlugin + '|' + (d.readConfig('Image') || '') + '|' + (d.readConfig('Accent') || ''));"""


def current_wallpaper(run: Callable = subprocess.run) -> Tuple[str, str]:
    from ui.settings_pages.wallpaper import _SHELL
    for q in ("qdbus6", "qdbus"):
        try:
            r = run([q, *_SHELL, _READ], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        plugin, _, rest = (r.stdout or "").strip().partition("|")
        image, _, accent = rest.partition("|")
        if plugin == "org.halos.living" and _HEX.fullmatch(accent):
            return "living", accent.lower()
        if image:
            p = Path(url2pathname(urlparse(image).path)) if image.startswith("file:") else Path(image)
            if p.is_dir():                             # a wallpaper package: its biggest picture
                pics = sorted((f for f in p.rglob("*") if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")),
                              key=lambda f: f.stat().st_size, reverse=True)
                p = pics[0] if pics else p
            return ("image", str(p)) if p.is_file() else ("", "")
        return "", ""
    return "", ""


def apply(color: str, run: Callable = subprocess.run) -> str:
    """Make ``color`` the accent of Plasma and SAINT. Returns "" or why Plasma's part didn't work."""
    if not _HEX.fullmatch(color or ""):
        raise ValueError(f"not a colour: {color!r}")
    color = color.lower()
    from core.config import config
    config.set("appearance.accent", color)
    try:
        r = run(["plasma-apply-colorscheme", "--accent-color", color], capture_output=True, text=True, timeout=20)
        why = "" if r.returncode == 0 else " ".join((r.stderr or r.stdout or "").split())[:200] or "it failed"
    except (OSError, subprocess.SubprocessError) as e:
        why = str(e)
    if why:
        log.warning("accent.plasma_failed %s", why)
    return why


def sync(run: Callable = subprocess.run, image_accent: Callable[[str], str] = from_image) -> Optional[str]:
    """Accent from whatever the wallpaper is now; the colour applied, or None when the wallpaper can't be read."""
    kind, value = current_wallpaper(run)
    if not kind:
        return None
    color = value if kind == "living" else image_accent(value)
    apply(color, run)
    return color
