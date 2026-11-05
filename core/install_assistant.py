"""
core/install_assistant.py

The universal installation assistant (Halo): give SAINT a link, a GitHub release or a package file and it
works out what it is, shows a plan, installs it once you say yes, checks the app really starts, and keeps a
history you can uninstall and repair from.

    detect(text)          -> Target        what the input points at (kind, file, where from, checksum)
    build_plan(target)    -> InstallPlan   steps (core.saintos_apps.Step), risk and why, how to verify it
    plan_for(text)        -> InstallPlan   both
    verify(plan.verify)   -> {"installed", "launched", "detail"}   installed? does it start? (process appears)
    History               install history (JSON); uninstall_steps(entry), repair_plan(entry)

Inputs it understands:

    https://github.com/owner/repo[/releases[/tag/v1|/latest]]   the release's best asset for Halo
    https://github.com/owner/repo/releases/download/v1/file      that asset
    https://flathub.org/apps/<id>  or an app id (org.foo.Bar)    Flathub
    https://host/path/file.ext  or a file on this computer       by extension:
        .pkg.tar.zst/.xz   Arch package      pkexec pacman -U
        .flatpakref        Flatpak ref       flatpak install --user --from
        .AppImage          AppImage          into ~/Applications + a start-menu entry
        .deb               Debian package    converted with debtap, then pacman -U
        .exe / .msi        Windows app       Wine, in its own prefix (core/winapps.py)

Nothing here asks a model anything: the same input always gives the same plan. Steps are argument lists run
by core.saintos_apps.run_plan (so progress and failure reasons are the Store's own); downloads go through
core/winapps.py's fetch helper, which checks the SHA-256 when the publisher gives one (GitHub's asset digest
or a checksum file in the same release) and otherwise says, in the plan, that it can't. A Windows app or a
.deb with a native/Flatpak version in the Store gets that version offered first.

This file also runs as a small helper for the install steps (python install_assistant.py appimage ...).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import quote, unquote, urlparse

if __package__ in (None, ""):                    # run as a helper script by an install step
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import saintos_apps as sa              # noqa: E402
from core import winapps                         # noqa: E402

KIND_LABEL = {"pacman": "Arch package", "flatpakref": "Flatpak (.flatpakref)", "flathub": "Flathub app",
              "appimage": "AppImage", "deb": "Debian package (.deb)", "windows": "Windows app (Wine)"}
KIND_COMPAT = {"pacman": "native", "flatpakref": "flatpak", "flathub": "flatpak", "appimage": "native",
               "deb": "native", "windows": "wine"}
RISKS = ("low", "medium", "high")
GITHUB_API = "https://api.github.com/repos/{owner}/{repo}/releases/{which}"
_GITHUB = re.compile(r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]{1,100})/(?P<repo>[A-Za-z0-9_.-]{1,100})"
                     r"(?P<rest>/[^?#]*)?(?:[?#].*)?$")
_FLATHUB_PAGE = re.compile(r"^https://flathub\.org/(?:[a-z]{2}(?:[-_][A-Za-z]{2,4})?/)?apps/(?P<id>[A-Za-z0-9_.-]+)/?$")
_DOWNLOAD_HOSTS = ("https://github.com/", "https://objects.githubusercontent.com/",
                   "https://release-assets.githubusercontent.com/")
_PKGFILE = re.compile(r"^(?P<name>[a-z0-9@_+][a-z0-9@._+-]*)-(?P<ver>[^-/]+)-(?P<rel>[^-/]+)-(?P<arch>[^-/.]+)"
                      r"\.pkg\.tar\.(zst|xz|gz)$")
_SHA = re.compile(r"^[0-9a-fA-F]{64}$")
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
_PKG = re.compile(r"^[a-z0-9@_+][a-z0-9@._+-]{0,127}$")
_NOISE = re.compile(r"^(v?\d.*|x86[_-]?64|amd64|x64|win(32|64)?|windows|linux|setup|installer|install|portable|"
                    r"release|latest|stable|full|x86|i[3-6]86|64bit|32bit|any)$", re.I)
_CHECKSUM_FILES = ("sha256sums", "sha256sums.txt", "sha256sum.txt", "checksums.txt", "checksums.sha256",
                   "sha256.txt", "checksum.txt")


# --------------------------------------------------------------------------- what the input is
@dataclass
class Target:
    kind: str                       # one of KIND_LABEL
    name: str                       # a display name (from the repo or the file name)
    filename: str = ""
    url: str = ""                   # https download, when it isn't a local file
    path: str = ""                  # a local file
    sha256: str = ""
    checksum_from: str = ""         # where the SHA-256 comes from, said to the user ("" = none published)
    origin: str = ""                # where it comes from, said to the user
    flatpak_id: str = ""
    content: str = ""               # a .flatpakref's text (read when planning, so what's shown is what's installed)


def kind_of(filename: str) -> str:
    """The kind of package a file name is; ValueError says why when SAINT can't install it."""
    n = filename.lower()
    if re.search(r"\.pkg\.tar\.(zst|xz|gz)$", n):
        return "pacman"
    for ext, kind in ((".flatpakref", "flatpakref"), (".appimage", "appimage"), (".deb", "deb"),
                      (".exe", "windows"), (".msi", "windows")):
        if n.endswith(ext):
            return kind
    if n.endswith(".rpm"):
        raise ValueError("That's an RPM package (Fedora/openSUSE). Halo is Arch-based: search the Store for the "
                         "same app instead.")
    if n.endswith((".dmg", ".pkg")):
        raise ValueError("That's a macOS installer; it can't run on Halo.")
    if n.endswith(".flatpak"):
        raise ValueError("Single-file .flatpak bundles aren't supported yet: use the app's .flatpakref or Flathub.")
    if n.endswith((".zip", ".tar.gz", ".tgz", ".tar.xz", ".7z")):
        raise ValueError("That's an archive: SAINT can't tell which program inside it to install. Look for an "
                         "AppImage, .pkg.tar.zst, .deb or .flatpakref of the app.")
    raise ValueError(f"SAINT doesn't recognise “{filename}”. It installs .pkg.tar.zst, .flatpakref, .AppImage, "
                     ".deb, .exe and .msi files, GitHub releases and Flathub apps.")


