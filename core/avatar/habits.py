"""
core/avatar/habits.py

What SAINT's avatar learns about the person, so she grows into their habits: where they put her (per monitor and
time of day), which apps they perch her on, which animations they ask for. Small counts in one local JSON file
(<data_dir>/avatar_habits.json), never sent anywhere; deterministic (no model).

They bias her, never override her: her resting spot (behavior.settle: a learned favourite spot and anchor weights),
whether she goes to sit on a kind of window, and which idle animation she picks. Old counts fade (halved once the
total passes DECAY_AT), so a new habit takes over from an old one.
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Dict, Optional

log = logging.getLogger("SAINT.avatar")
GRID = (8, 6)                 # a monitor is split into 8 x 6 cells for remembering spots
DECAY_AT = 400.0
MIN_COUNT = 3.0               # a spot or a liking counts as a habit from this many


def part_of_day(hour: int) -> str:
    h = int(hour) % 24
    return "night" if h < 6 else "morning" if h < 12 else "afternoon" if h < 18 else "evening"


def screen_key(screen: tuple) -> str:
    return "{}x{}@{},{}".format(screen[2], screen[3], screen[0], screen[1])


class Habits:
    def __init__(self, path: Optional[Path] = None):
        if path is None:
            from core.paths import data_dir
            path = data_dir() / "avatar_habits.json"
        self.path = Path(path)
        self.data: Dict[str, Dict[str, float]] = {"spots": {}, "perch": {}, "clips": {}, "anchors": {}}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for k in self.data:
                if isinstance(raw.get(k), dict):
                    self.data[k] = {str(n): float(v) for n, v in raw[k].items() if isinstance(v, (int, float))}
        except (OSError, ValueError):
            pass

    # ---- learning
    def _add(self, table: str, key: str, weight: float = 1.0):
        t = self.data[table]
        t[key] = t.get(key, 0.0) + weight
        if sum(t.values()) > DECAY_AT:               # old habits fade so new ones can take over
            self.data[table] = {k: v / 2 for k, v in t.items() if v / 2 >= 0.25}
        self.save()

    def placed(self, pos: tuple, size: tuple, screen: tuple, hour: int, weight: float = 3.0):
        """The person put her at ``pos`` (top-left) on ``screen`` (x, y, w, h)."""
        sx, sy, sw, sh = screen
        cx, cy = pos[0] + size[0] / 2, pos[1] + size[1] / 2
        gx = max(0, min(GRID[0] - 1, int((cx - sx) / max(1, sw) * GRID[0])))
        gy = max(0, min(GRID[1] - 1, int((cy - sy) / max(1, sh) * GRID[1])))
        self._add("spots", f"{screen_key(screen)}|{part_of_day(hour)}|{gx},{gy}", weight)

    def perched(self, category: str, weight: float = 2.0):
        """The person sat her on a window of this kind (behavior.category)."""
        self._add("perch", category or "other", weight)

    def asked(self, clip: str):
        """The person asked for this animation."""
        self._add("clips", clip, 1.0)

    def settled(self, anchor: str, hour: int):
        self._add("anchors", f"{part_of_day(hour)}|{anchor}", 0.25)

    # ---- biasing
    def favourite_spot(self, screen: tuple, size: tuple, hour: int) -> Optional[tuple]:
        """The top-left of the cell the person puts her in most at this time of day on this monitor (else at any
        time), None until it's a habit."""
        key = screen_key(screen)
        for prefix in (f"{key}|{part_of_day(hour)}|", f"{key}|"):
            cells: Dict[str, float] = {}
            for k, v in self.data["spots"].items():
                if k.startswith(prefix):
                    cell = k.rsplit("|", 1)[1]
                    cells[cell] = cells.get(cell, 0.0) + v
            if cells:
                cell, n = max(sorted(cells.items()), key=lambda kv: kv[1])
                if n >= MIN_COUNT:
                    gx, gy = (int(c) for c in cell.split(","))
                    sx, sy, sw, sh = screen
                    return (int(sx + (gx + 0.5) * sw / GRID[0] - size[0] / 2),
                            int(sy + (gy + 0.5) * sh / GRID[1] - size[1] / 2))
        return None

    def anchor_bias(self, category: str, hour: int) -> Dict[str, float]:
        """anchor -> 0..1: how much the person's habits favour it right now."""
        out: Dict[str, float] = {}
        perch = self.data["perch"]
        total = sum(perch.values())
        if total >= MIN_COUNT and category in perch:
            out["titlebar"] = min(1.0, perch[category] / total * 1.5)
        prefix = part_of_day(hour) + "|"
        mine = {k[len(prefix):]: v for k, v in self.data["anchors"].items() if k.startswith(prefix)}
        top = max(mine.values(), default=0.0)
        for a, v in mine.items():
            out[a] = max(out.get(a, 0.0), 0.5 * v / top if top else 0.0)
        if self.data["spots"]:
            out["habit"] = 1.0
        return out

    def likes_perching(self, category: str) -> float:
        """0..1: how often the person sits her on this kind of window."""
        perch = self.data["perch"]
        total = sum(perch.values())
        return min(1.0, perch.get(category, 0.0) / total * 1.5) if total >= MIN_COUNT else 0.0

    def pick_clip(self, rng: random.Random, choices) -> str:
        """An idle animation, the person's favourites a little more often."""
        choices = list(choices)
        weights = [1.0 + min(3.0, self.data["clips"].get(c, 0.0) / 3) for c in choices]
        return rng.choices(choices, weights)[0]

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, separators=(",", ":")), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as e:                    # learning is a nicety: never break the avatar over it
            log.warning("avatar.habits_save_failed %s", e)
