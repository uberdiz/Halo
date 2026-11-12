"""
packaging/linux/branding/make_icon.py

The HalOS icon ("Orbit"): a tilted halo in perspective, circling a four-point star. Each size is drawn
directly from distance fields rather than scaled down, and strokes thicken as it shrinks, so 16 px stays a ring.

    python packaging/linux/branding/make_icon.py [OUTPUT_DIR]     (default: data/brand)

The PNGs are committed: make_branding.py and SAINT read them, so image builds don't need numpy.
Colours are SAINT's own orange (ui/theme.py).
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[3]
SIZES = (16, 20, 22, 24, 32, 40, 48, 64, 128, 256, 512, 1024)
TOP = np.array([255, 224, 150.0])
MID = np.array([254, 170, 52.0])
LOW = np.array([232, 96, 22.0])
STAR = np.array([255, 240, 200.0])
TILT = np.radians(-22)
FLATTEN = 0.44                  # ring height / width: how far the halo leans back
RING_RADIUS = 0.82


def _cover(d, px):
    return np.clip(0.5 - d / px, 0, 1)


def _over(rgb, a, new, na):
    out = na + a * (1 - na)
    safe = np.where(out > 0, out, 1)[..., None]
    return (new * na[..., None] + rgb * (a * (1 - na))[..., None]) / safe, out


def _ramp(y, y0=-0.85, y1=0.85):
    t = np.clip((y - y0) / (y1 - y0), 0, 1)[..., None]
    a = TOP + (MID - TOP) * np.clip(t * 2.2, 0, 1)
    return a + (LOW - a) * np.clip((t - 0.45) / 0.55, 0, 1)


def _star(x, y, points, outer, inner):
    """Signed distance to a regular star, tip up."""
    rad = np.hypot(x, y)
    sector = 2 * np.pi / points
    a = np.mod(np.arctan2(x, -y), sector)
    a = np.minimum(a, sector - a)
    px, py = rad * np.cos(a), rad * np.sin(a)
    bx, by = inner * np.cos(np.pi / points), inner * np.sin(np.pi / points)
    ex, ey = bx - outer, by
    return ((px - outer) * ey - py * ex) / np.hypot(ex, ey)


def _weight(n, big, small):
    return big + (small - big) * np.clip((64 - n) / 48, 0, 1)


def orbit(n: int) -> Image.Image:
    c = (np.arange(n) + 0.5) / n * 2 - 1
    x0, y0 = np.meshgrid(c, c)
    px = 2.0 / n
    x = x0 * np.cos(TILT) - y0 * np.sin(TILT)
    y = x0 * np.sin(TILT) + y0 * np.cos(TILT)

    # The ring, as an implicit ellipse, thicker towards the viewer.
    f = np.hypot(x, y / FLATTEN)
    grad = np.hypot(x, y / FLATTEN ** 2) / np.where(f > 1e-6, f, 1e-6)
    grad = np.where(grad > 1e-6, grad, 1)
    near = np.clip(y / (RING_RADIUS * FLATTEN) * 0.5 + 0.5, 0, 1)
    ring = np.abs((f - RING_RADIUS) / grad) - (_weight(n, 0.12, 0.2) / 2) * (0.62 + 0.38 * near)
    a_ring = _cover(ring, px)

    s = _weight(n, 0.62, 0.68)
    d_star = _star(x0, y0, 4, s, s * 0.2)
    a_star = _cover(d_star, px)

    # Back half of the ring, then the star (with a sliver of air round it), then the front half.
    back = np.clip(0.5 - y / px, 0, 1)
    base = _ramp(y0)
    air = _cover(d_star - _weight(n, 0.045, 0.06), px)
    a = a_ring * back * (1 - air)
    rgb = base * 0.74
    rgb, a = _over(rgb, a, np.ones_like(rgb) * STAR, a_star)
    rgb, a = _over(rgb, a, _ramp(y0 * 0.7 + 0.2), a_ring * (1 - back))

    # A soft glow, only where there are pixels to spare for it.
    if n >= 48:
        mask = Image.fromarray((a_ring * 255).astype("uint8")).filter(ImageFilter.GaussianBlur(0.03 * n))
        rgb, a = _over(np.ones_like(rgb) * MID, np.asarray(mask, dtype=float) / 255 * 0.4, rgb, a)

    return Image.fromarray(np.dstack([np.clip(rgb, 0, 255), np.clip(a, 0, 1) * 255]).astype("uint8"), "RGBA")


def main(argv) -> int:
    out = Path(argv[1]) if len(argv) > 1 else ROOT / "data" / "brand"
    out.mkdir(parents=True, exist_ok=True)
    for n in SIZES:
        orbit(n).save(out / f"halos-{n}.png", optimize=True)
    print(f"icon written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
