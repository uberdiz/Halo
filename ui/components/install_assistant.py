"""
ui/components/install_assistant.py

The Store's installation assistant panel (core/install_assistant.py): paste a link, a GitHub release or a
Flathub app, or choose a package file -> SAINT shows the plan (what it is, where from, checksum, risk, every
step) -> Install runs it through the Store's own queue -> SAINT checks it starts -> it lands in the history,
where it can be repaired or uninstalled. A Windows app or .deb with a Linux version in the Store offers that
version first.
"""

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
                               QVBoxLayout, QWidget)

from ui.widgets import Card, Segmented, chip, clear_layout, run_async

RISK_CHIP = {"low": "ok", "medium": "warn", "high": "err"}


class InstallAssistantPanel(QWidget):
    """``queue(result, steps, after)`` hands a job to the Store's install queue; ``install_store(result)`` installs
    a Store result the usual way (with its own confirmations)."""

    def __init__(self, queue, install_store, history=None, tab: int = 0):
        super().__init__()
        from core import install_assistant as ia
        self.ia = ia
        self.queue = queue
        self.install_store = install_store
        self.history = history or ia.History()
        self.plan = None
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)
        self.tabs = Segmented(["Install from a file or link", "Installed by SAINT"])
        self.tabs.changed.connect(self._tab)
        v.addWidget(self.tabs, 0, Qt.AlignLeft)

        # ---- install
        self.install_box = QWidget()
        iv = QVBoxLayout(self.install_box)
        iv.setContentsMargins(0, 0, 0, 0)
        iv.setSpacing(10)
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setObjectName("StoreSearch")
        self.input.setPlaceholderText("A link, a GitHub release, a Flathub app id — or choose a file "
                                      "(.pkg.tar.zst, .flatpakref, .AppImage, .deb, .exe, .msi)")
        self.input.returnPressed.connect(self.check)
        row.addWidget(self.input, 1)
        browse = QPushButton("Choose file…")
        browse.setObjectName("CatPill")
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        self.check_btn = QPushButton("Check")
        self.check_btn.setObjectName("TileAction")
        self.check_btn.clicked.connect(self.check)
        row.addWidget(self.check_btn)
        iv.addLayout(row)
        self.note = QLabel("SAINT works out what it is and shows the plan. Nothing runs until you press Install.")
        self.note.setObjectName("Faint")
        self.note.setWordWrap(True)
        iv.addWidget(self.note)
        self.plan_card = Card("Plan")
        self.plan_card.hide()
        iv.addWidget(self.plan_card)
        v.addWidget(self.install_box)

        # ---- history
        self.history_box = QWidget()
        self.history_list = QVBoxLayout(self.history_box)
        self.history_list.setContentsMargins(0, 0, 0, 0)
        self.history_list.setSpacing(8)
        v.addWidget(self.history_box)
        v.addStretch()
        self.tabs.set_index(tab)
        self._tab(tab)

    def _tab(self, i):
        self.install_box.setVisible(i == 0)
        self.history_box.setVisible(i == 1)
        if i == 1:
            self.show_history()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose a package or installer", "",
                                              "Apps (*.pkg.tar.zst *.pkg.tar.xz *.flatpakref *.AppImage *.appimage "
                                              "*.deb *.exe *.msi);;All files (*)")
        if path:
            self.input.setText(path)
            self.check()

    # ------------------------------------------------------------------ plan
    def check(self):
        text = self.input.text().strip()
        if not text:
            self.note.setText("Paste a link or choose a file first.")
            return
        self.check_btn.setEnabled(False)
        self.note.setText("Checking what this is…")
        self.plan_card.hide()

        def done(plan):
            self.check_btn.setEnabled(True)
            self.show_plan(plan)

        def failed(e):
            self.check_btn.setEnabled(True)
            self.note.setText(str(e))
        run_async(lambda: self.ia.plan_for(text), done, failed)

    def show_plan(self, plan):
        self.plan = plan
        self.note.setText("")
        card = self.plan_card
        while card.body.count() > 1:                  # keep the header row
            item = card.body.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                clear_layout(item.layout())
        card.title_label.setText(plan.name.upper())
        head = QHBoxLayout()
        head.addWidget(chip(self.ia.KIND_LABEL[plan.kind], "accent"))
        head.addWidget(chip(f"Risk: {plan.risk}", RISK_CHIP[plan.risk]))
        head.addStretch()
        card.body.addLayout(head)
        for label, value in (("From", plan.target.origin or "?"), ("Checksum", plan.checksum)):
            lbl = QLabel(f"<b>{label}:</b> {value}")
            lbl.setWordWrap(True)
            lbl.setTextFormat(Qt.RichText)
            card.body.addWidget(lbl)
        for r in plan.reasons:
            lbl = QLabel("· " + r)
            lbl.setObjectName("Muted")
            lbl.setWordWrap(True)
            card.body.addWidget(lbl)
        if plan.alternatives:
            alt = plan.alternatives[0]
            box = QHBoxLayout()
            lbl = QLabel(f"<b>{alt.name}</b> is in the Store ({alt.label}). A native or Flatpak version is "
                         "preferred: it updates with the system and needs no Wine or conversion.")
            lbl.setWordWrap(True)
            box.addWidget(lbl, 1)
            use = QPushButton(f"Install the {alt.label} version")
            use.setObjectName("Primary")
            use.clicked.connect(lambda _=False, a=alt: self.install_store(a))
            box.addWidget(use)
            card.body.addLayout(box)
        if plan.blocked:
            lbl = QLabel(f"Won't work on Halo: {plan.blocked}")
            lbl.setObjectName("Muted")
            lbl.setWordWrap(True)
            card.body.addWidget(lbl)
            return
        steps = QLabel("<br>".join(f"{i}. {s.label}" + (" <i>(asks for your password)</i>" if s.needs_admin else "")
                                   for i, s in enumerate(plan.steps, 1)))
        steps.setTextFormat(Qt.RichText)
        steps.setWordWrap(True)
        card.body.addWidget(steps)
        for n in plan.notes[1 if plan.alternatives else 0:]:
            lbl = QLabel(n)
            lbl.setObjectName("Faint")
            lbl.setWordWrap(True)
            card.body.addWidget(lbl)
        row = QHBoxLayout()
        self.launch = QCheckBox("Open it afterwards to check it starts")
        self.launch.setChecked(True)
        row.addWidget(self.launch)
        row.addStretch()
        go = QPushButton("Install anyway" if plan.alternatives else "Install")
        go.setObjectName("TileAction" if plan.alternatives else "Primary")
        go.clicked.connect(self.approve)
        row.addWidget(go)
        card.body.addLayout(row)
        card.show()

    def approve(self):
        plan = self.plan
        if plan is None or plan.blocked:
            return
        if plan.risk == "high":
            ok = QMessageBox.question(self, "Install it?", "\n".join(plan.lines()) + "\n\nInstall it?")
            if ok != QMessageBox.Yes:
                return
        from core.store import Result
        launch = self.launch.isChecked()
        r = Result("file", plan.app_id, plan.name)
        self.queue(r, plan.steps, lambda result, errors: self._after(plan, result, errors, launch))
        self.note.setText(f"{plan.name} is in the install queue.")
        self.plan_card.hide()

    def _after(self, plan, result, errors, launch):
        ok = bool(result) and all(result.values())
        error = (errors or {}).get(plan.app_id, "")
        if not ok:
            self.history.record(self.ia.entry_from_plan(plan, False, error=error), "install", False, error)
            self.note.setText(f"{plan.name} wasn't installed: {error or 'see the details'}")
            return
        self.note.setText(f"{plan.name} is installed. Checking it starts…")

        def check():
            return self.ia.verify(plan.verify, launch=launch)

        def done(c):
            e = self.history.record(self.ia.entry_from_plan(plan, True, c), "install", c.get("installed", False),
                                    c.get("detail", ""))
            self.note.setText(f"{plan.name}: {e['status']} — {c.get('detail', '')}")
        run_async(check, done, lambda err: self.note.setText(f"{plan.name} is installed; the check failed: {err}"))

    # ------------------------------------------------------------------ history
    def show_history(self):
        clear_layout(self.history_list)
        entries = self.history.entries()
        if not entries:
            lbl = QLabel("Nothing yet. Apps SAINT installs (from the Store or from a file or link) show up here, "
                         "with where they came from and whether they started.")
            lbl.setObjectName("Faint")
            lbl.setWordWrap(True)
            self.history_list.addWidget(lbl)
            return
        for e in entries:
            self.history_list.addWidget(self._row(e))

    def _row(self, e):
        row = Card("")
        h = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(2)
        name = QLabel(e.get("name", e["id"]))
        name.setObjectName("TileName")
        col.addWidget(name)
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(e.get("updated_at", 0)))
        meta = QLabel(f"{e.get('origin', '')} · {when}" + (f" · SHA-256 {e['sha256'][:12]}…" if e.get("sha256") else ""))
        meta.setObjectName("Faint")
        meta.setWordWrap(True)
        col.addWidget(meta)
        if e.get("detail"):
            d = QLabel(e["detail"])
            d.setObjectName("Muted")
            d.setWordWrap(True)
            col.addWidget(d)
        h.addLayout(col, 1)
        status = e.get("status", "")
        h.addWidget(chip(status, "ok" if status == "installed" else "" if status == "uninstalled" else "warn"),
                    0, Qt.AlignTop)
        if status != "uninstalled":
            rep = QPushButton("Repair")
            rep.setObjectName("CatPill")
            rep.clicked.connect(lambda _=False, x=e: self.repair(x))
            h.addWidget(rep, 0, Qt.AlignTop)
            rm = QPushButton("Uninstall")
            rm.setObjectName("CatPill")
            rm.clicked.connect(lambda _=False, x=e: self.uninstall(x))
            h.addWidget(rm, 0, Qt.AlignTop)
        row.body.addLayout(h)
        return row

    def uninstall(self, e):
        try:
            steps = self.ia.uninstall_steps(e)
        except ValueError as err:
            QMessageBox.information(self, "Can't uninstall", str(err))
            return
        ok = QMessageBox.question(self, f"Uninstall {e.get('name')}?",
                                  "\n".join(s.label for s in steps) + "\n\nUninstall it?")
        if ok != QMessageBox.Yes:
            return
        from core.store import Result

        def after(result, errors):
            good = bool(result) and all(result.values())
            why = (errors or {}).get(e["id"], "")
            self.history.record({"id": e["id"], "status": "uninstalled" if good else e.get("status", ""),
                                 "detail": "" if good else why}, "uninstall", good, why)
            self.show_history()
        self.queue(Result("file", e["id"], e.get("name", e["id"])), steps, after)

    def repair(self, e):
        from core.store import Result
        name = e.get("name", e["id"])

        def go(steps):
            def after(result, errors):
                good = bool(result) and all(result.values())
                why = (errors or {}).get(e["id"], "")
                self.history.record({"id": e["id"], "status": "installed" if good else "failed",
                                     "detail": why}, "repair", good, why)
                self.show_history()
            for s in steps:                            # the history entry is what the queue reports on
                s.apps = [e["id"]] if s.apps else []
            self.queue(Result("file", e["id"], name), steps, after)
        run_async(lambda: self.ia.repair_steps(e), go,
                  lambda err: QMessageBox.information(self, "Can't repair", str(err)))
