"""
core/actions/sets/avatar.py

SAINT's avatar: play an animation, make a new one from built-in moves (the model only picks move names; the
clip is built and validated by core/avatar/clips.compose), and change how she looks and behaves. The desktop
avatar hears about it through the AVATAR_COMMAND event (ui/avatar/companion.py), so these run from any thread.
"""

from __future__ import annotations

from ..registry import SAFE, Action, ActionError, ActionResult, P

# avatar.set: setting -> (parameter, how it's checked)
_SETTABLE = {
    "outfit": P("string", "outfit name (see the Avatar settings page)", required=False),
    "size": P("integer", "size in pixels", required=False, minimum=80, maximum=720),
    "placement": P("string", "where she is", required=False, enum=["floating", "widget", "off"]),
    "presence": P("string", "always on the desktop, or pop in for actions", required=False, enum=["always", "pop"]),
    "behaviors": P("boolean", "desktop play (title bars, climbing, dancing)", required=False),
    "idle_animations": P("boolean", "small idle animations", required=False),
    "shy": P("boolean", "move aside when the cursor comes close", required=False),
    "voice_style": P("string", "voice indicator", required=False, enum=["glow", "ring", "bars", "off"]),
    "view": P("string", "full body or head and shoulders", required=False, enum=["full", "portrait"]),
    "style": P("string", "the 3D look", required=False, enum=["realistic", "hologram"]),
}


def _tell(payload: dict):
    from core.events import EventType, event_bus
    event_bus.emit_event(EventType.AVATAR_COMMAND, payload)


def _play(p):
    from core.avatar import clips
    name = p["clip"].strip().lower().replace(" ", "-")
    if clips.get(name) is None:
        raise ActionError(f"There's no animation called “{p['clip']}”. Some I know: "
                          f"{', '.join(clips.names()[:12])} …", "NOT_FOUND")
    _tell({"play": name})
    return ActionResult(True, f"Playing {name.replace('-', ' ')}.", data={"clip": name})


def _create(p):
    from core.avatar import clips
    name = p["name"].strip().lower().replace(" ", "-")
    try:
        clip = clips.save(clips.compose([m.strip().lower().replace(" ", "-") for m in p["moves"]], name,
                                        speed=p.get("speed", 1.0), loop=bool(p.get("loop", False))))
    except clips.ClipError as e:
        raise ActionError(str(e), "INVALID_PARAMS")
    if p.get("play", True):
        _tell({"play": clip["name"]})
    return ActionResult(True, f"Made “{clip['name']}” ({' then '.join(p['moves'])}); it's in her animation list.",
                        data={"clip": clip["name"], "duration": clip["duration"]}, undo={"name": clip["name"]})


def _uncreate(u):
    from core.avatar import clips
    clips.remove(u["name"])
    return f"Removed the animation {u['name']}."


def _set(p):
    from core.avatar import outfits, settings
    from core.config import config
    changes = {k: p[k] for k in _SETTABLE if k in p}
    if not changes:
        raise ActionError("say what to change: " + ", ".join(_SETTABLE), "INVALID_PARAMS")
    if "outfit" in changes:
        wanted = changes["outfit"].strip().lower().replace(" ", "-")
        found = outfits.presets()
        match = wanted if wanted in found else next((n for n, o in found.items() if o["title"].lower() == wanted.replace("-", " ")), None)
        if match is None:
            raise ActionError(f"There's no outfit called “{changes['outfit']}”. Outfits: {', '.join(found)}.",
                              "NOT_FOUND")
        changes["outfit"] = match
    before = settings()
    for k, v in changes.items():
        config.set(f"avatar.{k}", v)
    _tell({"settings": True})
    said = ", ".join(f"{k.replace('_', ' ')} {('on' if v else 'off') if isinstance(v, bool) else v}" for k, v in changes.items())
    return ActionResult(True, f"Avatar: {said}.", data=changes, undo={k: before[k] for k in changes})


def _unset(u):
    from core.config import config
    for k, v in u.items():
        if k in _SETTABLE:
            config.set(f"avatar.{k}", v)
    _tell({"settings": True})
    return "Avatar settings put back."


def register(registry):
    from core.avatar import clips
    moves = ", ".join(sorted(clips.PRIMITIVES))
    registry.register(
        Action("avatar.play", "Play an avatar animation", _play,
               {"clip": P("string", "animation name, e.g. wave, nod, dance, stretch, or one you made")},
               risk=SAFE, keywords="avatar animation play wave dance nod bow cheer move gesture emote",
               preview=lambda p: f"Play the animation {p['clip']}."), replace=True)
    registry.register(
        Action("avatar.create_animation", "Make a new avatar animation from moves", _create,
               {"name": P("string", "new animation name (letters, digits, '-')", pattern=r"[A-Za-z0-9][A-Za-z0-9 -]{0,39}"),
                "moves": P("array", f"1-12 built-in moves in order, from: {moves}"),
                "speed": P("number", "0.25-4, 1 = normal", required=False, minimum=0.25, maximum=4),
                "loop": P("boolean", "repeat until stopped", required=False),
                "play": P("boolean", "play it right away (default yes)", required=False)},
               risk=SAFE, undo=_uncreate, keywords="avatar animation create make new dance routine choreography moves",
               preview=lambda p: f"Make the animation {p['name']} from {', '.join(p['moves'])}."), replace=True)
    registry.register(
        Action("avatar.set", "Change the avatar's look or behaviour", _set, dict(_SETTABLE),
               risk=SAFE, undo=_unset,
               keywords="avatar outfit clothes size bigger smaller presence pop in hide shy idle voice indicator look",
               preview=lambda p: "Change the avatar: " + ", ".join(f"{k}={p[k]}" for k in _SETTABLE if k in p)),
        replace=True)
