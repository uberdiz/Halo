"""
core/store.py

SAINT Store (Halo): one search over every place Halo gets apps from, installed through one queue.

    featured  SAINT's picks (packaging/linux/apps/catalog.json): Roblox, Roblox Studio, VS Code, Blender...
    repo      Arch Linux's official repositories      pacman -Ss
    flathub   Flathub                                  flathub.org search API (or `flatpak search`)
    aur       the Arch User Repository                 aur.archlinux.org RPC v5 (votes, popularity, out of date)
    windows   Windows apps through Wine                core/winapps.py (winget's catalog)

    search("blender")            -> [Result, ...] best first (exact names, then featured, repo, flathub, aur)
    plan(result)                 -> [core.saintos_apps.Step, ...] argument lists for core.saintos_apps.run_plan

Searching is read-only. Install commands are built only from names that pass strict patterns, so a
search result (which comes from the network) can't smuggle options or shell syntax into a command.
AUR packages are built by paru as the user (never root); the AUR is user-submitted, so results carry
votes, popularity and the PKGBUILD link, and the Store says so before installing.
"""

from concurrent.futures import ThreadPoolExecutor
import logging
import os
import posixpath
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional
from urllib.parse import quote

from core import saintos_apps as sa

log = logging.getLogger("saint.store")

SOURCES = ("featured", "repo", "flathub", "aur", "windows")
SOURCE_LABEL = {"featured": "SAINT pick", "repo": "Arch", "flathub": "Flathub", "aur": "AUR", "windows": "Windows app"}
AUR_RPC = "https://aur.archlinux.org/rpc/v5/search/{q}?by=name-desc"
AUR_PKG = "https://aur.archlinux.org/packages/{name}"
FLATHUB_SEARCH = "https://flathub.org/api/v2/search"
_PKG = re.compile(r"^[a-z0-9@_+][a-z0-9@._+-]{0,127}$")
_REPO_LINE = re.compile(r"^(?P<repo>[a-z0-9-]+)/(?P<name>\S+) (?P<version>\S+)(?P<rest>.*)$")


@dataclass
class Result:
    source: str
    id: str                          # package name, Flatpak id, catalog id or winget id
    name: str
    summary: str = ""
    version: str = ""
    installed: bool = False
    extra: Dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        return SOURCE_LABEL.get(self.source, self.source)


def _ok_query(q: str) -> str:
    q = " ".join(q.split())[:64]
    if not q or q.startswith("-"):
        raise ValueError("empty or invalid search")
    return q


def pick_result(a: sa.App) -> Result:
    """A catalog app as a Store result."""
    return Result("featured", a.id, a.name, a.about, extra={"method": a.method, "ref": a.ref, "arch": a.arch, "art": a.art,
                                                            "category": a.category, "icon_file": a.icon,
                                                            "developer": a.developer})


def flathub_result(hit: Dict) -> Optional[Result]:
    """One Flathub API hit as a Store result; None when its id isn't safe to install."""
    app_id = hit.get("app_id", "")
    if not sa._SAFE_FLATPAK.match(app_id):
        return None
    cats = hit.get("main_categories") or []
    cats = [cats] if isinstance(cats, str) else [c for c in cats if isinstance(c, str)]
    cats += [c for c in (hit.get("sub_categories") or []) if isinstance(c, str)]
    return Result("flathub", app_id, hit.get("name") or app_id, hit.get("summary") or "",
                  extra={"icon": hit.get("icon") or "", "developer": hit.get("developer_name") or "",
                         "categories": cats, "installs": hit.get("installs_last_month") or 0})


def app_key(r: Result) -> str:
    """What identifies the app itself: a pick and the Flathub or AUR result it installs are the same app."""
    e = r.extra or {}
    if r.source == "featured" and e.get("method") in ("flatpak", "aur"):
        return e.get("ref") or r.id
    return r.id


