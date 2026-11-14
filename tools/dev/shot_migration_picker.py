"""
tools/dev/shot_migration_picker.py

Screenshots for the docs, on SAMPLE data in a temp directory (none of the user's files): the migration wizard's
"pick files and folders yourself" browser with Quick add, and HalOS Files' Downloads & installs, light and dark.
    python tools/dev/shot_migration_picker.py docs/screenshots
"""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt":
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget  # noqa: E402

SAMPLE = ["Users/seb/NTUSER.DAT", "Users/seb/Documents/Taxes/2025.pdf", "Users/seb/Documents/CV.docx",
          "Users/seb/Pictures/Holiday/beach.jpg", "Users/seb/Pictures/Screenshots/shot.png",
          "Users/seb/Saved Games/Elden Ring/save.sl2", "Users/seb/AppData/Roaming/.minecraft/saves/World/level.dat",
          "Users/seb/Desktop/notes.txt", "Windows/System32/config/SOFTWARE", "Windows/explorer.exe",
          "Games/Factorio/saves/base.zip"]


def wait(app, ms=400):
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.02)


def host_for(widget, bg):
    host = QWidget()
    host.setObjectName("ShotHost")
    host.setStyleSheet(f"#ShotHost {{ background: {bg}; }}")
    lay = QVBoxLayout(host)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(widget)
    return host


def main(out_dir: str) -> int:
    app = QApplication.instance() or QApplication([])
    from core import downloads as dl
    from core import windows_migration as wm
    from ui import theme
    from ui.settings_pages import migrate_windows as mw
    from ui.settings_pages.downloads import DownloadsPage
    root = Path(tempfile.mkdtemp()) / "C"
    for rel in SAMPLE:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 300_000)
    inst = wm.probe_root(root)
    inst.label, inst.device, inst.size, inst.edition = "Windows", "/dev/nvme0n1p3", 1_700 * 10 ** 9, "Windows 11 Pro 23H2"
    store = {wm.QUICK_KEY: [{"label": "Factorio saves", "path": "/Games/Factorio/saves"}]}
    real = wm.quick_add_entries
    wm.quick_add_entries = lambda get=None: real(get=lambda k, d=None: store.get(k, d))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    now = time.time()
    active = [dl.Item("Installing Blender", "Flathub", pct=62, speed=8.4e6, eta_s=95, key="a", cancellable=True),
              dl.Item("ubuntu-24.04.iso", "Browser", 2_100_000_000, 0, 31e6, path="/home/seb/Downloads/x.part")]
    done = [dl.Item("HalOS-Setup.exe", "Finished", 61_000, 61_000, state="finished", key="f1", path=__file__),
            dl.Item("Taxes 2025.pdf", "Finished", 2_400_000, 2_400_000, state="finished", key="f2", path=__file__)]
    for name in ("Dark", "Light"):
        app.setStyleSheet(theme.build_stylesheet(theme=name))
        bg = theme.palette_for(name).bg
        page = mw.MigratePage()
        page._detected = True                          # no real drive scan
        page.show_installs([inst])
        page.go(1)
        page.pick_model.toggle(str(root / "Users/seb/Documents"), True)
        page.pick_model.toggle(str(root / "Users/seb/Saved Games"), True)
        host = host_for(page, bg)
        host.resize(1100, 1400)
        host.show()
        wait(app, 900)
        page.tree.expand(page.pick_model.index(str(root / "Users/seb")))
        wait(app, 600)
        host.grab().save(str(out / f"migration-picker-{name.lower()}.png"))
        dpage = DownloadsPage(source=lambda: active, finished=lambda: done)
        dpage.show_items(active, done)
        dhost = host_for(dpage, bg)
        dhost.resize(900, 620)
        dhost.show()
        wait(app, 1200)
        wait(app, 600)
        dhost.grab().save(str(out / f"files-downloads-{name.lower()}.png"))
        host.close()
        dhost.close()
        print(out / f"migration-picker-{name.lower()}.png", out / f"files-downloads-{name.lower()}.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "docs/screenshots"))
