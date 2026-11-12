"""Settings page "Avatar": SAINT's name, the avatar picture/model (import, choose, remove, restore default),
where it sits, its size, accent and reduce motion (core/avatar, ui/avatar)."""

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QSlider, QWidget)
from PySide6.QtCore import Qt

from core.avatar import PLACEMENTS, STYLES, SIZE_MAX, SIZE_MIN, settings
from core.avatar import library
from core.config import config
from ui.avatar import AvatarView, quick3d_available
from ui.reactive import ui_bus
from ui.settings_pages.desktop import scrolling_page

TITLE = "Avatar"
ICON = "user"
ORDER = 22
GROUP = "SAINT"


class Page:
    def __init__(self):
        self.widget, v = scrolling_page("Avatar", "How SAINT looks on your desktop.")
        s = settings()
        form = QFormLayout()
        v.addLayout(form)

        self.enabled = QCheckBox("Show the avatar")
        self.enabled.setChecked(s["enabled"])
        self.enabled.toggled.connect(lambda on: self.save("avatar.enabled", on))
        form.addRow("", self.enabled)

        self.name = QLineEdit(s["name"])
        self.name.setMaxLength(40)
        self.name.editingFinished.connect(lambda: self.save("avatar.name", self.name.text().strip() or "SAINT"))
        form.addRow("Name", self.name)

        self.choice = QComboBox()
        self.choice.activated.connect(lambda _i: self.save("avatar.id", self.choice.currentData()))
        form.addRow("Avatar", self.choice)

        row = QHBoxLayout()
        for text, slot in (("Import…", self.import_dialog), ("Remove", self.remove_selected),
                           ("Restore default", self.restore_default)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch(1)
        form.addRow("", row)

        self.placement = QComboBox()
        for p in PLACEMENTS:
            self.placement.addItem({"floating": "Floating (drag anywhere)", "widget": "Corner widget",
                                    "off": "Off"}[p], p)
        self.placement.setCurrentIndex(PLACEMENTS.index(s["placement"]))
        self.placement.activated.connect(lambda _i: self.save("avatar.placement", self.placement.currentData()))
        form.addRow("Placement", self.placement)

        self.style = QComboBox()                   # 3D avatars only; a 2D picture always draws as it is
        for key in STYLES:
            self.style.addItem({"hologram": "Hologram (glows in the accent colour)",
                                "realistic": "Realistic (the model's own materials)"}[key], key)
        self.style.setCurrentIndex(STYLES.index(s["style"]))
        self.style.activated.connect(lambda _i: self.save("avatar.style", self.style.currentData()))
        form.addRow("3D look", self.style)

        self.size = QSlider(Qt.Horizontal)
        self.size.setRange(SIZE_MIN, SIZE_MAX)
        self.size.setValue(s["size"])
        self.size.sliderReleased.connect(lambda: self.save("avatar.size", self.size.value()))
        form.addRow("Size", self.size)

        arow = QHBoxLayout()
        self.accent_btn = QPushButton("Choose colour…")
        self.accent_btn.clicked.connect(self.pick_accent)
        reset = QPushButton("Use theme accent")
        reset.clicked.connect(lambda: self.save("avatar.accent", ""))
        arow.addWidget(self.accent_btn)
        arow.addWidget(reset)
        arow.addStretch(1)
        form.addRow("Accent", arow)

        self.reduce = QCheckBox("Reduce motion (no breathing or spinning)")
        self.reduce.setChecked(s["reduce_motion"])
        self.reduce.toggled.connect(lambda on: self.save("avatar.reduce_motion", on))
        form.addRow("", self.reduce)

        self.preview = AvatarView()
        self.preview.setFixedSize(180, 180)
        v.addWidget(self.preview, 0, Qt.AlignLeft)
        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        v.addWidget(self.msg)
        v.addStretch(1)
        self.refresh()

    def refresh(self):
        current = settings()["id"]
        self.choice.clear()
        for a in library.list_avatars():
            label = a["name"] + (" (3D)" if a["kind"] == "3d" else "")
            self.choice.addItem(label, a["id"])
        idx = self.choice.findData(current)
        self.choice.setCurrentIndex(max(0, idx))
        self.preview.reload()
        chosen = library.get(current)
        note = ""
        if chosen["kind"] == "3d" and not quick3d_available():
            note = "3D models need QtQuick3D, which this PySide6 doesn't include, so the 2D avatar is shown. "
        meta = chosen.get("meta") or {}
        if meta:
            note += " · ".join(f"{k}: {meta[k]}" for k in ("title", "author", "license") if meta.get(k))
        self.msg.setText(note)

    def save(self, key, value):
        config.set(key, value)
        ui_bus.setting_changed.emit(key)
        self.refresh()

    def import_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self.widget, "Import avatar", "",
                                              "Avatars (*.vrm *.glb *.gltf *.png *.webp)")
        if path:
            self.import_path(path)

    def import_path(self, path):
        try:
            record = library.import_file(path)
        except (library.AvatarError, OSError) as e:
            self.msg.setText(f"Not imported: {e}")
            return
        self.save("avatar.id", record["id"])
        self.msg.setText(f"Imported {record['name']}. " + self.msg.text())

    def remove_selected(self):
        avatar_id = self.choice.currentData()
        if avatar_id == library.DEFAULT_ID:
            self.msg.setText("The default avatar can't be removed.")
            return
        library.remove(avatar_id)
        self.save("avatar.id", library.DEFAULT_ID)

    def restore_default(self):
        self.save("avatar.id", library.DEFAULT_ID)

    def pick_accent(self):
        c = QColorDialog.getColor(QColor(settings()["accent"] or config.get("appearance.accent", "#feaa34")),
                                  self.widget, "Avatar accent")
        if c.isValid():
            self.save("avatar.accent", c.name())


def build() -> QWidget:
    page = Page()
    page.widget._page = page
    return page.widget