def guess_name(filename: str) -> str:
    """'HeroicGamesLauncher-2.15.2.AppImage' -> 'Heroic Games Launcher' (for display and the Store search)."""
    base = re.sub(r"\.(pkg\.tar\.(zst|xz|gz)|flatpakref|appimage|deb|exe|msi)$", "", filename, flags=re.I)
    words = []
    for tok in re.split(r"[-_ .]+", base):
        if not tok:
            continue
        if _NOISE.match(tok):
            break
        words.append(tok)
    name = " ".join(words) or base or "App"
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).strip()


def _pretty_repo(repo: str) -> str:
    return re.sub(r"[-_]+", " ", repo).strip() or repo


def _asset_rank(name: str) -> Optional[Tuple[int, int]]:
    """Lower is better; None = not something Halo can install."""
    n = name.lower()
    try:
        kind = kind_of(n)
    except ValueError:
        return None
    other_arch = re.search(r"arm64|aarch64|armv7|armhf|arm\b|i386|i686|ppc64|s390x|riscv", n)
    if other_arch and not re.search(r"x86[_-]?64|amd64|x64", n):
        return None
    order = {"pacman": 0, "flatpakref": 1, "appimage": 2, "deb": 3, "windows": 4}[kind]
    if n.endswith(".msi"):
        order = 5
    return order, 0 if re.search(r"x86[_-]?64|amd64|x64", n) else 1


def pick_asset(assets: List[dict]) -> dict:
    """The release file to install on Halo: a native package, then Flatpak, AppImage, .deb, Windows installer."""
    ranked = sorted(((r, a) for a in assets if (r := _asset_rank(a.get("name", ""))) is not None),
                    key=lambda ra: ra[0])
    if not ranked:
        names = ", ".join(a.get("name", "?") for a in assets[:12]) or "no files"
        raise ValueError(f"This release has nothing Halo can install ({names}).")
    return ranked[0][1]


