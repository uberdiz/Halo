"""
ui/taskmanager.py

SAINT Task Manager: processes, performance, app history, startup apps, users, services and system
information, from core/sysinfo.py. Its own small process (`saint-taskmgr`, Ctrl+Shift+Esc on Halo) so it
opens fast and keeps working when SAINT itself is busy or stopped: it loads no voice, AI or SAINT modules.

Only the page you're looking at refreshes (every 2 s); nothing is polled while the window is hidden.
"""

import os
import sys
import time
from collections import deque

if __package__ in (None, ""):                         # run as a script: /opt/saint/app/ui/taskmanager.py
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QFrame, QGridLayout,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox,
                               QPushButton, QScrollArea, QStackedWidget, QStyledItemDelegate, QTableView, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from core import sysinfo
from core.sysinfo import human_bytes, human_duration
from ui import motion

PAGES = ["Processes", "Performance", "App history", "Startup apps", "Users", "Services", "System information"]
PAGE_ICONS = {"Processes": "list", "Performance": "activity", "App history": "history", "Startup apps": "power",
              "Users": "user", "Services": "settings", "System information": "cpu"}
REFRESH_MS = 2000
HISTORY = 60                                          # points per graph (2 minutes at 2 s)
RANGES = ["Live", "5m", "1h", "24h", "7d"]            # Live: this window's 2 s samples; the rest core/sys_history
RANGE_LABELS = {"Live": "Last 2 minutes", "5m": "Last 5 minutes", "1h": "Last hour", "24h": "Last 24 hours",
                "7d": "Last 7 days"}
RANGE_WORDS = {"5m": "5 minutes", "1h": "an hour", "24h": "24 hours", "7d": "7 days"}


def _palette():
    try:
        from ui.theme import current_palette
        return current_palette()
    except Exception:
        from ui.theme import palette_for
        return palette_for("Dark")


_MONO = None


def _mono() -> QFont:
    """Tabular numbers, so columns of values don't jitter as they change."""
    global _MONO
    if _MONO is None:
        _MONO = QFont("Noto Sans Mono")
        _MONO.setStyleHint(QFont.Monospace)
        _MONO.setFamilies(["Noto Sans Mono", "Cascadia Mono", "Consolas", "monospace"])
        _MONO.setPointSizeF(QApplication.font().pointSizeF() * 0.95)
    return _MONO


def _tint(base: str, t: float) -> QColor:
    """SAINT orange at strength t (0..1): the heat of a busy cell."""
    c = QColor(base)
    c.setAlpha(int(18 + 150 * max(0.0, min(1.0, t))))
    return c


def _proc_name(pid):
    try:
        import psutil
        return psutil.Process(pid).name()
    except Exception:
        return ""


def _na(v, unit=""):
    return "N/A" if v is None else f"{v:.0f}{unit}"


def _nvidia_stats(detail, procs, i):
    """Every NVML field for NVIDIA GPU ``i`` (N/A when the card doesn't report it) and who holds its memory."""
    g = next((d for d in detail if d.get("index") == i), detail[i] if i < len(detail) else None)
    if g is None:
        return []
    mine = [p for p in procs if not g.get("uuid") or p["gpu_uuid"] == g["uuid"]]
    gen, throttle = g.get("pcie.link.gen.current"), g.get("thermal_throttle")
    return [("Memory load", _na(g.get("utilization.memory"), " %")),
            ("Encoder", _na(g.get("utilization.encoder"), " %")),
            ("Decoder", _na(g.get("utilization.decoder"), " %")),
            ("Power", _na(g.get("power.draw"), " W") + " / " + _na(g.get("power.limit"), " W")),
            ("Core clock", _na(g.get("clocks.gr"), " MHz")), ("Memory clock", _na(g.get("clocks.mem"), " MHz")),
            ("Fan", _na(g.get("fan.speed"), " %")),
            ("PCIe", "N/A" if gen is None else f"Gen {gen:.0f} x{_na(g.get('pcie.link.width.current'))}"),
            ("Thermal throttling", "N/A" if throttle is None else "yes" if throttle else "no"),
            ("CUDA", g.get("cuda") or "N/A"), ("Driver", g.get("driver_version") or "N/A"),
            ("Using the GPU", ", ".join(p["name"] + (f" {human_bytes(p['memory_mb'] * 2 ** 20)}" if p["memory_mb"]
                                                     else "") for p in mine[:4]) or "none")]


# --------------------------------------------------------------------------- widgets
class Graph(QWidget):
    """A line graph over a shared history deque: gridlines, a fill that fades to nothing, and a live end-point.
    ``maximum`` 0 scales to the largest value shown (network throughput)."""

    def __init__(self, values=None, maximum=100.0, compact=False):
        super().__init__()
        self.values = values if values is not None else deque(maxlen=HISTORY)
        self.maximum = maximum
        self.compact = compact
        self.span = HISTORY                            # points across the width
        self.setMinimumHeight(36 if compact else 220)

    def paintEvent(self, _):
        p = _palette()
        accent = QColor(p.accent)
        g = QPainter(self)
        g.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if not self.compact:
            g.setPen(QPen(QColor(p.border), 1))
            g.drawRoundedRect(r, 8, 8)
            grid = QPen(QColor(p.border), 1, Qt.DashLine)
            g.setPen(grid)
            for f in (0.25, 0.5, 0.75):
                y = r.top() + r.height() * f
                g.drawLine(QPointF(r.left() + 1, y), QPointF(r.right() - 1, y))
            r = r.adjusted(2, 6, -2, -2)
        vals = list(self.values)
        known = [v for v in vals if v is not None]
        if len(known) < 2:
            return
        top = self.maximum or (max(known) * 1.15) or 1.0
        step = r.width() / (max(self.span, len(vals)) - 1)
        x0 = r.right() - step * (len(vals) - 1)
        hi, lo = QColor(accent), QColor(accent)
        hi.setAlpha(90 if not self.compact else 70)
        lo.setAlpha(0)
        grad = QLinearGradient(0, r.top(), 0, r.bottom())
        grad.setColorAt(0, hi)
        grad.setColorAt(1, lo)
        segments, seg = [], []                         # None (no sample: SAINT wasn't running) breaks the line
        for i, v in enumerate(vals):
            if v is None:
                segments, seg = segments + [seg] if seg else segments, []
            else:
                seg.append(QPointF(x0 + i * step, r.bottom() - min(1.0, v / top) * r.height()))
        segments += [seg] if seg else []
        g.setPen(QPen(accent, 1.4 if self.compact else 1.8))
        for seg in segments:
            path = QPainterPath(seg[0])
            for pt in seg[1:]:
                path.lineTo(pt)
            fill = QPainterPath(path)
            fill.lineTo(seg[-1].x(), r.bottom())
            fill.lineTo(seg[0].x(), r.bottom())
            g.fillPath(fill, grad)
            g.drawPath(path)
        pts = segments[-1]
        if not self.compact:                           # the live end-point
            halo = QColor(accent)
            halo.setAlpha(60)
            g.setPen(Qt.NoPen)
            g.setBrush(halo)
            g.drawEllipse(pts[-1], 6, 6)
            g.setBrush(accent)
            g.drawEllipse(pts[-1], 2.6, 2.6)


