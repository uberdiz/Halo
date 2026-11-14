"""
The "Migrate from Windows" settings page: a five-step wizard over core/windows_migration.py. Every long job runs
off the GUI thread. Removing the old Windows is the last step, on its own, and needs the volume's name typed.
"""

import threading
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QListView, QListWidget,
                               QListWidgetItem, QMenu, QMessageBox, QProgressBar, QPushButton, QRadioButton,
                               QStackedWidget, QTreeView, QVBoxLayout, QWidget)

from core import drives, os_switch
from core import windows_migration as wm
from ui.widgets import Page, clear_layout, run_async

TITLE = "Migrate from Windows"
ICON = "download"
ORDER = 41
STEPS = ("Choose Windows", "Files", "Browser & settings", "Apps", "Remove old Windows")


class _Progress(QObject):
    changed = Signal(str, int)


def _pick_model_class():
    """HalOS Files' model (folder sizes in the background) with a tick box per row. Built on first use so the page
    loads without the Files module."""
    from ui.files_app import FilesModel

    class PickModel(FilesModel):
        picked_changed = Signal()

        def __init__(self, sizes, parent=None):
            super().__init__(sizes, parent)
            self.picked = []                      # paths, in the order ticked

        def flags(self, index):
            f = super().flags(index)
            return f | Qt.ItemIsUserCheckable if index.column() == 0 else f

        def is_picked(self, path: str) -> bool:
            p = Path(path)
            return any(p == Path(x) or p.is_relative_to(x) for x in self.picked)

        def data(self, index, role=Qt.DisplayRole):
            if role == Qt.CheckStateRole and index.column() == 0:
                return Qt.Checked if self.is_picked(self.filePath(index)) else Qt.Unchecked
            return super().data(index, role)

        def setData(self, index, value, role=Qt.EditRole):
            if role != Qt.CheckStateRole or index.column() != 0:
                return super().setData(index, value, role)
            self.toggle(self.filePath(index), Qt.CheckState(value) == Qt.Checked)
            return True

        def toggle(self, path: str, on: bool):
            if on and not self.is_picked(path):
                self.picked = [x for x in self.picked if not Path(x).is_relative_to(path)] + [path]
            elif not on:
                self.picked = [x for x in self.picked if x != path]
            self.layoutChanged.emit()            # ticks on every visible child follow the folder
            self.picked_changed.emit()

    return PickModel


def _text(words="", name="Muted") -> QLabel:
    label = QLabel(words)
    label.setObjectName(name)
    label.setWordWrap(True)
    return label


