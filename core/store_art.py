"""
core/store_art.py

Real app artwork for the Store: icon, screenshots, description, developer and brand colour from AppStream, the
publishers' own metadata:

    a Flatpak or a pick     Flathub's data (https://flathub.org/api/v2/appstream/<id>)
    an Arch or AUR package  this system's AppStream catalog (archlinux-appstream-data) by package name, else the
                            Flathub entry with exactly that app's name (the same app, packaged differently)

Nothing is made up: an app nobody has a picture of gets no picture (the Store draws a tinted tile with its
initial instead). Everything is cached on disk (metadata for a week, images until they change), so the Store
opens instantly after the first visit and works offline with what it has seen.
"""

from __future__ import annotations

import glob
import gzip
import hashlib
import html
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Dict, List, Optional

log = logging.getLogger("saint.store_art")

APPSTREAM = "https://flathub.org/api/v2/appstream/{id}"
MAX_SHOTS = 6
THUMB_W, GALLERY_W, HERO_W = 624, 752, 1248        # a card's preview, the gallery, and a full-width hero
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]{3,128}$")
_SAFE_HOSTS = ("https://dl.flathub.org/", "https://flathub.org/")
META_TTL = 7 * 24 * 3600
SCHEMA = 2                                         # older cached entries lack the sizes above: refetch them
SWCATALOG_DIRS = ("/usr/share/swcatalog", "/var/lib/swcatalog")


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


def _shot_url(shot, want_width: int = GALLERY_W) -> Optional[str]:
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


def _pick_screenshot(shots, want_width: int = GALLERY_W) -> Optional[str]:
    """The screenshot size closest to ``want_width`` from the first screenshot."""
    return _shot_url(shots[0], want_width) if shots else None