class DeviceTile(QFrame):
    """One device in the Performance list: its sparkline, name and current reading. Click to see it in detail."""
    clicked = Signal(str)

    def __init__(self, key, title, values, maximum=100.0):
        super().__init__()
        self.key = key
        self.setObjectName("DeviceTile")
        self.setCursor(Qt.PointingHandCursor)
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 8, 12, 8)
        h.setSpacing(12)
        self.graph = Graph(values, maximum, compact=True)
        self.graph.setFixedSize(68, 40)
        h.addWidget(self.graph)
        col = QVBoxLayout()
        col.setSpacing(1)
        self.title = QLabel(title)
        self.title.setStyleSheet("font-weight: 600;")
        self.sub = QLabel("—")
        self.sub.setObjectName("Muted")
        col.addWidget(self.title)
        col.addWidget(self.sub)
        h.addLayout(col, 1)

    def set_active(self, on):
        self.setObjectName("DeviceTileActive" if on else "DeviceTile")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, e):
        self.clicked.emit(self.key)
        super().mousePressEvent(e)


class PerCore(QWidget):
    """One small bar per logical CPU, filled to its current load."""

    def __init__(self):
        super().__init__()
        self.values = []
        self.setFixedHeight(46)
        self.setToolTip("Load of each logical processor")

    def paintEvent(self, _):
        if not self.values:
            return
        p = _palette()
        g = QPainter(self)
        w = self.width() / len(self.values)
        for i, v in enumerate(self.values):
            r = QRectF(i * w + 1, 0, max(2.0, w - 2), self.height())
            g.fillRect(r, QColor(p.border))
            h = r.height() * min(1.0, v / 100)
            g.fillRect(QRectF(r.left(), r.bottom() - h, r.width(), h), _tint(p.accent, 0.4 + v / 170))


class Stat(QWidget):
    """A small-caps label over a monospace value."""

    def __init__(self, label):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        lab = QLabel(label.upper())
        lab.setObjectName("StatLabel")
        f = lab.font()
        f.setLetterSpacing(QFont.AbsoluteSpacing, 1.0)
        lab.setFont(f)
        self.value = QLabel("—")
        self.value.setObjectName("ReadoutSmall")
        self.value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(lab)
        v.addWidget(self.value)


NUMERIC = ("pid", "cpu", "memory", "disk", "threads")
GROUP_ROLE = Qt.UserRole + 1                          # the group name on a group header row, None on a process row
USAGE_ROLE = Qt.UserRole + 2                          # 0..1 share of the machine, drawn as a bar under the number


class ProcessModel(QAbstractTableModel):
    """Processes in groups (Apps / Background / SAINT / System, core/sysinfo.GROUPS), each under a header row that
    sums it up and folds it away on a click. Header clicks sort inside every group."""
    COLS = [("Name", "name"), ("PID", "pid"), ("User", "user"), ("Status", "status"), ("CPU", "cpu"),
            ("Memory", "memory"), ("Disk", "disk"), ("Threads", "threads")]

    def __init__(self):
        super().__init__()
        self.groups = []                              # [(group, [procs])] as core/sysinfo.group_processes gives it
        self.rows = []                                # flattened: {"group": name, "procs": [...]} or a process dict
        self.collapsed = {"System"}                   # the system's own processes start folded away
        self.sort_key, self.descending = "cpu", True
        self.totals = {}                              # column key -> "23 %" shown above the column name
        self.ncpu = max(1, os.cpu_count() or 1)
        self.ram = 0
        try:
            import psutil
            self.ram = psutil.virtual_memory().total
        except Exception:
            pass

    # ---------------------------------------------------------------- content
    def set_totals(self, totals):
        self.totals = totals
        self.headerDataChanged.emit(Qt.Horizontal, 0, len(self.COLS) - 1)

    def set_groups(self, groups):
        self.beginResetModel()
        self.groups = groups
        self._flatten()
        self.endResetModel()

    def set_rows(self, rows):
        """A flat list (no grouping): kept for callers that just want rows."""
        self.set_groups([("Processes", rows)] if rows else [])

    def _flatten(self):
        self.rows = []
        for g, procs in self.groups:
            self.rows.append({"group": g, "procs": procs})
            if g not in self.collapsed:
                self.rows.extend(procs)

    def toggle(self, group):
        self.beginResetModel()
        self.collapsed ^= {group}
        self._flatten()
        self.endResetModel()

    def process(self, row):
        """The process dict on ``row``, or None for a group header."""
        r = self.rows[row] if 0 <= row < len(self.rows) else None
        return None if r is None or "group" in r else r

    def row_of(self, pid):
        return next((i for i, r in enumerate(self.rows) if r.get("pid") == pid), -1)

    def sort(self, column, order=Qt.AscendingOrder):
        self.sort_key, self.descending = self.COLS[column][1], order == Qt.DescendingOrder
        key = sysinfo.SORT_KEYS.get(self.sort_key, sysinfo.SORT_KEYS["cpu"])
        self.set_groups([(g, sorted(procs, key=key, reverse=self.descending)) for g, procs in self.groups])

    # ---------------------------------------------------------------- numbers
    def usage(self, p, key) -> float:
        """Share of the whole machine, 0..1: the length of the bar in the CPU and Memory columns."""
        if key == "cpu":
            return min(1.0, p["cpu"] / self.ncpu / 100.0)
        if key == "memory" and self.ram:
            return min(1.0, p["memory"] / self.ram)
        return 0.0

    def heat(self, p, key) -> float:
        """How hard a process works this resource, 0..1, for the cell's orange tint."""
        if key == "cpu":
            return p["cpu"] / self.ncpu / 25.0         # a quarter of the whole machine is full heat
        if key == "memory" and self.ram:
            return p["memory"] / self.ram / 0.08       # 8 % of RAM is full heat
        if key == "disk" and p["disk_read"] is not None:
            return ((p["disk_read"] or 0) + (p["disk_write"] or 0)) / (20 * 2 ** 20)
        return 0.0

    def _sum(self, procs, key):
        if key == "cpu":
            return f"{sum(p['cpu'] for p in procs) / self.ncpu:.1f} %"
        if key == "memory":
            return human_bytes(sum(p["memory"] for p in procs))
        if key == "disk":
            return human_bytes(sum((p["disk_read"] or 0) + (p["disk_write"] or 0) for p in procs), rate=True)
        return ""

    # ---------------------------------------------------------------- Qt
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            name, key = self.COLS[section]
            return f"{self.totals[key]}\n{name}" if key in self.totals else name
        if orientation == Qt.Horizontal and role == Qt.TextAlignmentRole:
            key = self.COLS[section][1]
            return int((Qt.AlignRight if key in NUMERIC else Qt.AlignLeft) | Qt.AlignBottom)
        return None

    def data(self, index, role=Qt.DisplayRole):
        r = self.rows[index.row()]
        key = self.COLS[index.column()][1]
        if "group" in r:
            return self._group_data(r, key, role)
        p = r
        if role == Qt.DisplayRole:
            if key == "cpu":                          # share of the whole machine, like the total above it
                return f"{p['cpu'] / self.ncpu:.1f} %"
            if key == "memory":
                return human_bytes(p["memory"])
            if key == "disk":
                if p["disk_read"] is None:
                    return "—"
                return human_bytes((p["disk_read"] or 0) + (p["disk_write"] or 0), rate=True)
            if key == "user":
                return p["user"].split("\\")[-1]
            return str(p[key])
        if role == Qt.TextAlignmentRole:
            return int((Qt.AlignRight if key in NUMERIC else Qt.AlignLeft) | Qt.AlignVCenter)
        if role == Qt.ToolTipRole:
            return p["command"] or p["name"]
        if role == Qt.ForegroundRole:
            if p["critical"] and key == "name":
                return QColor(_palette().warning)
            if key in ("pid", "user", "status", "threads"):
                return QColor(_palette().muted)
        if role == USAGE_ROLE and key in ("cpu", "memory"):
            return self.usage(p, key)
        if role == Qt.BackgroundRole and key == "disk":
            t = self.heat(p, key)
            return _tint(_palette().accent, t) if t > 0.02 else None
        if role == Qt.FontRole and key in NUMERIC:
            return _mono()
        return None

    def _group_data(self, r, key, role):
        if role == GROUP_ROLE:
            return r["group"]
        if role == Qt.DisplayRole:
            if key == "name":
                arrow = "▸" if r["group"] in self.collapsed else "▾"
                return f"{arrow}  {r['group']}  ({len(r['procs'])})"
            return self._sum(r["procs"], key)
        if role == Qt.TextAlignmentRole:
            return int((Qt.AlignRight if key in NUMERIC else Qt.AlignLeft) | Qt.AlignVCenter)
        if role == Qt.FontRole:
            f = QFont(_mono() if key in NUMERIC else QApplication.font())
            f.setBold(True)
            return f
        if role == Qt.ToolTipRole:
            return f"{r['group']}: click to {'show' if r['group'] in self.collapsed else 'hide'} its processes"
        return None