def _when(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%d %b %Y") if ts else "unknown"


class MigratePage(Page):
    def __init__(self):
        super().__init__(TITLE, "Bring your files, bookmarks and apps across. Nothing leaves Windows until the last "
                                "step, and only if you ask.", scroll=True)
        self.installs, self.homes, self.volumes = [], [], []
        self.main = None
        self.plan = None
        self.matches = []
        self.choices = []
        self.cancel = threading.Event()
        self.signals = _Progress()
        self.signals.changed.connect(self._progress)
        self.step_label = _text("", "CardTitle")
        self.root.addWidget(self.step_label)
        self.stack = QStackedWidget()
        for build in (self._build_choose, self._build_files, self._build_browser, self._build_apps, self._build_remove):
            box = QWidget()
            lay = QVBoxLayout(box)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(10)
            build(lay)
            lay.addStretch(1)
            self.stack.addWidget(box)
        self.root.addWidget(self.stack)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setFixedHeight(6)
        self.bar.setTextVisible(False)
        self.bar.hide()
        self.root.addWidget(self.bar)
        self.status = _text()
        self.root.addWidget(self.status)
        nav = QHBoxLayout()
        self.back_btn = QPushButton("Back")
        self.back_btn.setObjectName("Ghost")
        self.back_btn.clicked.connect(lambda: self.go(self.stack.currentIndex() - 1))
        self.cancel_btn = QPushButton("Stop")
        self.cancel_btn.setObjectName("Ghost")
        self.cancel_btn.clicked.connect(self.cancel.set)
        self.cancel_btn.hide()
        self.next_btn = QPushButton("Next")
        self.next_btn.setObjectName("Primary")
        self.next_btn.clicked.connect(lambda: self.go(self.stack.currentIndex() + 1))
        nav.addWidget(self.back_btn)
        nav.addWidget(self.cancel_btn)
        nav.addStretch(1)
        nav.addWidget(self.next_btn)
        self.root.addLayout(nav)
        self.root.addStretch(1)
        self.go(0)
        self._detected = False

    def showEvent(self, e):
        super().showEvent(e)
        if not self._detected:
            self._detected = True
            self.detect()

    def go(self, index: int):
        index = max(0, min(index, len(STEPS) - 1))
        if index > 0 and self.source() is None:
            self.say("Choose where to bring things from first.")
            return
        self.stack.setCurrentIndex(index)
        self.step_label.setText(f"STEP {index + 1} OF {len(STEPS)}: {STEPS[index].upper()}")
        self.back_btn.setEnabled(index > 0)
        self.next_btn.setEnabled(index < len(STEPS) - 1)
        self.say("")
        if index == 1:
            self._fill_files()
        elif index == 2:
            self._fill_values()
        elif index == 4:
            self._fill_remove()

    def say(self, words: str):
        self.status.setText(words)

    def _progress(self, words, percent):
        self.bar.show()
        self.bar.setRange(0, 100)
        self.bar.setValue(percent)
        if words:
            self.say(words)

    def report(self, words="", percent=0):
        self.signals.changed.emit(words, percent)

    def _job(self, fn, done):
        """One long job at a time, with Stop and failures explained."""
        self.cancel.clear()
        self.cancel_btn.show()
        self.bar.setRange(0, 0)            # moving at once: the button press is seen before the first real number
        self.bar.show()
        self.say("Working…")
        pressed = self.sender() if isinstance(self.sender(), QPushButton) else None
        if pressed is not None:
            pressed.setEnabled(False)

        def settle():
            self.cancel_btn.hide()
            self.bar.hide()
            self.bar.setRange(0, 100)
            if pressed is not None:
                pressed.setEnabled(True)

        def finish(result):
            settle()
            done(result)

        def failed(e):
            settle()
            self.say(f"That didn't work: {e}. Details are in {wm.data_path(wm.LOG_NAME)}.")
        run_async(fn, finish, failed)

    # ------------------------------------------------------------------ 1. which Windows
    def _build_choose(self, lay):
        lay.addWidget(_text("Which Windows do you use? It's kept, whatever else you do here. The one used most recently "
                            "is suggested."))
        self.install_rows = QVBoxLayout()
        lay.addLayout(self.install_rows)
        self.main_group = QButtonGroup(self)
        self.main_group.idClicked.connect(self._pick_main)
        self.locked_note = _text()
        lay.addWidget(self.locked_note)
        form = QFormLayout()
        self.source_box = QComboBox()
        self.source_box.currentIndexChanged.connect(self._fill_users)
        self.user_box = QComboBox()
        form.addRow("Bring things from", self.source_box)
        form.addRow("Account", self.user_box)
        lay.addLayout(form)
        again = QPushButton("Look again")
        again.setObjectName("Ghost")
        again.clicked.connect(self.detect)
        lay.addWidget(again, 0, Qt.AlignLeft)

    def detect(self):
        self.say("Looking through your drives (read-only)…")

        def work():
            vols = drives.volumes()
            found = wm.detect_installs(vols)
            return vols, found, wm.linux_homes(vols)

        def done(res):
            self.volumes, found, self.homes = res
            self.show_installs(found["installs"], found["locked"], self.homes)
        run_async(work, done, lambda e: self.say(f"Couldn't look through the drives: {e}"))

    def show_installs(self, installs, locked=(), homes=()):
        self.installs, self.homes = list(installs), list(homes)
        self.main = wm.pick_main(self.installs)
        clear_layout(self.install_rows)
        for b in self.main_group.buttons():
            self.main_group.removeButton(b)
        for i, inst in enumerate(self.installs):
            r = QRadioButton(self.install_line(inst))
            r.setChecked(inst is self.main)
            self.main_group.addButton(r, i)
            self.install_rows.addWidget(r)
        self.locked_note.setText(" ".join(f"{v.name} is locked with BitLocker: unlock it under Drives & OS, then look "
                                          "again." for v in locked))
        self.source_box.blockSignals(True)
        self.source_box.clear()
        for inst in self.installs + self.homes:
            self.source_box.addItem(f"{'Linux' if inst.kind == 'linux' else inst.edition or 'Windows'}: {inst.name}"
                                    + (f" ({inst.size / 1e9:.0f} GB)" if inst.size else ""), inst)
        if self.main is not None:
            self.source_box.setCurrentIndex(self.installs.index(self.main))
        self.source_box.blockSignals(False)
        self._fill_users()
        if not self.installs and not self.homes:
            self.say("No Windows or other Linux was found on these drives.")
        else:
            self.say("")

    @staticmethod
    def install_line(inst) -> str:
        what = inst.edition or "Windows"
        who = f"last signed in: {inst.last_user}" if inst.last_user else f"accounts: {', '.join(inst.users) or 'none'}"
        return (f"{what} on {inst.name} ({inst.size / 1e9:.0f} GB, {inst.device or inst.root}): last used "
                f"{_when(inst.last_used)}; {who}")

    def _pick_main(self, index):
        self.main = self.installs[index]
        self.source_box.setCurrentIndex(index)

    def source(self):
        return self.source_box.currentData()

    def _fill_users(self):
        self.user_box.clear()
        src = self.source()
        if src is not None:
            self.user_box.addItems(src.users)
            if getattr(src, "last_user", "") in src.users:
                self.user_box.setCurrentText(src.last_user)          # the account used most recently

    # ------------------------------------------------------------------ 2. files
    def _build_files(self, lay):
        lay.addWidget(_text("Link keeps one copy, on the other drive, and shows it in your home folder: nothing is copied "
                            "and no space is used. Copy brings your own copy over. Hidden app data is skipped."))
        self.file_rows = QFormLayout()
        lay.addLayout(self.file_rows)
        self.write_box = QCheckBox("Let me change linked files too (makes that drive writable)")
        lay.addWidget(self.write_box)
        run = QPushButton("Bring these folders over")
        run.setObjectName("Primary")
        run.clicked.connect(self._run_files)
        lay.addWidget(run, 0, Qt.AlignLeft)
        self.file_result = _text()
        lay.addWidget(self.file_result)
        self._build_picker(lay)
        dupes = QPushButton("Find files that are on both sides")
        dupes.setToolTip("Compares your Windows folders with HalOS's by content and suggests what to merge. Nothing "
                         "moves until you say yes, and it can all be undone.")
        dupes.clicked.connect(self._find_duplicates)
        lay.addWidget(dupes, 0, Qt.AlignLeft)
        phone = QPushButton("Import photos from an iPhone (USB)")
        phone.clicked.connect(self._import_iphone)
        lay.addWidget(phone, 0, Qt.AlignLeft)
        self.phone_result = _text()
        lay.addWidget(self.phone_result)

    def _build_picker(self, lay):
        """Any file or folder on that Windows, like its File Explorer: quick-add shortcuts on top, a tree with
        sizes and tick boxes below, then Copy. One file that fails never stops the rest; Retry tries just those."""
        lay.addWidget(_text("PICK FILES AND FOLDERS YOURSELF", "CardTitle"))
        lay.addWidget(_text("Tick anything on that Windows (several at once), or start from a shortcut. Right-click "
                            "a folder to make it a shortcut of your own."))
        self.quick = QListWidget()
        self.quick.setObjectName("QuickAdd")
        self.quick.setFlow(QListView.LeftToRight)
        self.quick.setWrapping(True)
        self.quick.setResizeMode(QListView.Adjust)
        self.quick.setSpacing(4)
        self.quick.setMaximumHeight(84)
        self.quick.setContextMenuPolicy(Qt.CustomContextMenu)
        self.quick.customContextMenuRequested.connect(self._quick_menu)
        self.quick.itemClicked.connect(self._quick_clicked)
        lay.addWidget(self.quick)
        self.tree = QTreeView()
        self.tree.setObjectName("FilesView")              # HalOS Files' look
        self.tree.setMinimumHeight(300)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setSortingEnabled(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_menu)
        lay.addWidget(self.tree)
        self.pick_model = None
        row = QHBoxLayout()
        self.picked_label = _text("Nothing ticked yet.")
        self.dest_btn = QPushButton()
        self.dest_btn.setObjectName("Ghost")
        self.dest_btn.clicked.connect(self._choose_dest)
        self.copy_btn = QPushButton("Copy ticked items")
        self.copy_btn.setObjectName("Primary")
        self.copy_btn.clicked.connect(self._copy_picked)
        row.addWidget(self.picked_label, 1)
        row.addWidget(self.dest_btn)
        row.addWidget(self.copy_btn)
        lay.addLayout(row)
        self.dest = str(Path.home() / "From Windows")
        self.dest_btn.setText(f"Into {self.dest}")
        self.pick_result = _text()
        lay.addWidget(self.pick_result)
        self.fail_list = QListWidget()
        self.fail_list.setMaximumHeight(140)
        self.fail_list.hide()
        lay.addWidget(self.fail_list)
        self.retry_btn = QPushButton("Retry the ones that failed")
        self.retry_btn.clicked.connect(self._retry_picked)
        self.retry_btn.hide()
        lay.addWidget(self.retry_btn, 0, Qt.AlignLeft)
        self.failed = []

    def _fill_picker(self, src, user):
        from ui.files_app import FolderSizes
        if self.pick_model is None:
            self.pick_sizes = FolderSizes()
            self.pick_model = _pick_model_class()(self.pick_sizes, self)
            self.pick_model.picked_changed.connect(self._update_picked)
            self.tree.setModel(self.pick_model)
            self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        root = str(src.root)
        self.pick_model.picked = []
        self.pick_model.setRootPath(root)
        self.tree.setRootIndex(self.pick_model.index(root))
        try:
            profile = str(wm.profile_dir(src, user))
            self.tree.setCurrentIndex(self.pick_model.index(profile))
            self.tree.expand(self.pick_model.index(profile))
        except ValueError:
            pass
        self._fill_quick(src, user)
        self._update_picked()

    def _fill_quick(self, src, user):
        self.quick.clear()
        for e in wm.quick_add_entries():
            try:
                path = wm.quick_add_path(src, user, e["path"])
            except ValueError:
                path = None
            it = QListWidgetItem(("★ " if e["own"] else "+ ") + e["label"])
            it.setData(Qt.UserRole, str(path) if path else None)
            it.setData(Qt.UserRole + 1, e)
            it.setToolTip(str(path) if path else f"{e['path']}: not on this Windows")
            if path is None:
                it.setFlags(Qt.NoItemFlags)
            self.quick.addItem(it)

    def _quick_clicked(self, it):
        path = it.data(Qt.UserRole)
        if path and self.pick_model is not None:
            self.pick_model.toggle(path, not self.pick_model.is_picked(path))
            idx = self.pick_model.index(path)
            self.tree.scrollTo(idx)
            self.tree.setCurrentIndex(idx)

    def _quick_menu(self, pos):
        it = self.quick.itemAt(pos)
        entry = it.data(Qt.UserRole + 1) if it else None
        if not entry or not entry["own"]:
            return
        menu = QMenu(self)
        menu.addAction(f"Remove the shortcut \"{entry['label']}\"", lambda: self.remove_shortcut(entry))
        menu.exec(self.quick.mapToGlobal(pos))

    def _tree_menu(self, pos):
        idx = self.tree.indexAt(pos)
        if not idx.isValid():
            return
        path = self.pick_model.filePath(idx)
        menu = QMenu(self)
        menu.addAction("Untick" if self.pick_model.is_picked(path) else "Tick",
                       lambda: self.pick_model.toggle(path, not self.pick_model.is_picked(path)))
        if self.pick_model.isDir(idx):
            menu.addAction("Add to Quick add…", lambda: self.add_shortcut(path))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def add_shortcut(self, path: str, label: str = ""):
        src, user = self.source(), self.user_box.currentText()
        if not label:
            label, ok = QInputDialog.getText(self, "Add to Quick add", "Name for this shortcut:", text=Path(path).name)
            if not ok or not label.strip():
                return
        own = [e for e in wm.quick_add_entries() if e["own"]]
        own.append({"label": label.strip(), "path": wm.relative_quick_path(src, user, path)})
        wm.save_quick_add(own)
        self._fill_quick(src, user)

    def remove_shortcut(self, entry):
        own = [e for e in wm.quick_add_entries() if e["own"] and e != entry]
        wm.save_quick_add(own)
        self._fill_quick(self.source(), self.user_box.currentText())

    def _update_picked(self):
        n = len(self.pick_model.picked) if self.pick_model else 0
        self.picked_label.setText(f"{n} ticked: " + ", ".join(Path(p).name for p in self.pick_model.picked[:4])
                                  + ("…" if n > 4 else "") if n else "Nothing ticked yet.")
        self.copy_btn.setEnabled(bool(n))

    def _choose_dest(self):
        d = QFileDialog.getExistingDirectory(self, "Copy into", self.dest)
        if d:
            self.dest = d
            self.dest_btn.setText(f"Into {d}")

    def _copy_picked(self):
        src, picked, dest = self.source(), list(self.pick_model.picked), self.dest
        self._job(lambda: wm.copy_paths(src, picked, dest, progress=self.report, cancel=self.cancel),
                  self.show_copy_result)

    def _retry_picked(self):
        failed = list(self.failed)
        self._job(lambda: wm.retry_copies(failed, progress=self.report, cancel=self.cancel), self.show_copy_result)

    def show_copy_result(self, res):
        self.failed = res["errors"]
        words = f"Copied {res['copied']} files into {res.get('dest') or self.dest}"
        words += f", {res['skipped']} were already there" if res.get("skipped") else ""
        words += f". {res['note']}" if res.get("note") else "."
        if self.failed:
            words += f" {len(self.failed)} couldn't be copied; the rest came across."
        self.pick_result.setText(words)
        self.fail_list.clear()
        for e in self.failed:
            self.fail_list.addItem(f"{e['path']}: {e['why']}")
        self.fail_list.setVisible(bool(self.failed))
        self.retry_btn.setVisible(any(e.get("target") for e in self.failed))
        self.say("Done.")

    def _find_duplicates(self):
        """Propose merges between the old Windows folders and HalOS's; carry them out only after a yes."""
        from pathlib import Path

        from core import merge_plan
        from core.migration_journal import Journal
        src, user = self.source(), self.user_box.currentText()
        if src is None or src.kind != "windows":
            self.say("Choose a Windows to compare with first.")
            return

        def work():
            profile, home, plans = wm.profile_dir(src, user), Path.home(), []
            folders = ("Documents", "Desktop", "Pictures", "Music", "Videos", "Downloads")
            for i, name in enumerate(folders):
                self.report(f"Comparing {name}…", int(100 * i / len(folders)))
                old, new = wm._ci_path(profile, name), home / name
                if old is not None and new.is_dir() and not new.is_symlink():
                    plans.append(merge_plan.propose(old, new))
            return plans

        def done(plans):
            items = [i for p in plans for i in p.items]
            if not items:
                self.phone_result.setText("No file is on both sides: nothing to merge.")
                return
            freed = sum(p.bytes_same for p in plans)
            same = sum(i.kind == "same" for i in items)
            text = (f"{same} files are identical on both sides ({freed / 1e9:.1f} GB): keep one, with HalOS's copy "
                    f"moved to a Duplicates folder.\n{len(items) - same} have the same name but different content: keep "
                    "both, the Windows one renamed \"(Windows)\".\n\nNothing is deleted, Windows isn't changed, and "
                    "you can undo it. Merge them?")
            if QMessageBox.question(self, "Merge duplicates", text) != QMessageBox.Yes:
                self.phone_result.setText("Nothing was merged.")
                return
            journal = Journal(protect=[src.root])
            counts = {"same": 0, "conflict": 0}
            for p in plans:
                for k, v in merge_plan.apply(p, journal, approved=p.items,
                                             duplicates=Path.home() / "Duplicates").items():
                    counts[k] += v
            self.phone_result.setText(f"Merged: {counts['same']} duplicates set aside in ~/Duplicates, "
                                      f"{counts['conflict']} kept both ways.")
        self._job(work, done)

    def _import_iphone(self):
        """New photos and videos only, into Pictures/iPhone; the phone is read, never changed."""
        from core import iphone_photos

        def work():
            return iphone_photos.import_photos(progress=lambda n, total: self.report(
                f"Copying photo {n} of {total}…", int(100 * n / max(1, total))))
        self._job(work, lambda r: self.phone_result.setText(r["message"]))

    def _fill_files(self):
        while self.file_rows.rowCount():
            self.file_rows.removeRow(0)
        self.choices = []
        src, user = self.source(), self.user_box.currentText()
        if src is None or not user:
            self.say("This one has no account to bring files from.")
            return
        try:
            self.choices = wm.plan_folders(src, user)
        except ValueError as e:
            self.say(str(e))
            return
        self._fill_picker(src, user)
        for c in self.choices:
            box = QComboBox()
            box.addItems(["Link (no copying)", "Copy", "Skip"])
            box.setToolTip(str(c.source))
            box.currentIndexChanged.connect(lambda i, ch=c: setattr(ch, "mode", ("link", "copy", "skip")[i]))
            self.file_rows.addRow(c.name, box)

    def _run_files(self):
        src, user = self.source(), self.user_box.currentText()
        write = self.write_box.isChecked()

        def work():
            if write and any(c.mode == "link" for c in self.choices):
                vol = next((v for v in drives.volumes() if v.uuid == src.uuid), None)
                if vol is not None:
                    res = drives.mount(vol, write=True)
                    if res.message:
                        self.report(res.message)
            return wm.run_files(src, user, self.choices, write=write, progress=self.report, cancel=self.cancel)

        def done(results):
            lines = []
            for r in results:
                word = "couldn't be brought over" if r.get("failed") else "linked" if r["mode"] == "link" else "copied"
                lines.append(f"{r['name']}: {word}" + (f" ({r['note']})" if r.get("note") else ""))
            self.file_result.setText("\n".join(lines))
            self.say("Done." if results else "Nothing was chosen.")
        self._job(work, done)

    # ------------------------------------------------------------------ 3. browser and settings
    def _build_browser(self, lay):
        lay.addWidget(_text("Saved passwords and cookies are never read or copied by SAINT. To bring passwords, export "
                            "them yourself and import them into your browser here:"))
        how = QPushButton("How to bring my passwords")
        how.setObjectName("Ghost")
        how.clicked.connect(lambda: QMessageBox.information(self, "Bringing your passwords", PASSWORD_STEPS))
        lay.addWidget(how, 0, Qt.AlignLeft)
        self.bookmarks_box = QCheckBox("Bookmarks from Chrome, Edge, Brave and Firefox, into Firefox")
        self.wallpaper_box = QCheckBox("Wallpaper")
        self.engine_box = QCheckBox("Wallpaper Engine wallpapers (subscribed and your own; shown in Wallpapers)")
        self.vscode_box = QCheckBox("VS Code settings, keybindings, snippets and extension list")
        self.saint_box = QCheckBox("SAINT's history and what it remembers about you")
        self.claude_box = QCheckBox("Claude Code: history, settings, skills, and the Claude app's MCP servers")
        self.models_box = QCheckBox("AI models already downloaded on Windows (copied, not downloaded again)")
        self.wifi_box = QCheckBox("Saved Wi-Fi networks (with passwords only from an export made with -WifiPasswords)")
        for box in (self.bookmarks_box, self.wallpaper_box, self.engine_box, self.vscode_box, self.saint_box,
                    self.claude_box,
                    self.models_box, self.wifi_box):
            box.setChecked(True)
            lay.addWidget(box)
        run = QPushButton("Import these")
        run.setObjectName("Primary")
        run.clicked.connect(self._run_browser)
        lay.addWidget(run, 0, Qt.AlignLeft)
        self.browser_result = _text()
        lay.addWidget(self.browser_result)
        self.step_fail_list = QListWidget()
        self.step_fail_list.setMaximumHeight(140)
        self.step_fail_list.hide()
        lay.addWidget(self.step_fail_list)
        self.step_retry_btn = QPushButton("Retry what failed")
        self.step_retry_btn.clicked.connect(lambda: self._run_browser(self.failed_steps))
        self.step_retry_btn.hide()
        lay.addWidget(self.step_retry_btn, 0, Qt.AlignLeft)
        self.failed_steps = []
        lay.addWidget(_text(wm.SETTINGS_NOTICE, "Faint"))
        self.values = _text()
        lay.addWidget(self.values)

    def _fill_values(self):
        src = self.source()
        if src is None or src.kind != "windows":
            self.values.setText("")
            return

        def work():
            values = wm.windows_values(src)
            libraries = wm.steam_libraries(src)
            if libraries:
                values["Steam game folders"] = ", ".join(libraries) + (" (add one in Steam > Settings > Storage. "
                                                                       "Proton runs poorly from NTFS)")
            return values
        run_async(work, lambda v: self.values.setText("\n".join(f"{k}: {x}" for k, x in v.items())),
                  lambda e: self.values.setText(str(e)))

    def _browser_steps(self, src, user):
        """(key, label, fn -> one line) for each import; _run_browser runs the ticked ones, each on its own."""
        def wifi():
            r = wm.import_wifi(src)
            return (f"Wi-Fi: {r['added']} of {r['found']} networks saved"
                    + (f", {r['with_passwords']} with passwords." if r["with_passwords"] else
                       "; each asks for its password the first time." if r["found"] else "."))

        def journal():
            from core.migration_journal import Journal
            return Journal(protect=[src.root])        # every change can be undone; the old disk is read-only

        def saint():
            from core import migrate_ai
            r = migrate_ai.import_saint(wm.profile_dir(src, user), journal())
            return (f"SAINT: {r['history_added']} past requests added to your history, {r['copied']} memory files."
                    if r["found"] else f"SAINT: {r['note']}")

        def claude():
            from core import migrate_ai
            r = migrate_ai.import_claude(wm.profile_dir(src, user), journal())
            return (f"Claude: {r['copied']} files ({', '.join(r['parts'])}); {r['kept']} already here were kept. "
                    f"{r['note']}" if r["found"] else f"Claude: {r['note']}")

        def models():
            from core import agent_catalog, pkg_queue
            stores = agent_catalog.windows_model_stores(globs=[str(wm.profile_dir(src, user) / ".ollama" / "models")])
            if not stores:
                return "AI models: none found on that Windows."
            res = pkg_queue.run_plan(agent_catalog.reuse_steps(stores[0]["path"]), on_line=lambda _l: None,
                                     on_wait=lambda t: self.report(t, 9))
            if not (res and all(res.values())):
                raise RuntimeError(f"{', '.join(stores[0]['models'])} didn't copy (see the log)")
            return f"AI models: {', '.join(stores[0]['models'])} copied."

        def marks():
            r = wm.import_bookmarks(src, user)
            return (f"Bookmarks: {r['count']} imported. {r.get('note', '')}" if r["count"] else
                    "Bookmarks: none found.") + "".join(f"\n  {e}" for e in r["errors"])

        def wallpaper():
            r = wm.import_wallpaper(src, user)
            if not r["ok"] and r.get("errors"):
                raise RuntimeError(r["note"])
            return (f"Wallpaper: saved as {r['path']}" + (" and applied." if r["applied"] else ".")) if r["ok"] \
                else f"Wallpaper: {r['note']}"

        def engine():
            others = [v.mountpoint for v in self.volumes if v.mountpoint and v.mountpoint != str(src.root)]
            r = wm.import_wallpaper_engine(src, extra_roots=others, progress=self.report, cancel=self.cancel)
            if not r["found"]:
                return "Wallpaper Engine: none found on that Windows."
            if r["errors"] and not r["copied"] and not r["kept"]:
                raise RuntimeError(r["errors"][0]["why"])
            return (f"Wallpaper Engine: {r['copied']} copied, {r['kept']} already here (in {r['dest']})"
                    + (f"; {len(r['errors'])} files couldn't be read." if r["errors"] else "."))

        def code():
            r = wm.import_vscode(src, user)
            return (f"VS Code: {len(r['copied'])} settings files, {len(r['extensions'])} extensions listed, "
                    f"{r['installed']} installed. Install VS Code from the Apps step, then import again for the rest."
                    if r["extensions"] and not r["installed"] else
                    f"VS Code: {len(r['copied'])} settings files, {r['installed']} extensions installed.")

        return [("wifi", "Wi-Fi", self.wifi_box, wifi), ("saint", "SAINT", self.saint_box, saint),
                ("claude", "Claude Code", self.claude_box, claude), ("models", "AI models", self.models_box, models),
                ("bookmarks", "Bookmarks", self.bookmarks_box, marks),
                ("wallpaper", "Wallpaper", self.wallpaper_box, wallpaper),
                ("engine", "Wallpaper Engine", self.engine_box, engine), ("vscode", "VS Code", self.vscode_box, code)]

    def _run_browser(self, only=None):
        """Each ticked import on its own: one failing is listed (with Retry) and the others still run."""
        src, user = self.source(), self.user_box.currentText()
        if src is None or src.kind != "windows":
            self.say("Browser data is only imported from Windows.")
            return
        steps = [(k, label, fn) for k, label, box, fn in self._browser_steps(src, user)
                 if (k in only if only else box.isChecked())]

        def work():
            lines, failed = [], []
            for n, (key, label, fn) in enumerate(steps):
                if self.cancel.is_set():
                    break
                self.report(f"{label}…", int(100 * n / max(1, len(steps))))
                try:
                    lines.append(fn())
                except Exception as e:           # one import failing never stops the others
                    wm._log(f"import {key} failed: {e}")
                    failed.append((key, label, str(e)))
            return lines, failed

        self._job(work, self.show_browser_result)

    def show_browser_result(self, res):
        lines, failed = res
        self.failed_steps = [k for k, _l, _w in failed]
        self.browser_result.setText("\n".join(lines))
        self.step_fail_list.clear()
        for _k, label, words in failed:
            self.step_fail_list.addItem(f"{label}: {words}")
        self.step_fail_list.setVisible(bool(failed))
        self.step_retry_btn.setVisible(bool(failed))
        self.say(f"Done. {len(failed)} didn't work; the rest did." if failed else "Done.")

    # ------------------------------------------------------------------ 4. apps
    def _build_apps(self, lay):
        lay.addWidget(_text("What was installed on that Windows, matched to what to use on HalOS. Apps with a Linux version "
                            "are ticked. Apps that need Wine aren't, because not all of them work well."))
        row = QHBoxLayout()
        find = QPushButton("Find my apps")
        find.setObjectName("Primary")
        find.clicked.connect(self._find_apps)
        self.install_btn = QPushButton("Install ticked apps")
        self.install_btn.clicked.connect(self._install_apps)
        self.install_btn.setEnabled(False)
        self.all_btn = QPushButton("Tick all that work")
        self.all_btn.setObjectName("Ghost")
        self.all_btn.clicked.connect(self._tick_working)
        self.all_btn.setEnabled(False)
        row.addWidget(find)
        row.addWidget(self.install_btn)
        row.addWidget(self.all_btn)
        row.addStretch(1)
        lay.addLayout(row)
        filters = QHBoxLayout()
        self.app_filter = QComboBox()
        self.app_filter.setSizeAdjustPolicy(QComboBox.AdjustToContents)      # "Works with Wine or Proton (12)" in full
        self.app_filter.setMinimumWidth(250)
        self.app_filter.addItem("All apps", "")
        self.app_filter.currentIndexChanged.connect(self._apply_app_filter)
        self.app_search = QLineEdit()
        self.app_search.setPlaceholderText("Search these apps")
        self.app_search.setClearButtonEnabled(True)
        self.app_search.textChanged.connect(self._apply_app_filter)
        filters.addWidget(self.app_filter)
        filters.addWidget(self.app_search, 1)
        lay.addLayout(filters)
        self.app_list = QListWidget()
        self.app_list.setMinimumHeight(280)
        self.app_list.setWordWrap(True)
        lay.addWidget(self.app_list)

    def _find_apps(self):
        src = self.source()
        if src.kind != "windows":
            self.say("Apps are only matched from Windows.")
            return

        def work():
            self.report("Reading the list of installed apps…", 0)
            names = wm.collect_app_names(src)
            return wm.match_apps(names, progress=lambda n, p: self.report(f"Looking for {n}…", p), cancel=self.cancel)
        self._job(work, self.show_matches)

    @staticmethod
    def _match_line(m) -> str:
        if m.kind == "native" and m.result is not None:
            how = f"{m.result.label}: {m.result.name}"
        elif m.kind == "native":
            how = f"Linux version at {m.link}" if m.link else "has a Linux version"
        elif m.kind == "wine":
            how = "Windows version with Wine"
        elif m.kind == "web":
            how = "use the web app" + (f": {m.link}" if m.link else "")
        elif m.kind == "alternative":
            other = m.alternative or (m.result.name if m.result is not None else "an alternative")
            how = f"no Linux version. Use {other}"
        elif m.kind == "not_needed":
            how = "not needed on HalOS"
        else:
            how = "no Linux or Wine version found"
        return f"{m.windows_name}: {how}" + (f"\n{m.why}" if m.why and m.kind != "native" else "")

    def show_matches(self, matches):
        from core.app_match import KIND_LABEL, KINDS
        order = {k: i for i, k in enumerate(KINDS)}
        self.matches = sorted(matches, key=lambda m: (order.get(m.kind, 9), m.windows_name.lower()))
        self.app_list.clear()
        for m in self.matches:
            item = QListWidgetItem(self._match_line(m))
            if m.result is None:
                item.setFlags(Qt.ItemIsEnabled)
            else:
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if m.kind == "native" else Qt.Unchecked)
                item.setData(Qt.UserRole, m.result)
            item.setData(Qt.UserRole + 1, m.kind)
            self.app_list.addItem(item)
        counts = wm.match_counts(self.matches)
        self.app_filter.blockSignals(True)
        self.app_filter.clear()
        self.app_filter.addItem(f"All apps ({len(self.matches)})", "")
        for kind in KINDS:
            if counts.get(kind):
                self.app_filter.addItem(f"{KIND_LABEL[kind]} ({counts[kind]})", kind)
        self.app_filter.blockSignals(False)
        self._apply_app_filter()
        can = any(m.result is not None for m in self.matches)
        self.install_btn.setEnabled(can)
        self.all_btn.setEnabled(can)
        real = [m for m in self.matches if m.kind != "not_needed"]
        works = sum(m.kind in ("native", "wine", "web") for m in real)
        self.say(f"{works} of {len(real)} apps work on HalOS ({counts.get('native', 0)} with a Linux version). "
                 f"{counts.get('not_needed', 0)} drivers and Windows components aren't needed.")

    def _apply_app_filter(self, *_):
        kind, words = self.app_filter.currentData() or "", self.app_search.text().strip().lower()
        for i in range(self.app_list.count()):
            item = self.app_list.item(i)
            item.setHidden(bool((kind and item.data(Qt.UserRole + 1) != kind) or (words and words not in item.text().lower())))

    def _tick_working(self):
        """Tick every app with a Linux version (Wine apps stay the user's choice)."""
        for i in range(self.app_list.count()):
            item = self.app_list.item(i)
            if item.flags() & Qt.ItemIsUserCheckable and item.data(Qt.UserRole + 1) == "native":
                item.setCheckState(Qt.Checked)

    def _install_apps(self):
        from core import saintos_apps as sa
        from core import store
        ticked = [self.app_list.item(i).data(Qt.UserRole) for i in range(self.app_list.count())
                  if self.app_list.item(i).checkState() == Qt.Checked]
        ticked = [r for r in ticked if r is not None]
        if not ticked:
            self.say("Tick at least one app.")
            return

        def work():
            errors, _warnings = sa.blockers()
            if errors:
                raise RuntimeError(" ".join(errors))
            outcome, why = {}, {}
            for i, r in enumerate(ticked):
                if self.cancel.is_set():
                    break
                self.report(f"Installing {r.name}…", int(100 * i / len(ticked)))
                try:
                    from core import pkg_queue
                    res = pkg_queue.run_plan(store.plan(r), on_line=lambda _l: None, errors=why,
                                             on_wait=lambda t, i=i: self.report(t, int(100 * i / len(ticked))))
                    outcome[r.name] = bool(res) and all(res.values())
                except (ValueError, OSError, RuntimeError) as e:
                    outcome[r.name], why[r.name] = False, str(e)
            return outcome, why

        def done(res):
            outcome, why = res
            bad = [n for n, ok in outcome.items() if not ok]
            self.say(f"Installed {len(outcome) - len(bad)} of {len(outcome)}." +
                     (f" Failed: {', '.join(bad)}. {' '.join(map(str, why.values()))}" if bad else ""))
        self._job(work, done)

    # ------------------------------------------------------------------ 5. remove the old Windows
    def _build_remove(self, lay):
        lay.addWidget(_text("Optional, and it can't be undone: this deletes an old Windows's system folders to free its space. "
                            "Your main Windows, partitions, EFI partitions and Recovery are never touched, and files in Users "
                            "stay unless you tick the box."))
        form = QFormLayout()
        self.old_box = QComboBox()
        self.old_box.currentIndexChanged.connect(lambda _i: self._reset_remove())
        form.addRow("Old Windows", self.old_box)
        lay.addLayout(form)
        self.users_box = QCheckBox("Also remove user files (Users folder)")
        self.users_box.clicked.connect(lambda _c: self._reset_remove())
        lay.addWidget(self.users_box)
        row = QHBoxLayout()
        self.writable_btn = QPushButton("Make this drive writable")
        self.writable_btn.setObjectName("Ghost")
        self.writable_btn.clicked.connect(self._make_writable)
        preview = QPushButton("Show what would be removed")
        preview.clicked.connect(self._preview_removal)
        row.addWidget(self.writable_btn)
        row.addWidget(preview)
        row.addStretch(1)
        lay.addLayout(row)
        self.remove_list = QListWidget()
        self.remove_list.setMinimumHeight(160)
        lay.addWidget(self.remove_list)
        self.remove_info = _text()
        lay.addWidget(self.remove_info)
        self.confirm_edit = QLineEdit()
        self.confirm_edit.textChanged.connect(lambda _t: self._update_remove_button())
        lay.addWidget(self.confirm_edit)
        row2 = QHBoxLayout()
        self.dry_btn = QPushButton("Dry run (delete nothing)")
        self.dry_btn.setObjectName("Ghost")
        self.dry_btn.clicked.connect(lambda: self._remove(True))
        self.remove_btn = QPushButton("Remove old Windows")
        self.remove_btn.setObjectName("Danger")
        self.remove_btn.clicked.connect(lambda: self._remove(False))
        row2.addWidget(self.dry_btn)
        row2.addWidget(self.remove_btn)
        row2.addStretch(1)
        lay.addLayout(row2)
        self.boot_box = QCheckBox("")
        self.boot_box.hide()
        self.boot_btn = QPushButton("Remove that boot entry")
        self.boot_btn.setObjectName("Ghost")
        self.boot_btn.clicked.connect(self._remove_boot_entry)
        self.boot_btn.hide()
        lay.addWidget(self.boot_box)
        lay.addWidget(self.boot_btn, 0, Qt.AlignLeft)
        self._reset_remove()

    def _fill_remove(self):
        self.old_box.blockSignals(True)
        self.old_box.clear()
        for inst in self.installs:
            if self.main is None or not wm._same_install(inst, self.main):
                self.old_box.addItem(f"{inst.name} ({inst.device or inst.root})", inst)
        self.old_box.blockSignals(False)
        self._reset_remove()
        if not self.old_box.count():
            self.say("There's no other Windows on this PC to remove.")

    def _reset_remove(self):
        self.plan = None
        self.remove_list.clear()
        self.confirm_edit.clear()
        self.remove_info.setText("")
        self.confirm_edit.setPlaceholderText("")
        target = self.old_box.currentData()
        self.users_box.setEnabled(target is not None and wm.migration_ran(target.uuid))
        if not self.users_box.isEnabled():
            self.users_box.setChecked(False)
            self.users_box.setToolTip("Bring this Windows's files over in the Files step first.")
        self._update_remove_button()

    def _update_remove_button(self):
        ready = self.plan is not None and self.plan.allowed and self.confirm_edit.text() == self.plan.token
        self.remove_btn.setEnabled(ready)
        self.dry_btn.setEnabled(ready)

    def _make_writable(self):
        target = self.old_box.currentData()
        if target is None:
            return

        def work():
            vol = next((v for v in drives.volumes() if v.uuid == target.uuid), None)
            if vol is None:
                return drives.Result(False, "That drive isn't there any more.")
            res = drives.mount(vol, write=True)
            if res.mountpoint:
                target.root = type(target.root)(res.mountpoint)
            return res
        run_async(work, lambda r: (self.say(r.message or "It's writable now."), self._reset_remove()),
                  lambda e: self.say(str(e)))

    def _preview_removal(self):
        target = self.old_box.currentData()
        if target is None:
            return
        users = self.users_box.isChecked()
        self._job(lambda: wm.build_removal(target, self.main, users), self.show_plan)

    def show_plan(self, plan):
        self.plan = plan
        self.remove_list.clear()
        for item in plan.items:
            self.remove_list.addItem(f"{item.path}   {item.size / 1e9:.1f} GB")
        for path in plan.skipped:
            self.remove_list.addItem(f"{path}   is a link: left alone")
        if plan.refusals:
            self.remove_info.setText("This can't go ahead:\n" + "\n".join(f"- {r}" for r in plan.refusals))
        else:
            self.remove_info.setText(f"This frees {plan.size / 1e9:.1f} GB. "
                                     + ("Users is on the list." if plan.include_users else "Users stays.")
                                     + f" Type {plan.token} below to confirm.")
            self.confirm_edit.setPlaceholderText(f"Type {plan.token}")
        self._update_remove_button()

    def _remove(self, dry_run: bool):
        plan, typed = self.plan, self.confirm_edit.text()
        if plan is None:
            return
        if not dry_run:
            ok = QMessageBox.warning(self, "Remove this Windows for good?",
                                     f"{len(plan.items)} items ({plan.size / 1e9:.1f} GB) on {plan.install.name} are "
                                     "deleted for good, not moved to a Recycle Bin. That Windows won't start again.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ok != QMessageBox.Yes:
                return

        def done(res):
            if res["refused"]:
                self.say("Nothing was removed: " + " ".join(res["refused"]))
                return
            word = "Would free" if dry_run else "Freed"
            trouble = f" {len(res['errors'])} items couldn't be removed; see {res['log']}." if res["errors"] else ""
            self.say(f"{word} {res['freed'] / 1e9:.1f} GB.{trouble}")
            if not dry_run:
                self._reset_remove()
                self._check_boot_entry(plan.install)
        self._job(lambda: wm.execute_removal(plan, self.main, typed, dry_run=dry_run, progress=self.report,
                                             cancel=self.cancel), done)

    def _check_boot_entry(self, old):
        main = self.main

        def work():
            vols = drives.volumes()
            return os_switch.stale_windows_entry(old.partuuid, main.partuuid, lambda p: wm.read_bcd_for(p, vols))

        def done(res):
            entry = res["entry"]
            self.remove_info.setText(res["reason"])
            self.boot_box.setVisible(bool(entry))
            self.boot_btn.setVisible(bool(entry))
            if entry:
                self.boot_box.setChecked(False)          # off unless the user turns it on
                self.boot_box.setText(f"Yes, remove the boot entry \"{entry['label']}\"")
                self.boot_btn.setProperty("num", entry["num"])
        run_async(work, done, lambda e: self.remove_info.setText(f"Every boot entry stays: {e}"))

    def _remove_boot_entry(self):
        if not self.boot_box.isChecked():
            self.say("Tick the box first.")
            return
        import subprocess
        argv = os_switch.remove_entry_argv(self.boot_btn.property("num"))
        run_async(lambda: subprocess.run(argv, capture_output=True, text=True, timeout=120),
                  lambda r: self.say("Boot entry removed." if r.returncode == 0 else
                                     f"The boot entry stays: {r.stderr.strip()}"),
                  lambda e: self.say(str(e)))


PASSWORD_STEPS = "1. Export them where they are now, to a CSV file on a USB stick or your Windows disk:\n   Chrome or Edge or Brave: Settings > Passwords > Export passwords\n   Apple Passwords (Mac, iPhone): Passwords app > File > Export All Passwords\n   Firefox on Windows: about:logins > ... > Export passwords\n2. On HalOS, in Firefox: about:logins > ... > Import from a file, and pick that CSV\n   (Chrome or Brave on HalOS: Settings > Passwords > Import).\n3. Delete the CSV afterwards: it holds your passwords in plain text.\n\nSAINT never opens that file, so your passwords stay between you and your browser."


def build():
    return MigratePage()
