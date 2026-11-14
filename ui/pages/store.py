"""
ui/pages/store.py

SAINT Store's window contents (ui/store_app.py is the app around it): one search over Arch, the AUR, Flathub and
Windows apps (core/store.py), the whole catalogue to browse (core/store_browse.py), and one install queue with
live progress. Home opens like a store: a full-bleed featured banner (the app's real screenshot), SAINT's picks,
then every app, a page at a time as you scroll, by category and source. Icons, screenshots and developers are the
publishers' own (core/store_art.py, cached); an app without any shows a tile in its colour with its initial.

Clicking an app opens its own page (ui/components/store_tiles.AppDetails) with "Apps like this" under it; Back
returns to where you were, scrolled as you left it. Every install or removal updates every card, banner and page
in place, and ends in a notification naming what happened (core/saintos_apps.finish). The install queue is only
on screen while something is queued, or after a failure, until it's dismissed.

AUR packages are made by Arch users, not Arch, and Windows apps run under Wine: both say so, with
votes / the PKGBUILD link / what to expect, and wait for a yes before anything runs.

Search results filter by how the app runs (native, Flatpak, AUR, Wine, or "won't work" with the reason), by
installed status and by type. The installation assistant (ui/components/install_assistant.py) takes a link,
GitHub release or package file and runs through the same queue; every install is recorded in the history
(core/install_assistant.History).
"""

from collections import deque

from PySide6.QtCore import QObject, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QRadialGradient
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar,
                               QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from core import store, store_browse
from ui.components.store_tiles import AppDetails, AppTile, HeroBanner, TileGrid
from ui.widgets import (Card, Page, Segmented, Skeleton, Spinner, chip, clear_layout, run_async, run_with_feedback,
                        set_chip)

# The sources a search asks, in the order the progress row names them (core.store.SOURCES without the picks).
SEARCH_SOURCES = [("repo", "Arch"), ("flathub", "Flathub"), ("aur", "AUR"), ("windows", "Windows apps")]

# How it runs on Halo (core.store.compatibility); "Won't work" lists what can't, with why.
FILTERS = [("All", None), ("Native", "native"), ("Flatpak", "flatpak"), ("AUR", "aur"), ("Windows (Wine)", "wine"),
           ("Won't work", "blocked")]
INSTALLED_FILTERS = [("Any", None), ("Installed", True), ("Not installed", False)]
TYPE_FILTERS = [("Every type", None), ("Apps", "app"), ("Games", "game"), ("Developer tools", "developer"),
                ("Libraries & system", "system")]
BROWSE_FROM = [("All sources", None), ("Flathub", "flathub"), ("Arch", "repo"), ("AUR", "aur")]
FEATURED = ["blender", "heroic", "obs", "steam", "krita", "spotify"]      # the banner's rotation (catalog ids)
LOAD_AHEAD = 900                              # px from the bottom at which the next page starts loading


def pkg_wait_text(position: int) -> str:
    from core import pkg_queue
    return pkg_queue.wait_text(position)


class _Bridge(QObject):
    line = Signal(str)
    step = Signal(int, int, str, str, int)
    wait = Signal(str)                            # the queue's "Waiting for another install to finish…"
    source = Signal(int, str, int)                # search seq, source, how many it found


