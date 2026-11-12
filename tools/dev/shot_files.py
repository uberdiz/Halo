"""
tools/dev/shot_files.py

Screenshot of HalOS Files for the docs, on a SAMPLE folder made in a temp directory (none of the user's files are
shown), searching "the app for claude" against two sample app entries, and "tax pdf".
    python tools/dev/shot_files.py docs/process/screenshots
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt":
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PySide6.QtWidgets import QApplication  # noqa: E402

SAMPLE = ["Documents/Taxes/TaxReturn2025.pdf", "Documents/Taxes/Receipts 2025.pdf", "Documents/CV.docx",
          "Documents/Budget 2025.xlsx", "Pictures/Holiday/beach.jpg", "Pictures/Holiday/sunset.jpg",
          "Music/playlist.m3u", "Videos/birthday.mp4", "Downloads/HalOS-Setup.exe"]
APPS = [{"name": "Claude Code", "generic": "AI coding agent", "keywords": "anthropic;ai;", "comment": "", "path": "/usr/share/applications/claude-code.desktop"},
        {"name": "AIDE", "generic": "Code", "keywords": "code;editor;claude;ai;", "comment": "", "path": "/usr/share/applications/aide.desktop"}]


def main(out_dir: str) -> int:
    app = QApplication.instance() or QApplication([])
    from core import file_index as fi
    from ui import files_app, theme
    app.setStyleSheet(theme.build_stylesheet())
    home = Path(tempfile.mkdtemp()) / "home"
    for rel in SAMPLE:
        p = home / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 2048)
    idx = fi.FileIndex(home.parent / "idx.sqlite")
    idx.update([str(home)])
    idx._apps = APPS
    files_app.places = lambda: [(n, home / n) for n in ("Documents", "Pictures", "Music", "Videos", "Downloads")]
    files_app.FilesWindow.reindex = lambda self: None
    w = files_app.FilesWindow(str(home / "Documents"), index=idx, roots=[str(home)])
    w.resize(1100, 600)
    w.show()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, text in (("files-app-search.png", "the app for claude"), ("files-tax-search.png", "tax pdf")):
        w.search.setText(text)
        w.run_search()
        w.results.setCurrentRow(0)
        app.processEvents()
        w.path_label.setText("~/Documents")
        w.grab().save(str(out / name))
        print(out / name, w.status.text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "docs/process/screenshots"))
