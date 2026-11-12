"""
tools/dev/shot_migration_apps.py

Screenshot of the migration wizard's Apps step for the docs, filled from THIS Windows PC's real installed-app
list (read-only: the Uninstall registry keys) matched against the curated table only (no network, nothing is
installed).   python tools/dev/shot_migration_apps.py docs/process/screenshots
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt":
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PySide6.QtWidgets import QApplication  # noqa: E402


def installed_names():
    import winreg
    names = set()
    for hive, path in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                       (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                       (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")):
        try:
            key = winreg.OpenKey(hive, path)
        except OSError:
            continue
        for i in range(winreg.QueryInfoKey(key)[0]):
            try:
                names.add(winreg.QueryValueEx(winreg.OpenKey(key, winreg.EnumKey(key, i)), "DisplayName")[0])
            except OSError:
                pass
    return sorted(n for n in names if "$" not in n)


def main(out_dir: str) -> int:
    app = QApplication.instance() or QApplication([])
    from core import app_match
    from core import windows_migration as wm
    from ui import theme
    from ui.settings_pages import migrate_windows as mw
    app.setStyleSheet(theme.build_stylesheet())
    matches = wm.match_apps(installed_names(), search=lambda q, sources=(): [], curated=app_match.lookup)
    page = mw.MigratePage()
    page.stack.setCurrentIndex(3)
    page.step_label.setText("STEP 4 OF 5: APPS")
    page.show_matches(matches)
    from PySide6.QtWidgets import QVBoxLayout, QWidget
    host = QWidget()                                   # the window behind the page, as in SAINT
    host.setObjectName("ShotHost")
    host.setStyleSheet(f"#ShotHost {{ background: {theme.current_palette().bg}; }}")
    lay = QVBoxLayout(host)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(page)
    host.resize(980, 720)
    app.processEvents()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, index in (("migration-apps-all.png", 0), ("migration-apps-works.png", 1)):
        page.app_filter.setCurrentIndex(index)
        app.processEvents()
        host.grab().save(str(out / name))
        print(out / name, page.app_filter.currentText())
    print(page.status.text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "docs/process/screenshots"))
