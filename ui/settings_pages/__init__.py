"""
ui/settings_pages

HalOS settings pages that live in their own files. Each module here defines:

    TITLE = "Startup apps"      the page's name in the left rail
    ICON = "power"              a ui/icons.py name
    ORDER = 50                  position among these pages, low first
    def build() -> QWidget      the page; called once, when the window opens

Control Center (ui/saintos_center.py) adds whatever it finds, so a new page needs no edit there. A page that
fails to build is logged and left out: one broken page never costs the others.
"""

import importlib
import logging
import pkgutil
from types import ModuleType
from typing import List

log = logging.getLogger("saint.settings_pages")


def discover() -> List[ModuleType]:
    found = []
    for info in pkgutil.iter_modules(__path__):
        try:
            mod = importlib.import_module(f"{__name__}.{info.name}")
            if all(hasattr(mod, a) for a in ("TITLE", "ICON", "build")):
                found.append(mod)
        except Exception:
            log.exception("settings page %s failed to load", info.name)
    return sorted(found, key=lambda m: (getattr(m, "ORDER", 100), m.TITLE))
