"""The avatar.* actions (play, create_animation, set) and their plain-phrase intents."""
import sys

import pytest

from core import actions
from core.actions import ActionLog, executor, log as log_mod


@pytest.fixture
def halos(tmp_path, monkeypatch):
    fresh = ActionLog(tmp_path / "log.jsonl")
    for mod in (log_mod, executor, actions):
        monkeypatch.setattr(mod, "action_log", fresh)
    actions.load_builtin()
    for name, mod in list(sys.modules.items()):
        if name.startswith("core.actions") and hasattr(mod, "platform_name"):
            monkeypatch.setattr(mod, "platform_name", lambda: "linux")
    monkeypatch.setenv("SAINT_DATA_DIR", str(tmp_path / "data"))
    import core.config
    cfg = core.config.Config(path=str(tmp_path / "c.json"))
    monkeypatch.setattr(core.config, "config", cfg)
    cfg.set("actions.default_trust", "ask_risky", persist=False)
    from core.actions.sets import avatar
    told = []
    monkeypatch.setattr(avatar, "_tell", told.append)
    return cfg, told


def test_avatar_actions_are_registered_with_their_risk(halos):
    for aid in ("avatar.play", "avatar.create_animation", "avatar.set"):
        a = actions.registry.get(aid)
        assert a is not None and a.available() and a.risk == actions.SAFE
    spec = actions.registry.get("avatar.create_animation").to_tool_spec()
    moves = spec["parameters"]["properties"]["moves"]
    assert moves["type"] == "array" and "wave" in moves["description"]       # the model only picks names


def test_play(halos):
    _cfg, told = halos
    r = actions.execute("avatar.play", {"clip": "Wave"}, source="agent")
    assert r.ok and told == [{"play": "wave"}]
    r = actions.execute("avatar.play", {"clip": "moonwalk"}, source="agent")
    assert not r.ok and r.code == "NOT_FOUND"


def test_create_animation_composes_saves_and_undoes(halos):
    from core.avatar import clips
    _cfg, told = halos
    r = actions.execute("avatar.create_animation", {"name": "happy spin", "moves": ["wave", "spin", "bow"]},
                        source="agent")
    assert r.ok and clips.get("happy-spin") is not None and told[-1] == {"play": "happy-spin"}
    assert actions.undo(r.entry_id).ok and clips.get("happy-spin") is None
    bad = actions.execute("avatar.create_animation", {"name": "x", "moves": ["rm -rf /"]}, source="agent")
    assert not bad.ok and bad.code == "INVALID_PARAMS"


def test_set_changes_settings_and_undoes(halos):
    from core.avatar import settings
    cfg, told = halos
    r = actions.execute("avatar.set", {"outfit": "Midnight", "size": 300, "presence": "pop"}, source="agent")
    assert r.ok and told[-1] == {"settings": True}
    s = settings(cfg)
    assert (s["outfit"], s["size"], s["presence"]) == ("midnight", 300, "pop")
    assert actions.undo(r.entry_id).ok
    s = settings(cfg)
    assert (s["outfit"], s["size"], s["presence"]) == ("default", 160, "always")
    assert actions.execute("avatar.set", {"outfit": "spacesuit"}, source="agent").code == "NOT_FOUND"
    assert actions.execute("avatar.set", {}, source="agent").code == "INVALID_PARAMS"
    assert actions.execute("avatar.set", {"size": 5000}, source="agent").code == "INVALID_PARAMS"


@pytest.mark.parametrize("text, action, params", [
    ("SAINT, wave", "avatar.play", {"clip": "wave"}),
    ("can you dance for me", "avatar.play", {"clip": "dance"}),
    ("look around", "avatar.play", {"clip": "look-around"}),
    ("play the sit swing animation", "avatar.play", {"clip": "sit-swing"}),
    ("make a new animation called party time with wave, spin and bow", "avatar.create_animation",
     {"name": "party time", "moves": ["wave", "spin", "bow"]}),
    ("hide the avatar", "avatar.set", {"placement": "off"}),
    ("put on the sakura outfit", "avatar.set", {"outfit": "sakura"}),
    ("only pop in when you're doing something", "avatar.set", {"presence": "pop"}),
    ("make the avatar bigger", "avatar.set", {"size": 200}),
])
def test_plain_phrases(halos, monkeypatch, text, action, params):
    from modules.agent import os_intents
    seen = []
    monkeypatch.setattr(os_intents, "_run", lambda a, p: seen.append((a, p)))
    intent = os_intents.parse_os(text)
    assert intent is not None and intent.name == f"os.{action}"
    intent.run()
    assert seen == [(action, params)]
