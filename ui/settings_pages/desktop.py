"""Control Center page "Desktop": the screen edge that opens SAINT's overlay, and virtual desktops."""

import threading

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from core import kde_desktop as kde

TITLE = "Desktop"
ICON = "layout"
ORDER = 30


class _Bridge(QObject):
    done = Signal(str)


def heading(text: str, sub: str) -> QWidget:
    box = QWidget()
    v = QVBoxLayout(box)
    v.setContentsMargins(0, 0, 0, 8)
    t = QLabel(text)
    t.setObjectName("PageTitle")
    v.addWidget(t)
    s = QLabel(sub)
    s.setObjectName("PageSubtitle")
    s.setWordWrap(True)
    v.addWidget(s)
    return box


def scrolling_page(title: str, sub: str):
    """A settings page that scrolls: (page, its content layout)."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.NoFrame)
    inner = QWidget()
    v = QVBoxLayout(inner)
    v.setContentsMargins(32, 26, 32, 26)
    v.setSpacing(12)
    v.addWidget(heading(title, sub))
    area.setWidget(inner)
    return area, v


def build() -> QWidget:
    page, v = scrolling_page("Desktop", "Where SAINT's overlay can open from, and switching desktops without a touchpad.")
    bridge = _Bridge(page)
    msg = QLabel("" if kde.available() else "These settings need KDE Plasma, so nothing here will change on this system.")
    msg.setObjectName("Muted")
    msg.setWordWrap(True)
    bridge.done.connect(msg.setText)

    # ---- the overlay's screen edge
    box = QGroupBox("SAINT overlay")
    form = QFormLayout(box)
    edge = QComboBox()
    for key, label in kde.EDGES.items():
        edge.addItem(label, key)
    now, now_delay = kde.overlay_edge()
    edge.setCurrentIndex(edge.findData(now))
    delay = QSpinBox()
    delay.setRange(0, kde.MAX_EDGE_DELAY_MS)
    delay.setSingleStep(100)
    delay.setSuffix(" ms")
    delay.setValue(now_delay)
    delay.setEnabled(now != "off")
    form.addRow("Open from", edge)
    form.addRow("Hover for", delay)
    note = QLabel("Alt+` always opens the overlay. Plasma's own screen edges (Overview, for one) can share a corner: "
                  "both then respond, and those are set in System Settings, Screen Edges.")
    note.setObjectName("Muted")
    note.setWordWrap(True)
    form.addRow(note)
    v.addWidget(box)

    def reload_shell():
        kde.reload_shell_script()
        bridge.done.emit("Saved. It works now.")

    def save_edge():
        key = edge.currentData()
        delay.setEnabled(key != "off")
        try:
            if not kde.set_overlay_edge(key, delay.value()):
                msg.setText("KDE's settings tool didn't save that.")
                return
        except ValueError as e:
            msg.setText(str(e))
            return
        threading.Thread(target=reload_shell, daemon=True).start()

    # A spin box fires on every step: wait until the typing stops before reloading KWin's script.
    edge_timer = QTimer(page)
    edge_timer.setSingleShot(True)
    edge_timer.setInterval(500)
    edge_timer.timeout.connect(save_edge)
    edge.activated.connect(lambda _i: save_edge())
    delay.valueChanged.connect(lambda _v: edge_timer.start())

    # ---- virtual desktops
    box = QGroupBox("Desktops")
    form = QFormLayout(box)
    count = QSpinBox()
    count.setRange(1, kde.MAX_DESKTOPS)
    have = kde.desktops() if kde.available() else []
    configured = kde.read_value(kde.KWINRC, "Desktops", "Number", "4")
    count.setValue(len(have) or (int(configured) if configured.isdigit() else 4))
    form.addRow("How many", count)

    count_timer = QTimer(page)
    count_timer.setSingleShot(True)
    count_timer.setInterval(500)
    count_timer.timeout.connect(lambda: msg.setText(kde.set_desktop_count(count.value())[1]))
    count.valueChanged.connect(lambda _v: count_timer.start())

    meta_wheel = QCheckBox("Meta + mouse wheel switches desktops")
    meta_wheel.setChecked(kde.meta_wheel_on())
    meta_wheel.toggled.connect(lambda on: msg.setText("Saved." if kde.set_meta_wheel(on) else "That wasn't saved."))
    form.addRow(meta_wheel)

    bg_wheel = QCheckBox("Mouse wheel on the desktop background does too")
    bg_wheel.setChecked(kde.background_wheel_on())
    bg_wheel.setToolTip("Plasma's panels and wallpaper restart for a moment to pick this up. Your windows stay.")
    bg_wheel.toggled.connect(lambda on: msg.setText("Saved. The panels restart for a moment."
                                                    if kde.set_background_wheel(on) else "That wasn't saved."))
    form.addRow(bg_wheel)

    for keys, what in kde.SHORTCUTS_SHOWN:
        label = QLabel(what)
        label.setObjectName("Muted")
        label.setWordWrap(True)
        form.addRow(keys, label)

    row = QHBoxLayout()
    fix = QPushButton("Set these shortcuts")
    fix.setToolTip("For an account from before these shortcuts existed. New accounts already have them.")
    fix.clicked.connect(lambda: msg.setText("Saved. They work the next time you sign in." if kde.write_shortcuts()
                                            else "That wasn't saved."))
    row.addWidget(fix)
    row.addStretch(1)
    form.addRow(row)
    v.addWidget(box)

    v.addWidget(msg, 0, Qt.AlignTop)
    v.addStretch(1)
    return page