def parse_checksums(text: str, filename: str) -> str:
    """The SHA-256 for ``filename`` from a checksum file (GNU 'hash  name', BSD 'SHA256 (name) = hash', or a
    file holding one hash); '' when it isn't there."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines:
        m = re.match(r"^SHA256 \((?P<f>.+)\) = (?P<h>[0-9a-fA-F]{64})$", line)
        if m and os.path.basename(m["f"]) == filename:
            return m["h"].lower()
        parts = line.split()
        if len(parts) >= 2 and _SHA.match(parts[0]) and os.path.basename(parts[-1].lstrip("*")) == filename:
            return parts[0].lower()
    if len(lines) == 1 and _SHA.match(lines[0].split()[0]) and len(lines[0].split()) == 1:
        return lines[0].split()[0].lower()
    return ""


def _asset_checksum(asset: dict, assets: List[dict], fetch_text: Callable[[str], str]) -> Tuple[str, str]:
    digest = asset.get("digest") or ""
    if digest.startswith("sha256:") and _SHA.match(digest[7:]):
        return digest[7:].lower(), "GitHub's SHA-256 for this file"
    name = asset.get("name", "")
    wanted = {f"{name.lower()}.sha256", f"{name.lower()}.sha256sum", *_CHECKSUM_FILES}
    for a in assets:
        if a.get("name", "").lower() in wanted and str(a.get("browser_download_url", "")).startswith(_DOWNLOAD_HOSTS):
            try:
                sha = parse_checksums(fetch_text(a["browser_download_url"]) or "", name)
            except Exception:
                continue
            if sha:
                return sha, f"{a['name']} in the same release"
    return "", ""


def _github(m, url: str, fetch_json: Callable, fetch_text: Callable) -> Target:
    owner, repo = m["owner"], re.sub(r"\.git$", "", m["repo"])
    rest = [p for p in (m["rest"] or "").split("/") if p]
    want, tag = "", ""
    if rest[:2] == ["releases", "download"] and len(rest) >= 4:
        tag, want = unquote(rest[2]), unquote(rest[-1])
    elif rest[:2] == ["releases", "tag"] and len(rest) >= 3:
        tag = unquote(rest[2])
    api = GITHUB_API.format(owner=owner, repo=repo, which=f"tags/{quote(tag, safe='')}" if tag else "latest")
    try:
        rel = fetch_json(api) or {}
    except Exception as e:
        if want:                                  # a direct link still works without the API (no checksum)
            return _plain_url(url, origin=f"github.com/{owner}/{repo}, release {tag}")
        raise ValueError(f"Couldn't read the release from GitHub ({e}).")
    assets = rel.get("assets") or []
    if want:
        asset = next((a for a in assets if a.get("name") == want), None)
        if asset is None:
            raise ValueError(f"The release {tag} has no file called {want}.")
        kind_of(want)
    else:
        asset = pick_asset(assets)
    dl = str(asset.get("browser_download_url", ""))
    if not dl.startswith(_DOWNLOAD_HOSTS):
        raise ValueError("GitHub gave a download link that isn't on github.com.")
    sha, frm = _asset_checksum(asset, assets, fetch_text)
    fname = asset["name"]
    kind = kind_of(fname)
    pm = _PKGFILE.match(fname)
    name = pm["name"] if kind == "pacman" and pm else _pretty_repo(repo)
    return Target(kind, name, filename=fname, url=dl, sha256=sha, checksum_from=frm,
                  origin=f"github.com/{owner}/{repo}, release {rel.get('tag_name') or tag or 'latest'}")


def _plain_url(url: str, origin: str = "") -> Target:
    p = urlparse(url)
    fname = os.path.basename(unquote(p.path))
    if not fname:
        raise ValueError("That link doesn't end in a file name.")
    kind = kind_of(fname)
    return Target(kind, guess_name(fname), filename=fname, url=url, origin=origin or p.netloc)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def detect(text: str, fetch_json: Optional[Callable] = None, fetch_text: Optional[Callable] = None,
           isfile: Callable[[str], bool] = os.path.isfile) -> Target:
    """What ``text`` (a link, a GitHub release, a Flathub app or a file) points at. ValueError says why not."""
    fetch_json = fetch_json or _get_json
    fetch_text = fetch_text or _get_text
    s = text.strip().strip('"').strip("'")
    if not s:
        raise ValueError("Paste a link or choose a file first.")
    if s.startswith("file://"):
        s = unquote(urlparse(s).path)
        if re.match(r"^/[A-Za-z]:/", s):          # file:///C:/... on Windows
            s = s[1:]
    if re.match(r"^[a-z]+://", s, re.I):
        if not s.lower().startswith("https://"):
            raise ValueError("Only https links: an http download could be changed on the way.")
        if any(c.isspace() for c in s):
            raise ValueError("That link has spaces in it.")
        if (m := _FLATHUB_PAGE.match(s)) and sa._SAFE_FLATPAK.match(m["id"]):
            return Target("flathub", m["id"].split(".")[-1], flatpak_id=m["id"], origin="Flathub")
        if m := _GITHUB.match(s):
            t = _github(m, s, fetch_json, fetch_text)
        else:
            t = _plain_url(s)
        if t.kind == "flatpakref":
            t.content = fetch_text(t.url) or ""
        return t
    if isfile(s):
        fname = os.path.basename(s)
        kind = kind_of(fname)
        name = guess_name(fname)
        if kind == "pacman" and (pm := _PKGFILE.match(fname)):
            name = pm["name"]
        t = Target(kind, name, filename=fname, path=os.path.abspath(s), sha256=sha256_file(s),
                   checksum_from="worked out from the file (it has no publisher checksum)",
                   origin="a file on this computer")
        if kind == "flatpakref":
            t.content = Path(s).read_text(encoding="utf-8", errors="replace")
        return t
    if sa._SAFE_FLATPAK.match(s) and "/" not in s and "\\" not in s:
        try:
            kind_of(s)                            # "Some-1.2.AppImage" looks like an id too: it's a missing file
        except ValueError:
            return Target("flathub", s.split(".")[-1], flatpak_id=s, origin="Flathub")
        raise ValueError(f"There's no file called {s} here.")
    if re.search(r"[\\/]", s) or re.search(r"\.[A-Za-z0-9]{2,11}$", s):
        raise ValueError(f"There's no file at {s}.")
    raise ValueError("SAINT needs a link (https://…), a GitHub release, a Flathub app id or a package file.")


def parse_flatpakref(text: str) -> Dict[str, str]:
    out = {}
    section = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            section = line
        elif "=" in line and section == "[Flatpak Ref]":
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


# --------------------------------------------------------------------------- the plan
@dataclass
class InstallPlan:
    input: str
    target: Target
    app_id: str                     # the history key: "pacman:<name>", "flatpak:<id>", "appimage:<slug>", "wine:<x>"
    name: str
    kind: str
    steps: List[sa.Step] = field(default_factory=list)
    risk: str = "low"
    reasons: List[str] = field(default_factory=list)
    verify: Dict = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    alternatives: List = field(default_factory=list)     # core.store.Result: a native/Flatpak version, first
    blocked: str = ""               # why it can't work at all ("" = it can)

    @property
    def checksum(self) -> str:
        t = self.target
        if t.sha256:
            return f"SHA-256 {t.sha256[:16]}… ({t.checksum_from})"
        if self.kind == "flathub":
            return "Flathub signs its apps (checked by flatpak)"
        return "none published: the download can't be checked"

    def lines(self) -> List[str]:
        """The plan, said plainly (for the Store's plan card and logs)."""
        out = [f"{self.name} — {KIND_LABEL[self.kind]}", f"From: {self.target.origin or '?'}",
               f"Checksum: {self.checksum}", f"Risk: {self.risk}"] + [f"  · {r}" for r in self.reasons]
        out += [f"{i}. {s.label}" + (" (asks for your password)" if s.needs_admin else "")
                for i, s in enumerate(self.steps, 1)]
        return out + self.notes


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48].strip("-") or "app"


