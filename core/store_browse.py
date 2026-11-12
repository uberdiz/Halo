"""
core/store_browse.py

The Store's whole catalogue, a page at a time, and "Apps like this". Search finds anything; this is what makes
the home screen browsable without knowing a name.

    Catalogue(category, source)  next_page() -> (results, more?)   popular Flathub apps, then Arch's desktop apps,
                                                                   then the AUR's well-voted packages
    similar(result, candidates)  -> deterministic ranking by shared categories

All of it is blocking and meant for a worker thread (ui.widgets.run_async). Flathub pages are cached on disk for
hours; when offline an old copy serves, and with no copy that source says so in Catalogue.failed and the others
still answer. The AUR's listing is one 10 MB download a day, fetched only when someone browses the AUR.
"""

from __future__ import annotations

import gzip
import json
import logging
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from core import saintos_apps as sa
from core import store, store_art
from core.store import Result

log = logging.getLogger("saint.store_browse")

FLATHUB_POPULAR = "https://flathub.org/api/v2/collection/popular?page={page}&per_page={per}"
FLATHUB_CATEGORY = "https://flathub.org/api/v2/collection/category/{cat}?page={page}&per_page={per}"
AUR_DUMP = "https://aur.archlinux.org/packages-meta-v1.json.gz"
PAGE_TTL = 6 * 3600
AUR_TTL = 24 * 3600
AUR_MIN_VOTES = 10                         # below this the AUR is mostly abandoned one-offs; search still finds them
AUR_KEEP = 5000
PER_PAGE = 24
BROWSE_SOURCES = ("flathub", "repo", "aur")


@dataclass(frozen=True)
class Category:
    label: str
    flathub: str = ""                      # Flathub's main category; "" = none (All, or SAINT's picks only)
    picks: Tuple[str, ...] = ()            # the catalog categories it shows


CATEGORIES = (
    Category("All"),
    Category("Games", "game", ("Gaming",)),
    Category("Developer", "development", ("Developer",)),
    Category("AI", "", ("AI",)),
    Category("Web & Chat", "network", ("Web & Chat",)),
    Category("Media", "audiovideo", ("Media",)),
    Category("Creative", "graphics", ("Creative",)),
    Category("Office", "office", ("Office & Utilities",)),
    Category("Utilities", "utility", ("Office & Utilities",)),
    Category("System", "system", ("Look & feel",)),
    Category("Education", "education"),
    Category("Science", "science"),
)
BY_LABEL = {c.label: c for c in CATEGORIES}
# Which main category a freedesktop category belongs to (AppStream data says "Video", Flathub's API "audiovideo").
_MAIN = {"audiovideo": "audiovideo", "audio": "audiovideo", "video": "audiovideo", "development": "development",
         "education": "education", "game": "game", "graphics": "graphics", "network": "network", "office": "office",
         "science": "science", "system": "system", "utility": "utility"}
# A catalog category, as the tags Flathub's categories use.
_PICK_TAGS = {"Gaming": {"game"}, "Developer": {"development"}, "Web & Chat": {"network"}, "Media": {"audiovideo"},
              "Creative": {"graphics"}, "Office & Utilities": {"office", "utility"}, "Look & feel": {"system"},
              "AI": {"ai"}}
# Says how an app is built, not what it's for.
_NOISE = {"qt", "gtk", "kde", "gnome", "xfce", "application", "other"}


def _trim(hit: Dict) -> Dict:
    return {k: hit.get(k) for k in ("app_id", "name", "summary", "icon", "main_categories", "sub_categories",
                                    "developer_name", "installs_last_month")}


def flathub_page(category: str, page: int, per_page: int = PER_PAGE, fetch: Optional[Callable] = None,
                 now: Optional[float] = None) -> Tuple[List[Dict], int]:
    """One page of Flathub, most popular first: (hits, total pages). Raises when offline with no copy on disk."""
    now = now if now is not None else time.time()
    slug = re.sub(r"[^a-z]", "", category.lower()) or "popular"
    path = store_art.cache_dir() / f"browse-{slug}-{per_page}-{page}.json"
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
        if now - cached.get("_at", 0) < PAGE_TTL:
            return cached["hits"], cached["pages"]
    except (OSError, ValueError, KeyError):
        cached = None
    url = (FLATHUB_CATEGORY.format(cat=slug, page=page, per=per_page) if category
           else FLATHUB_POPULAR.format(page=page, per=per_page))
    try:
        data = (fetch or store._get_json)(url) or {}
    except Exception as e:
        if cached and "hits" in cached:
            log.info("store_browse.using_stale_page %s: %s", slug, e)
            return cached["hits"], cached["pages"]
        raise
    hits, pages = [_trim(h) for h in data.get("hits", [])], int(data.get("totalPages") or 0)
    try:
        path.write_text(json.dumps({"hits": hits, "pages": pages, "_at": now}), encoding="utf-8")
    except OSError:
        pass
    return hits, pages


