"""
core/store_art.py

Real app artwork for the Store: icon, screenshots, developer and brand colour from Flathub's AppStream data
(the publisher's own metadata, https://flathub.org/api/v2/appstream/<id>). Nothing is made up: an app with no
Flathub entry gets no picture (the Store draws its initial instead).

Everything is cached on disk (metadata for a week, images until they change), so the Store opens instantly
after the first visit and works offline with what it has seen.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Dict, Optional

log = logging.getLogger("saint.store_art")

APPSTREAM = "https://flathub.org/api/v2/appstream/{id}"
MAX_SHOTS = 4
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]{3,128}$")
_SAFE_HOSTS = ("https://dl.flathub.org/", "https://flathub.org/")
META_TTL = 7 * 24 * 3600


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or (os.path.join(os.environ.get("LOCALAPPDATA", ""), "SAINT", "cache")
                                                if os.name == "nt" else os.path.expanduser("~/.cache"))
    d = Path(base) / ("saint/store" if os.name != "nt" else "store")
    d.mkdir(parents=True, exist_ok=True)
    return d


def flathub_id(result, catalog=None) -> Optional[str]:
    """The Flathub id whose artwork shows this Store result: the Flatpak itself, or a pick's ``art`` id."""
    if result.source == "flathub":
        return result.id
    if result.source == "featured":
        extra = result.extra or {}
        if extra.get("art"):
            return extra["art"]
        if extra.get("method") == "flatpak":
            return extra.get("ref")
    return None


def _shot_url(shot, want_width: int = 752) -> Optional[str]:
    """The size of one screenshot closest to ``want_width``."""
    sizes = shot.get("sizes", []) if isinstance(shot, dict) else []
    best = None
    for s in sizes:
        try:
            w = int(s.get("width", 0))
        except (TypeError, ValueError):
            continue
        if best is None or abs(w - want_width) < abs(best[0] - want_width):
            best = (w, s.get("src"))
    return best[1] if best else None


def _pick_screenshot(shots, want_width: int = 752) -> Optional[str]:
    """The screenshot size closest to ``want_width`` from the first screenshot."""
    return _shot_url(shots[0], want_width) if shots else None


def parse_appstream(data: dict) -> Dict:
    brand = {}
    for b in data.get("branding") or []:
        if b.get("type") == "primary" and b.get("value"):
            brand[b.get("scheme_preference") or "any"] = b["value"]
    shots = [u for u in (_shot_url(s) for s in (data.get("screenshots") or [])[:MAX_SHOTS]) if u]
    dev = data.get("developer_name") or ""
    if not dev and isinstance(data.get("developer"), dict):
        dev = data["developer"].get("name") or ""
    return {"icon": data.get("icon"), "screenshot": shots[0] if shots else None, "screenshots": shots,
            "developer": dev, "summary": data.get("summary") or "",
            "license": data.get("project_license") or "", "homepage": (data.get("urls") or {}).get("homepage", ""),
            "categories": [c for c in (data.get("categories") or []) if isinstance(c, str)],
            "brand_dark": brand.get("dark") or brand.get("any"), "brand_light": brand.get("light") or brand.get("any")}