def search_featured(q: str, catalog: Optional[Dict[str, sa.App]] = None) -> List[Result]:
    catalog = catalog if catalog is not None else sa.load_catalog()
    words = q.lower().split()
    return [pick_result(a) for a in catalog.values()
            if all(w in f"{a.id} {a.name} {a.about} {a.category}".lower() for w in words)]


def search_repo(q: str, run: Callable = subprocess.run) -> List[Result]:
    try:
        out = run(["pacman", "-Ss", "--", q], capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    hits, cur = [], None
    for line in out.splitlines():
        m = _REPO_LINE.match(line)
        if m:
            cur = Result("repo", m["name"], m["name"], version=m["version"], installed="[installed" in m["rest"],
                         extra={"repo": m["repo"]})
            hits.append(cur)
        elif cur is not None and line.startswith("    "):
            cur.summary = line.strip()
    return [h for h in hits if _PKG.match(h.id)]


def search_aur(q: str, fetch: Optional[Callable] = None) -> List[Result]:
    fetch = fetch or _get_json
    try:
        data = fetch(AUR_RPC.format(q=quote(q, safe="")))
    except Exception as e:                                   # offline, AUR down: the other sources still answer
        log.info("store.aur_unavailable %s", e)
        return []
    hits = []
    for r in (data or {}).get("results", []):
        name = r.get("Name", "")
        if not _PKG.match(name):
            continue
        hits.append(Result("aur", name, name, r.get("Description") or "", r.get("Version", ""),
                           extra={"votes": r.get("NumVotes", 0), "popularity": r.get("Popularity", 0.0),
                                  "out_of_date": bool(r.get("OutOfDate")), "maintainer": r.get("Maintainer"),
                                  "url": AUR_PKG.format(name=name)}))
    hits.sort(key=lambda h: (-float(h.extra["popularity"] or 0), -int(h.extra["votes"] or 0)))
    return hits


def search_flathub(q: str, post: Optional[Callable] = None, run: Callable = subprocess.run) -> List[Result]:
    post = post or _post_json
    hits = []
    try:
        data = post(FLATHUB_SEARCH, {"query": q})
        hits = [r for r in map(flathub_result, (data or {}).get("hits", [])) if r]
        return hits
    except Exception as e:
        log.info("store.flathub_api_unavailable %s", e)
    try:                                                     # the local appstream data, when the API isn't there
        out = run(["flatpak", "search", "--columns=application,name,description", "--", q],
                  capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and sa._SAFE_FLATPAK.match(parts[0]):
            hits.append(Result("flathub", parts[0], parts[1], parts[2] if len(parts) > 2 else ""))
    return hits


def search(q: str, sources=SOURCES, catalog=None, run: Callable = subprocess.run, fetch=None, post=None,
           windows: Optional[Callable] = None, limit: int = 40,
           on_source: Optional[Callable[[str, int], None]] = None) -> List[Result]:
    """Best first: an exact name match, then SAINT's picks, Arch, Flathub, the AUR, Windows apps.
    ``on_source(source, count)`` is called (from a worker thread) as each source answers, for the UI's progress."""
    q = _ok_query(q)
    results: List[Result] = []
    told = on_source or (lambda _s, _n: None)
    if "featured" in sources:
        results += search_featured(q, catalog)
        told("featured", len(results))
    jobs: List[Callable[[], List[Result]]] = []          # one slow source mustn't hold up the others

    def job(source: str, fn: Callable[[], List[Result]]):
        def go():
            found = fn()
            told(source, len(found))
            return found
        jobs.append(go)
    if "repo" in sources:
        job("repo", lambda: search_repo(q, run))
    if "flathub" in sources:
        job("flathub", lambda: search_flathub(q, post, run))
    if "aur" in sources:
        job("aur", lambda: search_aur(q, fetch))
    if "windows" in sources:
        from core import winapps
        job("windows", lambda: (windows or winapps.search)(q))
    if jobs:
        with ThreadPoolExecutor(max_workers=len(jobs), thread_name_prefix="store-search") as pool:
            for found in pool.map(lambda j: j(), jobs):
                results += found
    featured_refs = {r.extra.get("ref") for r in results if r.source == "featured"}
    results = [r for r in results if r.source == "featured" or r.id not in featured_refs]   # a pick shows once
    order = {s: i for i, s in enumerate(SOURCES)}
    ql = q.lower()
    results.sort(key=lambda r: (r.name.lower() != ql and r.id.lower() != ql, order[r.source]))
    return results[:limit]


def plan(result: Result, catalog=None, home: Optional[str] = None) -> List[sa.Step]:
    """The install steps for one search result (argument lists only)."""
    if result.source == "featured":
        catalog = catalog if catalog is not None else sa.load_catalog()
        return sa.plan([result.id], catalog, home=home, manager="pacman")
    if result.source == "repo":
        _check(result.id)
        return [sa.Step(f"{result.name} (Arch)", ["pkexec", "pacman", "-Syu", "--needed", "--noconfirm", result.id],
                        [result.id], needs_admin=True)]
    if result.source == "aur":
        _check(result.id)
        return [sa.Step(f"{result.name} (AUR)", ["paru", "-S", "--needed", "--noconfirm", "--skipreview", "--sudo",
                                                 "pkexec", result.id], [result.id], needs_admin=True)]
    if result.source == "flathub":
        if not sa._SAFE_FLATPAK.match(result.id):
            raise ValueError(f"unsafe Flatpak id {result.id!r}")
        return [sa.Step("Flathub (for your user)", ["flatpak", "remote-add", "--user", "--if-not-exists", "flathub",
                                                    sa.FLATHUB], []),
                sa.Step(f"{result.name} (Flathub)", ["flatpak", "install", "--user", "-y", "--noninteractive",
                                                     "flathub", result.id], [result.id])]
    if result.source == "windows":
        from core import winapps
        return winapps.plan(result)
    raise ValueError(f"unknown source {result.source!r}")


# ---------------------------------------------------------------------- filters
# How an app runs on Halo. "blocked" = it won't (kernel anti-cheat, drivers): shown only when asked for, with why.
COMPAT = ("native", "flatpak", "aur", "wine", "blocked")
COMPAT_LABEL = {"native": "Native", "flatpak": "Flatpak", "aur": "AUR", "wine": "Windows (Wine)",
                "blocked": "Won't work"}
_METHOD_COMPAT = {"flatpak": "flatpak", "aur": "aur", "dnf": "native", "npm": "native"}
APP_TYPES = ("app", "game", "developer", "system")
APP_TYPE_LABEL = {"app": "Apps", "game": "Games", "developer": "Developer tools", "system": "Libraries & system"}
# Package names that are parts of the system rather than apps you open.
_SYSTEM_PKG = re.compile(r"^(lib|python-|python2-|perl-|ruby-|lua-|haskell-|r-|node-|go-|rust-|php-|ocaml-|"
                         r"ttf-|otf-|noto-|linux-|firmware|kernel|xf86-|gst-|qt[56]-|kf6-|gtk[234]?-)"
                         r"|-(docs?|headers|devel|dev|debug|libs|firmware|dkms|utils)$")


def compatibility(r: Result) -> str:
    """native / flatpak / aur / wine / blocked (one of COMPAT)."""
    e = r.extra or {}
    if e.get("blocked"):
        return "blocked"
    if r.source == "featured":
        return _METHOD_COMPAT.get(e.get("method", ""), "native")
    return {"repo": "native", "flathub": "flatpak", "aur": "aur", "windows": "wine"}.get(r.source,
                                                                                         e.get("compat", "native"))


def app_type(r: Result) -> str:
    """app / game / developer / system, from the catalog category or Flathub's categories, else the package name."""
    e = r.extra or {}
    cats = {c.lower() for c in (e.get("categories") or [])}
    cat = (e.get("category") or "").lower()
    if "gaming" in cat or "game" in cats:
        return "game"
    if "developer" in cat or "development" in cats:
        return "developer"
    if r.source in ("repo", "aur") and _SYSTEM_PKG.search(r.id):
        return "system"
    return "app"


def matches(r: Result, compat: Optional[str] = None, installed: Optional[bool] = None,
            kind: Optional[str] = None) -> bool:
    """Does a result pass the Store's filters? None = any. A "won't work" app shows only under that filter."""
    c = compatibility(r)
    if (compat is None and c == "blocked") or (compat is not None and c != compat):
        return False
    if installed is not None and bool(r.installed) != installed:
        return False
    return kind is None or app_type(r) == kind


def installed(r: Result, run: Callable = subprocess.run, catalog=None) -> bool:
    """Is this search result installed? (pacman -Q / flatpak info / the Wine prefix)"""
    try:
        if r.source == "repo":
            return r.installed or run(["pacman", "-Q", r.id], capture_output=True).returncode == 0
        if r.source == "aur":
            return run(["pacman", "-Q", r.id], capture_output=True).returncode == 0
        if r.source == "flathub":
            return run(["flatpak", "info", r.id], capture_output=True).returncode == 0
        if r.source == "featured":
            catalog = catalog if catalog is not None else sa.load_catalog()
            return r.id in catalog and sa.installed(catalog[r.id], run)
        if r.source == "windows":
            from core import winapps
            return (winapps.prefix_for(r.id) / "drive_c").is_dir()
    except (OSError, ValueError):
        return False
    return False


def installed_snapshot(run: Callable = subprocess.run) -> Dict[str, Optional[set]]:
    """Everything installed, in two quick commands, so a page of apps doesn't start a process per card.
    A set is None when that tool isn't on this system (nothing is known about it, not "nothing's installed")."""
    def lines(argv):
        try:
            out = run(argv, capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return {ln.strip() for ln in (out.stdout or "").splitlines() if ln.strip()} if out.returncode == 0 else None
    return {"flatpak": lines(["flatpak", "list", "--app", "--columns=application"]),
            "pacman": lines(["pacman", "-Qq"])}


def is_installed(r: Result, snapshot: Dict[str, Optional[set]]) -> bool:
    """Is this result installed, going by ``installed_snapshot``? Keeps ``r.installed`` when that can't say."""
    e = r.extra or {}
    method = e.get("method") if r.source == "featured" else {"flathub": "flatpak", "repo": "dnf", "aur": "aur"}.get(
        r.source, "")
    if method == "flatpak" and snapshot.get("flatpak") is not None:
        return app_key(r) in snapshot["flatpak"]
    if method in ("aur", "dnf") and snapshot.get("pacman") is not None:
        names = e.get("arch", "").split() if r.source == "featured" and method == "dnf" else [app_key(r)]
        return bool(names) and all(n in snapshot["pacman"] for n in names)
    if method == "npm":
        return (Path.home() / ".local" / "lib" / "node_modules" / e.get("ref", "")).exists()
    if r.source == "windows":
        return installed(r)
    return r.installed


# Removing these would break Halo itself, or SAINT: the Store doesn't offer it.
_PROTECTED = {"saint", "saint-git", "halo-branding", "halo-system", "halo-calamares-config", "base", "linux", "systemd",
              "glibc", "pacman", "sudo", "polkit", "flatpak", "plasma-desktop", "plasma-workspace", "kwin", "sddm",
              "dolphin", "konsole", "networkmanager"}


def can_uninstall(r: Result) -> bool:
    """A bundle ("Developer tools": git, gcc...) stays: other things need what's in it."""
    e = r.extra or {}
    if r.source == "featured":
        if e.get("method") == "dnf":
            return False
        return e.get("ref") not in _PROTECTED
    return r.source in ("flathub", "repo", "aur") and r.id not in _PROTECTED


def uninstall_plan(r: Result, home: Optional[str] = None) -> List[sa.Step]:
    """The steps that remove an installed result (argument lists from checked names, never stored commands)."""
    if not can_uninstall(r):
        raise ValueError(f"The Store doesn't remove {r.name}.")
    e = r.extra or {}
    kind = e.get("method") if r.source == "featured" else r.source
    target = app_key(r)
    if kind in ("flatpak", "flathub"):
        if not sa._SAFE_FLATPAK.match(target):
            raise ValueError(f"unsafe Flatpak id {target!r}")
        return [sa.Step(f"Remove {r.name} (Flatpak)", ["flatpak", "uninstall", "-y", "--noninteractive", target],
                        [r.id])]
    if kind in ("repo", "aur"):
        _check(target)
        return [sa.Step(f"Remove {r.name}", ["pkexec", "pacman", "-R", "--noconfirm", target], [r.id],
                        needs_admin=True)]
    if kind == "npm":
        if not sa._SAFE_NPM.match(e.get("ref", "")):
            raise ValueError("unsafe npm package")
        prefix = posixpath.join(home or os.path.expanduser("~"), ".local")
        return [sa.Step(f"Remove {r.name} (npm)", ["npm", "uninstall", "-g", "--prefix", prefix, e["ref"]], [r.id])]
    raise ValueError(f"The Store doesn't know how to remove {r.name}.")


def openable(r: Result) -> bool:
    """Can "Open" start it? Terminal tools, bundles and Wine apps are opened some other way."""
    e = r.extra or {}
    return r.source in ("flathub", "repo", "aur") or (r.source == "featured" and e.get("method") in ("flatpak", "aur"))


def launch_argv(r: Result, run: Callable = subprocess.run) -> Optional[List[str]]:
    """How to start an installed app: its Flatpak, or the launcher (else the program) its package installed."""
    target = app_key(r)
    e = r.extra or {}
    if r.source == "flathub" or (r.source == "featured" and e.get("method") == "flatpak"):
        return ["flatpak", "run", target] if sa._SAFE_FLATPAK.match(target) else None
    if not openable(r) or not _PKG.match(target):
        return None
    try:
        out = run(["pacman", "-Qlq", target], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    files = (out.stdout or "").splitlines() if out.returncode == 0 else []
    desktop = next((f for f in files if f.startswith("/usr/share/applications/") and f.endswith(".desktop")), "")
    if desktop:
        return ["gio", "launch", desktop]
    prog = f"/usr/bin/{target}"
    return [prog] if prog in files else None


def install_source(r: Result) -> str:
    """Where an app actually comes from, for a person: a pick is from Flathub, Arch, the AUR or npm."""
    if r.source == "featured":
        return {"flatpak": "Flathub", "aur": "AUR", "dnf": "Arch", "npm": "npm"}.get((r.extra or {}).get("method"), "")
    return r.label


def source_link(r: Result) -> str:
    """The app's page at its source; "" when it has none."""
    e = r.extra or {}
    kind = e.get("method") if r.source == "featured" else r.source
    target = app_key(r)
    if kind in ("flatpak", "flathub"):
        return f"https://flathub.org/apps/{quote(target, safe='')}"
    if kind == "aur":
        return e.get("url") or AUR_PKG.format(name=quote(target, safe=""))
    if kind == "repo":
        return f"https://archlinux.org/packages/?name={quote(target, safe='')}"
    return ""


def open_store_app(*args: str, popen: Callable = subprocess.Popen, exists: Callable = os.path.exists) -> bool:
    """Open SAINT Store, its own app (`saint-store`; it brings a running Store forward). False if it can't start."""
    exe = "/usr/bin/saint-store"
    root = Path(__file__).resolve().parent.parent
    argv, cwd = ([exe, *args], None) if exists(exe) else ([sys.executable, "-m", "ui.store_app", *args], str(root))
    try:
        popen(argv, cwd=cwd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError as e:
        log.warning("store.open_failed %s", e)
        return False


def _check(name: str):
    if not _PKG.match(name):
        raise ValueError(f"unsafe package name {name!r}")


def _get_json(url: str):
    import requests
    r = requests.get(url, timeout=10, headers={"User-Agent": "SAINT-Store/1"})
    r.raise_for_status()
    return r.json()


def _post_json(url: str, body: dict):
    import requests
    r = requests.post(url, json=body, timeout=10, headers={"User-Agent": "SAINT-Store/1"})
    r.raise_for_status()
    return r.json()
