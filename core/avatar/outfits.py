"""
core/avatar/outfits.py

Outfits for a VRoid avatar: colour tints per material group, and accessories on or off. No new meshes: an outfit
recolours what the model already wears (ui/avatar/avatar3d.qml multiplies each material's own base colour by the
tint of its group; the hologram look ignores outfits).

    {"name": "midnight", "title": "Midnight", "tints": {"Tops": "#3b4a7a", "HAIR": "#2a2f45"},
     "hide_accessories": false}

Groups are found in VRoid material names (N00_002_01_Tops_01_CLOTH ...), most specific first; "CLOTH" tints every
piece of clothing that has no tint of its own. Presets ship in data/avatars/outfits.json; outfits from the Visual
Shop (or "Import outfit…") go to <data_dir>/avatar_outfits/<name>.json. Every outfit is validated: it's data from
the internet.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Optional

GROUPS = ("Tops", "Bottoms", "Shoes", "Onepiece", "Accessory", "CLOTH", "HAIR")
CLOTHES = ("Tops", "Bottoms", "Shoes", "Onepiece", "Accessory")
DEFAULT = "default"
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class OutfitError(ValueError):
    """An outfit that can't be used; the message is shown to the person."""


def clean(outfit) -> dict:
    """A validated copy: unknown groups and bad colours are dropped, the name must be a plain slug."""
    if not isinstance(outfit, dict):
        raise OutfitError("an outfit must be an object")
    name = str(outfit.get("name", "")).strip().lower()
    if not _NAME.match(name):
        raise OutfitError("name: 1-40 lowercase letters, digits or '-'")
    tints = outfit.get("tints") or {}
    if not isinstance(tints, dict):
        raise OutfitError("tints must be {group: \"#rrggbb\"}")
    return {"name": name, "title": str(outfit.get("title") or name.replace("-", " ").title())[:40],
            "tints": {g: str(tints[g]).lower() for g in GROUPS if _COLOR.match(str(tints.get(g, "")))},
            "hide_accessories": bool(outfit.get("hide_accessories", False))}


def group_of(material: str) -> str:
    """The group a VRoid material belongs to ("" for skin, eyes, face). Mirrors groupOf() in avatar3d.qml."""
    return next((g for g in GROUPS if g in str(material)), "")


def tint_for(outfit: dict, material: str) -> Optional[str]:
    """The tint a material gets in this outfit, None when it keeps its own colour. Mirrors avatar3d.qml."""
    g = group_of(material)
    t = outfit.get("tints", {})
    return t.get(g) or (t.get("CLOTH") if g in CLOTHES else None)


def multiply(base: tuple, tint: str) -> tuple:
    """base (r, g, b) 0..1 times the tint "#rrggbb" — how a tint recolours a material."""
    tr, tg, tb = (int(tint[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return base[0] * tr, base[1] * tg, base[2] * tb


def _shipped() -> Path:
    from core.paths import resource_path
    return Path(resource_path("data", "avatars", "outfits.json"))


def user_dir() -> Path:
    from core.paths import data_dir
    d = data_dir() / "avatar_outfits"
    d.mkdir(parents=True, exist_ok=True)
    return d


def presets(shipped: Optional[Path] = None, folder: Optional[Path] = None) -> Dict[str, dict]:
    """Every usable outfit by name: the default (her own colours), the shipped presets, then the person's own."""
    out = {DEFAULT: clean({"name": DEFAULT, "title": "Her own colours"})}
    try:
        items = json.loads(Path(shipped or _shipped()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        items = []
    files = sorted((folder or user_dir()).glob("*.json"))
    for item in list(items if isinstance(items, list) else []) + files:
        try:
            o = clean(json.loads(item.read_text(encoding="utf-8")) if isinstance(item, Path) else item)
        except (OSError, ValueError):
            continue
        out.setdefault(o["name"], o)
    return out


def get(name: str, **kw) -> dict:
    all_ = presets(**kw)
    return all_.get(str(name or "").lower(), all_[DEFAULT])


def install(path, folder: Optional[Path] = None) -> dict:
    """Validate an outfit .json and keep it with the person's outfits. Returns the clean outfit."""
    try:
        o = clean(json.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError) as e:
        raise OutfitError(f"couldn't read it: {e}")
    except json.JSONDecodeError:
        raise OutfitError("that file isn't an outfit (not JSON)")
    if o["name"] == DEFAULT:
        raise OutfitError("pick another name than 'default'")
    (folder or user_dir()).joinpath(f"{o['name']}.json").write_text(json.dumps(o, indent=1), encoding="utf-8")
    return o
