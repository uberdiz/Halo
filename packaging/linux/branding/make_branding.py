"""
packaging/linux/branding/make_branding.py

Generates the HalOS artwork from the committed icon (data/brand, see make_icon.py):

    wallpaper/   SAINTOS-<w>x<h>.png      the default Plasma wallpaper (the HalOS icon on near-black)
    plymouth/    watermark.png            boot splash wordmark (Plymouth "spinner" theme)
    logo/        saintos-logo-<n>.png     the HalOS icon (file names keep their old prefix)
                 saint-<n>.png            SAINT's own logo, for the icon theme

    python packaging/linux/branding/make_branding.py OUTPUT_DIR [--name NAME] [--subtitle TEXT]

NAME (default HalOS) is the wordmark on the wallpaper and boot splash.

Colours are SAINT's own (ui/theme.py): background #0a0b0d, accent "SAINT orange" #feaa34.
Deterministic for a given font file. Needs Pillow.
"""

import argparse
import math
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[3]
BG = (10, 11, 13)
BG_LIFT = (22, 24, 30)
ACCENT = (254, 170, 52)
TEXT = (236, 238, 242)
MUTED = (138, 143, 152)
WALLPAPER_SIZES = [(3840, 2160), (2560, 1440), (1920, 1080), (1920, 1200), (1366, 768)]

_FONTS = [  # first one found wins; Fedora, then Arch paths
    "/usr/share/fonts/google-noto-vf/NotoSans[wght].ttf",
    "/usr/share/fonts/google-noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
]


def font(size: int):
    for path in _FONTS:
        if os.path.exists(path):
            f = ImageFont.truetype(path, size)
            try:
                f.set_variation_by_axes([300])          # light weight on variable fonts
            except Exception:
                pass
            return f
    raise SystemExit("make_branding: no TrueType font found (dnf install google-noto-sans-fonts)")


def _radial(size, inner, outer, center, radius) -> Image.Image:
    """A smooth radial gradient (computed small, scaled up — fast and banding-free enough)."""
    w, h = size
    sw, sh = max(1, w // 8), max(1, h // 8)
    img = Image.new("RGB", (sw, sh))
    px = img.load()
    cx, cy, r = center[0] / 8, center[1] / 8, radius / 8
    for y in range(sh):
        for x in range(sw):
            t = min(1.0, math.hypot(x - cx, y - cy) / r)
            t = t * t * (3 - 2 * t)
            px[x, y] = tuple(int(inner[i] + (outer[i] - inner[i]) * t) for i in range(3))
    return img.resize(size, Image.BICUBIC)


def halo(size, center, radius, width, glow) -> Image.Image:
    """The SAINT Halo: an orange ring with a soft glow, as an RGBA layer."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    box = [center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius]
    d.ellipse(box, outline=ACCENT + (255,), width=width)
    blurred = layer.filter(ImageFilter.GaussianBlur(glow))
    out = Image.alpha_composite(blurred, blurred)
    return Image.alpha_composite(out, layer)


def wallpaper(w: int, h: int, name: str = "HalOS", subtitle: str = "Arch Linux  ·  KDE Plasma") -> Image.Image:
    """The HalOS icon front and centre, the wordmark under it."""
    s = h / 1080
    center = (w // 2, int(h * 0.42))
    radius = int(200 * s)
    img = _radial((w, h), BG_LIFT, BG, center, int(h * 0.9)).convert("RGBA")
    side = int(radius * 2.2)
    mark = Image.open(ROOT / "data" / "brand" / "halos-1024.png").convert("RGBa").resize((side, side), Image.LANCZOS)
    mark = mark.convert("RGBA")
    img.alpha_composite(mark, (center[0] - side // 2, center[1] - side // 2))
    d = ImageDraw.Draw(img)
    word = font(int(64 * s))
    spaced = " ".join(name)                                   # letter-spaced wordmark
    box = d.textbbox((0, 0), spaced, font=word)
    d.text((center[0] - (box[2] - box[0]) // 2, center[1] + radius + int(56 * s)), spaced, font=word,
           fill=TEXT + (240,))
    d.text((int(74 * s), h - int(66 * s)), subtitle, font=font(int(18 * s)), fill=MUTED + (200,))
    return img.convert("RGB")


def logo(n: int) -> Image.Image:
    """The HalOS icon at n px (data/brand, drawn per size by make_icon.py)."""
    return Image.open(ROOT / "data" / "brand" / f"halos-{n}.png").convert("RGBA")


def saint_icon(n: int) -> Image.Image:
    """SAINT's own logo at n px, for the icon theme. Scaled premultiplied, so edge pixels keep their colour."""
    src = Image.open(ROOT / "SAINT.png").convert("RGBA").convert("RGBa")
    return src.resize((n, n), Image.LANCZOS).convert("RGBA")


def watermark(text: str = "HalOS") -> Image.Image:
    f = font(40)
    box = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), text, font=f)
    img = Image.new("RGBA", (box[2] + 8, box[3] + 12), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((4, 2), text, font=f, fill=TEXT + (255,))
    return img


def main(argv) -> int:
    ap = argparse.ArgumentParser(description="Generate the OS artwork")
    ap.add_argument("out")
    ap.add_argument("--name", default="HalOS")
    ap.add_argument("--subtitle", default="Arch Linux  ·  KDE Plasma")
    args = ap.parse_args(argv[1:])
    out = Path(args.out)
    for sub in ("wallpaper", "plymouth", "logo"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    for w, h in WALLPAPER_SIZES:
        wallpaper(w, h, args.name, args.subtitle).save(out / "wallpaper" / f"SAINTOS-{w}x{h}.png", optimize=True)
    for n in (16, 22, 24, 32, 48, 64, 128, 256, 512):
        logo(n).save(out / "logo" / f"saintos-logo-{n}.png", optimize=True)
        if n < 512:                                     # the saint package ships SAINT.png as the 512 px one
            saint_icon(n).save(out / "logo" / f"saint-{n}.png", optimize=True)
    watermark(args.name).save(out / "plymouth" / "watermark.png", optimize=True)
    print(f"branding written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
