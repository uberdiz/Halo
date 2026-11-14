"""Screenshots on HalOS (Plasma Wayland): Print drags a region, and SAINT's screenshot goes through Spectacle (or grim),
never Pillow/Qt grabbing, with the picture saved, copied and announced."""
import configparser
from pathlib import Path

import pytest

from core import screenshot as shot

ROOT = Path(__file__).resolve().parents[1]


class FakeRun:
    def __init__(self, write=True, rc=0):
        self.calls, self.write, self.rc = [], write, rc

    def __call__(self, argv, **kw):
        self.calls.append(list(argv))
        if argv[0] in ("spectacle", "grim") and self.write:
            Path(argv[-1]).write_bytes(b"\x89PNG fake")
        if argv[0] == "slurp":
            return type("R", (), {"returncode": 0, "stdout": "10,10 200x100\n", "stderr": ""})()
        return type("R", (), {"returncode": self.rc, "stdout": "", "stderr": ""})()


def have(*tools):
    return lambda t: f"/usr/bin/{t}" if t in tools else None


def test_print_key_lets_you_drag_an_area():
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.optionxform = str
    cfg.read(ROOT / "packaging/linux/rootfs/etc/xdg/spectaclerc", encoding="utf-8")
    assert cfg["General"]["launchAction"] == "TakeRectangularScreenshot"     # was UseLastUsedCapturemode = all screens
    assert cfg["General"]["useReleaseToCapture"] == "true"                   # letting go of the mouse takes it


@pytest.mark.parametrize("mode,flag", [("region", "-r"), ("full", "-f"), ("window", "-a"), ("screen", "-m")])
def test_spectacle_modes_save_copy_and_notify(tmp_path, mode, flag):
    run = FakeRun()
    out = tmp_path / "s.png"
    res = shot.capture(mode, out, which=have("spectacle", "wl-copy", "notify-send"), run=run)
    assert run.calls[0] == ["spectacle", "-b", "-n", flag, "-o", str(out)]
    assert res["path"] == str(out) and res["copied"]
    assert run.calls[1][:2] == ["wl-copy", "--type"] and run.calls[2][0] == "notify-send"


def test_escape_during_region_is_a_cancel_not_an_error(tmp_path):
    res = shot.capture("region", tmp_path / "s.png", which=have("spectacle"), run=FakeRun(write=False))
    assert res["cancelled"]
    with pytest.raises(shot.ScreenshotError):
        shot.capture("full", tmp_path / "s.png", which=have("spectacle"), run=FakeRun(write=False, rc=1))


def test_grim_and_slurp_elsewhere_and_a_clear_message_without_tools(tmp_path):
    run = FakeRun()
    shot.capture("region", tmp_path / "s.png", which=have("grim", "slurp"), run=run, notify=False)
    assert run.calls[0] == ["slurp"] and run.calls[1][:3] == ["grim", "-g", "10,10 200x100"]
    with pytest.raises(shot.ScreenshotError, match="Spectacle"):
        shot.capture("full", tmp_path / "s.png", which=have(), run=run)


def test_spoken_targets():
    assert [shot.mode_for(t) for t in ("", "area", "this window", "this screen", "firefox")] == [
        "full", "region", "window", "screen", ""]


def test_saint_screenshot_tool_uses_spectacle_on_linux(monkeypatch, tmp_path):
    import importlib
    registry = importlib.import_module("core.actions.registry")
    from modules.desktop import system_controls as sc
    monkeypatch.setattr(registry, "platform_name", lambda: "linux")
    seen = []
    monkeypatch.setattr(shot, "capture", lambda mode, *a, **k: seen.append(mode) or {"path": "x.png", "what": "w"})
    assert sc.screenshot("an area")["path"] == "x.png"
    assert sc.screenshot("")["what"] == "w"
    assert seen == ["region", "full"]


def test_snip_phrases_route_to_an_area_screenshot():
    from modules.agent.winctl_intents import parse_winctl
    for words in ("take a screenshot of an area", "snip", "take a snip", "grab a screenshot of the region"):
        intent = parse_winctl(words)
        assert intent is not None and intent.name == "system.screenshot", words
