"""
tools/dev/ui_pages_screenshots.py — every SAINT main-window page, dark and light, offscreen, from the
made-up data in screenshots.py (nothing from this PC).

    python tools/dev/ui_pages_screenshots.py OUT_DIR [suffix]    # writes <page>_<theme>[_suffix].png
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt":                     # the offscreen platform finds no fonts on Windows by itself
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import screenshots  # noqa: E402  (sets SAINT_DATA_DIR to a throwaway dir first)

PAGES = ["Overview", "Activity", "Tasks", "Agent", "Music", "Devices", "Memory", "Automations", "History",
         "Storage", "System", "Settings"]


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    suffix = f"_{sys.argv[2]}" if len(sys.argv) > 2 else ""
    out.mkdir(parents=True, exist_ok=True)
    app, w, settle, fake_junk = screenshots.build()
    w.resize(1280, 820)
    for theme in ("Dark", "Light"):
        w._set_theme(theme)
        for page in PAGES:
            w.navigate(page, animate=False)
            if page == "Storage":
                w.stack.currentWidget().cleanup.show_report(fake_junk)
            settle(600)
            w.grab().save(str(out / f"{page.lower()}_{theme.lower()}{suffix}.png"))
        print("saved", theme)
    w.demo.stop()
    w.quit()


if __name__ == "__main__":
    main()
