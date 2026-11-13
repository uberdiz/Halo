"""Settings page "Avatar": the one place to customise SAINT's avatar — name, picture/model (import, choose, remove,
restore default), outfit, where it sits and how big, presence (always / pops in for actions), desktop play, idle
animations, shy mode, the voice indicator, accent and reduce motion, and the animation library: play, delete, and
make new animations from moves in order (core/avatar, ui/avatar)."""

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QSlider, QWidget)
from PySide6.QtCore import Qt

from core.avatar import PLACEMENTS, PRESENCES, STYLES, VIEWS, VOICE_STYLES, SIZE_MAX, SIZE_MIN, settings
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

        self.view_box = QComboBox()                # 3D avatars only
        for key in VIEWS:
            self.view_box.addItem({"full": "Full body — animated, shows what she's doing",
                                   "portrait": "Head and shoulders"}[key], key)
        self.view_box.setCurrentIndex(VIEWS.index(s["view"]))
        self.view_box.activated.connect(lambda _i: self.save("avatar.view", self.view_box.currentData()))
        form.addRow("View", self.view_box)

        self.props = QCheckBox("Show what SAINT is working on (code screen, plan cards, badges)")
        self.props.setChecked(s["props"])
        self.props.toggled.connect(lambda on: self.save("avatar.props", on))
        form.addRow("", self.props)

        from PySide6.QtWidgets import QSlider
        self.motion = QSlider(Qt.Horizontal)
        self.motion.setRange(0, 150)
        self.motion.setValue(int(s["motion"] * 100))
        self.motion.setToolTip("How much she moves: 0 still, 100 natural, 150 lively")
        self.motion.sliderReleased.connect(lambda: self.save("avatar.motion", self.motion.value() / 100))
        form.addRow("Body motion", self.motion)

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

        self.outfit = QComboBox()                  # 3D VRoid avatars, realistic look
        self.outfit.activated.connect(lambda _i: self.save("avatar.outfit", self.outfit.currentData()))
        orow = QHBoxLayout()
        orow.addWidget(self.outfit, 1)
        imp = QPushButton("Import outfit…")
        imp.clicked.connect(self.import_outfit)
        orow.addWidget(imp)
        form.addRow("Outfit", orow)

        self.presence = self._combo("avatar.presence", s["presence"], PRESENCES,
                                    {"always": "Always on the desktop",
                                     "pop": "Pops in when SAINT does something, then fades out"})
        form.addRow("Presence", self.presence)
        self.voice = self._combo("avatar.voice_style", s["voice_style"], VOICE_STYLES,
                                 {"glow": "A soft glow", "ring": "Sound rings", "bars": "Bars", "off": "Off"})
        form.addRow("Voice indicator", self.voice)
        self.checks = {}
        for key, text in (("behaviors", "Desktop play: sits on your windows, climbs their edges, dances to music"),
                          ("idle_animations", "Idle animations: a stretch or a look around now and then"),
                          ("shy", "Shy: moves aside when the cursor comes close")):
            box = QCheckBox(text)
            box.setChecked(s[key])
            box.toggled.connect(lambda on, k=key: self.save(f"avatar.{k}", on))
            form.addRow("", box)
            self.checks[key] = box

        self.preview = AvatarView()
        self.preview.setFixedSize(180, 180)
        v.addWidget(self.preview, 0, Qt.AlignLeft)
        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        v.addWidget(self.msg)
        self._build_library(v)
        v.addStretch(1)
        self.refresh()

    def _combo(self, key, current, keys, labels) -> QComboBox:
        box = QComboBox()
        for k in keys:
            box.addItem(labels[k], k)
        box.setCurrentIndex(keys.index(current))
        box.activated.connect(lambda _i: self.save(key, box.currentData()))
        return box

    # ---- animation library: play, delete, make a new one from moves in order
    def _build_library(self, v):
        from PySide6.QtWidgets import QListWidget, QVBoxLayout
        from core.avatar import clips
        v.addWidget(QLabel("<b>Animations</b> — play one, or make your own from moves in order."))
        row = QHBoxLayout()
        self.clips = QListWidget()
        self.clips.setMaximumHeight(170)
        self.clips.itemDoubleClicked.connect(lambda _i: self.play_selected())
        row.addWidget(self.clips, 1)
        col = QVBoxLayout()
        for text, slot in (("Play", self.play_selected), ("Stop", self.stop_clip), ("Delete", self.delete_selected)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            col.addWidget(b)
        col.addStretch(1)
        row.addLayout(col)
        v.addLayout(row)
        make = QHBoxLayout()
        self.move_pick = QComboBox()
        for name in sorted(clips.PRIMITIVES):
            self.move_pick.addItem(name.replace("-", " "), name)
        make.addWidget(self.move_pick)
        for text, slot in (("Add move", self.add_move), ("Clear", self.clear_moves), ("Try", self.try_moves)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            make.addWidget(b)
        self.new_name = QLineEdit()
        self.new_name.setPlaceholderText("name, e.g. happy-dance")
        self.new_name.setMaxLength(40)
        make.addWidget(self.new_name, 1)
        save = QPushButton("Save")
        save.clicked.connect(self.save_moves)
        make.addWidget(save)
        v.addLayout(make)
        self.moves = []
        self.sequence = QLabel("No moves yet.")
        self.sequence.setWordWrap(True)
        v.addWidget(self.sequence)

    def refresh_clips(self):
        from core.avatar import clips
        current = self.clips.currentItem().data(Qt.UserRole) if self.clips.currentItem() else None
        self.clips.clear()
        for name in clips.names():
            from PySide6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(name.replace("-", " ") + ("" if name in clips.PRIMITIVES else "  (yours)"))
            item.setData(Qt.UserRole, name)
            self.clips.addItem(item)
            if name == current:
                self.clips.setCurrentItem(item)

    def _selected(self):
        item = self.clips.currentItem()
        return item.data(Qt.UserRole) if item else None

    def play(self, clip):
        """Play on the preview and on the desktop avatar (through the event bus, like the avatar.play action)."""
        from core.events import EventType, event_bus
        self.preview.play_clip(clip)
        event_bus.emit_event(EventType.AVATAR_COMMAND, {"clip" if isinstance(clip, dict) else "play": clip})

    def play_selected(self):
        if self._selected():
            self.play(self._selected())

    def stop_clip(self):
        from core.events import EventType, event_bus
        self.preview.stop_clip()
        event_bus.emit_event(EventType.AVATAR_COMMAND, {"stop": True})

    def delete_selected(self):
        from core.avatar import clips
        name = self._selected()
        if not name:
            return
        if name in clips.PRIMITIVES:
            self.msg.setText(f"“{name}” is a built-in move; only your own animations can be deleted.")
            return
        clips.remove(name)
        self.msg.setText(f"Deleted {name}.")
        self.refresh_clips()

    def add_move(self):
        if len(self.moves) >= 12:
            self.msg.setText("12 moves at most.")
            return
        self.moves.append(self.move_pick.currentData())
        self.sequence.setText(" → ".join(m.replace("-", " ") for m in self.moves))

    def clear_moves(self):
        self.moves = []
        self.sequence.setText("No moves yet.")

    def _composed(self, name):
        from core.avatar import clips
        try:
            return clips.compose(self.moves, name)
        except clips.ClipError as e:
            self.msg.setText(f"Can't make that animation: {e}.")
            return None

    def try_moves(self):
        clip = self._composed("try-it")
        if clip:
            self.play(clip)

    def save_moves(self):
        from core.avatar import clips
        name = self.new_name.text().strip().lower().replace(" ", "-")
        clip = self._composed(name or "x")
        if clip is None:
            return
        try:
            clip = clips.save(dict(clip, name=name))
        except clips.ClipError as e:
            self.msg.setText(f"Not saved: {e}.")
            return
        self.msg.setText(f"Saved “{clip['name']}”. It's in the list and in the avatar's right-click menu.")
        self.clear_moves()
        self.new_name.clear()
        self.refresh_clips()

    def import_outfit(self, path: str = ""):
        from core.avatar import outfits
        if not path:
            path, _ = QFileDialog.getOpenFileName(self.widget, "Import outfit", "", "Outfits (*.json)")
            if not path:
                return
        try:
            o = outfits.install(path)
        except outfits.OutfitError as e:
            self.msg.setText(f"Not imported: {e}.")
            return
        self.save("avatar.outfit", o["name"])
        self.msg.setText(f"{o['title']} is her outfit now.")

    def refresh(self):
        current = settings()["id"]
        self.choice.clear()
        for a in library.list_avatars():
            label = a["name"] + (" (3D)" if a["kind"] == "3d" else "")
            self.choice.addItem(label, a["id"])
        idx = self.choice.findData(current)
        self.choice.setCurrentIndex(max(0, idx))
        from core.avatar import outfits
        self.outfit.clear()
        for o in outfits.presets().values():
            self.outfit.addItem(o["title"], o["name"])
        self.outfit.setCurrentIndex(max(0, self.outfit.findData(settings()["outfit"])))
        self.refresh_clips()
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
