"""
tools/dev/shot_wallpaper.py

Screenshots of the Wallpaper settings page (its live preview is the same drawing rules as the Plasma wallpaper),
with two looks. Nothing is applied.   python tools/dev/shot_wallpaper.py docs/process/screenshots
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt":
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget  # noqa: E402


def main(out_dir: str) -> int:
    app = QApplication.instance() or QApplication([])
    from ui import theme
    from ui.settings_pages import wallpaper as wp
    app.setStyleSheet(theme.build_stylesheet())
    page = wp.WallpaperPage(applier=lambda v, s: True)
    host = QWidget()
    host.setObjectName("ShotHost")
    host.setStyleSheet(f"#ShotHost {{ background: {theme.current_palette().bg}; }}")
    lay = QVBoxLayout(host)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(page)
    host.resize(980, 1000)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    looks = {"wallpaper-page.png": {},
             "wallpaper-preview-blue.png": {"Background": "gradient", "Color": "#06121f", "Color2": "#1b4b7a",
                                            "Accent": "#5cc8ff", "LogoX": 0.82, "LogoY": 0.22, "LogoScale": 0.22,
                                            "Glow": 0.9, "Angle": 200}}
    for name, look in looks.items():
        page._load({**wp.DEFAULTS, **look})
        page.preview.t = 1.2                       # mid-breath, so the bars show
        app.processEvents()
        (host if name == "wallpaper-page.png" else page.preview).grab().save(str(out / name))
        print(out / name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "docs/process/screenshots"))
