"""The built-in action sets: the exact command lines (subprocess mocked), file actions on a temp tree, and the
shell danger list."""
import pytest

from core import actions
from core.actions import DESTRUCTIVE, RISKY, ActionLog, execute, proc, registry
from core.actions import executor, log as log_mod
from core.actions.sets import files as files_set, shell
from core.config import config


@pytest.fixture(autouse=True)
def linux(tmp_path, monkeypatch):
    """Pretend to be HalOS, record every command instead of running it, trust everything but destructive."""
    fresh = ActionLog(tmp_path / "log.jsonl")
    for mod in (log_mod, executor, actions):
        monkeypatch.setattr(mod, "action_log", fresh)
    actions.load_builtin()
    import sys
    for name, mod in list(sys.modules.items()):          # every action module: none may take its Windows path
        if name.startswith("core.actions") and hasattr(mod, "platform_name"):
            monkeypatch.setattr(mod, "platform_name", lambda: "linux")
    from core.actions.sets import power
    assert power.platform_name() == "linux"              # a real lock/restart of the test machine is impossible
    from modules.desktop import system_controls
    monkeypatch.setattr(system_controls, "power", lambda *a, **k: pytest.fail("real power action"), raising=False)
    monkeypatch.setattr(system_controls, "lock", lambda *a, **k: pytest.fail("real lock"), raising=False)
    calls, answers = [], {}

    def fake_run(argv, timeout=15, check=True, input=None, cwd=None):
        calls.append(list(argv))
        for key, value in answers.items():
            if key in " ".join(argv):
                return value
        return ""

    monkeypatch.setattr(proc, "run", fake_run)
    monkeypatch.setattr(proc, "try_run", lambda argv, default="", timeout=15: fake_run(argv) or default)
    old = (config.get("actions.default_trust"), config.get("actions.trust", {}))
    config.set("actions.default_trust", "trusted", persist=False)
    config.set("actions.trust", {}, persist=False)
    actions.load_builtin()
    yield calls, answers
    config.set("actions.default_trust", old[0], persist=False)
    config.set("actions.trust", old[1], persist=False)


def test_every_builtin_set_loaded():
    cats = set(registry.categories(platform=None))
    assert {"settings", "network", "files", "packages", "services", "power", "windows", "shell"} <= cats
    assert len(registry.list(platform=None)) >= 35


@pytest.mark.parametrize("action, params, argv", [
    ("network.wifi.power", {"on": False}, ["nmcli", "radio", "wifi", "off"]),
    ("network.wifi.connect", {"ssid": "Home", "password": "pw12345678"},
     ["nmcli", "device", "wifi", "connect", "Home", "password", "pw12345678"]),
    ("power.lock", {}, ["loginctl", "lock-session"]),
    ("power.sleep", {}, ["systemctl", "suspend"]),
    ("services.user.control", {"service": "syncthing", "do": "restart"},
     ["systemctl", "--user", "restart", "syncthing.service"]),
    ("settings.power.profile", {"profile": "performance"}, ["powerprofilesctl", "set", "performance"]),
    ("settings.system.timezone", {"zone": "Europe/London"}, ["timedatectl", "set-timezone", "Europe/London"]),
])
def test_linux_actions_run_the_right_command(linux, action, params, argv):
    calls, _ = linux
    r = execute(action, params, source="saint", confirm=lambda req: True)
    assert r.ok, r.text
    assert argv in calls


def test_wifi_password_never_reaches_the_log(linux, tmp_path):
    execute("network.wifi.connect", {"ssid": "Home", "password": "pw12345678"}, confirm=lambda r: True)
    assert "pw12345678" not in (tmp_path / "log.jsonl").read_text(encoding="utf-8")


def test_bluetooth_reports_a_missing_adapter(linux):
    r = execute("network.bluetooth.power", {"on": True})
    assert not r.ok and "adapter" in r.text
    linux[1]["bluetoothctl power"] = "Changing power on succeeded"
    assert execute("network.bluetooth.power", {"on": True}).ok