def _safe_filename(name: str) -> str:
    n = re.sub(r"[^A-Za-z0-9._+-]", "_", name)[:120]
    return "_" + n if n.startswith(("-", ".")) else n


def _apps_dir() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "applications"


def _raise(risk: str, to: str) -> str:
    return max(risk, to, key=RISKS.index)


def default_search(q: str) -> list:
    from core import store
    return store.search(q, sources=("featured", "repo", "flathub"), limit=12)


def alternatives(name: str, search: Callable[[str], list]) -> list:
    """Native or Flatpak versions of ``name`` in the Store (best first, at most 3)."""
    words = [w for w in re.split(r"\W+", name.lower()) if len(w) > 1]
    if not words:
        return []
    try:
        hits = search(" ".join(words[:3]))
    except Exception:
        return []
    joined = "".join(words)
    good = [r for r in hits if r.source in ("featured", "repo", "flathub")
            and (all(w in r.name.lower() for w in words) or re.sub(r"\W", "", r.name.lower()) == joined)]
    return good[:3]


def build_plan(t: Target, text: str = "", which: Callable = shutil.which, python: str = sys.executable,
               exists: Callable[[str], bool] = os.path.exists, search: Optional[Callable] = None) -> InstallPlan:
    """The steps for one target, with the risk said in words. ValueError when it can't be installed at all."""
    from core import store
    helper = str(Path(__file__).resolve())
    file = t.path
    steps: List[sa.Step] = []
    reasons: List[str] = []
    notes: List[str] = []
    risk = "low"

    def download(app_id: str):
        nonlocal file
        if t.path:
            return
        if not t.url.startswith("https://"):
            raise ValueError("Only https downloads.")
        file = str(winapps.CACHE / "assistant" / slug(t.name) / _safe_filename(t.filename))
        steps.append(winapps.download_step(t.name, t.url, t.sha256 or winapps.UNVERIFIED, file, app_id, python))

    if t.kind == "flathub":
        if not sa._SAFE_FLATPAK.match(t.flatpak_id):
            raise ValueError(f"{t.flatpak_id!r} isn't a Flatpak app id.")
        app_id = f"flatpak:{t.flatpak_id}"
        steps = store.plan(store.Result("flathub", t.flatpak_id, t.name))
        for s in steps:
            s.apps = [app_id] if s.apps else []
        reasons.append("From Flathub: sandboxed, and signed by Flathub.")
        verify = {"flatpak": t.flatpak_id}
    elif t.kind == "flatpakref":
        ref = parse_flatpakref(t.content)
        fid = ref.get("Name", "")
        if not sa._SAFE_FLATPAK.match(fid):
            raise ValueError("This .flatpakref doesn't name a valid app.")
        app_id = f"flatpak:{fid}"
        t.name = ref.get("Title") or t.name
        remote = urlparse(ref.get("Url", "")).netloc
        if not t.path:                            # install exactly the text that was read for this plan
            cache = winapps.CACHE / "assistant" / slug(fid)
            cache.mkdir(parents=True, exist_ok=True)
            file = str(cache / _safe_filename(t.filename or f"{fid}.flatpakref"))
            Path(file).write_text(t.content, encoding="utf-8")
            t.sha256 = hashlib.sha256(t.content.encode("utf-8")).hexdigest()
            t.checksum_from = "of the .flatpakref read for this plan (flatpak checks the app's own signature)"
        steps.append(sa.Step(f"{t.name} (Flatpak, for your user)",
                             ["flatpak", "install", "--user", "-y", "--noninteractive", "--from", file], [app_id]))
        if remote == "dl.flathub.org":
            reasons.append("The app comes from Flathub: sandboxed, and signed by Flathub.")
        else:
            risk = "medium"
            reasons.append(f"Adds the Flatpak source {remote or '(unnamed)'} for your user; its apps are signed by "
                           "that source, not Flathub.")
        verify = {"flatpak": fid}
    elif t.kind == "pacman":
        m = _PKGFILE.match(t.filename)
        if not m:
            raise ValueError("That file isn't named like an Arch package (name-version-release-arch.pkg.tar.zst).")
        if m["arch"] not in ("x86_64", "any"):
            raise ValueError(f"That package is for {m['arch']}; Halo is x86_64.")
        app_id = f"pacman:{m['name']}"
        t.name = m["name"]
        download(app_id)
        steps.append(sa.Step(f"Install {m['name']} (pacman)", ["pkexec", "pacman", "-U", "--noconfirm", file],
                             [app_id], needs_admin=True))
        risk = "high"
        reasons.append("A package from outside Arch's repositories: it isn't signed by Arch and its install "
                       "scripts run as root.")
        verify = {"pacman": m["name"]}
    elif t.kind == "appimage":
        sl = slug(t.name)
        app_id = f"appimage:{sl}"
        download(app_id)
        if not any(exists(p) for p in ("/usr/lib/libfuse.so.2", "/usr/lib64/libfuse.so.2")):
            steps.append(sa.Step("FUSE 2 (AppImages need it; once)",
                                 ["pkexec", "pacman", "-S", "--needed", "--noconfirm", "fuse2"], [], needs_admin=True))
        steps.append(sa.Step(f"Add {t.name} to your apps", [python, helper, "appimage", file, sl, t.name], [app_id]))
        risk = "medium"
        reasons.append("AppImages aren't sandboxed: it runs with your permissions and doesn't update itself.")
        verify = {"appimage": sl, "exec": str(Path.home() / "Applications" / f"{sl}.AppImage"),
                  "desktop": str(_apps_dir() / f"saint-appimage-{sl}.desktop")}
    elif t.kind == "deb":
        sl = slug(t.name)
        app_id = f"deb:{sl}"
        download(app_id)
        out = str(winapps.CACHE / "assistant" / sl / "converted")
        if not which("debtap"):
            steps.append(sa.Step("debtap (converts .deb packages; once, from the AUR)",
                                 ["paru", "-S", "--needed", "--noconfirm", "--skipreview", "--sudo", "pkexec",
                                  "debtap"], [], needs_admin=True))
        steps.append(sa.Step("Update debtap's package names", ["pkexec", "debtap", "-u"], [], needs_admin=True))
        steps.append(sa.Step(f"Convert {t.name} and install it (pacman)", [python, helper, "deb", file, out],
                             [app_id], needs_admin=True))
        risk = "high"
        reasons.append("Made for Debian/Ubuntu: converted with debtap. Its dependencies may be named differently "
                       "on Arch, so it may not start; the package's scripts run as root.")
        verify = {"deb_result": str(Path(out) / "result.json")}
    elif t.kind == "windows":
        why = winapps.blocked("", f"{t.name} {t.filename}")
        sl = slug(t.name)
        prefix = winapps.prefix_for(f"assistant-{sl}")
        app_id = f"wine:{prefix.name}"
        verify = {"wine_prefix": str(prefix)}
        if why:
            return InstallPlan(text, t, app_id, t.name, t.kind, [], "high", [why[0]], verify, [],
                               alternatives(t.name, search or default_search), blocked=why[0])
        steps += winapps.wine_setup_steps(which)
        download(app_id)
        kind = "msi" if t.filename.lower().endswith(".msi") else "exe"
        steps.append(winapps.wine_install_step(t.name, file, kind, [], prefix, app_id))
        risk = "medium"
        reasons.append("Runs under Wine in its own folder: most apps work, some don't (anti-cheat, drivers, some "
                       "copy protection).")
        notes.append("The installer's own window opens: click through it as on Windows.")
    else:
        raise ValueError(f"unknown kind {t.kind!r}")

    if not t.path and not t.sha256 and t.kind != "flathub":
        risk = "high"
        reasons.append("The publisher gives no checksum, so SAINT can't confirm the download is their file.")
    if t.path:
        risk = _raise(risk, "medium")
        reasons.append("A file on this computer: SAINT can't tell where it came from.")
    alts = alternatives(t.name, search or default_search) if t.kind in ("windows", "deb", "appimage") else []
    if alts:
        notes.insert(0, f"{alts[0].name} is in the Store ({alts[0].label}): that version is preferred.")
    return InstallPlan(text, t, app_id, t.name, t.kind, steps, risk, reasons, verify, notes, alts)