class _ProcDelegate(QStyledItemDelegate):
    """Group header rows on a soft band; a usage bar under the CPU and Memory numbers; the disk heat tint."""

    def paint(self, painter, option, index):
        p = _palette()
        rect = QRectF(option.rect)
        if index.data(GROUP_ROLE):
            painter.fillRect(rect, QColor(p.surface2))
        else:
            bg = index.data(Qt.BackgroundRole)
            if isinstance(bg, QColor):
                painter.fillRect(rect.adjusted(1, 1, -1, -1), bg)
        super().paint(painter, option, index)
        share = index.data(USAGE_ROLE)
        if share is None:
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        track = QRectF(rect.left() + 10, rect.bottom() - 8, rect.width() - 20, 3)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(p.border_strong))
        painter.drawRoundedRect(track, 1.5, 1.5)
        if share > 0.002:
            fill = QRectF(track)
            fill.setWidth(max(3.0, track.width() * share))
            painter.setBrush(QColor(p.danger if share > 0.6 else p.accent))
            painter.drawRoundedRect(fill, 1.5, 1.5)
        painter.restore()


def _table_style():
    """The Processes table's look, shared by every table in the Task Manager."""
    return (f"QHeaderView::section {{ padding: 8px 18px 8px 10px; color: {_palette().muted}; }}"
            "QTableView::item { padding: 6px 10px; }")


def _style_table(t):
    t.setStyleSheet(_table_style())
    t.verticalHeader().hide()
    t.verticalHeader().setDefaultSectionSize(40)
    t.setShowGrid(False)
    t.setWordWrap(False)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    head = t.horizontalHeader()
    head.setMinimumHeight(40)
    head.setHighlightSections(False)
    motion.smooth_scroll(t)


SORT_ROLE = Qt.UserRole + 3                           # what a cell sorts by: the number behind "1.2 GB", not the text
KEY_ROLE = Qt.UserRole + 4                            # the row's real identity (a unit file name, an app's file)


class _Item(QTableWidgetItem):
    def __lt__(self, other):
        a, b = self.data(SORT_ROLE), other.data(SORT_ROLE)
        if a is not None and b is not None:
            return a < b
        return self.text().lower() < other.text().lower()


class _Table(QTableWidget):
    """A table in the Processes style: right-aligned tabular numbers, a usage bar where a cell has a share, sorting by
    the real value, and a plain sentence in place of an empty list."""

    def __init__(self, headers, numeric=(), widths=None, stretch=0, empty="", sortable=True):
        super().__init__(0, len(headers))
        self.numeric = set(numeric)
        self.sortable = sortable
        self.empty_text = empty
        self.setHorizontalHeaderLabels(headers)
        for c in range(len(headers)):
            self.horizontalHeaderItem(c).setTextAlignment(
                int((Qt.AlignRight if c in self.numeric else Qt.AlignLeft) | Qt.AlignVCenter))
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setItemDelegate(_ProcDelegate(self))
        _style_table(self)
        head = self.horizontalHeader()
        head.setSectionResizeMode(QHeaderView.Interactive)
        head.setSectionResizeMode(stretch, QHeaderView.Stretch)
        for c, w in (widths or {}).items():
            self.setColumnWidth(c, w)
        self.setSortingEnabled(sortable)

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.rowCount() or not self.empty_text:
            return
        g = QPainter(self.viewport())
        g.setPen(QColor(_palette().muted))
        g.drawText(self.viewport().rect().adjusted(40, 0, -40, 0), Qt.AlignCenter | Qt.TextWordWrap, self.empty_text)

    def key(self, row):
        """The real identity of ``row`` (KEY_ROLE on its first cell, else its text), or None."""
        item = self.item(row, 0) if row >= 0 else None
        return None if item is None else (item.data(KEY_ROLE) or item.text())


def cell(text, sort=None, usage=None, color=None, tip=None, key=None, group=None):
    """One table cell: its text, plus what it sorts by, a 0..1 usage bar, a text colour, a tooltip, the row's key, or
    (on a section row) the section name."""
    return {"text": text, "sort": sort, "usage": usage, "color": color, "tip": tip, "key": key, "group": group}


def _fill(table, rows):
    """Fill ``table`` from rows of cells (plain values or cell(...)); the selected row stays selected."""
    keep = table.key(table.currentRow())
    table.setSortingEnabled(False)
    table.setRowCount(len(rows))
    for r, cells in enumerate(rows):
        for c, val in enumerate(cells):
            d = val if isinstance(val, dict) else cell("" if val is None else str(val),
                                                        sort=val if isinstance(val, (int, float)) else None)
            item = _Item(str(d["text"]))
            if d["sort"] is not None:
                item.setData(SORT_ROLE, d["sort"])
            for role, v in ((USAGE_ROLE, d["usage"]), (Qt.ForegroundRole, d["color"] and QColor(d["color"])),
                            (Qt.ToolTipRole, d["tip"]), (KEY_ROLE, d["key"]), (GROUP_ROLE, d["group"])):
                if v is not None:
                    item.setData(role, v)
            numeric = c in table.numeric
            item.setTextAlignment(int((Qt.AlignRight if numeric else Qt.AlignLeft) | Qt.AlignVCenter))
            if numeric:
                item.setFont(_mono())
            if d["group"]:
                f = QFont(QApplication.font())
                f.setBold(True)
                item.setFont(f)
            table.setItem(r, c, item)
    table.setSortingEnabled(table.sortable)
    if keep is not None:
        row = next((r for r in range(table.rowCount()) if table.key(r) == keep), -1)
        if row >= 0:
            table.selectRow(row)


def _status(v):
    """The faint one-line summary under a table, as on the Processes page."""
    s = QLabel("")
    s.setObjectName("Faint")
    v.addWidget(s)
    return s


