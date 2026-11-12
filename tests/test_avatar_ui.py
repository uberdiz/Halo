import os

import pytest

from tests.test_avatar_core import VRM1, glb


@pytest.fixture
def env(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv("SAINT_DATA_DIR", str(tmp_path / "data"))
    import core.config
    import ui.avatar
    import ui.settings_pages.avatar as page_mod
    cfg = core.config.Config(path=str(tmp_path / "c.json"))
    for mod in (core.config, ui.avatar, page_mod):
        monkeypatch.setattr(mod, "config", cfg)
    return app, cfg, page_mod, tmp_path


def test_page_buttons(env, capfd):
    app, cfg, page_mod, tmp = env
    from ui.avatar import FloatingAvatar
    floating = FloatingAvatar()
    assert floating.isVisible()
    page = page_mod.build()._page
    (tmp / "bad.vrm").write_bytes(b"nope")
    page.import_path(str(tmp / "bad.vrm"))
    assert page.msg.text().startswith("Not imported") and page.choice.count() == 1
    (tmp / "Saint.vrm").write_bytes(glb(VRM1))
    page.import_path(str(tmp / "Saint.vrm"))
    assert page.choice.count() == 2 and cfg.get("avatar.id") != "default"
    assert "author: Seb" in page.msg.text()
    page.remove_selected()
    assert page.choice.count() == 1 and cfg.get("avatar.id") == "default"
    page.placement.setCurrentIndex(2)
    page.save("avatar.placement", page.placement.currentData())
    assert not floating.isVisible()
    page.save("avatar.placement", "floating")
    assert floating.isVisible()
    page.save("avatar.reduce_motion", True)
    assert not floating.view._timer.isActive()
    page.save("avatar.reduce_motion", False)
    assert floating.view._timer.isActive()
    from core.avatar import AvatarState
    for st in AvatarState:                                # every state paints without raising
        floating.view.state = st
        floating.view._level = 0.5
        assert not floating.view.grab().isNull()
    assert "Error calling" not in capfd.readouterr().err
    floating.hide()
    assert not floating.view._timer.isActive()           # paused while hidden
