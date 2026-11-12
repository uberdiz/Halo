"""
core/tiling.py

Split the screen between windows: when SAINT works on several things at once, each gets its own part of the
screen. Pure layout here; the windows are placed by the desktop backend without being activated, so whatever you
are typing into keeps the focus.

    grid(3, (0, 0, 1920, 1040)) -> [(0,0,960,1040), (960,0,960,520), (960,520,960,520)]
"""

from __future__ import annotations

import math
from typing import List, Tuple

Rect = Tuple[int, int, int, int]          # x, y, width, height


def grid(n: int, area: Rect, gap: int = 6) -> List[Rect]:
    """n tiles filling ``area``: 1 full, 2 side by side, 3 one big on the left and two stacked, 4 a 2x2 grid,
    more in balanced columns."""
    x, y, w, h = area
    if n <= 0:
        return []
    if n == 1:
        return [area]
    if n == 3:
        half = w // 2
        return [(x, y, half - gap // 2, h), (x + half + gap // 2, y, w - half - gap // 2, h // 2 - gap // 2),
                (x + half + gap // 2, y + h // 2 + gap // 2, w - half - gap // 2, h - h // 2 - gap // 2)]
    cols = math.ceil(math.sqrt(n)) if n != 2 else 2
    rows = math.ceil(n / cols)
    out = []
    for i in range(n):
        r, c = divmod(i, cols)
        in_row = cols if r < rows - 1 else n - cols * (rows - 1)        # the last row may have fewer, wider tiles
        cw = (w - gap * (in_row - 1)) // in_row
        ch = (h - gap * (rows - 1)) // rows
        out.append((x + c * (cw + gap), y + r * (ch + gap), cw, ch))
    return out