def arch_apps(category: str = "", run: Callable = subprocess.run, index: Optional[Dict[str, Dict]] = None) -> List[Result]:
    """Arch's desktop apps from this system's AppStream catalog: real apps, with their categories. Without that
    catalog, pacman's whole list minus libraries and the like, and only under "All" (it has no categories)."""
    index = index if index is not None else store_art.package_index()
    if not index:
        return [r for r in store.search_repo(".", run) if store.app_type(r) != "system"] if not category else []
    out = []
    for pkg, meta in index.items():
        cats = [c for c in meta.get("categories", []) if c]
        if category and category not in {_MAIN.get(c.lower()) for c in cats}:
            continue
        if store._PKG.match(pkg):
            out.append(Result("repo", pkg, meta.get("name") or pkg, meta.get("summary", ""),
                              extra={"repo": meta.get("repo", ""), "developer": meta.get("developer", ""),
                                     "categories": cats}))
    # The ones with pictures read best, so they come first; a stable order pages reliably.
    out.sort(key=lambda r: (not index[r.id].get("screenshots"), r.name.lower()))
    return out


def aur_apps(fetch: Optional[Callable[[str], bytes]] = None, now: Optional[float] = None) -> List[Result]:
    """The AUR's popular packages, most popular first. The AUR publishes this list for tools to use instead of
    hammering its search; it has no categories. Raises when offline with no copy on disk."""
    now = now if now is not None else time.time()
    path = store_art.cache_dir() / "browse-aur.json"
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cached = None
    if not cached or now - cached.get("_at", 0) >= AUR_TTL:
        try:
            rows = json.loads(gzip.decompress((fetch or store_art._get_bytes)(AUR_DUMP)))
            keep = [[r["Name"], r.get("Description") or "", r.get("Version", ""), r.get("NumVotes", 0),
                     r.get("Popularity", 0.0), r.get("Maintainer"), bool(r.get("OutOfDate"))]
                    for r in rows if r.get("NumVotes", 0) >= AUR_MIN_VOTES and store._PKG.match(r.get("Name", ""))
                    and not r["Name"].endswith(("-git", "-debug", "-svn", "-hg"))]
            keep.sort(key=lambda k: (-float(k[4] or 0), -int(k[3] or 0), k[0]))
            cached = {"rows": keep[:AUR_KEEP], "_at": now}
            try:
                path.write_text(json.dumps(cached), encoding="utf-8")
            except OSError:
                pass
        except (ValueError, OSError, EOFError, KeyError, TypeError) as e:
            if not cached:
                raise RuntimeError(f"the AUR's list isn't readable: {e}") from e
        except Exception:                  # requests' errors: offline
            if not cached:
                raise
    out = []
    for name, desc, version, votes, popularity, maintainer, stale in cached["rows"]:
        r = Result("aur", name, name, desc, version, extra={"votes": votes, "popularity": popularity,
                                                            "out_of_date": stale, "maintainer": maintainer,
                                                            "url": store.AUR_PKG.format(name=name)})
        if store.app_type(r) != "system":
            out.append(r)
    return out