class StorePage(Page):
    idle = Signal()                               # the install queue has finished

    def __init__(self, window=None):
        super().__init__("Store", "")
        self.window = window
        self.title.hide()                             # the Store draws its own header below
        self._category = "All"
        self._queue = deque()
        self._busy = False
        self._results = []
        self._snapshot = {}                           # what's installed (core.store.installed_snapshot)
        self._job_state = {}                          # app key -> "Queued" / "Installing…" / "Removing…"
        self._catalog = {}
        self._catalogue = None                        # the listing being browsed (core.store_browse.Catalogue)
        self._browse_seq = 0
        self._loading = False
        self._more = False
        self._browse_grid = None
        self._browse_note = None
        self._browse_retry = None
        self._browse_count = None
        self._loaded = 0
        self._source_index = 0
        self._hero = None
        self._details = None
        self._detail_stack = []
        self._bridge = _Bridge()
        self._bridge.line.connect(self._log_line)
        self._bridge.step.connect(self._on_step)
        self._bridge.wait.connect(self._on_wait)
        self._bridge.source.connect(self._on_source)
        self._source_chips = {}
        self._search_note = None

        # Header: an orange eyebrow, a display title, then search across every source.
        self.masthead = QWidget()
        mast = QVBoxLayout(self.masthead)
        mast.setContentsMargins(0, 0, 0, 0)
        mast.setSpacing(4)
        eyebrow = QLabel("SAINT STORE")
        eyebrow.setObjectName("RailEyebrow")
        eyebrow.setStyleSheet("padding: 0px;")
        f = eyebrow.font()
        f.setLetterSpacing(QFont.AbsoluteSpacing, 2.0)
        eyebrow.setFont(f)
        mast.addWidget(eyebrow)
        headline = QLabel("Find your next app")
        headline.setObjectName("StoreHeadline")
        mast.addWidget(headline)
        sub = QLabel("Arch, Flathub, the AUR and Windows apps in one search. SAINT installs it and tells you "
                     "when it is there.")
        sub.setObjectName("PageSubtitle")
        sub.setWordWrap(True)
        mast.addWidget(sub)
        self.root.addWidget(self.masthead)
        bar = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setObjectName("StoreSearch")
        try:
            from ui import icons
            from ui.theme import current_palette
            self.query.addAction(icons.icon("search", current_palette().muted, 18), QLineEdit.LeadingPosition)
        except Exception:
            pass
        self.query.setPlaceholderText("Search every app — Blender, Roblox Studio, VS Code, Notepad++…")
        self.query.setClearButtonEnabled(True)
        # Live search: results follow the text as it's typed (debounced), and an empty box shows the picks at once.
        self._seq = 0
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self.search)
        self.query.textChanged.connect(self._typed)
        self.query.returnPressed.connect(self.search)
        bar.addWidget(self.query, 1)
        for text, tab in (("From a file or link", 0), ("Installed by SAINT", 1)):
            b = QPushButton(text)
            b.setObjectName("CatPill")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, t=tab: self.show_assistant(t))
            bar.addWidget(b)
        self.root.addLayout(bar)
        # Browsing: category pills. Searching: where results come from.
        self.pill_row = QScrollArea()
        self.pill_row.setWidgetResizable(True)
        self.pill_row.setFrameShape(QScrollArea.NoFrame)
        self.pill_row.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.pill_row.setFixedHeight(44)
        pill_inner = QWidget()
        self.pills = QHBoxLayout(pill_inner)
        self.pills.setContentsMargins(0, 4, 0, 4)
        self.pills.setSpacing(8)
        self.pill_row.setWidget(pill_inner)
        self._pill_buttons = {}
        self.root.addWidget(self.pill_row)
        refilter = (lambda *_a: self._show_results() if self.query.text().strip() else None)
        self.filters = QWidget()
        frow = QHBoxLayout(self.filters)
        frow.setContentsMargins(0, 0, 0, 0)
        frow.setSpacing(10)
        self.filter = Segmented([f[0] for f in FILTERS])
        self.filter.changed.connect(refilter)
        frow.addWidget(self.filter)
        self.installed_filter = Segmented([f[0] for f in INSTALLED_FILTERS])
        self.installed_filter.changed.connect(refilter)
        frow.addWidget(self.installed_filter)
        self.type_filter = QComboBox()
        self.type_filter.addItems([f[0] for f in TYPE_FILTERS])
        self.type_filter.currentIndexChanged.connect(refilter)
        frow.addWidget(self.type_filter)
        frow.addStretch()
        self.filters.hide()
        self.root.addWidget(self.filters)

        # Install queue: what's running, how far, and its log.
        self.job = Card("Installing")
        self.job_label = QLabel("")
        self.job_label.setWordWrap(True)
        self.job.body.addWidget(self.job_label)
        self.job_bar = QProgressBar()
        self.job_bar.setRange(0, 100)
        self.job_bar.setTextVisible(False)
        self.job_bar.setFixedHeight(4)
        self.job.body.addWidget(self.job_bar)
        self.job_log = QPlainTextEdit()
        self.job_log.setReadOnly(True)
        self.job_log.setMaximumHeight(140)
        self.job_log.hide()
        log_btn = QPushButton("Details")
        log_btn.setObjectName("Ghost")
        log_btn.clicked.connect(lambda: self.job_log.setVisible(not self.job_log.isVisible()))
        self.job.header.addWidget(log_btn)
        self.job_dismiss = QPushButton("Dismiss")
        self.job_dismiss.setObjectName("Ghost")
        self.job_dismiss.clicked.connect(self.job.hide)
        self.job_dismiss.hide()
        self.job.header.addWidget(self.job_dismiss)
        self.job.body.addWidget(self.job_log)
        self.job.hide()
        self.root.addWidget(self.job)

        # Two views: home (browsing, results, the assistant) and an app's page. Home stays alive underneath, so
        # Back returns to the same place in a long list.
        self.views = QStackedWidget()
        self.home_scroll, self.list = self._scroll_view()
        self.detail_scroll, self.detail_host = self._scroll_view()
        self.views.addWidget(self.home_scroll)
        self.views.addWidget(self.detail_scroll)
        self.root.addWidget(self.views, 1)
        bar = self.home_scroll.verticalScrollBar()
        bar.valueChanged.connect(lambda _v: self._maybe_more())
        bar.rangeChanged.connect(lambda *_r: self._maybe_more())
        self.status = QLabel("")
        self.status.setObjectName("Faint")
        self.root.addWidget(self.status)
        self._show_picks()
        self._refresh_status()

    @staticmethod
    def _scroll_view():
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        rows = QVBoxLayout(inner)
        rows.setContentsMargins(0, 0, 10, 0)
        rows.setSpacing(14)
        rows.addStretch()
        scroll.setWidget(inner)
        return scroll, rows

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self._maybe_more)

    def busy(self) -> bool:
        return self._busy or bool(self._queue)

    def open_query(self, text: str):
        """Open on a search (`saint-store blender`, or a link to an app)."""
        self._home_view()
        self.query.setText(" ".join(text.split())[:64])

    # ------------------------------------------------------------------ results
    def _tile(self, r):
        t = AppTile(r, self._act, self._open if store.openable(r) else None, self.show_details)
        if not r.installed and self._snapshot and store.is_installed(r, self._snapshot):
            r.installed = True
        t.set_installed(r.installed, self._job_state.get(store.app_key(r), ""))
        return t

    def _act(self, r):
        alt = (r.extra or {}).get("instead")
        if (r.extra or {}).get("blocked"):
            if alt:
                self._search_pick(alt)
            return
        self.install(r)

    def _open(self, r):
        import subprocess

        def work():
            argv = store.launch_argv(r)
            if not argv:
                raise RuntimeError("it has no window to open; look for it in the start menu or a terminal")
            subprocess.Popen(argv, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.status.setText(f"Opening {r.name}…")
        self._flash(r, "busy", "Opening…")

        def opened(_res):
            self.status.setText(f"{r.name} is opening.")
            self._flash(r, "done", "Opened")

        def failed(e):
            self.status.setText(f"Couldn't open {r.name}: {e}")
            self._flash(r, "failed", "Couldn't open")
        run_async(work, opened, failed)

    def _flash(self, r, state, text):
        """The outcome of a button's work, on every button for that app (tiles, the app's page)."""
        key = store.app_key(r)
        for t in self.findChildren(AppTile):
            if store.app_key(t.result) == key:
                t.flash(state, text)
        if self._details is not None and store.app_key(self._details.result) == key:
            self._details.flash(state, text)

    def _set_rows(self, rows):
        clear_layout(self.list)
        self._browse_seq += 1                         # whatever was still loading is for a list that's gone
        self._catalogue = self._browse_grid = self._browse_note = self._browse_retry = self._hero = None
        self._loading = self._more = False
        for w in rows:
            self.list.addWidget(w)
        self.list.addStretch()
        self.home_scroll.verticalScrollBar().setValue(0)

    def _picks(self):
        from core import saintos_apps as sa
        catalog = sa.load_catalog()
        self._catalog = catalog
        return catalog, [store.pick_result(a) for a in catalog.values()]

    def _build_pills(self):
        if self._pill_buttons:
            return
        for c in store_browse.CATEGORIES:
            b = QPushButton(c.label.replace("&", "&&"))       # "&" would become a shortcut underline
            b.setObjectName("CatPill")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, n=c.label: self._pick_category(n))
            self.pills.addWidget(b)
            self._pill_buttons[c.label] = b
        self.pills.addStretch()

    def _pick_category(self, name):
        self._category = name
        if self.query.text():
            self.query.clear()                        # clearing shows home (in this category)
        else:
            self._show_picks()

    @staticmethod
    def _section_head(title, note="", more=None, more_text="See all  \u2192"):
        """A shelf's title row; (its widget, its count label)."""
        head = QHBoxLayout()
        head.setContentsMargins(0, 8, 0, 0)
        name = QLabel(title)
        name.setObjectName("ShelfTitle")
        count = QLabel(note)
        count.setObjectName("Faint")
        head.addWidget(name)
        head.addSpacing(8)
        head.addWidget(count, 0, Qt.AlignBottom)
        head.addStretch()
        if more:
            b = QPushButton(more_text)
            b.setObjectName("ShelfMore")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(more)
            head.addWidget(b)
        box = QWidget()
        box.setLayout(head)
        return box, count

    def _show_picks(self):
        """Home: the banner, SAINT's picks, then the whole catalogue in this category, loaded as it's scrolled."""
        from ui import motion
        self._home_view()
        self._build_pills()
        for n, b in self._pill_buttons.items():
            b.setChecked(n == self._category)
        self.pill_row.show()
        self.filters.hide()
        cat = store_browse.BY_LABEL.get(self._category, store_browse.CATEGORIES[0])
        rows, shelf = [], []
        try:
            catalog, picks = self._picks()
        except Exception as e:
            catalog, picks = {}, []
            self.status.setText(f"SAINT's app list isn't available: {e}")
        else:
            self.status.setText("")
        by_id = {r.id: r for r in picks}
        everything = cat is store_browse.CATEGORIES[0]
        hero = None
        if everything and by_id:
            for r in by_id.values():
                self._mark(r)
            hero = HeroBanner([by_id[i] for i in FEATURED if i in by_id], self._act, self.show_details, self._open)
            hero.busy_of = lambda r: self._job_state.get(store.app_key(r), "")
            hero.refresh()
            rows.append(hero)
        shown = picks if everything else [r for r in picks if r.extra.get("category") in cat.picks]
        if shown:
            shelf = [self._tile(r) for r in shown]
            box, _count = self._section_head("SAINT's picks", f"{len(shown)} apps", self._show_collection)
            rows.append(box)
            grid = TileGrid()
            grid.set_tiles(shelf, max_rows=1 if everything else 0)
            rows.append(grid)
        browsable = everything or cat.flathub
        if browsable:
            head, count = self._section_head("All apps" if everything else cat.label)
            rows.append(head)
            source = Segmented([s[0] for s in BROWSE_FROM])
            source.set_index(self._source_index)
            source.changed.connect(self._pick_source)
            source.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
            rows.append(source)
            grid = TileGrid()
            rows.append(grid)
            note = QLabel("")
            note.setObjectName("Faint")
            note.setAlignment(Qt.AlignCenter)
            rows.append(note)
            retry = QPushButton("Try again")
            retry.setObjectName("ShelfMore")
            retry.setCursor(Qt.PointingHandCursor)
            retry.clicked.connect(self._restart_catalogue)
            retry.hide()
            rows.append(retry)
        self._set_rows(rows)
        self._hero = hero
        if browsable:
            self._browse_grid, self._browse_note, self._browse_retry, self._browse_count = grid, note, retry, count
            self._restart_catalogue()
        motion.stagger([t for t in shelf if not t.isHidden()][:12], step=22, dy=8)

    def _mark(self, r):
        if self._snapshot and store.is_installed(r, self._snapshot):
            r.installed = True

    def _show_collection(self):
        """SAINT's picks in full, by category; what first-run pointed people at, a click from installing."""
        from ui import motion
        self._home_view()
        self.filters.hide()
        for b in self._pill_buttons.values():
            b.setChecked(False)
        back = QPushButton("\u2190  Back to the Store")
        back.setObjectName("ShelfMore")
        back.setCursor(Qt.PointingHandCursor)
        back.clicked.connect(self._show_picks)
        rows = [back]
        try:
            _catalog, picks = self._picks()
        except Exception as e:
            self.status.setText(f"SAINT's app list isn't available: {e}")
            picks = []
        box, _count = self._section_head("SAINT's picks", "", self._install_common, "Install the common picks")
        rows.append(box)
        tiles = []
        for cat in dict.fromkeys(r.extra["category"] for r in picks):
            shelf = [self._tile(r) for r in picks if r.extra["category"] == cat]
            tiles += shelf
            sub_head, _n = self._section_head(cat, f"{len(shelf)} apps")
            rows.append(sub_head)
            grid = TileGrid()
            grid.set_tiles(shelf)
            rows.append(grid)
        self._set_rows(rows)
        motion.stagger(tiles[:12], step=22, dy=8)

    def _install_common(self):
        from core import saintos_apps as sa
        wanted = [store.pick_result(self._catalog[i]) for i in sa.COMMON_PICKS if i in self._catalog]
        wanted = [r for r in wanted if not r.installed and not store.is_installed(r, self._snapshot)]
        if not wanted:
            self.status.setText("The common picks are already installed.")
            return
        names = ", ".join(r.name for r in wanted)
        if QMessageBox.question(self, "Install the common picks?", f"Install {names}?") == QMessageBox.Yes:
            for r in wanted:
                self.enqueue(r)

    # ------------------------------------------------------------------ browsing the whole catalogue
    def _pick_source(self, i):
        self._source_index = i
        self._restart_catalogue()

    def _restart_catalogue(self):
        if self._browse_grid is None:
            return
        self._browse_seq += 1
        self._browse_grid.clear()
        self._browse_retry.hide()
        self._loaded = 0
        source = BROWSE_FROM[self._source_index][1]
        self._catalogue = store_browse.Catalogue(self._category, source, catalog=self._catalog)
        self._loading, self._more = False, True
        self._load_more()

    def _load_more(self):
        if self._catalogue is None or self._loading or not self._more:
            return
        self._loading = True
        seq, catalogue = self._browse_seq, self._catalogue
        self._browse_note.setText("Loading more apps…")
        run_async(catalogue.next_page, lambda res: self._got_page(seq, res), lambda e: self._page_failed(seq, e))

    def _got_page(self, seq, res):
        if seq != self._browse_seq or self._browse_grid is None:
            return
        rows, more = res
        self._loading, self._more = False, more
        self._loaded += len(rows)
        tiles = [self._tile(r) for r in rows]
        if tiles:
            self._browse_grid.append(tiles)
        self._browse_count.setText(f"{self._loaded} so far" if more else f"{self._loaded} apps")
        failed = [store.SOURCE_LABEL.get(s, s) for s in self._catalogue.failed]
        if failed:
            self._browse_note.setText(f"Couldn't reach {' or '.join(failed)}. Everything else still works.")
            self._browse_retry.setVisible(not self._loaded or not more)
        elif more:
            self._browse_note.setText("")
        else:
            self._browse_note.setText("That's everything." if self._loaded else "Nothing here yet.")
        QTimer.singleShot(0, self._maybe_more)        # the window may be taller than what's loaded

    def _page_failed(self, seq, e):
        if seq != self._browse_seq or self._browse_note is None:
            return
        self._loading, self._more = False, False
        self._browse_note.setText(f"Couldn't load more apps: {e}")
        self._browse_retry.show()

    def _maybe_more(self):
        """Near the bottom of the list (and looking at it), fetch the next page."""
        if not self._more or self._loading or self._catalogue is None or not self.isVisible():
            return
        if self.views.currentWidget() is not self.home_scroll:
            return
        bar = self.home_scroll.verticalScrollBar()
        if bar.value() >= bar.maximum() - LOAD_AHEAD:
            self._load_more()

    # ------------------------------------------------------------------ what's installed, everywhere
    def _refresh_status(self):
        """Ask the system what's installed (two quick commands, off the GUI thread); show it everywhere."""
        run_async(store.installed_snapshot, self._got_snapshot, lambda _e: None)

    def _got_snapshot(self, snapshot):
        self._snapshot = snapshot or {}
        self._apply_status()

    def _apply_status(self):
        """Every card, the banner and the open app page, in place: nothing rebuilt, nothing scrolled."""
        seen = set()
        for t in self.findChildren(AppTile):
            r = t.result
            if id(r) not in seen:
                seen.add(id(r))
                r.installed = store.is_installed(r, self._snapshot)
            t.set_installed(r.installed, self._job_state.get(store.app_key(r), ""))
        for r in self._results:
            r.installed = store.is_installed(r, self._snapshot)
        if self._hero is not None:
            for r in self._hero.results:
                r.installed = store.is_installed(r, self._snapshot)
            self._hero.refresh()
        if self._details is not None:
            r = self._details.result
            r.installed = store.is_installed(r, self._snapshot)
            self._details.set_installed(r.installed, self._job_state.get(store.app_key(r), ""))

    def _mark_result(self, r, installed: bool):
        """What an install or removal just did, before the system is asked again (and where it can't be asked)."""
        key = store.app_key(r)
        for t in self.findChildren(AppTile):
            if store.app_key(t.result) == key:
                t.result.installed = installed
        for other in [r, *self._results, *(self._hero.results if self._hero else []),
                      *([self._details.result] if self._details else [])]:
            if store.app_key(other) == key:
                other.installed = installed
        kind = "flatpak" if key in (self._snapshot.get("flatpak") or ()) or store.compatibility(r) == "flatpak" else "pacman"
        known = self._snapshot.get(kind)
        if known is not None:
            (known.add if installed else known.discard)(key)
        self._job_state.pop(key, None)
        self._show_marks()

    def _show_marks(self):
        """Redraw the state without re-deciding it."""
        for t in self.findChildren(AppTile):
            t.set_installed(t.result.installed, self._job_state.get(store.app_key(t.result), ""))
        if self._hero is not None:
            self._hero.refresh()
        if self._details is not None:
            r = self._details.result
            self._details.set_installed(r.installed, self._job_state.get(store.app_key(r), ""))

    def _search_pick(self, catalog_id):
        self.query.setText(catalog_id)
        self.search()

    def _typed(self, text):
        if not text.strip():
            self._debounce.stop()
            self.search()
        else:
            self._debounce.start(350)

    def search(self):
        self._debounce.stop()
        self._seq += 1
        seq = self._seq
        q = self.query.text().strip()
        if not q:
            self._results = []
            self.status.setText("")
            self._show_picks()
            return
        if len(q) < 2:
            return
        self._home_view()
        self._show_searching(q)
        run_async(lambda: store.search(q, on_source=lambda s, n: self._bridge.source.emit(seq, s, n)),
                  lambda res: self._got(seq, res), lambda e: self._search_failed(seq, e))

    def _show_searching(self, q):
        """At once, before any source answers: a spinner, each source's own progress, and placeholder tiles."""
        from ui.components.store_tiles import TILE_H, TILE_W
        self.pill_row.hide()
        self.filters.show()
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        h.addWidget(Spinner(18))
        self._search_note = QLabel("Searching Arch, Flathub, AUR…")
        self._search_note.setObjectName("Muted")
        h.addWidget(self._search_note)
        self._source_chips = {}
        for source, label in SEARCH_SOURCES:
            c = chip(f"{label} …")
            c.setProperty("label", label)
            self._source_chips[source] = c
            h.addWidget(c)
        h.addStretch()
        grid = TileGrid()
        ghosts = []
        for _ in range(8):
            g = Skeleton(TILE_H, 14)
            g.setFixedSize(TILE_W, TILE_H)
            ghosts.append(g)
        grid.set_tiles(ghosts)
        self._set_rows([row, grid])
        self.status.setText(f"Searching for “{q}”…")

    def _on_source(self, seq, source, count):
        c = self._source_chips.get(source)
        if seq != self._seq or c is None:
            return
        try:
            set_chip(c, f"{c.property('label')} ✓ {count}" if count else f"{c.property('label')}: none",
                     "ok" if count else "")
            left = [l for s, l in SEARCH_SOURCES if "…" in self._source_chips[s].text()]
            if self._search_note is not None:
                self._search_note.setText(f"Still searching {', '.join(left)}…" if left else "Sorting the results…")
        except RuntimeError:                          # the progress row was replaced already
            pass

    def _search_failed(self, seq, e):
        if seq != self._seq:
            return
        self._source_chips, self._search_note = {}, None
        retry = QPushButton("Try again")
        retry.setObjectName("ShelfMore")
        retry.setCursor(Qt.PointingHandCursor)
        retry.clicked.connect(self.search)
        note = QLabel(f"The search didn't finish: {e}")
        note.setObjectName("ErrorText")
        note.setWordWrap(True)
        self._set_rows([note, retry])
        self.status.setText("Search failed.")

    def _got(self, seq, results):
        if seq != self._seq:                  # an older query finished after a newer one started
            return
        self._source_chips, self._search_note = {}, None
        self._results = results
        for r in results:
            self._mark(r)
        self._show_results()

    # ------------------------------------------------------------------ an app's page and the assistant
    def _home_view(self):
        self.views.setCurrentWidget(self.home_scroll)
        self.masthead.show()
        self._detail_stack = []
        if self._details is not None:
            clear_layout(self.detail_host)
            self._details = None

    def _back(self):
        """Out of the assistant or the collection: the results if there are any, else home."""
        if self.query.text().strip() and self._results:
            self._home_view()
            self._show_results()
        else:
            self._show_picks()

    def show_details(self, r):
        """Open an app's own page; Back returns to wherever this was opened from."""
        if not self._detail_stack:                    # what home had showing, for Back
            self._home_chrome = (not self.pill_row.isHidden(), not self.filters.isHidden())
        self._detail_stack.append(r)
        self._render_details(r)

    def _render_details(self, r):
        clear_layout(self.detail_host)
        self._details = AppDetails(r, self._act, self._details_back, self._open if store.openable(r) else None,
                                   self._uninstall)
        self._details.set_installed(r.installed, self._job_state.get(store.app_key(r), ""))
        self.detail_host.addWidget(self._details)
        self.masthead.hide()
        self.pill_row.hide()
        self.filters.hide()
        self.views.setCurrentWidget(self.detail_scroll)
        self.detail_scroll.verticalScrollBar().setValue(0)
        self.status.setText("")
        seq = self._seq_details = getattr(self, "_seq_details", 0) + 1
        run_async(lambda: store_browse.similar_for(r, self._catalog or None),
                  lambda found: self._got_similar(seq, found), lambda _e: None)

    def _got_similar(self, seq, found):
        if seq != self._seq_details or self._details is None:
            return
        self._details.set_similar([self._tile(c) for c in found or []])

    def _details_back(self):
        self._detail_stack.pop()
        if self._detail_stack:
            self._render_details(self._detail_stack[-1])
            return
        clear_layout(self.detail_host)
        self._details = None
        self.masthead.show()
        self.pill_row.setVisible(self._home_chrome[0])
        self.filters.setVisible(self._home_chrome[1])
        self.views.setCurrentWidget(self.home_scroll)
        QTimer.singleShot(0, self._maybe_more)

    def show_assistant(self, tab=0):
        from ui.components.install_assistant import InstallAssistantPanel
        self._home_view()
        self.pill_row.hide()
        self.filters.hide()
        back = QPushButton("\u2190  Back to the Store")
        back.setObjectName("ShelfMore")
        back.setCursor(Qt.PointingHandCursor)
        back.clicked.connect(self._back)
        self.assistant = InstallAssistantPanel(self.enqueue, self.install, tab=tab)
        self._set_rows([back, self.assistant])
        self.status.setText("")

    def _show_results(self):
        compat = FILTERS[max(0, self.filter.index())][1]
        inst = INSTALLED_FILTERS[max(0, self.installed_filter.index())][1]
        kind = TYPE_FILTERS[max(0, self.type_filter.currentIndex())][1]
        # "Won't work" apps (anti-cheat, drivers, or a Windows build of a native app) show only under that filter.
        shown = [r for r in self._results if store.matches(r, compat, inst, kind)]
        self.pill_row.hide()
        self.filters.show()
        grid = TileGrid()
        tiles = [self._tile(r) for r in shown]
        grid.set_tiles(tiles)
        self._set_rows([grid] if shown else [])
        from ui import motion
        motion.stagger(tiles[:16], step=22, dy=8)
        self.status.setText(f"{len(shown)} result(s)" if shown else "Nothing found. Try another name.")

    def paintEvent(self, e):
        """A low orange glow behind the header: the Store's light, in SAINT's colour."""
        super().paintEvent(e)
        from ui.theme import current_palette
        p = current_palette()
        g = QPainter(self)
        glow = QRadialGradient(QPointF(self.width() * 0.18, -40), max(320.0, self.width() * 0.5))
        c = QColor(p.accent)
        c.setAlpha(34 if p.dark else 26)
        glow.setColorAt(0, c)
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        g.fillRect(self.rect(), glow)
        g.end()

    # ------------------------------------------------------------------ installing
    def install(self, r):
        if r.source == "aur":
            e = r.extra
            ok = QMessageBox.question(
                self, "Install from the AUR?",
                f"{r.name} comes from the Arch User Repository: packages made by Arch users, not by Arch.\n\n"
                f"{e.get('votes', 0)} votes · maintainer {e.get('maintainer') or 'none'}"
                + (" · marked out of date" if e.get("out_of_date") else "")
                + f"\n\nYou can read exactly what it builds first: {e.get('url', '')}\n\nInstall it?")
            if ok != QMessageBox.Yes:
                return
        elif r.source == "windows":
            ok = QMessageBox.question(
                self, "Install a Windows app?",
                f"{r.name} is a Windows app. SAINT downloads its installer from the publisher (checked against "
                "winget's SHA-256), installs it with Wine in its own folder and adds it to the start menu.\n\n"
                "Most apps work; some don't (anti-cheat, drivers, some copy protection). Install it?")
            if ok != QMessageBox.Yes:
                return
        self.enqueue(r)

    def _uninstall(self, r):
        try:
            steps = store.uninstall_plan(r)
        except ValueError as e:
            self.status.setText(str(e))
            return
        if QMessageBox.question(self, f"Uninstall {r.name}?",
                                f"Remove {r.name} from this PC? You can install it again from the Store."
                                ) != QMessageBox.Yes:
            return
        self.enqueue(r, steps, removing=True)

    def enqueue(self, r, steps=None, after=None, removing=False):
        """Queue a job: a Store result (planned when its turn comes), or ready ``steps`` with ``after(result,
        errors)`` called when they've run (the installation assistant, repair). ``removing``: it's an uninstall."""
        self._queue.append((r, steps, after, removing))
        self._job_state.setdefault(store.app_key(r), "Queued")
        if self._busy:                                # something is running: this one waits its turn, and says so
            self.status.setText(f"{r.name} is queued: {pkg_wait_text(len(self._queue))}")
        self._show_marks()
        self.job_dismiss.hide()
        self.job.show()
        self._next()

    def _next(self):
        if self._busy:
            return
        if not self._queue:
            self.idle.emit()
            return
        r, steps, after, removing = self._queue.popleft()
        if steps is None:
            try:
                steps = store.plan(r)
            except Exception as e:
                self._job_state.pop(store.app_key(r), None)
                self._show_marks()
                self._job_failed(f"{r.name}: {e}")
                return self._next()
        self._busy = True
        self._current = r
        self._after = after
        self._removing = removing
        self._job_state[store.app_key(r)] = "Removing…" if removing else "Installing…"
        self._show_marks()
        self.job.title_label.setText("REMOVING" if removing else "INSTALLING")
        self.job_dismiss.hide()
        self.job_log.clear()
        self.job_bar.setValue(0)
        left = f" ({len(self._queue)} more in the queue)" if self._queue else ""
        self.job_label.setText(f"{r.name}: getting ready…{left}")

        def work():
            from core import pkg_queue
            from core import saintos_apps as sa
            errors, warnings = sa.blockers()
            if errors:
                raise RuntimeError(" ".join(errors))
            for w in warnings:
                self._bridge.line.emit(w)
            self._errors = {}
            from core import downloads
            source = "Flathub" if r.source == "flathub" else "SAINT Store"
            verb = "Removing" if removing else "Installing"
            # The Downloads page and its toasts see this install, with flatpak's/pacman's own progress lines.
            with downloads.Tracker(f"store:{store.app_key(r)}", f"{verb} {r.name}", source) as track:
                def line(text):
                    track.line(text)
                    self._bridge.line.emit(text)

                def step(i, n, s, st, p):
                    track.step()
                    self._bridge.step.emit(i, n, s.label, st, p)
                # Through the one package queue: it waits for pacman and for other SAINT installs instead of failing.
                return pkg_queue.run_plan(steps, on_wait=self._bridge.wait.emit, on_line=line, on_step=step,
                                          errors=self._errors, cancel=track.cancel)   # Cancel in Downloads
        run_async(work, self._done, self._failed)

    def _job_failed(self, text):
        """A failure stays on screen until it's dismissed, with its log; it isn't "installing" any more."""
        self.job.title_label.setText("DIDN'T FINISH")
        self.job_label.setText(text)
        self.job_log.show()
        self.job_dismiss.show()
        self.job.show()
        self._failure = True

    def _job_ended(self, r, installed, summary=""):
        """After every job: the card goes away unless a failure is on it, and the Store shows the new state."""
        self._busy = False
        self._mark_result(r, installed)
        if summary:
            self.status.setText(summary)
        if self._queue:
            self._next()
            return
        if not getattr(self, "_failure", False):
            self.job.hide()
        self._failure = False
        self._refresh_status()
        self.idle.emit()
        if self.filters.isVisible() and self._results and self.installed_filter.index() > 0:
            self._show_results()              # an "Installed" filter's list has changed

    def _log_line(self, text):
        self.job_log.appendPlainText(text)

    def _on_wait(self, text):
        """The queue is waiting (pacman is busy, or another SAINT window is installing): say so, keep the place."""
        r = self._current
        left = f" ({len(self._queue)} more in the queue)" if self._queue else ""
        self.job.title_label.setText("WAITING")
        self.job_label.setText(f"{r.name}: {text}{left}")
        self.job_bar.setRange(0, 0)                   # moving, not stuck
        self.job_log.appendPlainText(text)
        self._job_state[store.app_key(r)] = "Waiting…"
        self._show_marks()

    def _on_step(self, i, n, label, status, pct):
        if self.job_bar.maximum() == 0:               # it was waiting; now it runs
            self.job_bar.setRange(0, 100)
            self.job.title_label.setText("REMOVING" if getattr(self, "_removing", False) else "INSTALLING")
            self._job_state[store.app_key(self._current)] = "Removing…" if self._removing else "Installing…"
            self._show_marks()
        what = {"started": "starting", "progress": f"{pct} %", "done": "done", "failed": "failed"}[status]
        self.job_label.setText(f"{self._current.name} — step {i + 1} of {n}: {label} — {what}")
        self.job_bar.setValue(int(((i + (pct / 100 if status != "started" else 0)) / max(n, 1)) * 100))

    def _done(self, result):
        from core import saintos_apps as sa
        try:
            catalog = sa.load_catalog()
        except Exception:
            catalog = {}
        r = self._current
        removing = getattr(self, "_removing", False)
        errors = getattr(self, "_errors", None) or {}
        title, body = sa.finish(result or {r.id: False}, catalog, names={r.id: r.name}, errors=errors,
                                verb="Removed" if removing else "Installed")
        self._record(r, result, errors, removing)
        ok = bool(result) and all(result.values())
        text = f"{title}: " + body.replace("\n", "  ")
        if not ok:
            self._job_failed(text)            # a failure shows its log without another click
        self.job_bar.setRange(0, 100)
        self.job_bar.setValue(100)
        self._job_ended(r, (not ok) if removing else ok, text if ok else "")
        self._flash(r, "done" if ok else "failed",
                    ("Removed" if removing else "Installed") if ok else ("Not removed" if removing else "Didn't install"))

    def _record(self, r, result, errors, removing=False):
        """Store installs go in the install history; assistant jobs report back to whoever queued them."""
        after, self._after = getattr(self, "_after", None), None
        try:
            if after is not None:
                after(result or {}, errors)
            elif r.source != "file":
                from core import install_assistant as ia
                ok = bool(result) and all(result.values())
                why = errors.get(r.id, "")
                ia.History().record(ia.entry_from_store(r, ok, error=why), "uninstall" if removing else "install",
                                    ok, why)
        except Exception as e:                        # the history never breaks an install
            self._log_line(f"install history: {e}")

    def _failed(self, e):
        r = self._current
        removing = getattr(self, "_removing", False)
        self._job_failed(f"{r.name}: {e}")
        self._record(r, {}, {r.id: str(e)}, removing)
        self.job_bar.setRange(0, 100)
        self._job_ended(r, removing or bool(r.installed))
        self._flash(r, "failed", "Not removed" if removing else "Didn't install")
