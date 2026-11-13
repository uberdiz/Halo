"""
ui/passwords_app.py

HalOS Passwords: search your saved logins, copy the username or password (the clipboard is wiped after 20 s and
marked x-kde-passwordManagerHint=secret so Klipper keeps no history), "Fill in" types username, Tab, password into
the window you were in (modules/desktop/controller.type_text), TOTP codes, a strength meter with weak / reused
badges, a generator, and an optional auto-lock after a few idle minutes. Passwords are revealed only on request.

Import is a repeatable merge of an Apple Passwords / Chrome / Firefox / Bitwarden CSV export (core/passwords.py).
When a password export lands in Downloads, the app offers to import it and then to delete the plain-text CSV.

    python -m ui.passwords_app [search]
"""

from __future__ import annotations

import hashlib
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QEvent, QFileSystemWatcher, QMimeData, QObject, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu,
                               QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSpinBox, QStackedWidget,
                               QToolButton, QVBoxLayout, QWidget)

from core import passwords as pw
from core.config import config

CLIPBOARD_CLEAR_MS = 20_000
FILL_DELAY_MS = 600                 # time for the previous window to get focus back after we minimise
AUTOLOCK_CHOICES = (0, 1, 5, 15, 30)
STRENGTH_COLORS = ("#e5484d", "#f76b15", "#f5a524", "#46a758", "#30a46c")
SYNC_NOTE = ("Live iCloud Keychain sync isn't possible from Linux: Apple offers no API for it. Export from the "
             "Passwords app (File > Export All Passwords) and import the CSV here again whenever you want to catch up: "
             "new logins are added, changed ones updated, and logins only kept here stay. On Windows, Apple's "
             "iCloud for Windows Passwords app is the live option.")
ID_ROLE = Qt.UserRole + 1


# --------------------------------------------------------------------------- helpers
def copy_secret(text: str, clear_ms: int = CLIPBOARD_CLEAR_MS):
    """Copy ``text`` marked as a secret (Klipper and Plasma's clipboard skip history) and wipe it after clear_ms,
    unless something else was copied in between."""
    cb = QApplication.clipboard()
    mime = QMimeData()
    mime.setText(text)
    mime.setData("x-kde-passwordManagerHint", b"secret")
    cb.setMimeData(mime)
    digest = hashlib.sha256(text.encode()).digest()

    def wipe():
        if hashlib.sha256((cb.text() or "").encode()).digest() == digest:
            cb.clear()
    QTimer.singleShot(clear_ms, wipe)


def site_icon(site: str, size: int = 36) -> QIcon:
    """A round letter badge in a colour picked from the site name. Local: no favicon fetch tells anyone your list."""
    hue = int(hashlib.md5(site.encode()).hexdigest()[:4], 16) % 360
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor.fromHsl(hue, 150, 120))
    p.drawRoundedRect(0, 0, size, size, size * 0.32, size * 0.32)
    p.setPen(QColor("#ffffff"))
    f = QFont()
    f.setPixelSize(int(size * 0.46))
    f.setBold(True)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, (site[:1] or "?").upper())
    p.end()
    icon = QIcon(pm)
    icon.addPixmap(pm, QIcon.Selected)                   # same colour on the selected row (no tint)
    return icon


class _Idle(QObject):
    """Notes the time of the last key press or click anywhere in the app (auto-lock)."""

    def __init__(self):
        super().__init__()
        self.last = time.monotonic()

    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.KeyPress, QEvent.MouseButtonPress, QEvent.Wheel):
            self.last = time.monotonic()
        return False