class Catalogue:
    """The listing behind the home screen, one page per ``next_page()``. Each app once: a Flathub app that's one of
    SAINT's picks shows as the pick, and an Arch or AUR package named like an app already listed is skipped."""

    def __init__(self, category: str = "All", source: Optional[str] = None, per_page: int = PER_PAGE,
                 catalog: Optional[Dict[str, sa.App]] = None, flathub: Callable = flathub_page,
                 arch: Callable = arch_apps, aur: Callable = aur_apps):
        self.category = BY_LABEL.get(category, CATEGORIES[0])
        self.per_page = per_page
        self.failed: List[str] = []        # the sources that couldn't answer
        self._flathub, self._arch, self._aur = flathub, arch, aur
        self._picks = {a.ref if a.method == "flatpak" else a.art: a for a in (catalog or {}).values()
                       if a.method == "flatpak" or a.art}
        browsable = self.category.flathub or self.category is CATEGORIES[0]        # "AI" is SAINT's picks only
        self._sources = [] if not browsable else [source] if source else list(BROWSE_SOURCES)
        if self.category.flathub and not source:
            self._sources = [s for s in self._sources if s != "aur"]               # the AUR has no categories
        self._page = 1
        self._rows: Optional[List[Result]] = None
        self._pos = 0
        self._seen: set = set()

    def _flathub_rows(self) -> Tuple[List[Result], bool]:
        hits, pages = self._flathub(self.category.flathub, self._page, self.per_page)
        self._page += 1
        out = []
        for hit in hits:
            r = store.flathub_result(hit)
            if r:
                pick = self._picks.get(r.id)
                out.append(store.pick_result(pick) if pick else r)
        return out, self._page <= pages and bool(hits)

    def _source_rows(self, source: str) -> List[Result]:
        if self._rows is None:
            self._rows = (self._arch(self.category.flathub) if source == "repo" else self._aur())
            self._pos = 0
        rows = self._rows[self._pos:self._pos + self.per_page]
        self._pos += self.per_page
        return rows

    def _fresh(self, rows: Iterable[Result]) -> List[Result]:
        out = []
        for r in rows:
            keys = {store.app_key(r), store_art._name_key(r.name)}
            if keys & self._seen:
                continue
            self._seen |= keys
            out.append(r)
        return out

    def next_page(self) -> Tuple[List[Result], bool]:
        """(the next apps, whether there are more)."""
        while self._sources:
            source = self._sources[0]
            try:
                if source == "flathub":
                    rows, more = self._flathub_rows()
                else:
                    rows = self._source_rows(source)
                    more = self._pos < len(self._rows or [])
            except Exception as e:
                log.info("store_browse.source_unavailable %s: %s", source, e)
                self.failed.append(source)
                rows, more = [], False
            if not more:
                self._sources.pop(0)
                self._rows = None
            fresh = self._fresh(rows)
            if fresh:
                return fresh, bool(self._sources)
        return [], False


def tags_of(r: Result, categories: Iterable[str] = ()) -> set:
    """What an app is, as lower-case category names: Flathub's, AppStream's or the catalog's."""
    e = r.extra or {}
    tags = {c.lower() for c in [*(e.get("categories") or []), *categories] if c}
    tags |= {m for m in (_MAIN.get(t) for t in tags) if m}
    tags |= _PICK_TAGS.get(e.get("category", ""), set())
    return tags - _NOISE


def similar(r: Result, candidates: Iterable[Result], categories: Iterable[str] = (), limit: int = 8) -> List[Result]:
    """Apps sharing the most categories with ``r``, most popular first; the same input gives the same list, and
    never the app itself."""
    mine = tags_of(r, categories)
    seen = {store.app_key(r)}
    scored = []
    for c in candidates:
        key = store.app_key(c)
        shared = len(mine & tags_of(c))
        if shared and key not in seen:
            seen.add(key)
            scored.append((-shared, -int((c.extra or {}).get("installs") or 0), c.name.lower(), c))
    scored.sort(key=lambda s: s[:3])
    return [s[3] for s in scored[:limit]]


def similar_for(r: Result, catalog: Optional[Dict[str, sa.App]] = None, limit: int = 8, fetch: Optional[Callable] = None,
                meta: Optional[Dict] = None) -> List[Result]:
    """``similar`` over SAINT's picks and the most popular apps in this app's main category."""
    catalog = catalog if catalog is not None else sa.load_catalog()
    if meta is None:
        from core.config import config
        fid = store_art.flathub_id(r) or ""
        meta = store_art.app_metadata(fid, "" if fid else r.name) if config.get("store.artwork", True) else {}
    categories = meta.get("categories") or []
    picks = {a.ref if a.method == "flatpak" else a.art: a for a in catalog.values() if a.method == "flatpak" or a.art}
    candidates = [store.pick_result(a) for a in catalog.values()]
    # First the app's own main category (categories are listed most specific last, so read them in order).
    main = next((m for m in (_MAIN.get(t.lower()) for t in [*categories, *((r.extra or {}).get("categories") or [])]) if m),
                next(iter(sorted(_PICK_TAGS.get((r.extra or {}).get("category", ""), set()) - {"ai"})), ""))
    if main:
        try:
            for hit in flathub_page(main, 1, 48, fetch=fetch)[0]:
                c = store.flathub_result(hit)
                if c and c.id not in picks:
                    candidates.append(c)
        except Exception as e:                 # offline: the picks still give an answer
            log.info("store_browse.similar_offline %s", e)
    return similar(r, candidates, categories, limit)