class _Description(HTMLParser):
    """AppStream markup, down to what the Store shows: no attributes, no links, no images."""
    KEEP = {"p", "ul", "ol", "li", "em", "strong", "code"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.KEEP:
            self.out.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in self.KEEP:
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        self.out.append(html.escape(re.sub(r"\s+", " ", data), quote=False))


def clean_description(markup: str) -> str:
    """Publisher-supplied text as safe rich text for a label ("" when there's none)."""
    if not markup or not isinstance(markup, str):
        return ""
    parser = _Description()
    parser.feed(markup)
    parser.close()
    return "".join(parser.out).strip()


def parse_appstream(data: dict) -> Dict:
    brand = {}
    for b in data.get("branding") or []:
        if b.get("type") == "primary" and b.get("value"):
            brand[b.get("scheme_preference") or "any"] = b["value"]
    raw = (data.get("screenshots") or [])[:MAX_SHOTS]
    shots = [u for u in (_shot_url(s) for s in raw) if u]
    large = [u for u in (_shot_url(s, HERO_W) for s in raw) if u]
    dev = data.get("developer_name") or ""
    if not dev and isinstance(data.get("developer"), dict):
        dev = data["developer"].get("name") or ""
    return {"icon": data.get("icon"), "screenshot": shots[0] if shots else None, "screenshots": shots,
            "thumb": _shot_url(raw[0], THUMB_W) if raw else None, "hero": large[0] if large else None,
            "shots_large": large, "description": clean_description(data.get("description")),
            "developer": dev, "summary": data.get("summary") or "",
            "license": data.get("project_license") or "", "homepage": (data.get("urls") or {}).get("homepage", ""),
            "categories": [c for c in (data.get("categories") or []) if isinstance(c, str)],
            "brand_dark": brand.get("dark") or brand.get("any"), "brand_light": brand.get("light") or brand.get("any")}


def _xml_component(comp) -> Dict:
    """The facts in one AppStream <component>."""
    import xml.etree.ElementTree as ET

    def plain(tag):                                   # the untranslated text (no xml:lang)
        for el in comp.findall(tag):
            if not any(k.endswith("lang") for k in el.attrib):
                return (el.text or "").strip()
        return ""
    icon, cached = "", ""
    for el in comp.findall("icon"):
        text = (el.text or "").strip()
        if el.get("type") == "remote" and text and not icon:
            icon = text
        elif el.get("type") == "cached" and text and not cached:
            cached = text
    shots, large = [], []
    for shot in comp.findall("screenshots/screenshot")[:MAX_SHOTS]:
        imgs = [(int(i.get("width") or 0), (i.text or "").strip()) for i in shot.findall("image") if (i.text or "").strip()]
        if imgs:
            shots.append(min(imgs, key=lambda wi: abs(wi[0] - GALLERY_W))[1])
            large.append(min(imgs, key=lambda wi: abs(wi[0] - HERO_W))[1])
    homepage = next(((u.text or "").strip() for u in comp.findall("url") if u.get("type") == "homepage"), "")
    desc = next((d for d in comp.findall("description") if not any(k.endswith("lang") for k in d.attrib)), None)
    body = "".join(ET.tostring(c, encoding="unicode") for c in desc if not any(k.endswith("lang") for k in c.attrib)) \
        if desc is not None else ""
    return {"icon": icon or None, "screenshot": shots[0] if shots else None, "screenshots": shots,
            "thumb": shots[0] if shots else None, "hero": large[0] if large else None, "shots_large": large,
            "description": clean_description(body),
            "developer": comp.findtext("developer/name", "").strip() or plain("developer_name"),
            "summary": plain("summary"), "license": (comp.findtext("project_license") or "").strip(),
            "homepage": homepage, "categories": [(c.text or "").strip() for c in comp.findall("categories/category")],
            "brand_dark": None, "brand_light": None, "local": True, "cached_icon": cached,
            "id": (comp.findtext("id") or "").strip(), "name": plain("name"),
            "package": (comp.findtext("pkgname") or "").strip()}


def parse_appstream_xml(text: str, app_id: str = "") -> Dict:
    """The same facts from local AppStream XML (``appstreamcli dump``: Arch's and Flatpak's catalog data)."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {}
    comps = [root] if root.tag == "component" else root.findall("component")
    comp = next((c for c in comps if not app_id or (c.findtext("id") or "").strip() == app_id), None)
    return _xml_component(comp) if comp is not None else {}


def _cached_icon(name: str, dirs=SWCATALOG_DIRS) -> str:
    """The catalog's own copy of an icon, largest first ("" when it isn't on disk)."""
    if not name or "/" in name or "\\" in name:
        return ""
    for size in ("128x128", "64x64", "48x48"):
        for base in dirs:
            for hit in glob.glob(os.path.join(glob.escape(base), "icons", "*", size, glob.escape(name))):
                return hit
    return ""


_packages: Dict[tuple, Dict[str, Dict]] = {}


def package_index(dirs=SWCATALOG_DIRS) -> Dict[str, Dict]:
    """Package name -> the desktop app it holds, from this system's AppStream catalog (archlinux-appstream-data).
    {} on a system without one. Parsed once per process: this is thousands of apps."""
    files = sorted(f for base in dirs for f in glob.glob(os.path.join(glob.escape(base), "xml", "*.xml*")))
    key = tuple((f, os.path.getmtime(f)) for f in files)
    if key in _packages:
        return _packages[key]
    import xml.etree.ElementTree as ET
    index: Dict[str, Dict] = {}
    for f in files:
        repo = os.path.basename(f).split(".")[0]
        try:
            with (gzip.open(f, "rb") if f.endswith(".gz") else open(f, "rb")) as stream:
                for _ev, el in ET.iterparse(stream):
                    if el.tag != "component":
                        continue
                    if el.get("type") == "desktop-application" and el.findtext("pkgname"):
                        meta = _xml_component(el)
                        meta["repo"] = repo
                        meta["icon_path"] = _cached_icon(meta.pop("cached_icon", ""), dirs)
                        index.setdefault(meta["package"], meta)
                    el.clear()
        except (OSError, EOFError, ET.ParseError) as e:
            log.info("store_art.catalog_unreadable %s: %s", f, e)
    _packages[key] = index
    return index


def _name_key(name: str) -> str:
    """A package or app name, compared loosely: ``krita``, ``Krita``, ``krita-bin`` are all the same name."""
    name = re.sub(r"[-_](bin|git|appimage|stable|desktop|nightly)$", "", name.lower().strip())
    return re.sub(r"[^a-z0-9]", "", name)


def match_flathub(name: str, post: Optional[Callable] = None, now: Optional[float] = None) -> str:
    """The Flathub id of the app called exactly ``name`` ("" for none). A near match isn't good enough: a picture
    of another app is worse than no picture. Answers are cached; a failed request isn't."""
    key = _name_key(name)
    if len(key) < 2:
        return ""
    now = now if now is not None else time.time()
    path = cache_dir() / f"name-{hashlib.sha1(key.encode()).hexdigest()}.json"
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
        if now - cached.get("_at", 0) < META_TTL:
            return cached.get("id", "")
    except (OSError, ValueError):
        pass
    try:
        if post is None:
            from core.store import FLATHUB_SEARCH, _post_json
            post = lambda body: _post_json(FLATHUB_SEARCH, body)          # noqa: E731
        hits = (post({"query": name}) or {}).get("hits", [])
    except Exception as e:
        log.info("store_art.name_search_unavailable %s: %s", name, e)
        return ""
    found = next((h.get("app_id", "") for h in hits
                  if key in (_name_key(h.get("name", "")), _name_key(h.get("app_id", "").rsplit(".", 1)[-1]))), "")
    if not _SAFE_ID.match(found or ""):
        found = ""
    try:
        path.write_text(json.dumps({"id": found, "_at": now}), encoding="utf-8")
    except OSError:
        pass
    return found


def app_metadata(flathub: str = "", lookup: str = "") -> Dict:
    """What's known about one Store result: by Flathub id, else by package or app name. {} when nothing is."""
    if flathub:
        return metadata(flathub)
    if not lookup:
        return {}
    local = package_index().get(lookup)
    if local:
        return local
    found = match_flathub(lookup)
    return metadata(found) if found else {}


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
        if now - cached.get("_at", 0) < META_TTL and cached.get("_v") == SCHEMA:
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
    meta["_at"], meta["_v"] = now, SCHEMA
    try:
        path.write_text(json.dumps(meta), encoding="utf-8")
    except OSError:
        pass
    return meta


def image(url: str, fetch: Optional[Callable[[str], bytes]] = None, any_host: bool = False) -> Optional[str]:
    """A local copy of an image (icon/screenshot); None if it can't be had. Only Flathub's, unless ``any_host``:
    this system's own AppStream catalog names each publisher's site, always over https."""
    if not url or not (url.startswith("https://") if any_host else url.startswith(_SAFE_HOSTS)):
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
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.{threading.get_ident()}.part")
    try:
        tmp.write_bytes(data)
        tmp.replace(path)
    except OSError as e:                              # a concurrent writer, or a full disk: not worth failing over
        log.info("store_art.image_not_cached %s: %s", url, e)
        return str(path) if path.exists() else None
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
