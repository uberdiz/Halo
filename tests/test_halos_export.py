"""Exports made on Windows or a Mac are found on a USB drive and read like a Windows disk: apps, bookmarks, Wi-Fi,
SAINT and Claude. The exporters only read the old system."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from core import drives
from core import windows_migration as wm

ROOT = Path(__file__).resolve().parents[1]
PS = ROOT / "packaging/windows-host/export_for_halos.ps1"
MAC = ROOT / "packaging/macos/export_for_halos.sh"


@pytest.fixture
def export(tmp_path):
    usb = tmp_path / "usb"
    out = usb / "HalOS-Export"
    me = out / "Users/sebas"
    (me / "Documents").mkdir(parents=True)
    (me / "Documents/cv.txt").write_text("cv")
    chrome = me / "AppData/Local/Google/Chrome/User Data/Default"
    chrome.mkdir(parents=True)
    (chrome / "Bookmarks").write_text(json.dumps({"roots": {"bookmark_bar": {"children": [
        {"type": "url", "name": "HalOS", "url": "https://github.com/uberdiz/Halo"}]}}}))
    (out / "apps.json").write_text(json.dumps([{"name": "Antigravity IDE (User)", "publisher": "Google"},
                                               {"name": "Discord", "publisher": "Discord Inc."}]), encoding="utf-8-sig")
    (out / "wifi").mkdir()
    (out / "wifi/Wi-Fi-Home.xml").write_text(
        "<WLANProfile><name>Home</name><MSM><security><authEncryption><authentication>WPA2PSK</authentication>"
        "</authEncryption><sharedKey><keyMaterial>hunter2hunter2</keyMaterial></sharedKey></security></MSM></WLANProfile>")
    (out / "wifi/Wi-Fi-Cafe.xml").write_text(
        "<WLANProfile><name>Cafe</name><MSM><security><authEncryption><authentication>open</authentication>"
        "</authEncryption></security></MSM></WLANProfile>")
    (out / "HALOS-EXPORT.json").write_text(json.dumps({"version": 1, "user": "sebas", "computer": "DESKTOP-1"}),
                                           encoding="utf-8-sig")
    return usb, out


def test_an_export_on_a_usb_drive_is_found_as_a_source(export):
    usb, out = export
    found = wm.find_exports([drives.Volume(device="/dev/sdb1", mountpoint=str(usb), fstype="exfat")])
    assert len(found) == 1 and found[0].name == "Export from DESKTOP-1" and found[0].users == ["sebas"]
    assert wm.probe_export(usb) is None                                     # only the HalOS-Export folder itself


def test_apps_bookmarks_and_profile_read_like_a_windows_disk(export):
    _usb, out = export
    src = wm.probe_export(out)
    assert wm.collect_app_names(src) == ["Antigravity IDE (User)", "Discord"]
    profile = wm.profile_dir(src, "sebas")
    assert [m.url for m in wm.read_bookmarks(profile)["marks"]] == ["https://github.com/uberdiz/Halo"]


def test_wifi_from_an_export_is_saved_with_nmcli(export):
    _usb, out = export
    src = wm.probe_export(out)
    profiles = {p["ssid"]: p for p in wm.wifi_profiles(src)}
    assert profiles["Home"]["key"] == "hunter2hunter2" and profiles["Cafe"]["key"] == ""
    calls = []

    def run(argv, **kw):
        calls.append(argv)
        out_ = "Cafe\n" if argv[:3] == ["nmcli", "-t", "-f"] else ""
        return type("R", (), {"returncode": 0, "stdout": out_, "stderr": ""})()
    r = wm.import_wifi(src, run=run)
    assert r == {"found": 2, "added": 1, "with_passwords": 1, "errors": []}           # Cafe was already saved
    add = calls[-1]
    assert add[:9] == ["nmcli", "connection", "add", "type", "wifi", "con-name", "Home", "ssid", "Home"]
    assert add[-2:] == ["wifi-sec.psk", "hunter2hunter2"]


def test_a_secured_network_without_its_password_asks_later():
    cmd = wm.wifi_commands([{"ssid": "Office", "key": "", "auth": "WPA2PSK"}])[0]
    assert cmd[-2:] == ["wifi-sec.psk-flags", "2"] and "wifi-sec.psk" not in cmd


@pytest.mark.parametrize("script", [PS, MAC])
def test_exporters_only_read_the_old_system(script):
    text = script.read_text(encoding="utf-8")
    for verb in ("Remove-Item", "Move-Item", "rm -", "mv ", "Set-ItemProperty", "reg delete", "diskpart", "Format-"):
        assert verb not in text, verb
    assert "HALOS-EXPORT.json" in text and "apps.json" in text
    assert "credentials.json" in text                                       # Claude sign-in tokens are left out


def test_windows_exporter_wifi_passwords_only_on_request():
    text = PS.read_text(encoding="utf-8")
    assert 'if ($WifiPasswords) { netsh wlan export profile folder="$wifi" key=clear' in text


@pytest.mark.skipif(os.name != "nt", reason="needs Windows PowerShell")
def test_windows_exporter_whatif_writes_nothing(tmp_path):
    res = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PS),
                          "-Destination", str(tmp_path), "-NoFiles", "-WhatIf"], capture_output=True, text=True,
                         timeout=180)
    assert res.returncode == 0, res.stderr
    assert "WhatIf: nothing was written." in res.stdout
    assert not (tmp_path / "HalOS-Export").exists()


@pytest.mark.skipif(not shutil.which("bash"), reason="needs bash")
def test_mac_exporter_syntax():
    assert subprocess.run([shutil.which("bash"), "-n", MAC.as_posix()], capture_output=True).returncode == 0