def plan_for(text: str, **kw) -> InstallPlan:
    """detect + build_plan. Keyword arguments go to whichever takes them (fetch_json, fetch_text, isfile; which,
    python, exists, search)."""
    d = {k: kw.pop(k) for k in ("fetch_json", "fetch_text", "isfile") if k in kw}
    return build_plan(detect(text, **d), text=text, **kw)


# --------------------------------------------------------------------------- did it work
def _desktop_exec(path: str, read: Callable[[str], str]) -> List[str]:
    """A desktop entry's Exec line as an argument list (field codes dropped); [] if there's none."""
    try:
        text = read(path)
    except OSError:
        return []
    in_entry = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            in_entry = line == "[Desktop Entry]"
        elif in_entry and line.startswith("Exec="):
            try:
                argv = shlex.split(line[5:])
            except ValueError:
                return []
            return [a for a in argv if not re.fullmatch(r"%[fFuUdDnNickvm]", a)]
    return []


def _token(argv: List[str]) -> str:
    """What to look for in the process list once it starts: the program's own name."""
    rest = [a for a in argv if "=" not in a or a.startswith("/")]
    if rest[:1] == ["env"]:
        rest = rest[1:]
    if rest[:2] == ["flatpak", "run"]:
        return next((a for a in rest[2:] if not a.startswith("-")), "")
    if rest[:1] == ["wine"] and len(rest) > 1:
        rest = rest[1:]
    prog = rest[0] if rest else ""
    return re.split(r"[\\/]", prog)[-1]


