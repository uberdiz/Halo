"""Plain phrases -> OS actions, through the registry (trust, confirmation and undo apply), with no model call."""
import sys

import pytest

from core import actions
from core.actions import ActionLog, executor, log as log_mod, proc
from core.config import config
from modules.agent import os_intents
from modules.agent.confirm import confirmations


@pytest.fixture
def halos(tmp_path, monkeypatch):
    """Pretend to be HalOS with every command recorded instead of run."""
    fresh = ActionLog(tmp_path / "log.jsonl")
    for mod in (log_mod, executor, actions):
        monkeypatch.setattr(mod, "action_log", fresh)
    actions.load_builtin()
    for name, mod in list(sys.modules.items()):
        if name.startswith("core.actions") and hasattr(mod, "platform_name"):
            monkeypatch.setattr(mod, "platform_name", lambda: "linux")
    calls = []

    def fake_run(argv, timeout=15, check=True, input=None, cwd=None):
        calls.append(list(argv))
        return "Changing power off succeeded" if argv[0] == "bluetoothctl" else ""
    monkeypatch.setattr(proc, "run", fake_run)
    monkeypatch.setattr(proc, "try_run", lambda argv, default="", timeout=15: fake_run(argv) or default)
    old = (config.get("actions.default_trust"), config.get("actions.trust", {}))
    config.set("actions.default_trust", "ask_risky", persist=False)
    config.set("actions.trust", {}, persist=False)
    confirmations._pending = None
    yield calls
    confirmations._pending = None
    config.set("actions.default_trust", old[0], persist=False)
    config.set("actions.trust", old[1], persist=False)


@pytest.mark.parametrize("text, name", [
    ("SAINT, dark mode", "os.settings.appearance.theme"),
    ("switch to the light theme", "os.settings.appearance.theme"),
    ("make the text bigger", "os.settings.appearance.text_size"),
    ("turn night light on", "os.settings.display.night_light"),
    ("turn off do not disturb", "os.settings.notifications.dnd"),
    ("turn bluetooth off", "os.network.bluetooth.power"),
    ("turn off the wifi", "os.network.wifi.power"),
    ("set the display scale to 125%", "os.settings.display.scale"),
    ("set the power mode to performance", "os.settings.power.profile"),
    ("run the command df -h", "os.shell.run"),
    ("run `uname -a`", "os.shell.run"),
    ("run ls -la in the terminal", "os.shell.run"),
    ("undo that", "os.undo"),
])
def test_phrases_map_to_actions(halos, text, name):
    intent = os_intents.parse_os(text)
    assert intent is not None and intent.name == name


@pytest.mark.parametrize("text", ["play dark mode by somebody", "run", "what is bluetooth", "open the terminal",
                                  "make the text", "run steam", "undo"])
def test_other_phrases_are_left_alone(halos, text):
    assert os_intents.parse_os(text) is None


def test_safe_action_runs_at_once_and_can_be_undone(halos):
    reply = os_intents.parse_os("turn bluetooth off").run()
    assert reply.ok and "Bluetooth is off" in reply.text and ["bluetoothctl", "power", "off"] in halos
    undone = os_intents.parse_os("undo that").run()
    assert undone.ok and halos[-1][:2] == ["bluetoothctl", "power"]


def test_a_command_is_shown_exactly_and_waits_for_a_yes(halos):
    reply = os_intents.parse_os("run the command rm -rf ~/Old Stuff").run()
    assert reply.expects_reply and "rm -rf ~/Old Stuff" in reply.text          # capitals and all, before anything runs
    assert not any(c[0] == "bash" for c in halos)
    pending = confirmations._pending
    assert pending is not None
    pending.run()
    assert ["bash", "-c", "rm -rf ~/Old Stuff"] in halos


def test_the_router_reaches_it_before_open_app(halos):
    from modules.agent import router
    order = router._SINGLE_PARSERS
    assert order.index(router.parse_os) < order.index(router.parse_desktop)
    intent = router.route_single("run the command df -h")
    assert intent is not None and intent.name == "os.shell.run"


def test_on_windows_linux_only_phrases_are_not_claimed(monkeypatch):
    actions.load_builtin()
    for name, mod in list(sys.modules.items()):
        if name.startswith("core.actions") and hasattr(mod, "platform_name"):
            monkeypatch.setattr(mod, "platform_name", lambda: "windows")
    assert os_intents.parse_os("dark mode") is None and os_intents.parse_os("turn bluetooth off") is None