def _search(placeholder, on_change):
    s = QLineEdit()
    s.setPlaceholderText(placeholder)
    s.setClearButtonEnabled(True)
    s.textChanged.connect(lambda _t: on_change())
    return s


def _page(title, sub=""):
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(24, 20, 24, 20)
    v.setSpacing(12)
    t = QLabel(title)
    t.setObjectName("PageTitle")
    v.addWidget(t)
    if sub:
        s = QLabel(sub)
        s.setObjectName("PageSubtitle")
        s.setWordWrap(True)
        v.addWidget(s)
    return w, v


# --------------------------------------------------------------------------- window
class TaskManager(QMainWindow):
    def __init__(self):
        super().__init__()
        from ui.components.side_rail import SideRail
        self.setWindowTitle("SAINT Task Manager")
        self.resize(1160, 740)
        self.procs = []
        self.sampler = sysinfo.ProcessSampler()
        self.rates = sysinfo.RateSampler()
        self.latest = {}
        root = QWidget()
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        self.rail = SideRail("SAINT · Halo", "Task Manager", [(p, PAGE_ICONS[p]) for p in PAGES],
                             footer="Ctrl+Shift+Esc opens this anywhere")
        self.nav = self.rail.nav
        self.stack = QStackedWidget()
        h.addWidget(self.rail)
        h.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        builders = [self._build_processes, self._build_performance, self._build_history, self._build_startup,
                    self._build_users, self._build_services, self._build_system]
        for b in builders:
            self.stack.addWidget(b())
        self._proc_graph_tiles()
        self.nav.currentRowChanged.connect(self._switch)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: (self.nav.setCurrentRow(0), self.search.setFocus()))
        QShortcut(QKeySequence(Qt.Key_Delete), self, activated=self._end_selected)
        QShortcut(QKeySequence("Shift+Delete"), self, activated=lambda: self._end_selected(tree=True))
        self.nav.setCurrentRow(0)

    # ---------------------------------------------------------------- lifecycle
    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()
        self.timer.start(REFRESH_MS)

    def hideEvent(self, e):
        super().hideEvent(e)
        self.timer.stop()

    def _switch(self, i):
        self.stack.setCurrentIndex(i)
        motion.fade_in(self.stack.currentWidget(), motion.FAST)
        self.refresh(full=True)

    def refresh(self, full=False):
        page = PAGES[self.stack.currentIndex()]
        if page in ("Processes", "Users", "App history"):
            self.procs = self.sampler.sample()
        # The graphs keep their history while other pages are shown.
        self._refresh_performance(visible=page == "Performance")
        {"Processes": self._refresh_processes, "Users": self._refresh_users,
         "App history": self._refresh_history if full else lambda: None,
         "Startup apps": self._refresh_startup if full else lambda: None,
         "Services": self._refresh_services if full else lambda: None,
         "System information": self._refresh_system if full else lambda: None,
         "Performance": lambda: None}[page]()

    # ---------------------------------------------------------------- processes
    def _build_processes(self):
        w, v = _page("Processes", "Grouped like you'd think of them: apps you opened, their helpers, SAINT, and the "
                                  "system. Click a group to fold it; amber names keep the desktop running.")
        self.proc_graphs = QHBoxLayout()               # CPU and Memory at a glance; filled once Performance exists
        self.proc_graphs.setSpacing(10)
        v.addLayout(self.proc_graphs)
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name, PID or command   (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self._refresh_processes())
        bar.addWidget(self.search, 1)
        self.only_mine = QCheckBox("Only my processes")
        self.only_mine.toggled.connect(lambda _c: self._refresh_processes())
        bar.addWidget(self.only_mine)
        self.kill_btn = QPushButton("End now")
        self.kill_btn.setObjectName("Ghost")
        self.kill_btn.setToolTip("Force it (SIGKILL): unsaved work in that app is lost")
        self.kill_btn.clicked.connect(lambda: self._end_selected(force=True))
        self.tree_btn = QPushButton("End process tree")
        self.tree_btn.setToolTip("End it and every process it started (Shift+Delete)")
        self.tree_btn.clicked.connect(lambda: self._end_selected(tree=True))
        self.end_btn = QPushButton("End task")
        self.end_btn.setObjectName("Primary")
        self.end_btn.setToolTip("Ask it to quit (Delete)")
        self.end_btn.clicked.connect(self._end_selected)
        for b in (self.kill_btn, self.tree_btn, self.end_btn):
            bar.addWidget(b)
        v.addLayout(bar)
        self.model = ProcessModel()
        self.table = QTableView()
        self.table.setObjectName("ProcTable")
        self.table.setItemDelegate(_ProcDelegate(self.table))
        self.table.setStyleSheet(_table_style())
        self.table.setModel(self.model)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(4, Qt.DescendingOrder)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.clicked.connect(self._proc_clicked)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._proc_menu)
        head = self.table.horizontalHeader()
        head.setMinimumHeight(52)
        head.setHighlightSections(False)
        head.setSectionResizeMode(0, QHeaderView.Stretch)
        for col, width in ((1, 84), (2, 120), (3, 100), (4, 110), (5, 120), (6, 110), (7, 84)):
            self.table.setColumnWidth(col, width)
        motion.smooth_scroll(self.table)
        v.addWidget(self.table, 1)
        self.proc_status = QLabel("")
        self.proc_status.setObjectName("Faint")
        v.addWidget(self.proc_status)
        return w

    def _proc_graph_tiles(self):
        """CPU and Memory sparklines over the process list, sharing the Performance page's history."""
        self.proc_tiles = {}
        for key in ("cpu", "mem"):
            d = self.devices[key]
            tile = DeviceTile(key, d["title"], d["values"], d["max"])
            tile.setObjectName("DeviceTileActive")
            tile.setToolTip("Open it on the Performance page")
            tile.clicked.connect(lambda k: (self.nav.setCurrentRow(PAGES.index("Performance")), self._select(k)))
            self.proc_graphs.addWidget(tile, 1)
            self.proc_tiles[key] = tile
        self.proc_graphs.addStretch(1)

    def _me(self):
        try:
            import getpass
            return getpass.getuser()
        except Exception:
            return ""

    def _refresh_processes(self):
        sel = self._selected_pid()
        me = self._me()
        rows = sysinfo.filter_processes(self.procs, self.search.text(), me if self.only_mine.isChecked() else "")
        lt = self.latest
        if lt:
            self.model.set_totals({"cpu": f"{lt['cpu']:.0f} %", "memory": f"{lt['mem']:.0f} %",
                                   "disk": human_bytes(lt["disk"], True)})
            for key, tile in getattr(self, "proc_tiles", {}).items():
                tile.sub.setText(self.devices[key]["tile"].sub.text())
                tile.graph.update()
        self.model.set_groups(sysinfo.group_processes(rows, me, self.model.sort_key, self.model.descending))
        if sel is not None and self.model.row_of(sel) >= 0:
            self.table.selectRow(self.model.row_of(sel))
        self.proc_status.setText(f"{len(rows)} shown of {len(self.procs)} processes")

    def _proc_clicked(self, index):
        group = index.data(GROUP_ROLE)
        if group:
            self.model.toggle(group)

    def _proc_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid() or self.model.process(index.row()) is None:
            return
        self.table.selectRow(index.row())
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.addAction("End task", self._end_selected)
        menu.addAction("End process tree", lambda: self._end_selected(tree=True))
        menu.addAction("End now (force)", lambda: self._end_selected(force=True))
        menu.addSeparator()
        menu.addAction("Copy command line",
                       lambda: QApplication.clipboard().setText(self.model.process(index.row())["command"]))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _selected_pid(self):
        idx = self.table.selectionModel().selectedRows() if hasattr(self, "table") else []
        p = self.model.process(idx[0].row()) if idx else None
        return p["pid"] if p else None

    def _end_selected(self, force=False, tree=False):
        pid = self._selected_pid()
        if pid is None:
            self.proc_status.setText("Select a process first.")
            return
        p = next((p for p in self.procs if p["pid"] == pid), None)
        if p is None:
            return
        kids = sysinfo.descendants(self.procs, pid) if tree else []
        if p["critical"] or any(k["critical"] for k in kids):
            ok = QMessageBox.warning(
                self, "End a system process?",
                f"{p['name']} keeps your desktop or system running. Ending it can close your session or stop the "
                "computer from working until you restart.\n\nEnd it anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ok != QMessageBox.Yes:
                return
        elif tree and kids:
            names = ", ".join(sorted({k["name"] for k in kids})[:6])
            if QMessageBox.question(self, "End process tree?",
                                    f"End {p['name']} and the {len(kids)} processes it started ({names})? "
                                    "Unsaved work in them may be lost.") != QMessageBox.Yes:
                return
        elif force:
            if QMessageBox.question(self, "End now?", f"Force {p['name']} to stop? Unsaved work in it is lost.") \
                    != QMessageBox.Yes:
                return
        self.proc_status.setText(sysinfo.end_process_tree(pid, force=force) if tree else
                                 sysinfo.end_process(pid, force=force))
        self.procs = self.sampler.sample()
        self._refresh_processes()

    # ---------------------------------------------------------------- performance
    def _build_performance(self):
        """Devices down the left, each with its sparkline; the chosen one large on the right."""
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        left = QScrollArea()
        left.setWidgetResizable(True)
        left.setFrameShape(QFrame.NoFrame)
        left.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left.setFixedWidth(250)
        tiles = QWidget()
        self.tile_box = QVBoxLayout(tiles)
        self.tile_box.setContentsMargins(14, 20, 6, 20)
        self.tile_box.setSpacing(4)
        self.tile_box.addStretch()
        left.setWidget(tiles)
        h.addWidget(left)
        rule = QFrame()
        rule.setFixedWidth(1)
        rule.setStyleSheet(f"background: {_palette().border};")
        h.addWidget(rule)

        detail = QWidget()
        v = QVBoxLayout(detail)
        v.setContentsMargins(28, 22, 28, 22)
        v.setSpacing(14)
        top = QHBoxLayout()
        names = QVBoxLayout()
        names.setSpacing(2)
        self.d_title = QLabel("CPU")
        self.d_title.setObjectName("PageTitle")
        self.d_model = QLabel("")
        self.d_model.setObjectName("Muted")
        self.d_model.setTextInteractionFlags(Qt.TextSelectableByMouse)
        names.addWidget(self.d_title)
        names.addWidget(self.d_model)
        top.addLayout(names, 1)
        self.d_value = QLabel("—")
        self.d_value.setObjectName("Readout")
        self.d_value.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        top.addWidget(self.d_value)
        v.addLayout(top)
        axis_row = QHBoxLayout()
        self.d_axis = QLabel("")
        self.d_axis.setObjectName("Muted")
        axis_row.addWidget(self.d_axis, 1)
        self.d_range = QComboBox()
        for r in RANGES:
            self.d_range.addItem(RANGE_LABELS[r], r)
        self.d_range.setToolTip("History is kept while SAINT runs: a point per 10 s for an hour, "
                                "per minute for a day, per 10 minutes for a week")
        self.d_range.currentTextChanged.connect(lambda _t: self._show_detail())
        axis_row.addWidget(self.d_range)
        v.addLayout(axis_row)
        self.d_graph = Graph()
        v.addWidget(self.d_graph, 1)
        self.d_cores = PerCore()
        v.addWidget(self.d_cores)
        self.d_stats = QGridLayout()
        self.d_stats.setHorizontalSpacing(28)
        self.d_stats.setVerticalSpacing(14)
        v.addLayout(self.d_stats)
        h.addWidget(detail, 1)

        self.devices = {}
        self.selected = "cpu"
        self.cpu_static = sysinfo.cpu_info()
        self._gpu_at = 0.0
        self._gpus = []
        self._nv, self._nv_procs = [], []
        self._history = None
        self._device("cpu", "CPU")
        self._device("mem", "Memory")
        self._select("cpu")
        return w

    def _device(self, key, title, maximum=100.0):
        if key not in self.devices:
            values = deque(maxlen=HISTORY)
            tile = DeviceTile(key, title, values, maximum)
            tile.clicked.connect(self._select)
            self.tile_box.insertWidget(self.tile_box.count() - 1, tile)
            self.devices[key] = {"title": title, "values": values, "max": maximum, "tile": tile, "model": "",
                                 "value": "—", "stats": [], "axis": ""}
        return self.devices[key]

    def _select(self, key):
        self.selected = key
        for k, d in self.devices.items():
            d["tile"].set_active(k == key)
        d = self.devices[key]
        self.d_graph.maximum = d["max"]
        self._show_detail()

    def _graph_values(self, key):
        """The selected range's points for a device: its live deque, or the stored history."""
        rng = self.d_range.currentData()
        if rng == "Live":
            return self.devices[key]["values"], HISTORY
        metric = "cpu" if key == "cpu" else "mem" if key == "mem" else "gpu" if key.startswith("gpu") else \
            "disk" if key.startswith("disk:") else "net"
        try:
            if self._history is None:
                from core.sys_history import History
                self._history = History()
            vals = self._history.series(rng, metric)
        except Exception:
            vals = []
        return vals, max(2, len(vals))

    def _show_detail(self):
        d = self.devices[self.selected]
        self.d_title.setText(d["title"])
        self.d_model.setText(d["model"])
        self.d_value.setText(d["value"])
        rng = self.d_range.currentData()
        self.d_graph.values, self.d_graph.span = self._graph_values(self.selected)
        if rng == "Live":
            self.d_axis.setText(d["axis"])
        else:
            what = d["axis"].split(" over ")[0]
            if self.selected.startswith(("disk:", "net:")):
                what = "all disks combined (bytes/s)" if self.selected.startswith("disk:") else \
                    "all networks combined (bytes/s)"
            has = any(x is not None for x in self.d_graph.values)
            self.d_axis.setText(f"{what} over {RANGE_WORDS[rng]}  ·  " +
                                ("gaps: SAINT wasn't running" if has else "no history yet (kept while SAINT runs)"))
        self.d_cores.setVisible(self.selected == "cpu")
        if [s for s, _ in d["stats"]] != getattr(self, "_stat_keys", None):
            while self.d_stats.count():
                item = self.d_stats.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self._stat_widgets = []
            for i, (label, _val) in enumerate(d["stats"]):
                s = Stat(label)
                self.d_stats.addWidget(s, i // 4, i % 4)
                self._stat_widgets.append(s)
            self._stat_keys = [s for s, _ in d["stats"]]
        for s, (_label, val) in zip(self._stat_widgets, d["stats"]):
            s.value.setText(val)
        self.d_graph.update()

    def _set(self, key, value, sub, model, stats, axis):
        d = self.devices[key]
        d.update(value=value, model=model, stats=stats, axis=axis)
        d["tile"].sub.setText(sub)
        d["tile"].graph.update()

    def _refresh_performance(self, visible=True):
        import psutil
        cores = psutil.cpu_percent(percpu=True)
        cpu = sum(cores) / len(cores) if cores else 0.0
        self.d_cores.values = cores
        mem = sysinfo.memory()
        rates = self.rates.sample()
        now = time.monotonic()
        if now - self._gpu_at > 4:                    # nvidia-smi is slow-ish: every 4 s is plenty
            self._gpu_at, self._gpus = now, sysinfo.gpus()
            if any(g["vendor"] == "NVIDIA" for g in self._gpus):
                self._nv, self._nv_procs = sysinfo.nvidia_detail(), sysinfo.gpu_processes(names=_proc_name)
        disk_total = sum((d["read"] or 0) + (d["write"] or 0) for d in rates["disks"].values())
        self.latest = {"cpu": cpu, "mem": mem["percent"], "disk": disk_total}

        c = self.cpu_static
        freq = psutil.cpu_freq()
        temp = sysinfo.cpu_temp()
        speed = f"{freq.current / 1000:.2f} GHz" if freq else "not available"
        self.devices["cpu"]["values"].append(cpu)
        self._set("cpu", f"{cpu:.0f}%", f"{cpu:.0f}%  ·  {speed}", c["model"],
                  [("Utilization", f"{cpu:.0f} %"), ("Speed", speed),
                   ("Temperature", f"{temp} °C" if temp is not None else "not available"),
                   ("Processes", str(len(self.procs) or len(psutil.pids()))),
                   ("Cores", str(c["cores"])), ("Threads", str(c["threads"])),
                   ("Up for", human_duration(time.time() - psutil.boot_time()))],
                  "% utilization over 2 minutes")
        self.devices["mem"]["values"].append(mem["percent"])
        self._set("mem", f"{mem['percent']:.0f}%",
                  f"{human_bytes(mem['used'])} of {human_bytes(mem['total'])}",
                  f"{human_bytes(mem['total'])} installed",
                  [("In use", human_bytes(mem["used"])), ("Available", human_bytes(mem["available"])),
                   ("Swap used", human_bytes(mem["swap_used"])), ("Swap size", human_bytes(mem["swap_total"]))],
                  "% of memory in use over 2 minutes")
        for i, g in enumerate(self._gpus):
            key = f"gpu{i}"
            self._device(key, f"GPU {i}")["values"].append(g["percent"] or 0)
            pct = "—" if g["percent"] is None else f"{g['percent']:.0f}%"
            vram = (f"{human_bytes(g['memory_used'])} / {human_bytes(g['memory_total'])}" if g["memory_total"]
                    else "not reported")
            self._set(key, pct, f"{pct}  ·  {g['temp_c']} °C" if g["temp_c"] is not None else pct,
                      f"{g['name']}  ·  {g['driver'] or 'driver unknown'}",
                      [("Utilization", pct.replace("%", " %")), ("Video memory", vram),
                       ("Temperature", f"{g['temp_c']} °C" if g["temp_c"] is not None else "not available"),
                       ("Vendor", g["vendor"])] + (_nvidia_stats(self._nv, self._nv_procs, i)
                                                   if g["vendor"] == "NVIDIA" else []),
                      "% utilization over 2 minutes")
        for name, d in rates["disks"].items():
            key = f"disk:{name}"
            self._device(key, f"Disk {name}")["values"].append(d["busy"] or 0)
            busy = "—" if d["busy"] is None else f"{d['busy']:.0f}%"
            self._set(key, busy, ("" if d["busy"] is None else f"{busy}  ·  ") + f"Read {human_bytes(d['read'], True)}", f"/dev/{name}" if os.name != "nt" else name,
                      [("Active time", busy.replace("%", " %")), ("Read", human_bytes(d["read"], True)),
                       ("Write", human_bytes(d["write"], True))],
                      "% of time the disk was busy over 2 minutes")
        for name, n in rates["networks"].items():
            if not n["up"]:
                continue
            key = f"net:{name}"
            total = (n["recv"] or 0) + (n["sent"] or 0)
            self._device(key, name, maximum=0)["values"].append(total)
            self._set(key, human_bytes(total, True),
                      f"↓ {human_bytes(n['recv'], True)}  ↑ {human_bytes(n['sent'], True)}",
                      f"Link {n['speed_mbps']} Mb/s" if n["speed_mbps"] else "link speed not reported",
                      [("Receive", human_bytes(n["recv"], True)), ("Send", human_bytes(n["sent"], True)),
                       ("Link speed", f"{n['speed_mbps']} Mb/s" if n["speed_mbps"] else "not reported")],
                      "throughput over 2 minutes (scale follows the peak)")
        if visible:
            self._show_detail()

    # ---------------------------------------------------------------- app history
    def _build_history(self):
        w, v = _page("App history", "How much processor time each app has used since it started. Linux keeps no "
                                    "history across restarts, so this begins when each app started.")
        self.hist_search = _search("Search apps", self._show_history)
        v.addWidget(self.hist_search)
        self.hist_table = _Table(["App", "Processor time", "Processes", "Running for"], numeric=(1, 2, 3),
                                 widths={1: 170, 2: 110, 3: 140}, empty="No app has used the processor yet.")
        self.hist_table.sortByColumn(1, Qt.DescendingOrder)
        v.addWidget(self.hist_table, 1)
        self.hist_status = _status(v)
        self.hist_rows = []
        return w

    def _refresh_history(self):
        self.hist_rows = sysinfo.app_history(self.procs or self.sampler.sample())
        self._show_history()

    def _show_history(self):
        q = self.hist_search.text().strip().lower()
        rows = [a for a in self.hist_rows if not q or q in a["name"].lower()][:300]
        total = sum(a["cpu_seconds"] for a in self.hist_rows) or 1
        now = time.time()
        _fill(self.hist_table, [(
            a["name"],
            cell(human_duration(a["cpu_seconds"]) if a["cpu_seconds"] >= 60 else f"{a['cpu_seconds']:.1f} s",
                 sort=a["cpu_seconds"], usage=a["cpu_seconds"] / total,
                 tip=f"{a['cpu_seconds'] / total:.0%} of all processor time used"),
            a["processes"],
            cell(human_duration(now - a["since"]) if a["since"] else "—", sort=now - a["since"] if a["since"] else -1,
                 tip=time.strftime("Started %d %b %H:%M", time.localtime(a["since"])) if a["since"] else None))
            for a in rows])
        total = sum(a["cpu_seconds"] for a in self.hist_rows)
        self.hist_status.setText(f"{len(rows)} shown of {len(self.hist_rows)} apps  ·  "
                                 f"{human_duration(total) if total >= 60 else f'{total:.0f} s'} of processor time in all")

    # ---------------------------------------------------------------- startup
    SCOPE_WORDS = {"user": "Only you", "system": "Everyone on this PC", "system+user": "Everyone (changed for you)"}

    def _build_startup(self):
        w, v = _page("Startup apps", "Apps that start by themselves when you sign in. Turning one off only "
                                     "affects you, and you can turn it back on any time.")
        self.start_search = _search("Search startup apps", self._show_startup)
        v.addWidget(self.start_search)
        self.start_table = _Table(["App", "Starts at sign-in", "Applies to", "Command"], widths={0: 240, 1: 150, 2: 210},
                                  stretch=3, empty="No apps start by themselves when you sign in.")
        self.start_table.sortByColumn(0, Qt.AscendingOrder)
        self.start_table.itemSelectionChanged.connect(self._startup_buttons)
        v.addWidget(self.start_table, 1)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.start_msg = QLabel("")
        self.start_msg.setObjectName("Muted")
        row.addWidget(self.start_msg, 1)
        self.start_off = QPushButton("Turn off")
        self.start_off.setToolTip("Don't start it when you sign in")
        self.start_on = QPushButton("Turn on")
        self.start_on.setToolTip("Start it when you sign in")
        self.start_on.clicked.connect(lambda: self._toggle_startup(True))
        self.start_off.clicked.connect(lambda: self._toggle_startup(False))
        row.addWidget(self.start_off)
        row.addWidget(self.start_on)
        v.addLayout(row)
        self.start_status = _status(v)
        self.startup = []
        self._startup_buttons()
        return w

    def _refresh_startup(self):
        self.startup = sysinfo.autostart_entries()     # none where there are no autostart folders (Windows)
        self._show_startup()

    def _show_startup(self):
        p = _palette()
        q = self.start_search.text().strip().lower()
        shown = [e for e in self.startup if not q or q in e["name"].lower() or q in e["command"].lower()]
        _fill(self.start_table, [(cell(e["name"], key=e["file"], tip=e["path"]),
                                  cell("On" if e["enabled"] else "Off", color=p.success if e["enabled"] else p.muted),
                                  self.SCOPE_WORDS.get(e["scope"], e["scope"]),
                                  cell(e["command"], color=p.muted, tip=e["command"])) for e in shown])
        on = sum(e["enabled"] for e in self.startup)
        self.start_status.setText(f"{on} of {len(self.startup)} apps start when you sign in")
        self._startup_buttons()

    def _selected_startup(self):
        key = self.start_table.key(self.start_table.currentRow()) if self.start_table.selectedItems() else None
        return next((e for e in self.startup if e["file"] == key), None)

    def _startup_buttons(self):
        e = self._selected_startup()
        self.start_on.setEnabled(bool(e) and not e["enabled"])
        self.start_off.setEnabled(bool(e) and e["enabled"])

    def _toggle_startup(self, enabled):
        entry = self._selected_startup()
        if entry is None:
            self.start_msg.setText("Select an app first.")
            return
        try:
            self.start_msg.setText(sysinfo.set_autostart(entry, enabled) + ".")
        except OSError as e:
            self.start_msg.setText(f"Couldn't change it: {e}")
        self._refresh_startup()

    # ---------------------------------------------------------------- users
    def _build_users(self):
        w, v = _page("Users", "Who is signed in, and how much of this PC their programs use. Accounts without a "
                              "session belong to the system or to a service.")
        self.user_table = _Table(["User", "Signed in", "Since", "Processes", "CPU", "Memory"], numeric=(3, 4, 5),
                                 widths={1: 150, 2: 150, 3: 110, 4: 120, 5: 130}, empty="No one is signed in.")
        self.user_table.sortByColumn(5, Qt.DescendingOrder)
        v.addWidget(self.user_table, 1)
        self.user_status = _status(v)
        return w

    def _refresh_users(self):
        ncpu, ram = self.model.ncpu, self.model.ram
        users = sysinfo.users(self.procs)
        _fill(self.user_table, [(
            u["name"],
            cell(f"{u['sessions']} session{'s' if u['sessions'] != 1 else ''}" if u["sessions"] else "No (system)",
                 sort=u["sessions"], color=None if u["sessions"] else _palette().muted),
            cell(time.strftime("%d %b %H:%M", time.localtime(u["since"])) if u["since"] else "—", sort=u["since"] or 0),
            u["processes"],
            cell(f"{u['cpu'] / ncpu:.1f} %", sort=u["cpu"], usage=min(1.0, u["cpu"] / ncpu / 100)),   # share of the PC
            cell(human_bytes(u["memory"]), sort=u["memory"], usage=min(1.0, u["memory"] / ram) if ram else None))
            for u in users])
        signed = sum(1 for u in users if u["sessions"])
        self.user_status.setText(f"{signed} signed in  ·  {len(users)} accounts running programs")

    # ---------------------------------------------------------------- services
    SERVICE_BUTTONS = [("start", "Start", "Start it now"), ("stop", "Stop", "Stop it now"),
                       ("restart", "Restart", "Stop it and start it again"),
                       ("enable", "Start at boot", "Start it every time the PC starts"),
                       ("disable", "Don't start at boot", "Don't start it when the PC starts")]

    @staticmethod
    def service_status(s):
        """Plain words (and a palette colour name) for a unit's active/sub state."""
        if s["active"] == "failed":
            return "Failed", "danger"
        if s["active"] == "active":
            return ("Running", "success") if s["sub"] == "running" else ("Done", "muted") if s["sub"] == "exited" \
                else (s["sub"].capitalize(), "text")
        if s["active"] in ("activating", "reloading"):
            return "Starting", "warning"
        if s["active"] == "deactivating":
            return "Stopping", "warning"
        return "Stopped", "muted"

    BOOT_WORDS = {"enabled": "Yes", "enabled-runtime": "Yes (this boot)", "disabled": "No", "static": "When needed",
                  "indirect": "When needed", "generated": "Automatic", "masked": "Blocked", "alias": "Alias", "": "—"}

    def _build_services(self):
        w, v = _page("Services", "Programs that run in the background (systemd). Changing a system service asks "
                                 "for your password.")
        top = QHBoxLayout()
        top.setSpacing(8)
        self.svc_scope = QComboBox()
        self.svc_scope.addItems(["System services", "My services"])
        self.svc_scope.currentIndexChanged.connect(lambda _i: self._refresh_services())
        self.svc_show = QComboBox()
        self.svc_show.addItems(["All", "Running", "Stopped", "Failed"])
        self.svc_show.setToolTip("Show only services in this state")
        self.svc_show.currentIndexChanged.connect(lambda _i: self._show_services())
        self.svc_filter = _search("Search services by name or description", self._show_services)
        top.addWidget(self.svc_scope)
        top.addWidget(self.svc_show)
        top.addWidget(self.svc_filter, 1)
        v.addLayout(top)
        self.svc_table = _Table(["Service", "Description", "Status", "Starts at boot"], widths={0: 260, 2: 120, 3: 150},
                                stretch=1, empty="No services to show.")
        self.svc_table.sortByColumn(0, Qt.AscendingOrder)
        self.svc_table.itemSelectionChanged.connect(self._service_buttons)
        v.addWidget(self.svc_table, 1)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.svc_msg = QLabel("")
        self.svc_msg.setObjectName("Muted")
        self.svc_msg.setWordWrap(True)
        row.addWidget(self.svc_msg, 1)
        self.svc_buttons = {}
        for action, label, tip in self.SERVICE_BUTTONS:
            b = QPushButton(label)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, a=action: self._service_action(a))
            row.addWidget(b)
            self.svc_buttons[action] = b
        v.addLayout(row)
        self.svc_status = _status(v)
        self.svc_rows = []
        self._service_buttons()
        return w

    def _refresh_services(self):
        self.svc_rows = sysinfo.services(user=self.svc_scope.currentIndex() == 1)
        no_systemd = os.name == "nt" or not __import__("shutil").which("systemctl")
        self.svc_table.empty_text = ("Services are managed by systemd, which this system doesn't have." if no_systemd
                                     else "No services match." if self.svc_rows else "No services to show.")
        self._show_services()

    def _show_services(self):
        p = _palette()
        q = self.svc_filter.text().strip().lower()
        want = self.svc_show.currentText()
        shown = []
        for s in self.svc_rows:
            word, colour = self.service_status(s)
            if q and q not in s["name"].lower() and q not in s["description"].lower():
                continue
            if want != "All" and word != want:
                continue
            shown.append(s)
            s["_status"] = (word, getattr(p, colour))
        _fill(self.svc_table, [(cell(s["name"].removesuffix(".service"), key=s["name"], tip=s["name"]),
                                cell(s["description"], tip=s["description"]),
                                cell(s["_status"][0], color=s["_status"][1]),
                                cell(self.BOOT_WORDS.get(s["enabled"], s["enabled"]),
                                     color=p.muted if s["enabled"] not in ("enabled", "enabled-runtime") else None))
                               for s in shown])
        words = [self.service_status(s)[0] for s in self.svc_rows]
        failed = words.count("Failed")
        self.svc_status.setText(f"{len(shown)} shown of {len(self.svc_rows)} services  ·  {words.count('Running')} running"
                                + (f"  ·  {failed} failed" if failed else ""))
        self._service_buttons()

    def _service_buttons(self):
        name = self.svc_table.key(self.svc_table.currentRow()) if self.svc_table.selectedItems() else None
        s = next((s for s in self.svc_rows if s["name"] == name), None)
        running = bool(s) and s["active"] in ("active", "activating", "reloading")
        at_boot = bool(s) and s["enabled"] in ("enabled", "enabled-runtime")
        fixed = bool(s) and s["enabled"] in ("static", "indirect", "generated", "masked", "alias", "")
        for action, b in self.svc_buttons.items():
            b.setEnabled(bool(s) and {"start": not running, "stop": running, "restart": running,
                                      "enable": not at_boot and not fixed, "disable": at_boot}[action])

    def _service_action(self, action):
        name = self.svc_table.key(self.svc_table.currentRow()) if self.svc_table.selectedItems() else None
        if not name:
            self.svc_msg.setText("Select a service first.")
            return
        label = dict((a, l) for a, l, _t in self.SERVICE_BUTTONS)[action]
        user = self.svc_scope.currentIndex() == 1
        if action in ("stop", "disable") and QMessageBox.question(
                self, f"{label}: {name}?",
                f"{label}: {name}? Something that depends on it may stop working.") != QMessageBox.Yes:
            return
        import subprocess
        try:
            res = subprocess.run(sysinfo.service_argv(name, action, user), capture_output=True, text=True, timeout=60)
            self.svc_msg.setText(f"{name}: done ({label.lower()})." if res.returncode == 0 else
                                 f"{name}: {label.lower()} didn't work — {(res.stderr or res.stdout).strip()[:200]}")
        except (OSError, ValueError, subprocess.TimeoutExpired) as e:
            self.svc_msg.setText(f"{name}: {e}")
        self._refresh_services()

    # ---------------------------------------------------------------- system
    def _build_system(self):
        w, v = _page("System information", "What this PC is made of and how it's doing.")
        self.sys_table = _Table(["", ""], widths={0: 240}, stretch=1, sortable=False)
        self.sys_table.horizontalHeader().hide()
        v.addWidget(self.sys_table, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        copy = QPushButton("Copy all")
        copy.setToolTip("Copy everything on this page, for a bug report or a forum post")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self._system_text()))
        row.addWidget(copy)
        v.addLayout(row)
        self.sys_rows = []
        return w

    def _system_text(self):
        return "\n".join(f"\n{k}" if v is None else f"{k}: {v}" for k, v in self.sys_rows).strip()

    def _refresh_system(self):
        s = sysinfo.system()
        c = self.cpu_static
        mem = sysinfo.memory()
        rows = [("This PC", None), ("Operating system", s["os"]), ("Kernel", s["kernel"]),
                ("Computer name", s["hostname"]), ("Computer", s["machine"] or "not reported"),
                ("Motherboard", s["board"] or "not reported"), ("Firmware (BIOS/UEFI)", s["bios"] or "not reported"),
                ("Architecture", s["arch"]),
                ("Running", None), ("Started", time.strftime("%d %b %Y %H:%M", time.localtime(s["boot_time"]))),
                ("Up for", human_duration(s["uptime_s"])),
                ("Hardware", None), ("Processor", f"{c['model']} ({c['cores']} cores, {c['threads']} threads)"),
                ("Memory", human_bytes(mem["total"]))]
        for i, g in enumerate(self._gpus or sysinfo.gpus()):
            rows.append((f"Graphics {i}", f"{g['name']} · {g['driver'] or 'driver unknown'}"))
        rows.append(("Health", None))
        failed = sysinfo.failed_units()
        rows.append(("Failed services", "not available (no systemd)" if failed is None else
                     ", ".join(u["name"] + (" (user)" if u["user"] else "") for u in failed) or "none"))
        for name in self.rates.sample()["disks"]:
            rows.append((f"Disk {name} health", sysinfo.disk_health(name) if os.name != "nt" else "not available"))
        b = sysinfo.battery()
        if b:
            rows.append(("Battery", f"{b['percent']} % · {b['status']}" +
                         (f" · health {b['health_percent']} % of design capacity" if b["health_percent"] else "")
                         + (f" · {b['cycles']} cycles" if b["cycles"] else "")))
        self.sys_rows = rows
        p = _palette()
        bad = lambda k, val: (k == "Failed services" and val not in ("none", "not available (no systemd)")) or \
            (k.endswith(" health") and str(val).upper().startswith(("FAIL", "BAD")))
        _fill(self.sys_table, [(cell(k, group=k), cell("", group=k)) if val is None else
                               (cell(k, color=p.muted), cell(str(val), color=p.danger if bad(k, val) else None,
                                                             tip=str(val)))
                               for k, val in rows])


def apply_style(app):
    """SAINT's own palette and stylesheet, so the Task Manager looks like the rest of SAINT."""
    try:
        from core.config import config
        from ui.theme import build_stylesheet, current_palette, qt_palette
        a = config.get("appearance", {}) or {}
        app.setPalette(qt_palette(current_palette()))
        app.setStyleSheet(build_stylesheet(a.get("theme", "Dark"), a.get("accent", "#feaa34"),
                                           a.get("font_family", "Noto Sans" if os.name != "nt" else "Segoe UI"),
                                           a.get("font_size", 13)))
    except Exception:
        pass


def main(argv=None) -> int:
    app = QApplication.instance() or QApplication(sys.argv if argv is None else argv)
    app.setApplicationName("SAINT Task Manager")
    app.setDesktopFileName("saint-taskmgr")
    apply_style(app)
    win = TaskManager()
    args = sys.argv if argv is None else argv
    if "--page" in args[:-1] and args[args.index("--page") + 1] in PAGES:
        win.nav.setCurrentRow(PAGES.index(args[args.index("--page") + 1]))
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
