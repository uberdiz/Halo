"""Avatar outfits (tints per VRoid material group), the clamped avatar settings and the customisation menu."""

import pytest

from core.avatar import outfits
from tests.test_avatar_companion import floating  # noqa: F401  (fixture)


def test_outfit_tints_are_parsed_and_clamped():
    o = outfits.clean({"name": "Party", "tints": {"Tops": "#FF0000", "HAIR": "red", "Skin": "#00ff00"},
                       "hide_accessories": 1})
    assert o == {"name": "party", "title": "Party", "tints": {"Tops": "#ff0000"}, "hide_accessories": True}
    for bad in ({"name": "a/b"}, {"name": "ok", "tints": ["#fff"]}, "not an outfit"):
        with pytest.raises(outfits.OutfitError):
            outfits.clean(bad)
    assert outfits.group_of("N00_002_01_Tops_01_CLOTH (Instance)") == "Tops"
    assert outfits.group_of("N00_000_00_Face_00_SKIN (Instance)") == ""
    cloth = outfits.clean({"name": "c", "tints": {"CLOTH": "#808080", "Shoes": "#000000"}})
    assert outfits.tint_for(cloth, "N00_001_02_Bottoms_01_CLOTH") == "#808080"      # CLOTH covers the rest
    assert outfits.tint_for(cloth, "N00_008_01_Shoes_01_CLOTH_01") == "#000000"
    assert outfits.tint_for(cloth, "N00_000_Hair_00_HAIR") is None
    assert outfits.multiply((1.0, 0.5, 1.0), "#ff8000") == pytest.approx((1.0, 0.5 * 128 / 255, 0.0))


def test_outfit_presets_and_import(tmp_path):
    shipped = outfits.presets(folder=tmp_path)
    assert "default" in shipped and "midnight" in shipped and not shipped["default"]["tints"]
    f = tmp_path / "mine.json"
    f.write_text('{"name": "mine", "tints": {"CLOTH": "#123456"}}', encoding="utf-8")
    user = tmp_path / "user"
    user.mkdir()
    assert outfits.install(f, user)["name"] == "mine"
    assert outfits.get("mine", folder=user)["tints"] == {"CLOTH": "#123456"}
    assert outfits.get("no-such", folder=user)["name"] == "default"
    f.write_text("nope", encoding="utf-8")
    with pytest.raises(outfits.OutfitError):
        outfits.install(f, user)


def test_avatar_settings_are_clamped():
    from core.avatar import SIZE_MAX, settings

    class Cfg:
        def __init__(self, d):
            self.d = d

        def get(self, key, default=None):
            return self.d if key == "avatar" else default
    s = settings(Cfg({"size": 99999, "presence": "sometimes", "voice_style": "lasers", "outfit": "a/b",
                      "behaviors": 0, "idle_animations": "", "shy": 1}))
    assert s["size"] == SIZE_MAX >= 720 and s["presence"] == "always" and s["voice_style"] == "ring"
    assert s["outfit"] == "default" and s["behaviors"] is False and s["idle_animations"] is False and s["shy"]
    d = settings(Cfg({}))
    assert d["behaviors"] and d["idle_animations"] and not d["shy"] and d["presence"] == "always"


def _names(page):
    return [page.clips.item(i).data(0x0100) for i in range(page.clips.count())]


def test_customization_menu(floating, monkeypatch):  # noqa: F811
    import core.config
    import ui.settings_pages.avatar as page_mod
    monkeypatch.setattr(page_mod, "config", core.config.config)
    page = page_mod.build()._page
    assert page.outfit.count() >= 2 and page.clips.count() >= 20
    page.save("avatar.outfit", "midnight")
    assert floating.view.cfg["outfit"] == "midnight"
    page.save("avatar.presence", "pop")
    assert floating.companion.presence.mode == "pop"
    for move in ("wave", "spin"):
        page.move_pick.setCurrentIndex(page.move_pick.findData(move))
        page.add_move()
    page.new_name.setText("hello spin")
    page.save_moves()
    from core.avatar import clips
    assert clips.get("hello-spin") is not None and "hello-spin" in _names(page)
    page.clips.setCurrentRow(_names(page).index("hello-spin"))
    page.play_selected()
    assert floating.view._clip["name"] == "hello-spin"         # played on the desktop avatar too
    page.delete_selected()
    assert clips.get("hello-spin") is None
