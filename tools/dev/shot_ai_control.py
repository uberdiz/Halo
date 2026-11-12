"""
tools/dev/shot_ai_control.py

Screenshot of Settings > "What SAINT may do" for the docs. The log shown is a temporary one filled by running
two harmless sample actions through the real executor (a throwaway action that changes nothing on the PC).
    python tools/dev/shot_ai_control.py docs/process/screenshots
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt":
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget  # noqa: E402


def main(out_dir: str) -> int:
    app = QApplication.instance() or QApplication([])
    from core import actions
    from core.actions import Action, ActionLog, ActionResult, P, executor, log as log_mod, registry, trust
    from ui import theme
    app.setStyleSheet(theme.build_stylesheet())
    fresh = ActionLog(Path(tempfile.mkdtemp()) / "log.jsonl")          # never the user's real log
    for mod in (log_mod, executor, actions):
        mod.action_log = fresh
    trust.set_level = lambda *a, **k: None                              # the screenshot saves nothing
    registry.register(Action("settings.sample.volume", "Set the volume", lambda p: ActionResult(
        True, f"Volume is {p['percent']}%.", undo={"percent": 30}), {"percent": P("integer")},
        undo=lambda t: "Volume is 30% again."), replace=True)
    registry.register(Action("files.sample.trash", "Move a file or folder to the trash", lambda p: ActionResult(
        True, "old-notes.txt is in the trash.", undo={"path": "x"}), {"path": P("string")}, risk="risky",
        undo=lambda t: "Put old-notes.txt back."), replace=True)
    actions.execute("settings.sample.volume", {"percent": 45}, source="saint")
    actions.execute("files.sample.trash", {"path": "~/Documents/old-notes.txt"}, source="saint", confirmed=True)
    actions.execute("files.sample.trash", {"path": "~/Documents/tax.pdf"}, source="saint", confirm=lambda r: False)
    from ui.settings_pages import ai_control
    page = ai_control.AIControlPage()
    for name in ("settings.sample.volume", "files.sample.trash"):
        registry.unregister(name)
    host = QWidget()
    host.setObjectName("ShotHost")
    host.setStyleSheet(f"#ShotHost {{ background: {theme.current_palette().bg}; }}")
    lay = QVBoxLayout(host)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(page)
    host.resize(980, 760)
    app.processEvents()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    host.grab().save(str(out / "ai-control.png"))
    print(out / "ai-control.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "docs/process/screenshots"))
