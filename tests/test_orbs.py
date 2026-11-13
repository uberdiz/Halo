"""ui/orbs.OrbBackground: fills its parent, ~30 fps only while shown, a still frame with reduce motion, and actually
paints the soft colour orbs on a light background."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from ui.orbs import FPS, OrbBackground

app = QApplication.instance() or QApplication([])


def test_timer_runs_only_while_shown_and_follows_the_parent():
    parent = QWidget()
    parent.resize(400, 300)
    orbs = OrbBackground(parent, animate=True)
    assert orbs.timer.interval() == 1000 // FPS and not orbs.timer.isActive()
    parent.show()
    app.processEvents()
    assert orbs.timer.isActive() and orbs.geometry() == parent.rect()
    parent.resize(500, 320)
    app.processEvents()
    assert orbs.size() == parent.size()
    parent.hide()
    assert not orbs.timer.isActive()


def test_reduce_motion_paints_one_still_frame_with_colour():
    parent = QWidget()
    parent.resize(300, 200)
    orbs = OrbBackground(parent, animate=False)
    parent.show()
    app.processEvents()
    assert not orbs.timer.isActive() and orbs.seconds() == 0.0
    img = orbs.grab().toImage()
    colours = {img.pixelColor(x, y).name() for x in range(0, 300, 30) for y in range(0, 200, 30)}
    assert len(colours) > 10                                       # gradients, not a flat fill
    assert all(img.pixelColor(x, y).lightness() > 150 for x in range(0, 300, 50) for y in range(0, 200, 50))
    parent.hide()


def test_install_chooser_has_the_background():
    from ui import install_chooser as ic
    dialog = ic.Chooser([])
    assert isinstance(dialog.orbs, OrbBackground)
