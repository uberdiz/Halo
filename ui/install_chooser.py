"""
ui/install_chooser.py

What "Install HalOS" opens in the live session: choose the free space (the safe path), or Calamares's own pages.
Writes nothing itself. core/install_target.py re-checks the choice as root and starts Calamares, which asks once
more before anything is written. Run with: python -m ui.install_chooser
"""

import subprocess
import sys
from pathlib import Path

from PySide6.QtWidgets import (QApplication, QButtonGroup, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QRadioButton, QVBoxLayout)

from core import install_target as target

SECURE_BOOT_NOTE = ("Secure Boot can stay on: HalOS uses the key you already approved for this live system. The password "
                    "at login is the one you set in the installer.")
HALOLIVE_WARNING = ("Calamares's own pages list every EFI partition. Never choose HALOLIVE (the live files) as the EFI "
                    "partition, and don't erase or shrink anything you still need. Continue?")


def failure_reason(returncode: int, stderr: str) -> str:
    """'' when the installer finished; else the plain reason core/install_target.py printed, or a general one."""
    if returncode == 0:
        return ""
    lines = [ln.split("halos-install:", 1)[1].strip() for ln in stderr.splitlines() if "halos-install:" in ln]
    return lines[-1] if lines else ("The installer stopped before it finished, and didn't say why. Nothing more was "
                                    "written after that. Try again; if it stops again, copy the log and report it.")


def install_log_text(reason: str, log: Path = target.INSTALL_LOG) -> str:
    """What Copy log puts on the clipboard: the reason, then the installer's own log when there is one."""
    try:
        body = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        body = "(the installer left no log)"
    return f"HalOS install failed: {reason}\n\n{body}"


def start_argv(c=None) -> list:
    """Root re-validates this against the disk: these three values select an offer, they aren't trusted."""
    script = str(Path(target.__file__).resolve())
    args = ["start", c.disk, str(c.start), str(c.end)] if c is not None else ["standard"]
    return ["sudo", "-E", "/usr/bin/python3", "-I", script, *args]


def describe(c: target.Candidate) -> str:
    where = f"{c.disk}{' (' + c.model + ')' if c.model else ''}"
    if c.reuse:
        return (f"{where}: the {c.size / 1e9:.0f} GB left by an earlier HalOS install that didn't finish. "
                "Those two HalOS partitions are erased and used again.")
    return (f"{where}: {c.size / 1e9:.0f} GB of free space. Adds a 512 MB EFI partition for HalOS and a "
            f"{(c.size - target.ESP_SIZE) / 1e9:.0f} GB HalOS partition.")


class Chooser(QDialog):
    def __init__(self, offers):
        super().__init__()
        self.offers = offers
        self.setWindowTitle("Install HalOS")
        self.setMinimumWidth(620)
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        intro = QLabel("HalOS goes in free space, next to what you have. Existing partitions, Windows and its EFI "
                       "partition aren't touched, and HalOS gets its own EFI partition, so removing the live files "
                       "later or a Windows update can't break it. Windows stays the default when the PC starts: pick "
                       "HalOS in the PC's boot menu (F12 on most PCs) or use Restart into HalOS in Windows."
                       if offers else
                       "No free space of 30 GB or more was found on an internal GPT disk. Free some in Windows (Disk "
                       "Management, Shrink Volume), or use the installer's own pages.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.group = QButtonGroup(self)
        for i, c in enumerate(offers):
            where, _, what = describe(c).partition(": ")      # a radio button can't wrap: the details get a label
            r = QRadioButton(where)
            r.setChecked(i == 0)
            self.group.addButton(r, i)
            lay.addWidget(r)
            details = QLabel(what)
            details.setWordWrap(True)
            lay.addWidget(details)
            if c.existing:
                kept = QLabel("Stays as it is: " + "; ".join(c.existing))
                kept.setWordWrap(True)
                kept.setObjectName("Faint")
                lay.addWidget(kept)
        if offers:
            note = QLabel(SECURE_BOOT_NOTE)
            note.setWordWrap(True)
            note.setObjectName("Muted")
            lay.addWidget(note)
        row = QHBoxLayout()
        advanced = QPushButton("Other options…")
        advanced.clicked.connect(self.standard)
        row.addWidget(advanced)
        row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        if offers:
            go = QPushButton("Continue to the installer")
            go.setObjectName("Primary")
            go.setDefault(True)
            go.clicked.connect(self.free_space)
            row.addWidget(go)
        lay.addLayout(row)

    def free_space(self):
        self._launch(start_argv(self.offers[self.group.checkedId()]))

    def standard(self):
        if QMessageBox.warning(self, "Install HalOS", HALOLIVE_WARNING, QMessageBox.Yes | QMessageBox.No,
                               QMessageBox.No) == QMessageBox.Yes:
            self._launch(start_argv())

    def _launch(self, argv, run=subprocess.run, ask=None):
        """Run the installer. A failure shows the plain reason with Retry and Copy log; Retry runs it again."""
        ask = ask or self._failed
        self.hide()
        while True:
            res = run(argv, stderr=subprocess.PIPE, text=True)
            reason = failure_reason(res.returncode, res.stderr or "")
            if not reason:
                self.accept()
                return
            if ask(reason) != "retry":
                self.show()
                return

    def _failed(self, reason: str) -> str:
        """The failure dialog: "retry" or "close". Copy log keeps the dialog open."""
        while True:
            box = QMessageBox(QMessageBox.Critical, "Install HalOS", "The install didn't finish.", parent=self)
            box.setInformativeText(reason)
            retry = box.addButton("Retry", QMessageBox.AcceptRole)
            copy = box.addButton("Copy log", QMessageBox.ActionRole)
            box.addButton("Close", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is copy:
                QApplication.clipboard().setText(install_log_text(reason))
                continue
            return "retry" if box.clickedButton() is retry else "close"


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setDesktopFileName("install-halo")           # Wayland takes the window's icon from this launcher
    try:
        from ui.theme import build_stylesheet
        app.setStyleSheet(build_stylesheet("Dark", "#feaa34", "Noto Sans"))
    except Exception as e:                 # the plain style still works
        print(f"install chooser: theme not loaded: {e}", file=sys.stderr)
    Chooser(target.candidates()).exec()
    return 0


if __name__ == "__main__":
    sys.exit(main())
