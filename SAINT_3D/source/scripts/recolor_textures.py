"""Recolour the CC0 MakeHuman textures into SAINT's palette (charcoal / black / white, thin cyan accent).

Edits the pixels themselves (not shader nodes) so the look survives glTF/VRM export.
Run with any Python that has numpy + PySide6 (HalOS .venv):  python recolor_textures.py
Inputs: ../../textures/source/*.png   Outputs: ../../textures/*.png
"""
from pathlib import Path

import numpy as np
from PySide6.QtGui import QImage

TEX = Path(__file__).resolve().parents[2] / "textures"
CHARCOAL = np.array([0.105, 0.11, 0.12])
TROUSER = np.array([0.035, 0.036, 0.04])
CYAN = np.array([0.0, 0.78, 0.86])


def load(name):
    img = QImage(str(TEX / "source" / name)).convertToFormat(QImage.Format_RGBA8888)
    a = np.frombuffer(img.constBits(), np.uint8).reshape(img.height(), img.width(), 4).astype(np.float32) / 255
    return a.copy()


def save(a, name):
    b = (np.clip(a, 0, 1) * 255).astype(np.uint8)
    QImage(b.data, b.shape[1], b.shape[0], b.shape[1] * 4, QImage.Format_RGBA8888).save(str(TEX / name))


def lum(a):
    return a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722


def detail(l, mask, strength):
    """Fabric detail as a multiplier around 1, from the original luminance inside mask."""
    m = l[mask].mean()
    return 1 + strength * (l - m) / max(m, 1e-3)


def suit():
    a = load("female_casualsuit01_diffuse.png")
    h, w = a.shape[:2]
    rgb, l = a[..., :3], lum(a)
    yy, xx = np.mgrid[0:h, 0:w]
    bg = (np.abs(rgb - rgb[5, 5]).sum(-1) < 0.04)                       # the grey page around the UV islands
    sat = rgb.max(-1) - rgb.min(-1)
    orange = (rgb[..., 0] > rgb[..., 2] + 0.25) & (sat > 0.35)
    shirt = ((yy < 0.44 * h) | ((xx > 0.72 * w) & (yy > 0.56 * h) & (yy < 0.94 * h))) & ~bg
    trousers = ~shirt & ~bg & (yy > 0.42 * h)
    out = rgb.copy()
    out[shirt] = (CHARCOAL * detail(l, shirt & ~orange, 0.35)[..., None])[shirt]
    out[shirt & orange] = CYAN * 0.9
    out[trousers] = (TROUSER * np.clip(detail(l, trousers, 0.12), 0.85, 1.15)[..., None])[trousers]
    # remove the chest logo: copy recoloured plain knit from the middle of the same panel
    y0, y1, x0, x1 = int(0.14 * h), int(0.32 * h), int(0.70 * w), int(0.885 * w)
    out[y0:y1, x0:x1] = out[y0:y1, x0 - 420:x1 - 420]
    a[..., :3] = out
    save(a, "saint_suit_diffuse.png")


def hair():
    a = load("long01_diffuse.png")
    l = lum(a)
    tint = np.array([0.075, 0.045, 0.03])                              # espresso brown
    a[..., :3] = tint * np.clip(detail(l, a[..., 3] > 0.5, 0.9), 0.4, 2.2)[..., None]
    save(a, "saint_hair_diffuse.png")


def shoes():
    a = load("shoes03_diffuse.png")
    l = lum(a)
    a[..., :3] = np.array([0.03, 0.03, 0.032]) * np.clip(detail(l, a[..., 3] > 0.5, 0.6), 0.5, 2.5)[..., None]
    save(a, "saint_shoes_diffuse.png")


def skin(dark_share=0.55):
    """A warm mid-tone: the two CC0 young-female skins share one UV layout, so blend them."""
    d, l = load("young_darkskinned_female_diffuse.png"), load("young_lightskinned_female_diffuse.png")
    if d.shape != l.shape:
        raise SystemExit("skin textures differ in size")
    save(d * dark_share + l * (1 - dark_share), "saint_skin_diffuse.png")


if __name__ == "__main__":
    suit(), hair(), shoes(), skin()
    print("written:", sorted(p.name for p in TEX.glob("saint_*.png")))
