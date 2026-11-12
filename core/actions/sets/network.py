"""
core/actions/sets/network.py

Wi-Fi and Bluetooth as actions (nmcli, bluetoothctl). Linux only: on Windows SAINT's existing tools do this.
"""

from __future__ import annotations

from .. import proc
from ..registry import RISKY, Action, ActionError, ActionResult, P

LINUX = ("linux",)
_SSID = r"[^\x00-\x1f]{1,32}"


def _on_off(on: bool) -> str:
    return "on" if on else "off"


def _wifi_on() -> bool:
    return proc.try_run(["nmcli", "-t", "radio", "wifi"]).strip() == "enabled"


def _wifi(p):
    before = _wifi_on()
    proc.run(["nmcli", "radio", "wifi", _on_off(p["on"])])
    return ActionResult(True, f"Wi-Fi is {_on_off(p['on'])}.", undo={"on": before})


def _undo_wifi(t):
    proc.run(["nmcli", "radio", "wifi", _on_off(t["on"])])
    return f"Wi-Fi is {_on_off(t['on'])} again."


def _active_wifi() -> str:
    for line in proc.try_run(["nmcli", "-t", "-f", "ACTIVE,SSID", "device", "wifi"]).splitlines():
        if line.startswith("yes:"):
            return line[4:]
    return ""


def _connect(p):
    before = _active_wifi()
    argv = ["nmcli", "device", "wifi", "connect", p["ssid"]]
    if p.get("password"):
        argv += ["password", p["password"]]
    proc.run(argv, timeout=45)
    return ActionResult(True, f"Connected to {p['ssid']}.", undo={"ssid": before} if before else None)


def _undo_connect(t):
    proc.run(["nmcli", "connection", "up", "id", t["ssid"]], timeout=45)
    return f"Back on {t['ssid']}."


def _bt_on() -> bool:
    return "Powered: yes" in proc.try_run(["bluetoothctl", "show"])


def _bluetooth(p):
    before = _bt_on()
    out = proc.run(["bluetoothctl", "power", _on_off(p["on"])])
    if "succeeded" not in out and "Changing power" not in out:
        raise ActionError("Bluetooth didn't change. Is there a Bluetooth adapter?", "FAILED")
    return ActionResult(True, f"Bluetooth is {_on_off(p['on'])}.", undo={"on": before})


def _undo_bluetooth(t):
    proc.run(["bluetoothctl", "power", _on_off(t["on"])])
    return f"Bluetooth is {_on_off(t['on'])} again."


def register(registry):
    for a in [
        Action("network.wifi.power", "Turn Wi-Fi on or off", _wifi, {"on": P("boolean")}, undo=_undo_wifi,
               platforms=LINUX, keywords="wifi wireless internet airplane",
               preview=lambda p: f"Turn Wi-Fi {_on_off(p['on'])}."),
        Action("network.wifi.connect", "Connect to a Wi-Fi network", _connect,
               {"ssid": P("string", "network name", pattern=_SSID),
                "password": P("string", required=False, secret=True)},
               risk=RISKY, undo=_undo_connect, platforms=LINUX, keywords="wifi join network hotspot",
               preview=lambda p: f"Connect to the Wi-Fi network “{p['ssid']}”."),
        Action("network.bluetooth.power", "Turn Bluetooth on or off", _bluetooth, {"on": P("boolean")},
               undo=_undo_bluetooth, platforms=LINUX, keywords="bluetooth headphones pair",
               preview=lambda p: f"Turn Bluetooth {_on_off(p['on'])}."),
    ]:
        registry.register(a, replace=True)