def launcher(v: Dict, run: Callable = subprocess.run, exists: Callable[[str], bool] = os.path.exists,
             read: Callable[[str], str] = lambda p: Path(p).read_text(encoding="utf-8", errors="replace"),
             walk: Callable = os.walk) -> Tuple[bool, List[str], str]:
    """(installed, how to start it, what's missing) for a history entry's ``verify``."""
    def q(argv):
        try:
            return run(argv, capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            return None
    if v.get("deb_result"):
        try:
            v = {**v, "pacman": json.loads(read(v["deb_result"])).get("package", "")}
        except (OSError, ValueError):
            return False, [], "The converted package wasn't installed."
    if v.get("flatpak"):
        r = q(["flatpak", "info", v["flatpak"]])
        if not r or r.returncode != 0:
            return False, [], f"Flatpak doesn't list {v['flatpak']}."
        return True, ["flatpak", "run", v["flatpak"]], ""
    if v.get("pacman"):
        r = q(["pacman", "-Qlq", v["pacman"]])
        if not r or r.returncode != 0:
            return False, [], f"pacman doesn't list {v['pacman']}."
        entries = [l.strip() for l in (r.stdout or "").splitlines()
                   if l.strip().startswith("/usr/share/applications/") and l.strip().endswith(".desktop")]
        for e in entries:
            if argv := _desktop_exec(e, read):
                return True, argv, ""
        return True, [], "Installed, but it adds no start-menu entry (a command-line program or a library)."
    if v.get("appimage"):
        if not exists(v["exec"]) or not exists(v["desktop"]):
            return False, [], "The AppImage or its start-menu entry is missing."
        return True, [v["exec"]], ""
    if v.get("wine_prefix"):
        prefix = v["wine_prefix"]
        if not exists(os.path.join(prefix, "drive_c")):
            return False, [], "Its Wine folder wasn't created."
        root = _apps_dir() / "wine"
        found = []
        for dirpath, _dirs, files in walk(str(root)):
            found += [os.path.join(dirpath, f) for f in files if f.endswith(".desktop")]
        for e in sorted(found):
            try:
                if prefix in read(e) and (argv := _desktop_exec(e, read)):
                    return True, argv, ""
            except OSError:
                continue
        return True, [], "Installed into its Wine folder, but the installer added no start-menu entry."
    return False, [], "SAINT has nothing to check for this one."


def _procs() -> List[Tuple[int, str]]:
    import psutil
    out = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            out.append((p.info["pid"], " ".join(p.info.get("cmdline") or []) or (p.info.get("name") or "")))
        except Exception:
            continue
    return out


def launch_check(argv: List[str], popen: Callable = subprocess.Popen, procs: Callable = _procs,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep,
                 wait: float = 8.0) -> Tuple[bool, str]:
    """Start the app and watch: it passes when its process appears (or is still running after ``wait`` s); it
    fails when it exits with an error. The app is left open: the user just installed it to use it."""
    token = _token(argv).lower()
    before = {pid for pid, _ in procs()}
    import tempfile
    err_file = tempfile.TemporaryFile()           # not a pipe: an app left running would block on a full one
    try:
        p = popen(argv, stdout=subprocess.DEVNULL, stderr=err_file, stdin=subprocess.DEVNULL,
                  start_new_session=True)
    except OSError as e:
        err_file.close()
        return False, f"couldn't start it: {e}"
    deadline = clock() + wait
    rc = None
    while clock() < deadline:
        rc = p.poll()
        if token and any(pid not in before and pid != getattr(p, "pid", None) and token in cmd.lower()
                         for pid, cmd in procs()):
            return True, "it started (its process is running)"
        if rc is not None and rc != 0:
            err = ""
            try:
                err_file.seek(0)
                err = err_file.read()[-300:].decode("utf-8", "replace")
            except Exception:
                pass
            err_file.close()
            tail = next((l.strip() for l in reversed(err.splitlines()) if l.strip()), "")
            return False, f"it exited at once with code {rc}" + (f": {tail}" if tail else "")
        sleep(0.5)
    if p.poll() is None:
        return True, f"it started (still running after {wait:.0f} s)"
    return False, "it started and closed again straight away, without an error code"


def verify(v: Dict, launch: bool = True, **kw) -> Dict:
    """Installed? And, when ``launch``, does it start? {"installed": bool, "launched": bool|None, "detail": str}"""
    lkw = {k: kw[k] for k in ("run", "exists", "read", "walk") if k in kw}
    ckw = {k: kw[k] for k in ("popen", "procs", "clock", "sleep", "wait") if k in kw}
    ok, argv, why = launcher(v, **lkw)
    if not ok:
        return {"installed": False, "launched": None, "detail": why}
    if not launch or not argv:
        return {"installed": True, "launched": None, "detail": why or "installed"}
    started, detail = launch_check(argv, **ckw)
    return {"installed": True, "launched": started, "detail": detail}


# --------------------------------------------------------------------------- history, uninstall, repair
def identity(v: Dict, fallback: str = "") -> str:
    for key, pre in (("flatpak", "flatpak"), ("pacman", "pacman"), ("appimage", "appimage")):
        if v.get(key):
            return f"{pre}:{v[key]}"
    if v.get("wine_prefix"):
        return "wine:" + os.path.basename(v["wine_prefix"].rstrip("/\\"))
    return fallback


def store_verify(result) -> Dict:
    """What to check (and remove) for a Store result, in the history's terms."""
    e = result.extra or {}
    if result.source in ("repo", "aur"):
        return {"pacman": result.id}
    if result.source == "flathub":
        return {"flatpak": result.id}
    if result.source == "windows":
        return {"wine_prefix": str(winapps.prefix_for(result.id))}
    if result.source == "featured":
        method, ref = e.get("method"), e.get("ref", "")
        if method == "flatpak":
            return {"flatpak": ref}
        if method == "aur":
            return {"pacman": ref}
        if method == "dnf":
            try:
                app = sa.load_catalog()[result.id]
                return {"pacman": app.system_refs("pacman")[0]}
            except Exception:
                return {}
    return {}


class History:
    """What SAINT installed, from where, whether it started, and how to undo it (a small JSON file)."""

    def __init__(self, path: Optional[Path] = None):
        if path is None:
            from core.paths import data_path
            path = data_path("install_history.json")
        self.path = Path(path)

    def entries(self) -> List[Dict]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return [e for e in data.get("entries", []) if isinstance(e, dict) and e.get("id")]

    def get(self, entry_id: str) -> Optional[Dict]:
        return next((e for e in self.entries() if e["id"] == entry_id), None)

    def _save(self, entries: List[Dict]):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".part")
        tmp.write_text(json.dumps({"version": 1, "entries": entries}, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def record(self, entry: Dict, what: str = "install", ok: bool = True, detail: str = "",
               now: Optional[float] = None) -> Dict:
        """Add or update an entry (same id = same app) and log the event (newest first)."""
        now = now if now is not None else time.time()
        entries = self.entries()
        old = next((e for e in entries if e["id"] == entry["id"]), {})
        merged = {**old, **entry, "updated_at": now}
        merged.setdefault("installed_at", now)
        merged["events"] = ([{"at": now, "what": what, "ok": ok, "detail": detail}] + old.get("events", []))[:20]
        entries = [merged] + [e for e in entries if e["id"] != entry["id"]]
        self._save(entries)
        return merged


def entry_from_plan(plan: InstallPlan, ok: bool, check: Optional[Dict] = None, error: str = "") -> Dict:
    t = plan.target
    check = check or {}
    return {"id": plan.app_id, "name": plan.name, "kind": plan.kind, "input": plan.input, "origin": t.origin,
            "url": t.url, "file": t.filename, "sha256": t.sha256, "checksum_from": t.checksum_from,
            "risk": plan.risk, "verify": plan.verify,
            "status": _status(ok, check), "detail": error or check.get("detail", "")}


def entry_from_store(result, ok: bool, check: Optional[Dict] = None, error: str = "") -> Dict:
    v = store_verify(result)
    check = check or {}
    return {"id": identity(v, f"store:{result.source}:{result.id}"), "name": result.name,
            "kind": f"store:{result.source}", "input": result.id, "origin": f"Store ({result.label})",
            "store": {"source": result.source, "id": result.id, "name": result.name,
                      "extra": {k: v2 for k, v2 in (result.extra or {}).items()
                                if isinstance(v2, (str, int, float, bool)) or v2 is None}},
            "verify": v, "status": _status(ok, check), "detail": error or check.get("detail", "")}


def _status(ok: bool, check: Dict) -> str:
    if not ok:
        return "failed"
    if check.get("installed") is False:
        return "failed"
    if check.get("launched") is False:
        return "installed, won't start"
    return "installed"


def uninstall_steps(entry: Dict, python: str = sys.executable) -> List[sa.Step]:
    """How to remove what an entry installed, rebuilt from its checked identifiers (never stored commands)."""
    v = entry.get("verify") or {}
    eid, name = entry["id"], entry.get("name", "the app")
    helper = str(Path(__file__).resolve())
    if v.get("deb_result"):
        try:
            v = {**v, "pacman": json.loads(Path(v["deb_result"]).read_text(encoding="utf-8")).get("package", "")}
        except (OSError, ValueError):
            raise ValueError("SAINT doesn't know which package the .deb became, so it can't remove it.")
    if v.get("flatpak"):
        if not sa._SAFE_FLATPAK.match(v["flatpak"]):
            raise ValueError("unsafe Flatpak id in the history")
        return [sa.Step(f"Remove {name} (Flatpak)", ["flatpak", "uninstall", "--user", "-y", "--noninteractive",
                                                     v["flatpak"]], [eid])]
    if v.get("pacman"):
        if not _PKG.match(v["pacman"]):
            raise ValueError("unsafe package name in the history")
        return [sa.Step(f"Remove {name} (pacman)", ["pkexec", "pacman", "-R", "--noconfirm", v["pacman"]], [eid],
                        needs_admin=True)]
    if v.get("appimage"):
        if not _SLUG.match(v["appimage"]):
            raise ValueError("unsafe AppImage name in the history")
        return [sa.Step(f"Remove {name} (AppImage)", [python, helper, "remove-appimage", v["appimage"]], [eid])]
    if v.get("wine_prefix"):
        prefix = Path(v["wine_prefix"]).resolve()
        root = winapps.PREFIXES.resolve()
        if prefix == root or root not in prefix.parents:
            raise ValueError("that Wine folder isn't one SAINT made")
        return [sa.Step(f"Remove {name} (its Wine folder and menu entries)",
                        [python, helper, "remove-wine", str(prefix)], [eid])]
    raise ValueError(f"SAINT doesn't know how to remove {name}.")


def reinstall_steps(steps: List[sa.Step]) -> List[sa.Step]:
    """The same steps, but reinstalling over what's there (pacman/paru without --needed, flatpak --reinstall)."""
    out = []
    for s in steps:
        argv = list(s.argv)
        tools = argv[:2]
        if "pacman" in tools or "paru" in tools[:1]:
            argv = [a for a in argv if a != "--needed"] if s.apps else argv
        if argv[:2] == ["flatpak", "install"] and "--reinstall" not in argv:
            argv.insert(2, "--reinstall")
        out.append(sa.Step(s.label, argv, s.apps, s.needs_admin))
    return out


def repair_steps(entry: Dict, plan_kw: Optional[Dict] = None) -> List[sa.Step]:
    """Reinstall from the same source (downloads are checked against the checksum again)."""
    if entry.get("store"):
        from core import store
        st = entry["store"]
        steps = store.plan(store.Result(st["source"], st["id"], st.get("name", st["id"]), extra=st.get("extra") or {}))
        return reinstall_steps(steps)
    plan = plan_for(entry["input"], **(plan_kw or {}))
    if plan.blocked:
        raise ValueError(plan.blocked)
    if plan.target.sha256 and entry.get("sha256") and plan.target.sha256 != entry["sha256"] and plan.target.path:
        raise ValueError("The file has changed since it was installed (its SHA-256 is different).")
    return reinstall_steps(plan.steps)


# --------------------------------------------------------------------------- helpers run by the install steps
def install_appimage(file: str, sl: str, name: str) -> int:
    if not _SLUG.match(sl):
        print("refusing: bad name")
        return 2
    dest_dir = Path.home() / "Applications"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{sl}.AppImage"
    shutil.copyfile(file, dest)
    dest.chmod(0o755)
    apps = _apps_dir()
    apps.mkdir(parents=True, exist_ok=True)
    clean = re.sub(r"[\r\n]", " ", name)[:80]
    (apps / f"saint-appimage-{sl}.desktop").write_text(
        "[Desktop Entry]\nType=Application\n"
        f"Name={clean}\nComment=AppImage (added by SAINT)\n"
        f"Exec=\"{dest}\" %U\nTryExec={dest}\n"
        "Icon=application-x-executable\nCategories=Utility;\nTerminal=false\n", encoding="utf-8")
    print(f"{clean} is in the start menu ({dest})")
    return 0


def remove_appimage(sl: str) -> int:
    if not _SLUG.match(sl):
        print("refusing: bad name")
        return 2
    for p in (Path.home() / "Applications" / f"{sl}.AppImage", _apps_dir() / f"saint-appimage-{sl}.desktop"):
        try:
            p.unlink()
            print(f"removed {p}")
        except FileNotFoundError:
            pass
    return 0


def convert_deb(file: str, out: str) -> int:
    """debtap the .deb into an Arch package in ``out``, install it with pacman -U, note its name."""
    outdir = Path(out)
    outdir.mkdir(parents=True, exist_ok=True)
    src = outdir / Path(file).name
    if Path(file).resolve() != src.resolve():
        shutil.copyfile(file, src)
    before = set(outdir.glob("*.pkg.tar.*"))
    rc = subprocess.call(["debtap", "-Q", str(src)], cwd=str(outdir))
    made = sorted(set(outdir.glob("*.pkg.tar.*")) - before, key=lambda p: p.stat().st_mtime)
    if rc != 0 or not made:
        print("debtap couldn't convert the package")
        return rc or 1
    pkg = made[-1]
    m = _PKGFILE.match(pkg.name)
    rc = subprocess.call(["pkexec", "pacman", "-U", "--noconfirm", str(pkg)])
    if rc == 0 and m:
        (outdir / "result.json").write_text(json.dumps({"package": m["name"]}), encoding="utf-8")
        print(f"installed as the Arch package {m['name']}")
    return rc


def remove_wine(prefix: str) -> int:
    p = Path(prefix).resolve()
    root = winapps.PREFIXES.resolve()
    if p == root or root not in p.parents:
        print("refusing: not a SAINT Wine folder")
        return 2
    wine_menu = _apps_dir() / "wine"
    for entry in (wine_menu.rglob("*.desktop") if wine_menu.is_dir() else []):
        try:
            if str(p) in entry.read_text(encoding="utf-8", errors="replace"):
                entry.unlink()
                print(f"removed {entry}")
        except OSError:
            pass
    shutil.rmtree(p, ignore_errors=True)
    print(f"removed {p}")
    return 0


def _get_json(url: str):
    import requests
    r = requests.get(url, timeout=15, headers={"User-Agent": "SAINT-Store/1", "Accept": "application/vnd.github+json"})
    if r.status_code == 404:
        raise ValueError("not found (404)")
    r.raise_for_status()
    return r.json()


def _get_text(url: str) -> str:
    import requests
    r = requests.get(url, timeout=15, headers={"User-Agent": "SAINT-Store/1"})
    r.raise_for_status()
    if len(r.content) > 1 << 20:
        raise ValueError("too large for a checksum or ref file")
    return r.text


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 4 and a[0] == "appimage":
        sys.exit(install_appimage(*a[1:]))
    if len(a) == 2 and a[0] == "remove-appimage":
        sys.exit(remove_appimage(a[1]))
    if len(a) == 3 and a[0] == "deb":
        sys.exit(convert_deb(*a[1:]))
    if len(a) == 2 and a[0] == "remove-wine":
        sys.exit(remove_wine(a[1]))
    print("usage: install_assistant.py appimage FILE SLUG NAME | remove-appimage SLUG | deb FILE OUTDIR | "
          "remove-wine PREFIX")
    sys.exit(2)