# --------------------------------------------------------------------------- dialogs
class GeneratorBox(QWidget):
    """Length, symbols, the password, Regenerate."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.length = QSpinBox()
        self.length.setRange(8, 64)
        self.length.setValue(20)
        self.symbols = QCheckBox("Symbols")
        self.symbols.setChecked(True)
        self.out = QLineEdit()
        self.out.setReadOnly(True)
        again = QPushButton("Regenerate")
        again.setObjectName("Ghost")
        for w in (QLabel("Length"), self.length, self.symbols, self.out, again):
            lay.addWidget(w)
        lay.setStretch(3, 1)
        self.length.valueChanged.connect(self.regenerate)
        self.symbols.toggled.connect(self.regenerate)
        again.clicked.connect(self.regenerate)
        self.regenerate()

    def regenerate(self):
        self.out.setText(pw.generate(self.length.value(), self.symbols.isChecked()))


class EntryDialog(QDialog):
    def __init__(self, entry: Optional[pw.Entry], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit login" if entry else "New login")
        self.setMinimumWidth(460)
        self.entry = entry or pw.Entry()
        form = QFormLayout(self)
        form.setSpacing(10)
        self.title = QLineEdit(self.entry.title)
        self.url = QLineEdit(self.entry.url)
        self.url.setPlaceholderText("https://example.com")
        self.user = QLineEdit(self.entry.username)
        self.pwd = QLineEdit(self.entry.password)
        self.pwd.setEchoMode(QLineEdit.Password)
        show = QToolButton()
        show.setText("Show")
        show.setCheckable(True)
        show.toggled.connect(lambda on: self.pwd.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
        gen = QToolButton()
        gen.setText("Generate")
        gen.clicked.connect(lambda: (self.pwd.setText(pw.generate()), show.setChecked(True)))
        row = QHBoxLayout()
        for w in (self.pwd, show, gen):
            row.addWidget(w)
        self.meter = StrengthMeter()
        self.pwd.textChanged.connect(self.meter.set_password)
        self.meter.set_password(self.pwd.text())
        self.otp = QLineEdit(self.entry.otpauth)
        self.otp.setPlaceholderText("otpauth://totp/... (optional)")
        self.notes = QPlainTextEdit(self.entry.notes)
        self.notes.setFixedHeight(70)
        form.addRow("Name", self.title)
        form.addRow("Website", self.url)
        form.addRow("Username", self.user)
        form.addRow("Password", row)
        form.addRow("", self.meter)
        form.addRow("One-time code", self.otp)
        form.addRow("Notes", self.notes)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def _accept(self):
        otp = self.otp.text().strip()
        if otp:
            try:
                pw.parse_otpauth(otp)
            except Exception:
                QMessageBox.warning(self, "One-time code", "That isn't an otpauth://totp/ link with a valid secret.")
                return
        if not self.pwd.text():
            QMessageBox.warning(self, "Password", "Type or generate a password first.")
            return
        e = self.entry
        e.title, e.url, e.username = self.title.text().strip(), self.url.text().strip(), self.user.text().strip()
        e.password, e.otpauth, e.notes = self.pwd.text(), otp, self.notes.toPlainText()
        self.accept()


class StrengthMeter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.bar = QProgressBar()
        self.bar.setRange(0, 4)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.label = QLabel()
        self.label.setObjectName("Muted")
        lay.addWidget(self.bar, 1)
        lay.addWidget(self.label)

    def set_password(self, text: str):
        score, label = pw.strength(text)
        self.bar.setValue(max(score, 1 if text else 0))
        self.bar.setStyleSheet(f"QProgressBar::chunk {{ background: {STRENGTH_COLORS[score]}; border-radius: 3px; }}"
                               "QProgressBar { border: none; border-radius: 3px; }")
        self.label.setText(label if text else "")


# --------------------------------------------------------------------------- main window
class PasswordsWindow(QMainWindow):
    def __init__(self, vault: Optional[pw.Vault] = None, query: str = "", downloads: Optional[Path] = None):
        super().__init__()
        self.vault = vault or pw.vault()
        self.downloads = Path(downloads) if downloads else Path.home() / "Downloads"
        self.setWindowTitle("Passwords")
        self.resize(940, 620)
        self._reused: set = set()
        self._revealed = False
        self._offer: Optional[Path] = None

        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(14)
        self.setCentralWidget(root)

        top = QHBoxLayout()
        title = QLabel("Passwords")
        title.setObjectName("PageTitle")
        self.search = QLineEdit(query)
        self.search.setPlaceholderText("Search sites and usernames")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        new = QPushButton("New")
        new.setObjectName("Primary")
        new.clicked.connect(self.new_entry)
        imp = QPushButton("Import…")
        imp.setObjectName("Ghost")
        imp.clicked.connect(self.choose_import)
        self.more = more = QToolButton()
        more.setText("⋯")
        more.setPopupMode(QToolButton.InstantPopup)
        more.setMenu(self._menu())
        for w in (title,):
            top.addWidget(w)
        top.addSpacing(12)
        top.addWidget(self.search, 1)
        for w in (new, imp, more):
            top.addWidget(w)
        outer.addLayout(top)

        self.banner = QFrame()
        self.banner.setObjectName("Banner")
        bl = QHBoxLayout(self.banner)
        self.banner_text = QLabel()
        self.banner_text.setWordWrap(True)
        b_imp = QPushButton("Import")
        b_imp.setObjectName("Primary")
        b_imp.clicked.connect(lambda: self.import_file(self._offer, offer_delete=True))
        b_no = QPushButton("Not now")
        b_no.setObjectName("Ghost")
        b_no.clicked.connect(self._dismiss_offer)
        bl.addWidget(self.banner_text, 1)
        bl.addWidget(b_imp)
        bl.addWidget(b_no)
        self.banner.hide()
        outer.addWidget(self.banner)

        self.pages = QStackedWidget()
        outer.addWidget(self.pages, 1)
        self.pages.addWidget(self._lock_page())
        self.pages.addWidget(self._main_page())

        self._idle = _Idle()
        QApplication.instance().installEventFilter(self._idle)
        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._every_second)
        self._tick.start()

        self._watch = QFileSystemWatcher(self)
        if self.downloads.is_dir():
            self._watch.addPath(str(self.downloads))
        self._watch.directoryChanged.connect(lambda _p: QTimer.singleShot(800, self.check_downloads))

        self.unlock()
        QTimer.singleShot(0, self.check_downloads)

    # ---- layout
    def _menu(self) -> QMenu:
        m = QMenu(self)
        m.addAction("Lock now", self.lock)
        m.addAction("Generate a password…", self.show_generator)
        auto = m.addMenu("Lock when idle")
        cur = int(config.get("passwords.autolock_minutes", 5) or 0)
        for n in AUTOLOCK_CHOICES:
            a = auto.addAction("Never" if n == 0 else f"After {n} min")
            a.setCheckable(True)
            a.setChecked(n == cur)
            a.triggered.connect(lambda _c=False, n=n: self._set_autolock(n))
        m.addSeparator()
        m.addAction("About sync with Apple…", lambda: QMessageBox.information(self, "Sync with Apple", SYNC_NOTE))
        return m

    def _set_autolock(self, n: int):
        config.set("passwords.autolock_minutes", n)
        self.more.setMenu(self._menu())

    def _lock_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addStretch(1)
        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(420)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(28, 28, 28, 28)
        cl.setSpacing(12)
        t = QLabel("Passwords is locked")
        t.setObjectName("SectionTitle")
        self.lock_msg = QLabel("Your logins stay in the system keyring (KWallet). Unlock to see them.")
        self.lock_msg.setObjectName("Muted")
        self.lock_msg.setWordWrap(True)
        b = QPushButton("Unlock")
        b.setObjectName("Primary")
        b.clicked.connect(self.unlock)
        for x in (t, self.lock_msg, b):
            cl.addWidget(x)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(card)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(2)
        return w

    def _main_page(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        self.list = QListWidget()
        self.list.setIconSize(QSize(36, 36))
        self.list.setSpacing(2)
        self.list.setMinimumWidth(320)
        self.list.currentItemChanged.connect(lambda *_: self.show_entry())
        self.list.itemDoubleClicked.connect(lambda *_: self.copy("password"))
        try:
            from ui.motion import smooth_scroll
            smooth_scroll(self.list)
        except Exception:
            pass
        lay.addWidget(self.list, 2)

        self.detail = QFrame()
        self.detail.setObjectName("Card")
        d = QVBoxLayout(self.detail)
        d.setContentsMargins(24, 22, 24, 22)
        d.setSpacing(10)
        head = QHBoxLayout()
        self.d_icon = QLabel()
        self.d_title = QLabel()
        self.d_title.setObjectName("SectionTitle")
        self.d_badges = QLabel()
        head.addWidget(self.d_icon)
        head.addWidget(self.d_title, 1)
        head.addWidget(self.d_badges)
        d.addLayout(head)
        self.d_site = QLabel()
        self.d_site.setObjectName("Muted")
        d.addWidget(self.d_site)

        def field(label, button_text, slot, extra=None):
            cap = QLabel(label)
            cap.setObjectName("Eyebrow")
            d.addWidget(cap)
            row = QHBoxLayout()
            val = QLabel()
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            row.addWidget(val, 1)
            if extra:
                row.addWidget(extra)
            b = QPushButton(button_text)
            b.setObjectName("Ghost")
            b.clicked.connect(slot)
            row.addWidget(b)
            d.addLayout(row)
            return val, b

        self.d_user, _ = field("USERNAME", "Copy", lambda: self.copy("username"))
        self.reveal_btn = QPushButton("Reveal")
        self.reveal_btn.setObjectName("Ghost")
        self.reveal_btn.clicked.connect(self.toggle_reveal)
        self.d_pass, _ = field("PASSWORD", "Copy", lambda: self.copy("password"), self.reveal_btn)
        self.meter = StrengthMeter()
        d.addWidget(self.meter)
        self.otp_box = QWidget()
        ol = QVBoxLayout(self.otp_box)
        ol.setContentsMargins(0, 0, 0, 0)
        cap = QLabel("ONE-TIME CODE")
        cap.setObjectName("Eyebrow")
        orow = QHBoxLayout()
        self.d_otp = QLabel()
        self.d_otp.setObjectName("Metric")
        self.d_otp_left = QLabel()
        self.d_otp_left.setObjectName("Muted")
        ob = QPushButton("Copy")
        ob.setObjectName("Ghost")
        ob.clicked.connect(lambda: self.copy("otp"))
        orow.addWidget(self.d_otp)
        orow.addWidget(self.d_otp_left, 1)
        orow.addWidget(ob)
        ol.addWidget(cap)
        ol.addLayout(orow)
        d.addWidget(self.otp_box)
        self.d_notes = QLabel()
        self.d_notes.setWordWrap(True)
        self.d_notes.setObjectName("Muted")
        d.addWidget(self.d_notes)
        d.addStretch(1)
        acts = QHBoxLayout()
        fill = QPushButton("Fill in")
        fill.setObjectName("Primary")
        fill.setToolTip("Types the username, Tab and the password into the window you were using")
        fill.clicked.connect(self.fill_in)
        edit = QPushButton("Edit")
        edit.setObjectName("Ghost")
        edit.clicked.connect(self.edit_entry)
        dele = QPushButton("Delete")
        dele.setObjectName("Danger")
        dele.clicked.connect(self.delete_entry)
        acts.addWidget(fill)
        acts.addWidget(edit)
        acts.addStretch(1)
        acts.addWidget(dele)
        d.addLayout(acts)
        self.empty = QLabel("No logins yet.\n\nImport an export from Apple Passwords, Chrome, Firefox or Bitwarden, "
                            "or add one with New.")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.setObjectName("Muted")
        self.right = QStackedWidget()
        self.right.addWidget(self.empty)
        self.right.addWidget(self.detail)
        lay.addWidget(self.right, 3)
        return w

    # ---- state
    def current(self) -> Optional[pw.Entry]:
        it = self.list.currentItem()
        return self.vault.get(it.data(ID_ROLE)) if it and not self.vault.locked else None

    def unlock(self):
        try:
            self.vault.unlock()
        except RuntimeError as e:
            self.lock_msg.setText(str(e))
            self.pages.setCurrentIndex(0)
            return
        self._idle.last = time.monotonic()
        self.pages.setCurrentIndex(1)
        self.refresh()

    def lock(self):
        self.vault.lock()
        self._revealed = False
        self.list.clear()
        self.lock_msg.setText("Locked. Your logins stay in the system keyring (KWallet).")
        self.pages.setCurrentIndex(0)

    def refresh(self):
        if self.vault.locked:
            return
        keep = self.list.currentItem().data(ID_ROLE) if self.list.currentItem() else None
        self._reused = pw.reused(self.vault.entries)
        self.list.clear()
        for e in self.vault.find(self.search.text()):
            badges = []
            if pw.strength(e.password)[0] <= 1:
                badges.append("weak")
            if e.id in self._reused:
                badges.append("reused")
            text = f"{e.title or e.site}\n{e.username or '(no username)'}"
            if badges:
                text += "   · " + " · ".join(badges)
            it = QListWidgetItem(site_icon(e.site), text)
            it.setData(ID_ROLE, e.id)
            it.setSizeHint(QSize(0, 52))
            self.list.addItem(it)
            if e.id == keep:
                self.list.setCurrentItem(it)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self.show_entry()

    def show_entry(self):
        e = self.current()
        self.right.setCurrentIndex(1 if e else 0)
        if not e:
            return
        self._revealed = False
        self.d_icon.setPixmap(site_icon(e.site, 44).pixmap(44, 44))
        self.d_title.setText(e.title or e.site)
        self.d_site.setText(e.url or e.site)
        badges = [("Weak", "ChipWarn")] if pw.strength(e.password)[0] <= 1 else []
        if e.id in self._reused:
            badges.append(("Reused", "ChipErr"))
        self.d_badges.setText("  ".join(b for b, _ in badges))
        self.d_badges.setObjectName(badges[0][1] if badges else "Chip")
        self.d_badges.setVisible(bool(badges))
        self.d_badges.style().polish(self.d_badges)
        self.d_user.setText(e.username or "(none)")
        self._show_password(e)
        self.meter.set_password(e.password)
        self.otp_box.setVisible(bool(e.otpauth))
        self._update_otp(e)
        self.d_notes.setText(e.notes)

    def _show_password(self, e):
        self.d_pass.setText(e.password if self._revealed else "•" * min(len(e.password), 16))
        self.reveal_btn.setText("Hide" if self._revealed else "Reveal")

    def toggle_reveal(self):
        e = self.current()
        if e:
            self._revealed = not self._revealed
            self._show_password(e)

    def _update_otp(self, e=None):
        e = e or self.current()
        if not e or not e.otpauth:
            return
        try:
            code, left = pw.totp_from_uri(e.otpauth)
            self.d_otp.setText(f"{code[:len(code) // 2]} {code[len(code) // 2:]}")
            self.d_otp_left.setText(f"  {left} s")
        except Exception:
            self.d_otp.setText("—")
            self.d_otp_left.setText("  this code link can't be read")

    def _every_second(self):
        if self.vault.locked:
            return
        mins = int(config.get("passwords.autolock_minutes", 5) or 0)
        if mins and time.monotonic() - self._idle.last > mins * 60:
            self.lock()
            return
        if self.otp_box.isVisible():
            self._update_otp()

    # ---- actions
    def copy(self, what: str):
        e = self.current()
        if not e:
            return
        if what == "username":
            QApplication.clipboard().setText(e.username)
            self.statusBar().showMessage("Username copied.", 3000)
            return
        if what == "otp":
            text = pw.totp_from_uri(e.otpauth)[0]
        else:
            text = e.password
        copy_secret(text)
        self.statusBar().showMessage(f"Copied. The clipboard is cleared in {CLIPBOARD_CLEAR_MS // 1000} s.", 5000)

    def fill_in(self):
        e = self.current()
        if not e:
            return
        text = f"{e.username}\t{e.password}" if e.username else e.password
        self.showMinimized()                      # focus goes back to the window you came from

        def type_it():
            try:
                from modules.desktop.controller import desktop
                desktop.type_text(text)
            except Exception as err:              # never log the text; the reason only
                QTimer.singleShot(0, self, lambda: self._fill_failed(str(err) or type(err).__name__))

        QTimer.singleShot(FILL_DELAY_MS, lambda: threading.Thread(target=type_it, daemon=True).start())

    def _fill_failed(self, reason: str):
        self.showNormal()
        QMessageBox.warning(self, "Fill in", f"Couldn't type the login: {reason}")

    def new_entry(self):
        if self.vault.locked:
            return
        dlg = EntryDialog(None, self)
        if dlg.exec():
            self._save(lambda: self.vault.upsert(dlg.entry))
            self._select(dlg.entry.id)

    def edit_entry(self):
        e = self.current()
        if not e:
            return
        copy = pw.Entry(**{k: getattr(e, k) for k in pw.Entry.__dataclass_fields__})
        dlg = EntryDialog(copy, self)
        if dlg.exec():
            self._save(lambda: self.vault.upsert(dlg.entry))

    def delete_entry(self):
        e = self.current()
        if e and QMessageBox.question(self, "Delete login", f"Delete the login for {e.username or e.site} "
                                      f"on {e.site}? This can't be undone.") == QMessageBox.Yes:
            self._save(lambda: self.vault.delete(e.id))

    def _save(self, fn):
        try:
            fn()
        except RuntimeError as err:
            QMessageBox.warning(self, "Passwords", str(err))
        self.refresh()

    def _select(self, entry_id):
        for i in range(self.list.count()):
            if self.list.item(i).data(ID_ROLE) == entry_id:
                self.list.setCurrentRow(i)

    def show_generator(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Generate a password")
        lay = QVBoxLayout(dlg)
        box = GeneratorBox()
        meter = StrengthMeter()
        box.out.textChanged.connect(meter.set_password)
        meter.set_password(box.out.text())
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        copy = bb.addButton("Copy", QDialogButtonBox.ActionRole)
        copy.clicked.connect(lambda: (copy_secret(box.out.text()), dlg.accept()))
        bb.rejected.connect(dlg.reject)
        for w in (box, meter, bb):
            lay.addWidget(w)
        dlg.exec()

    # ---- import
    def choose_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import passwords (CSV export)", str(self.downloads),
                                              "CSV exports (*.csv)")
        if path:
            self.import_file(Path(path), offer_delete=True)

    def import_file(self, path: Optional[Path], offer_delete: bool = False):
        if not path:
            return
        self.banner.hide()
        self._mark_seen(path)
        if self.vault.locked:
            self.unlock()
        try:
            c = self.vault.import_csv(path)
        except (ValueError, RuntimeError, OSError) as err:
            QMessageBox.warning(self, "Import", f"Couldn't import {path.name}: {err}")
            return
        self.refresh()
        msg = (f"{c['added']} added, {c['updated']} updated, {c['unchanged']} unchanged, "
               f"{c['kept']} kept that were only here.")
        if not offer_delete:
            QMessageBox.information(self, "Imported", msg)
            return
        box = QMessageBox(QMessageBox.Question, "Imported", msg + f"\n\n{path.name} holds your passwords in plain "
                          "text. Delete it now?", QMessageBox.NoButton, self)
        delete = box.addButton("Delete the CSV", QMessageBox.DestructiveRole)
        box.addButton("Keep it", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is delete:
            try:
                path.unlink()
                self.statusBar().showMessage(f"Deleted {path.name}.", 4000)
            except OSError as err:
                QMessageBox.warning(self, "Delete", f"Couldn't delete {path.name}: {err}")

    def check_downloads(self):
        seen = config.get("passwords.seen_exports", []) or []
        found = pw.pending_exports(self.downloads, seen)
        self._offer = found[0] if found else None
        if self._offer:
            self.banner_text.setText(f"<b>{self._offer.name}</b> in Downloads looks like a password export. "
                                     "Import it? New and changed logins are merged in.")
            self.banner.show()

    def _mark_seen(self, path: Path):
        seen = list(config.get("passwords.seen_exports", []) or [])
        seen = (seen + [pw.export_id(path)])[-50:]
        config.set("passwords.seen_exports", seen)

    def _dismiss_offer(self):
        if self._offer:
            self._mark_seen(self._offer)
        self.banner.hide()
        self.check_downloads()

    def handle_command(self, cmd: str):
        """From a second `halos-passwords [search]`: come to the front with that search."""
        from core import instance
        if cmd.startswith("token:"):
            instance.use_activation_token(cmd[6:])
            return
        if cmd.startswith("open:"):
            self.search.setText(cmd[5:])
        self.showNormal()
        self.raise_()
        self.activateWindow()


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    from core import instance
    token = instance.activation_token()
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("Passwords")
    app.setDesktopFileName("halos-passwords")
    if QIcon.themeName() in ("", "hicolor") and os.path.isdir("/usr/share/icons/HalOS"):
        QIcon.setThemeName("HalOS")
    app.setWindowIcon(QIcon.fromTheme("halos-passwords"))
    try:
        from ui import theme
        a = config.get("appearance", {}) or {}
        app.setPalette(theme.qt_palette(theme.current_palette()))
        app.setStyleSheet(theme.build_stylesheet(a.get("theme", "Dark"), a.get("accent", "#feaa34"),
                                                 a.get("font_family", "Noto Sans" if os.name != "nt" else "Segoe UI"),
                                                 a.get("font_size", 13)))
    except Exception:
        pass
    query = " ".join(a for a in argv if not a.startswith("--"))
    if token:
        instance.send(f"token:{token}", 800, name="passwords")
    if instance.send(f"open:{query}" if query else "show", 800, name="passwords"):
        return 0
    w = PasswordsWindow(query=query)
    server = instance.Server(app, name="passwords")
    server.command.connect(w.handle_command)
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
