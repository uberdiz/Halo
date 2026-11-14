"""
tools/dev/settings_screenshots.py — every HalOS Settings page (ui/saintos_center.py), dark and light, offscreen,
against the throwaway data dir from screenshots.py. Paths, the host and the OS name are made up: nothing from this PC.

    python tools/dev/settings_screenshots.py OUT_DIR [suffix] [page,page,...] [themes]
                                            # writes <page>_<theme>[_suffix].png; themes e.g. "Dark" or "Dark,Light"
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import screenshots  # noqa: E402  (sets SAINT_DATA_DIR to a throwaway dir first)


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    suffix = f"_{sys.argv[2]}" if len(sys.argv) > 2 and sys.argv[2] else ""
    only = [p.strip().lower() for p in sys.argv[3].split(",")] if len(sys.argv) > 3 and sys.argv[3] else []
    themes = sys.argv[4].split(",") if len(sys.argv) > 4 else ["Dark", "Light"]
    out.mkdir(parents=True, exist_ok=True)
    screenshots.seed()
    from core.logger import init_logger
    init_logger("Errors Only")
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv[:1])
    from ui import saintos_center as sc
    from ui.theme import build_stylesheet
    sc.is_halo = lambda: True
    sc.os_name = lambda: "HalOS 2.3"
    sc.data_locations = lambda: {"Settings, memory, history": "/home/alex/.local/share/saint",
                                 "Models": "/home/alex/.local/share/saint/models",
                                 "Logs": "/home/alex/.local/share/saint/logs", "SAINT program": "/opt/saint"}
    sc.systemd_user_available = lambda: False
    import core.windows_migration as wm
    wm.should_offer = lambda: False
    win = sc.build_window("Welcome")
    win.resize(1180, 800)
    win.show()

    def settle(ms):
        from PySide6.QtCore import QEventLoop, QTimer
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()
    names = [n for n, icon in sc.rail_rows(__import__("ui.settings_pages", fromlist=["x"]).discover()) if icon]
    for theme in themes:
        app.setStyleSheet(build_stylesheet(theme, "#feaa34", "Segoe UI"))
        for name in names:
            if only and name.lower() not in only:
                continue
            win._open(name)
            settle(400)
            slug = name.lower().replace(" ", "_").replace("/", "")
            win.grab().save(str(out / f"{slug}_{theme.lower()}{suffix}.png"))
        print("saved", theme)
    os._exit(0)


if __name__ == "__main__":
    main()
