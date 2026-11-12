"""Draws every HalOS icon on one sheet (with its name) for review and the docs.
    python tools/icons/contact_sheet.py docs/process/screenshots/halos-icons.png"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt":
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402

THEME = Path(__file__).resolve().parents[2] / "packaging/linux/rootfs/usr/share/icons/HalOS/scalable"


def main(out: str) -> int:
    QGuiApplication.instance() or QGuiApplication([])
    files = sorted(THEME.glob("*/*.svg"), key=lambda p: (p.parent.name != "places", p.parent.name, p.stem))
    cols, cell, label = 10, 120, 28
    rows = (len(files) + cols - 1) // cols
    img = QImage(cols * cell, rows * (cell + label), QImage.Format_ARGB32)
    img.fill(QColor("#121316"))
    g = QPainter(img)
    g.setRenderHint(QPainter.Antialiasing)
    g.setFont(QFont("Segoe UI", 7))
    g.setPen(QColor("#9a9ca3"))
    for i, f in enumerate(files):
        x, y = (i % cols) * cell, (i // cols) * (cell + label)
        QSvgRenderer(str(f)).render(g, QRectF(x + 28, y + 16, 64, 64))
        g.drawText(QRectF(x + 2, y + 86, cell - 4, label + 8), Qt.AlignHCenter | Qt.TextWrapAnywhere, f.stem)
    g.end()
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(out, len(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "docs/process/screenshots/halos-icons.png"))
