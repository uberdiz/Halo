"""core/recovery.py: firmware setup support, one-time boot into another system, snapshots."""

from core import recovery

EFIBOOTMGR = """BootCurrent: 0002
Timeout: 1 seconds
BootOrder: 0002,0000,0001
Boot0000* Windows Boot Manager	HD(1,GPT,...)/File(\EFI\Microsoft\Boot\bootmgfw.efi)
Boot0001  UEFI: PXE IPv4	PciRoot(0x0)
Boot0002* Halo	HD(1,GPT,...)/File(\EFI\Halo\grubx64.efi)
"""


def run_with(out, code=0):
    calls = []

    def run(argv, **kw):
        calls.append(argv)
        return type("R", (), {"stdout": out, "returncode": code})()
    run.calls = calls
    return run


def test_boot_entries_and_restart_into_windows_once():
    entries = recovery.boot_entries(run_with(EFIBOOTMGR))
    assert [(e.num, e.label, e.active, e.current) for e in entries] == [
        ("0000", "Windows Boot Manager", True, False), ("0001", "UEFI: PXE IPv4", False, False), ("0002", "Halo", True, True)]
    win = next(e for e in entries if e.is_windows)
    assert recovery.boot_once(win) == [["pkexec", "efibootmgr", "--bootnext", "0000"], ["systemctl", "reboot"]]
    bad = recovery.BootEntry("00; rm", "x", True)
    try:
        recovery.boot_once(bad)
        assert False
    except ValueError:
        pass


def test_firmware_setup_needs_uefi_support(tmp_path):
    assert not recovery.firmware_setup_supported(tmp_path)
    (tmp_path / recovery.OS_INDICATIONS_SUPPORTED).write_bytes(b"\x06\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00")
    assert recovery.firmware_setup_supported(tmp_path)
    (tmp_path / recovery.OS_INDICATIONS_SUPPORTED).write_bytes(b"\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")
    assert not recovery.firmware_setup_supported(tmp_path)
    assert recovery.REBOOT_TO_FIRMWARE == ["systemctl", "reboot", "--firmware-setup"]


def test_snapshots_newest_first_or_none():
    out = "number,date,description\n0,,current\n1,2026-10-30 10:00:00,pacman -S blender\n2,2026-10-30 11:00:00,Taken in SAINT\n"
    snaps = recovery.snapshots(run_with(out))
    assert [s.number for s in snaps] == [2, 1] and snaps[0].description == "Taken in SAINT"
    assert recovery.snapshots(run_with("", code=1)) is None
    cmd = recovery.snapshot_now("Before `rm -rf` $(x)")
    assert cmd[:4] == ["pkexec", "snapper", "-c", "root"] and "`" not in cmd[-1] and "$" not in cmd[-1]


# --------------------------------------------------------------------------- restart with what the image has
def _runner(results):
    """argv[0..1] -> (returncode, stderr); anything else succeeds. Records the calls."""
    calls = []

    def run(argv, **kw):
        calls.append(list(argv))
        code, err = results.get(" ".join(argv[:3]), results.get(argv[0], (0, "")))
        return type("R", (), {"stdout": "", "stderr": err, "returncode": code})()
    run.calls = calls
    return run


def test_restart_falls_back_until_one_way_works(monkeypatch):
    monkeypatch.setattr(recovery, "RESTART_HELPER", "/nonexistent/halo-restart")
    run = _runner({"systemctl reboot": (1, "Operation inhibited by \"Package install\"")})
    res = recovery.restart(run=run)
    assert res["ok"] and run.calls[0] == ["systemctl", "reboot"] and run.calls[-1] == ["systemctl", "reboot", "-i"]
    assert "inhibited" in res["log"]                       # Copy log has every attempt
    assert not any(c[0] in ("pacman", "paru", "pip", "curl") for c in run.calls)      # nothing is installed first


def test_restart_reports_a_plain_reason_when_nothing_works(monkeypatch):
    monkeypatch.setattr(recovery, "RESTART_HELPER", "/nonexistent/halo-restart")
    run = _runner({"systemctl": (1, "Interactive authentication required."), "busctl": (1, "Access denied")})
    res = recovery.restart(run=run)
    assert not res["ok"] and "password prompt" in res["reason"] and "systemctl reboot" in res["log"]


def test_restart_into_an_entry_stops_if_the_entry_cannot_be_set(monkeypatch):
    monkeypatch.setattr(recovery, "RESTART_HELPER", "/nonexistent/halo-restart")
    monkeypatch.setattr(recovery, "EFIBOOT_HELPER", "/nonexistent/halo-efiboot")
    entry = recovery.BootEntry("0000", "Windows Boot Manager", True, False)
    run = _runner({"pkexec": (1, "Could not prepare Boot variable: No such file or directory")})
    res = recovery.restart(entry, run=run)
    assert not res["ok"] and "Windows Boot Manager" in res["reason"]
    assert all(c[0] == "pkexec" for c in run.calls)        # the PC is not restarted into the wrong system
    ok = recovery.restart(entry, run=_runner({}))
    assert ok["ok"] and "Windows Boot Manager" in ok["reason"]


def test_boot_entries_are_read_from_the_firmware_when_efibootmgr_is_missing(tmp_path):
    guid = recovery.EFI_GLOBAL

    def var(name, payload):
        (tmp_path / f"{name}-{guid}").write_bytes(b"\x07\x00\x00\x00" + payload)

    def entry(label, active=True):
        return (1 if active else 0).to_bytes(4, "little") + (0).to_bytes(2, "little") + (label + "\0").encode("utf-16-le")
    var("BootCurrent", (2).to_bytes(2, "little"))
    var("Boot0000", entry("Windows Boot Manager"))
    var("Boot0002", entry("HalOS"))

    def missing(argv, **kw):
        raise FileNotFoundError(argv[0])
    found = recovery.boot_entries(run=missing, efivars=tmp_path)
    assert [(e.num, e.label, e.current) for e in found] == [("0000", "Windows Boot Manager", False), ("0002", "HalOS", True)]
    assert found[0].is_windows


def test_explain_never_returns_raw_tool_output():
    for raw in ("Operation inhibited", "bash: efibootmgr: command not found", "EFI variables are not supported",
                "something nobody has seen before 0x8000"):
        text = recovery.explain(raw)
        assert text and raw not in text and text[0].isupper()


def test_restart_helper_and_polkit_rule_ship_in_the_image():
    from pathlib import Path
    pkg = Path(__file__).resolve().parents[1] / "packaging/arch/pkgbuilds/halo-system"
    helper = (pkg / "halo-restart").read_text(encoding="utf-8")
    assert "systemctl" in helper and not any(w in helper for w in ("pacman", "pip ", "curl", "wget"))
    assert "halo-restart" in (pkg / "PKGBUILD").read_text(encoding="utf-8")
    assert "org.freedesktop.login1.reboot-ignore-inhibit" in (pkg / "50-halo-drives.rules").read_text(encoding="utf-8")
