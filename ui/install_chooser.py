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

SECURE_BOOT_NOTE = ("If Secure Boot is on, the first restart shows a blue MOK screen once: choose Enroll MOK, Continue, "
                    "Yes, then type the word halo. It only approves HalOS's boot key; your password is the one you "
                    "set in the installer.")
HALOLIVE_WARNING = ("Calamares's own pages list every EFI partition. Never choose HALOLIVE (the live files) as the EFI "
                    "partition, and don't erase or shrink anything you still need. Continue?")


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
                       "later or a Windows update can't break it. GRUB starts HalOS first and lists Windows."
                       if offers else
                       "No free space of 30 GB or more was found on an internal GPT disk. Free some in Windows (Disk "
                       "Management, Shrink Volume), or use the installer's own pages.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.group = QButtonGroup(self)
        for i, c in enumerate(offers):
            r = QRadioButton(describe(c))
            r.setChecked(i == 0)
            self.group.addButton(r, i)
            lay.addWidget(r)
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

    def _launch(self, argv, run=subprocess.run):
        self.hide()
        res = run(argv, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0 and res.stderr and "halos-install:" in res.stderr:
            QMessageBox.critical(self, "Install HalOS", res.stderr.strip())
            self.show()
            return
        self.accept()


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    try:
        from ui.theme import build_stylesheet
        app.setStyleSheet(build_stylesheet("Dark", "#feaa34", "Noto Sans"))
    except Exception as e:                 # the plain style still works
        print(f"install chooser: theme not loaded: {e}", file=sys.stderr)
    Chooser(target.candidates()).exec()
    return 0


if __name__ == "__main__":
    sys.exit(main())