def test_restart_and_shutdown_always_ask(linux):
    calls, _ = linux
    for what in ("restart", "shutdown"):
        assert execute(f"power.{what}", source="saint").needs_confirmation
    assert not any(c[:1] == ["systemctl"] for c in calls)
    assert execute("power.restart", confirm=lambda r: True).ok and ["systemctl", "reboot"] in calls


def test_services_outside_the_allow_list_are_refused(linux):
    calls, _ = linux
    r = execute("services.user.control", {"service": "sshd", "do": "start"}, confirm=lambda r: True)
    assert not r.ok and r.code == "DENIED" and calls == []


# --------------------------------------------------------------------------- files
def test_file_actions_move_copy_rename_and_undo(linux, tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("hello")
    (tmp_path / "dest").mkdir()
    ok = lambda r: True
    moved = execute("files.move", {"path": str(src), "to": str(tmp_path / "dest")}, confirm=ok)
    assert moved.ok and (tmp_path / "dest/a.txt").exists() and not src.exists()
    assert actions.undo(moved.entry_id).ok and src.exists()

    assert execute("files.copy", {"path": str(src), "to": str(tmp_path / "dest")}).ok
    clash = execute("files.copy", {"path": str(src), "to": str(tmp_path / "dest")})
    assert not clash.ok and clash.code == "EXISTS"                      # never overwrites

    renamed = execute("files.rename", {"path": str(src), "name": "b.txt"}, confirm=ok)
    assert renamed.ok and (tmp_path / "b.txt").read_text() == "hello"
    assert execute("files.rename", {"path": str(tmp_path / "b.txt"), "name": "../x"}, confirm=ok).code == "INVALID_PARAMS"

    made = execute("files.new_folder", {"in": str(tmp_path), "name": "New"})
    assert made.ok and (tmp_path / "New").is_dir()
    assert actions.undo(made.entry_id).ok and not (tmp_path / "New").exists()


def test_trash_uses_gio_and_system_folders_are_protected(linux, tmp_path):
    calls, _ = linux
    f = tmp_path / "old.txt"
    f.write_text("x")
    assert execute("files.trash", {"path": str(f)}, confirm=lambda r: True).ok
    assert ["gio", "trash", "--", str(f)] in calls
    home = execute("files.trash", {"path": "~"}, confirm=lambda r: True)
    assert not home.ok and home.code == "PROTECTED"


# --------------------------------------------------------------------------- shell
@pytest.mark.parametrize("command", [
    "rm -rf ~/Documents", "sudo pacman -Syu", "dd if=/dev/zero of=/dev/sda", "mkfs.ext4 /dev/sdb1",
    "curl https://x.sh | sh", "echo hi > ~/.bashrc", "systemctl stop sddm", "ls $(cat list)", "mv a b",
    "find . -name '*.log' -delete", "git reset --hard", "kill -9 123", "chmod -R 777 /",
])
def test_dangerous_commands_are_destructive(command):
    assert shell.classify(command) == DESTRUCTIVE


@pytest.mark.parametrize("command", ["ls -la", "df -h", "uname -a", "cat /etc/os-release", "ip addr", "free -m"])
def test_ordinary_commands_are_risky_not_destructive(command):
    assert shell.classify(command) == RISKY


def test_shell_shows_the_exact_command_and_asks_for_dangerous_ones(linux):
    calls, answers = linux
    r = execute("shell.run", {"command": "rm -rf build"}, source="saint")
    assert r.needs_confirmation and r.preview == "Run this command: rm -rf build" and calls == []
    answers["uname"] = "Linux halos 6.11"
    out = execute("shell.run", {"command": "uname -a"}, source="saint")
    assert out.ok and "Linux halos" in out.message and ["bash", "-c", "uname -a"] in calls