def parse_appstream_xml(text: str, app_id: str = "") -> Dict:
    """The same facts from local AppStream XML (``appstreamcli dump``: Arch's and Flatpak's catalog data)."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {}
    comps = [root] if root.tag == "component" else root.findall("component")
    comp = next((c for c in comps if not app_id or (c.findtext("id") or "").strip() == app_id), None)
    if comp is None:
        return {}

    def plain(tag):                                   # the untranslated text (no xml:lang)
        for el in comp.findall(tag):
            if not any(k.endswith("lang") for k in el.attrib):
                return (el.text or "").strip()
        return ""
    icon = ""
    for el in comp.findall("icon"):
        if el.get("type") == "remote" and (el.text or "").strip():
            icon = el.text.strip()
            break
    shots = []
    for shot in comp.findall("screenshots/screenshot")[:MAX_SHOTS]:
        imgs = [(int(i.get("width") or 0), (i.text or "").strip()) for i in shot.findall("image") if (i.text or "").strip()]
        if imgs:
            shots.append(min(imgs, key=lambda wi: abs(wi[0] - 752))[1])
    homepage = next(((u.text or "").strip() for u in comp.findall("url") if u.get("type") == "homepage"), "")
    return {"icon": icon or None, "screenshot": shots[0] if shots else None, "screenshots": shots,
            "developer": comp.findtext("developer/name", "").strip() or plain("developer_name"),
            "summary": plain("summary"), "license": (comp.findtext("project_license") or "").strip(),
            "homepage": homepage, "categories": [(c.text or "").strip() for c in comp.findall("categories/category")],
            "brand_dark": None, "brand_light": None, "local": True}


def local_metadata(app_id: str, run: Callable = subprocess.run, which: Callable = shutil.which) -> Dict:
    """AppStream data already on this system (``appstreamcli``, Linux only): works offline, and covers Arch
    packages that aren't on Flathub. {} when there's no such tool or component."""
    if not app_id or app_id.startswith("-") or not _SAFE_ID.match(app_id) or not which("appstreamcli"):
        return {}
    try:
        out = run(["appstreamcli", "dump", app_id], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    return parse_appstream_xml(out.stdout or "", app_id) if out.returncode == 0 else {}


def metadata(app_id: str, fetch: Optional[Callable[[str], dict]] = None, now: Optional[float] = None,
             local: Optional[Callable[[str], dict]] = None) -> Dict:
    """Flathub's facts about one app, else the system's own AppStream data ({} when neither knows it and
    nothing is cached)."""
    if not app_id or not _SAFE_ID.match(app_id):
        return {}
    path = cache_dir() / f"{app_id}.json"
    now = now if now is not None else time.time()
    local = local or local_metadata
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
        if now - cached.get("_at", 0) < META_TTL:
            return cached
    except (OSError, ValueError):
        cached = {}
    try:
        meta = parse_appstream((fetch or _get_json)(APPSTREAM.format(id=app_id)) or {})
    except Exception as e:
        log.info("store_art.metadata_unavailable %s: %s", app_id, e)
        if cached:
            return cached                             # stale beats nothing
        return local(app_id) or {}                    # offline, never seen: what this system knows (not cached)
    if not meta.get("icon") and not meta.get("summary"):
        meta = local(app_id) or meta                  # not on Flathub: maybe in Arch's AppStream data
    meta["_at"] = now
    try:
        path.write_text(json.dumps(meta), encoding="utf-8")
    except OSError:
        pass
    return meta


def image(url: str, fetch: Optional[Callable[[str], bytes]] = None) -> Optional[str]:
    """A local copy of a Flathub image (icon/screenshot); None if it can't be had."""
    if not url or not url.startswith(_SAFE_HOSTS):
        return None
    ext = os.path.splitext(url.split("?")[0])[1].lower()
    path = cache_dir() / (hashlib.sha1(url.encode()).hexdigest() + (ext if ext in (".png", ".jpg", ".jpeg", ".webp")
                                                                     else ".img"))
    if path.exists() and path.stat().st_size > 0:
        return str(path)
    try:
        data = (fetch or _get_bytes)(url)
    except Exception as e:
        log.info("store_art.image_unavailable %s: %s", url, e)
        return None
    if not data or len(data) > 8 * 2 ** 20:
        return None
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(path)
    return str(path)


def _get_json(url: str):
    import requests
    r = requests.get(url, timeout=10, headers={"User-Agent": "SAINT-Store/1"})
    if r.status_code == 404:
        return {}
    r.raise_for_status()
    return r.json()


def _get_bytes(url: str) -> bytes:
    import requests
    r = requests.get(url, timeout=15, headers={"User-Agent": "SAINT-Store/1"})
    r.raise_for_status()
    return r.content
