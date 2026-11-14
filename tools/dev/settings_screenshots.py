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
    # Made-up downloads and sound devices: never this PC's real files or hardware.
    from core import downloads as dl, sound
    dl.snapshot = lambda **kw: [dl.Item("Blender 4.2", "Flathub", 310_000_000, 420_000_000, 8_400_000),
                                dl.Item("llama3.1:8b", "Ollama", 0, 0, state="waiting", pct=12)]
    dl.finished_items = lambda **kw: [dl.Item("holiday-photos.zip", "Browser", 52_000_000, 52_000_000, state="finished",
                                              path="/home/alex/Downloads/holiday-photos.zip"),
                                      dl.Item("Inkscape", "Flathub", 98_000_000, 98_000_000, state="finished")]

    def fake_out(name, label, default=False, kind="sink", available=True, pct=70):
        return {"kind": kind, "name": name, "label": label, "card": "", "profile": "", "available": available,
                "default": default, "percent": pct, "mute": False, "bluetooth": False, "hdmi": False, "combined": False}
    sound.outputs = lambda: [fake_out("speakers", "Speakers", True), fake_out("headset", "Bluetooth headphones", pct=45),
                             fake_out("hdmi", "Monitor (HDMI)", kind="profile", available=True)]
    sound.apps = lambda: [{"id": 1, "app": "Firefox", "media": "A video", "sink": "speakers", "percent": 80,
                           "mute": False},
                          {"id": 2, "app": "Spotify", "media": "", "sink": "headset", "percent": 60, "mute": False}]
    import ui.settings_pages.sound as sound_page
    import types
    sound_page.sys = types.SimpleNamespace(platform="linux")
    sound_page.shutil = types.SimpleNamespace(which=lambda name: "/usr/bin/" + name)
    # The Voice page's check card reads real paths and device names: a made-up one instead.
    from core import voice_check
    voice_check.status = lambda service=None: {
        "configured voice": "kokoro / af_heart", "speaking with": "Kokoro (cuda)",
        "kokoro model": "/home/alex/.local/share/saint/tts/kokoro-onnx", "runtime": "onnxruntime",
        "audio output": "Speakers", "microphone": "USB microphone",
        "speech recognition": "faster-whisper base.en (downloaded)", "last kokoro test": "passed, 2 days ago",
        "last whisper test": "never run"}
    from core.config import config
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
        config.set("appearance", {**(config.get("appearance", {}) or {}), "theme": theme})   # painted widgets' palette
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
