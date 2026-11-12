"""
tools/dev/shot_plan_panel.py

Renders the real plan panel (ui/plan_panel.py) offscreen with a sample three-step plan and saves a PNG for the
docs. The steps are samples: nothing is executed.   python tools/dev/shot_plan_panel.py docs/process/screenshots
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt":                                  # the offscreen platform has no fonts of its own
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PySide6.QtGui import QColor, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def main(out_dir: str) -> int:
    app = QApplication.instance() or QApplication([])
    from ui import motion, theme
    from ui.plan_panel import PlanPanel
    motion.enabled = lambda: False
    app.setStyleSheet(theme.build_stylesheet())
    panel = PlanPanel()
    titles = ["Switch dark or light theme", "Set the volume", "Move a file or folder to the trash"]
    steps = [{"index": i, "title": t, "status": "pending", "message": ""} for i, t in enumerate(titles)]
    panel.start({"plan": "demo", "title": "Movie mode, then tidy the desktop", "steps": steps})
    panel.step(dict(steps[0], status="done", plan="demo"))
    panel.step(dict(steps[1], status="running", plan="demo"))
    app.processEvents()
    shot = panel.grab()
    canvas = QPixmap(shot.width() + 48, shot.height() + 48)
    canvas.fill(QColor(theme.current_palette().bg))
    g = QPainter(canvas)
    g.drawPixmap(24, 24, shot)
    g.end()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "plan-panel.png"
    canvas.save(str(target))
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "docs/process/screenshots"))
