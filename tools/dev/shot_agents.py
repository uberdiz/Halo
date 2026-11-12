"""
tools/dev/shot_agents.py

Screenshot of Settings > AI agents for the docs, rated for THIS PC's real hardware (read only; nothing is installed).
    python tools/dev/shot_agents.py docs/process/screenshots
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
    from core import device_profile
    from ui import theme
    from ui.settings_pages import agents
    app.setStyleSheet(theme.build_stylesheet())
    agents.run_async = lambda fn, done, failed: done(fn())
    hw = device_profile.detect(disk_path="C:\\" if os.name == "nt" else "")
    page = agents.AgentsPage(detect=lambda: hw, installed=lambda: set(), stores=lambda: [])
    host = QWidget()
    host.setObjectName("ShotHost")
    host.setStyleSheet(f"#ShotHost {{ background: {theme.current_palette().bg}; }}")
    lay = QVBoxLayout(host)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(page)
    host.resize(980, 880)
    app.processEvents()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    host.grab().save(str(out / "agents.png"))
    print(out / "agents.png", hw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "docs/process/screenshots"))
