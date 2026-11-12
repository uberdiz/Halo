"""
ui/components/drives_panel.py

Every partition with Open / Mount / Unmount, and "Restart into Windows". Shared by the Storage page and the
"Drives & OS" settings page; the work is in core/drives.py and core/os_switch.py.
"""

from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout

from core import drives, os_switch
from ui.widgets import Card, clear_layout, run_async


def _gb(n) -> str:
    return f"{n / 1e9:.1f} GB"


def describe(v: drives.Volume) -> str:
    parts = [v.kind, v.fstype.upper() if v.fstype else "", _gb(v.size)]
    if v.mountpoint:
        parts.append(f"{_gb(v.used)} used, {_gb(v.free)} free")
        parts.append(f"at {v.mountpoint}" + (" (read-only)" if v.read_only else ""))
    else:
        parts.append("not mounted")
    parts.append(v.device + (f" on {v.model}" if v.model else ""))
    return " · ".join(p for p in parts if p)


class DrivesPanel(Card):
    def __init__(self):
        super().__init__("Drives and partitions")
        refresh = QPushButton("Refresh")
        refresh.setObjectName("Ghost")
        refresh.clicked.connect(self.refresh)
        self.header.addWidget(refresh)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(10)
        self.body.addLayout(self.rows)
        self.note = QLabel("")
        self.note.setWordWrap(True)
        self.note.setObjectName("Muted")
        self.note.hide()
        self.body.addWidget(self.note)

    def refresh(self):
        run_async(drives.volumes, self.show_volumes, lambda e: self.say(f"Couldn't list the drives: {e}"))

    def say(self, text: str):
        self.note.setText(text)
        self.note.setVisible(bool(text))

    def show_volumes(self, vols):
        clear_layout(self.rows)
        for v in vols:
            self.rows.addLayout(self._row(v))
        if not vols:
            self.say("No drives were found.")

    def _row(self, v: drives.Volume):
        row = QHBoxLayout()
        text = QVBoxLayout()
        text.setSpacing(1)
        name = QLabel(v.name)
        name.setStyleSheet("font-weight: 600;")
        sub = QLabel(describe(v))
        sub.setObjectName("Faint")
        sub.setWordWrap(True)
        text.addWidget(name)
        text.addWidget(sub)
        row.addLayout(text, 1)
        if v.protected:
            left = QLabel("Left alone")
            left.setObjectName("Faint")
            left.setToolTip("HalOS doesn't mount or change EFI, Recovery or live partitions.")
            row.addWidget(left)
            return row
        if v.locked:
            row.addWidget(self._button("Unlock…", lambda: self._unlock(v), primary=True))
            return row
        if v.mountpoint:
            row.addWidget(self._button("Open in Dolphin", lambda: self._open(v.mountpoint)))
            if v.is_windows:
                write = QCheckBox("Allow writing")
                write.setChecked(not v.read_only)
                write.setToolTip("Windows system drives are read-only unless you turn this on.")
                write.clicked.connect(lambda on, w=write: self._toggle_write(v, on, w))
                row.addWidget(write)
            row.addWidget(self._button("Unmount", lambda: self._unmount(v)))
        else:
            row.addWidget(self._button("Mount", lambda: self._mount(v), primary=True))
        return row

    @staticmethod
    def _button(text, slot, primary=False):
        b = QPushButton(text)
        b.setObjectName("Primary" if primary else "Ghost")
        b.clicked.connect(lambda _=False: slot())
        return b

    def _open(self, path):
        res = drives.open_in_files(path)
        self.say("" if res.ok else res.message)

    def _after(self, res: drives.Result):
        self.say(res.message)
        self.refresh()

    def _mount(self, v, write=False):
        self.say(f"Mounting {v.name}…")
        run_async(lambda: drives.mount(v, write=write), self._after, lambda e: self.say(str(e)))

    def _unmount(self, v):
        run_async(lambda: drives.unmount(v), self._after, lambda e: self.say(str(e)))

    def _toggle_write(self, v, on, box):
        if on:
            ok = QMessageBox.warning(self, "Allow writing to Windows?",
                                     f"{v.name} holds a Windows installation. Changing files here can stop that "
                                     "Windows from starting.\n\nAllow writing until you turn this off?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ok != QMessageBox.Yes:
                box.setChecked(False)
                return
            self._mount(v, write=True)
            return

        def back_to_read_only():
            res = drives.unmount(v)
            if not res.ok:
                return res
            v.mountpoint = ""
            return drives.mount(v)
        run_async(back_to_read_only, self._after, lambda e: self.say(str(e)))

    def _unlock(self, v):
        key, ok = QInputDialog.getText(self, "Unlock BitLocker", drives.BITLOCKER, QLineEdit.Password)
        if ok and key:
            run_async(lambda k=key: drives.unlock(v, k), self._after, lambda _e: self.say("The drive couldn't be unlocked."))
        del key


class OsSwitchCard(Card):
    def __init__(self):
        super().__init__("Switch operating system")
        self.rows = QVBoxLayout()
        self.rows.setSpacing(8)
        self.body.addLayout(self.rows)
        self.note = QLabel("One restart only: after that the PC goes back to its normal start order.")
        self.note.setObjectName("Faint")
        self.note.setWordWrap(True)
        self.body.addWidget(self.note)

    def refresh(self):
        available, why = os_switch.available()
        if not available:
            self.note.setText(why)
            return
        run_async(os_switch.others, self.show_entries, lambda e: self.note.setText(str(e)))

    def show_entries(self, entries):
        clear_layout(self.rows)
        for e in entries:
            b = QPushButton(f"Restart into {e.label}")
            b.setObjectName("Primary" if e.is_windows else "Ghost")
            b.clicked.connect(lambda _=False, ent=e: self.restart(ent))
            self.rows.addWidget(b)
        if not entries:
            self.note.setText("No other operating system is in this PC's boot list.")

    def restart(self, entry):
        ok = QMessageBox.question(self, f"Restart into {entry.label}?",
                                  f"The PC restarts now and starts {entry.label}, once. Save your work first: open "
                                  "apps will close.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ok != QMessageBox.Yes:
            return
        self.note.setText(f"Restarting into {entry.label}…")
        run_async(lambda: os_switch.restart_into(entry.num), lambda r: self.note.setText(r["message"]),
                  lambda e: self.note.setText(str(e)))
