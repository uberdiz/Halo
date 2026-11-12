"""An install that fails says why in plain words, and the chooser offers Retry and Copy log."""
import os

import pytest

from core import install_target as target

FAILED_LOG = """2026-11-10 - 12:00:01 [6]: Starting job "Unpacking image 1/1, file 100/9000"
2026-11-10 - 12:03:10 [1]: Installation failed: "Failed to unpack image"
    - message:  "Failed to unpack image "/run/archiso/bootmnt/arch/x86_64/airootfs.sfs""
    - details:  "unsquashfs: write error: No space left on device"
2026-11-10 - 12:03:11 [6]: Calamares will quit now.
"""


def _run(code):
    return lambda argv, **kw: type("R", (), {"returncode": code})()


def test_a_failed_job_becomes_a_plain_reason():
    f = target.calamares_failure(FAILED_LOG)
    assert f and "unpack" in f["message"].lower() and "No space left" in f["details"]
    assert "filled up" in f["reason"] and "unsquashfs" not in f["reason"]
    assert target.calamares_failure("2026-11-10 [6]: All done.") is None


@pytest.mark.parametrize("details, words", [
    ("grub-install: error: cannot find EFI directory.", "boot loader"),
    ("efibootmgr: Could not prepare Boot variable: No space left on device", "filled up"),
    ("Input/output error while reading /dev/sda3", "read or write error"),
    ("mount: /tmp/calamares-root: device or resource busy", "in use"),
    ("something entirely new", "copy the log"),
])
def test_known_failures_are_explained(details, words):
    assert words in target.explain_failure("Job failed", details)


def test_run_installer_reports_failure_and_saves_the_log(tmp_path, capsys):
    log, out = tmp_path / "session.log", tmp_path / "run/install.log"

    def run(argv, **kw):
        log.write_text(FAILED_LOG, encoding="utf-8")            # Calamares writes its log while it runs
        return type("R", (), {"returncode": 0})()
    assert target.run_installer(run=run, logs=[log], out=out) == 1
    assert "halos-install: " in capsys.readouterr().err and "No space left" in out.read_text(encoding="utf-8")


def test_run_installer_ignores_an_old_log_and_reports_a_crash(tmp_path, capsys):
    log = tmp_path / "session.log"
    log.write_text(FAILED_LOG, encoding="utf-8")                # from an earlier attempt
    assert target.run_installer(run=_run(0), logs=[log], out=tmp_path / "o.log") == 0
    assert target.run_installer(run=_run(139), logs=[log], out=tmp_path / "o.log") == 1
    assert "closed unexpectedly" in capsys.readouterr().err


def test_chooser_shows_the_reason_and_retries(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ui import install_chooser as ic

    assert ic.failure_reason(0, "") == ""
    assert ic.failure_reason(1, "warning: x\nhalos-install: The disk filled up.\n") == "The disk filled up."
    assert "didn't say why" in ic.failure_reason(1, "")
    saved = tmp_path / "install.log"
    saved.write_text("the full log", encoding="utf-8")
    text = ic.install_log_text("The disk filled up.", saved)
    assert "The disk filled up." in text and "the full log" in text
    assert "left no log" in ic.install_log_text("x", tmp_path / "missing.log")

    dialog = ic.Chooser([])
    if dialog is None:
        pytest.skip("chooser dialog class not found")
    results = iter([(1, "halos-install: The disk filled up."), (0, "")])
    runs, asked = [], []

    def run(argv, **kw):
        code, err = next(results)
        runs.append(argv)
        return type("R", (), {"returncode": code, "stderr": err})()
    dialog._launch(["halos-install"], run=run, ask=lambda reason: asked.append(reason) or "retry")
    assert len(runs) == 2 and asked == ["The disk filled up."]
