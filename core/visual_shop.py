"""
core/visual_shop.py

SAINT Visual Shop: a local catalog of looks (wallpapers, themes, palettes, icons, avatars ...) and the code that
installs them into the user's profile. No accounts, no payments, no network: the built-in catalog lists only
HalOS-made items shipped in this repo (data/visual_catalog/catalog.json), and users can import their own packs.

A pack is a folder or .zip holding manifest.json plus its files. Packs are untrusted data:
  - only file types in ALLOWED_EXT, nothing that looks like a program (MZ / ELF / #! / Mach-O), no <script> in SVG
  - no absolute paths, no "..", no links, nothing in the pack that the manifest doesn't list
  - size limits per file and per pack
  - every file's sha256 and size, and the pack sha256 over them, checked before anything is installed

Installed items live in <data_dir>/visual_shop/installed/<category>/<id>/ with their manifest; uninstall removes
that folder. Favourites are kept in <data_dir>/visual_shop/state.json.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, List, Optional, Tuple

from core.paths import PROJECT_ROOT, data_dir

log = logging.getLogger("visual_shop")

CATEGORIES = ("avatar", "outfit", "wallpaper", "animated-wallpaper", "theme", "palette", "icons", "cursor", "widget",
              "visualizer", "avatar-background", "lockscreen")
FIELDS = ("id", "name", "category", "creator", "license", "attribution", "version", "size", "sha256",
          "compatibility", "preview", "files")
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".webm", ".mp4", ".vrm", ".glb", ".json", ".colors",
               ".theme"}
COMPAT = {"halos", "windows", "any"}
MAX_FILE = 256 * 1024 * 1024
MAX_PACK = 512 * 1024 * 1024
MAX_FILES = 2000
_ID = re.compile(r"[a-z0-9][a-z0-9._-]{1,63}")
_VERSION = re.compile(r"\d+(\.\d+){0,3}")
_SHA = re.compile(r"[0-9a-f]{64}")
_MAGIC = (b"MZ", b"\x7fELF", b"#!", b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xce", b"\xca\xfe\xba\xbe", b"PK\x03\x04")
CATALOG = PROJECT_ROOT / "data" / "visual_catalog" / "catalog.json"


class PackError(ValueError):
    """A pack that can't be installed, with a reason fit to show the user."""


# ---------------------------------------------------------------------- manifest checks
def safe_rel(path: str) -> str:
    """A pack-relative path, or PackError. No absolute paths, drive letters, backslashes or '..'."""
    p = str(path or "")
    if not p or "\\" in p or p.startswith("/") or ":" in p or "\x00" in p:
        raise PackError(f"unsafe path {p!r}")
    if any(x in ("..", ".", "") for x in p.split("/")):
        raise PackError(f"unsafe path {p!r}")
    if PurePosixPath(p).suffix.lower() not in ALLOWED_EXT:
        raise PackError(f"{p}: this file type isn't allowed in a pack")
    return p


def package_digest(files: List[dict]) -> str:
    """The pack sha256: over every file's path and sha256, in path order."""
    lines = "\n".join(f"{f['path']}:{f['sha256']}" for f in sorted(files, key=lambda f: f["path"]))
    return hashlib.sha256(lines.encode()).hexdigest()


def version_key(v: str) -> Tuple[int, ...]:
    return tuple(int(x) for x in str(v).split(".")) if _VERSION.fullmatch(str(v)) else (0,)


def validate(m) -> List[str]:
    """Every problem with a manifest (empty list = fine)."""
    if not isinstance(m, dict):
        return ["the manifest isn't a JSON object"]
    errs = [f"missing {k}" for k in FIELDS if k not in m]
    if errs:
        return errs
    if not isinstance(m["id"], str) or not _ID.fullmatch(m["id"]):
        errs.append("id must be 2-64 lowercase letters, digits, '.', '_' or '-'")
    if m["category"] not in CATEGORIES:
        errs.append(f"unknown category {m['category']!r}")
    for k in ("name", "creator", "license", "attribution"):
        if not isinstance(m[k], str) or not m[k].strip() or len(m[k]) > 300:
            errs.append(f"{k} must be text")
    if not isinstance(m["version"], str) or not _VERSION.fullmatch(m["version"]):
        errs.append("version must look like 1.0 or 1.2.3")
    if not isinstance(m["sha256"], str) or not _SHA.fullmatch(m["sha256"]):
        errs.append("sha256 must be 64 lowercase hex digits")
    if not isinstance(m["compatibility"], list) or not m["compatibility"] or \
            not all(c in COMPAT for c in m["compatibility"]):
        errs.append("compatibility must list halos, windows or any")
    files = m["files"]
    if not isinstance(files, list) or not files or len(files) > MAX_FILES:
        return errs + [f"files must list 1-{MAX_FILES} files"]
    seen, total = set(), 0
    for f in files:
        try:
            if not isinstance(f, dict):
                raise PackError("each file must be an object")
            rel = safe_rel(f.get("path"))
            if rel.lower() in seen:
                raise PackError(f"{rel} is listed twice")
            seen.add(rel.lower())
            if not isinstance(f.get("sha256"), str) or not _SHA.fullmatch(f["sha256"]):
                raise PackError(f"{rel}: bad sha256")
            size = f.get("size")
            if not isinstance(size, int) or isinstance(size, bool) or not 0 <= size <= MAX_FILE:
                raise PackError(f"{rel}: size missing or over {MAX_FILE // 2**20} MB")
            total += size
        except PackError as e:
            errs.append(str(e))
    if errs:
        return errs
    if total > MAX_PACK:
        errs.append(f"the pack is over {MAX_PACK // 2**20} MB")
    if m["size"] != total:
        errs.append("size doesn't match the files")
    if m["sha256"] != package_digest(files):
        errs.append("sha256 doesn't match the files")
    if not isinstance(m["preview"], str) or m["preview"].lower() not in seen:
        errs.append("preview must be one of the pack's image files")
    elif PurePosixPath(m["preview"]).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}:
        errs.append("preview must be an image")
    return errs


def check_content(rel: str, data: bytes):
    """Reject content that is a program whatever its name says."""
    if data[:4].startswith(_MAGIC) and not rel.lower().endswith((".vrm", ".glb")):
        raise PackError(f"{rel} looks like a program or archive, not {PurePosixPath(rel).suffix}")
    low = rel.lower()
    if low.endswith(".svg") and re.search(rb"<script|javascript:|<foreignObject|\son[a-z]+\s*=", data, re.I):
        raise PackError(f"{rel} has script in it")
    if low.endswith(".json"):
        try:
            json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise PackError(f"{rel} isn't valid JSON")


# ---------------------------------------------------------------------- reading packs
Reader = Callable[[str], bytes]


def open_pack(src) -> Tuple[dict, Reader]:
    """(manifest, read) for a pack folder or .zip. Raises PackError if it can't be trusted."""
    src = Path(src)
    if src.is_dir():
        root = src.resolve()
        try:
            m = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            raise PackError("the pack has no readable manifest.json")
        _require(m)
        listed = {f["path"] for f in m["files"]} | {"manifest.json"}
        for p in root.rglob("*"):
            rel = p.relative_to(root).as_posix()
            if p.is_symlink():
                raise PackError(f"{rel} is a link")
            if p.is_file() and rel not in listed:
                raise PackError(f"{rel} is in the pack but not in the manifest")

        def read(rel: str) -> bytes:
            p = (root / safe_rel(rel))
            if p.is_symlink() or not p.resolve().is_relative_to(root):
                raise PackError(f"{rel} points outside the pack")
            return p.read_bytes()
        return m, read
    if src.suffix.lower() == ".zip" and src.is_file():
        try:
            z = zipfile.ZipFile(src)
            infos = {i.filename: i for i in z.infolist() if not i.is_dir()}
            m = json.loads(z.read("manifest.json").decode("utf-8")) if "manifest.json" in infos else None
        except (zipfile.BadZipFile, OSError, ValueError, UnicodeDecodeError, KeyError):
            raise PackError("the zip is damaged or has no manifest.json")
        _require(m)
        listed = {f["path"] for f in m["files"]} | {"manifest.json"}
        for name, i in infos.items():
            if name not in listed:
                raise PackError(f"{name} is in the pack but not in the manifest")
            if (i.external_attr >> 16) & 0o170000 == 0o120000:
                raise PackError(f"{name} is a link")
            if i.file_size > MAX_FILE:
                raise PackError(f"{name} is too big")

        def read(rel: str) -> bytes:
            i = infos.get(safe_rel(rel))
            if i is None:
                raise PackError(f"{rel} is missing from the pack")
            with z.open(i) as fh:
                data = fh.read(MAX_FILE + 1)
            return data
        return m, read
    raise PackError("choose a pack folder or a .zip")


def _require(m):
    errs = validate(m)
    if errs:
        raise PackError("; ".join(errs[:4]))


# ---------------------------------------------------------------------- the shop
class Shop:
    def __init__(self, root: Optional[Path] = None, catalog: Path = CATALOG, project: Path = PROJECT_ROOT):
        self.root = Path(root) if root else data_dir() / "visual_shop"
        self.catalog_path, self.project = Path(catalog), Path(project)
        self._catalog: Optional[List[dict]] = None

    # --- catalog
    def catalog(self) -> List[dict]:
        """Built-in items whose files exist in this tree and whose manifests are valid."""
        if self._catalog is None:
            try:
                raw = json.loads(self.catalog_path.read_text(encoding="utf-8")).get("items", [])
            except (OSError, ValueError) as e:
                log.warning("visual_shop.catalog_unreadable %s", e)
                raw = []
            self._catalog = []
            for m in raw:
                errs = validate(m)
                if errs:
                    log.warning("visual_shop.bad_item %s: %s", m.get("id") if isinstance(m, dict) else m, errs)
                    continue
                self._catalog.append(m)
        return self._catalog

    def catalog_reader(self, m: dict) -> Reader:
        srcs = {f["path"]: f.get("src", "") for f in m["files"]}
        base = self.project.resolve()

        def read(rel: str) -> bytes:
            p = (base / srcs.get(rel, "")).resolve()
            if not srcs.get(rel) or not p.is_relative_to(base) or not p.is_file():
                raise PackError(f"{rel} isn't in this copy of HalOS")
            return p.read_bytes()
        return read

    def preview_path(self, m: dict) -> Optional[Path]:
        """A local file for the item's preview image."""
        d = self.item_dir(m)
        if (d / m["preview"]).is_file():
            return d / m["preview"]
        src = next((f.get("src") for f in m["files"] if f["path"] == m["preview"]), None)
        return (self.project / src) if src and (self.project / src).is_file() else None

    # --- installed library
    def item_dir(self, m: dict) -> Path:
        return self.root / "installed" / m["category"] / m["id"]

    def installed(self) -> Dict[str, dict]:
        out = {}
        for p in sorted((self.root / "installed").glob("*/*/manifest.json")):
            try:
                m = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not validate(m) and p.parent == self.item_dir(m):
                out[m["id"]] = m
        return out

    def items(self) -> List[dict]:
        """Catalog plus imported items (installed things not in the catalog), each once."""
        cat = self.catalog()
        ids = {m["id"] for m in cat}
        return cat + [m for i, m in self.installed().items() if i not in ids]

    def update_available(self, m: dict) -> bool:
        have = self.installed().get(m["id"])
        return bool(have) and version_key(m["version"]) > version_key(have["version"])

    # --- favourites
    def _state(self) -> dict:
        try:
            return json.loads((self.root / "state.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def favourites(self) -> set:
        return set(self._state().get("favourites", []))

    def set_favourite(self, item_id: str, on: bool = True):
        st = self._state()
        fav = set(st.get("favourites", []))
        fav = fav | {item_id} if on else fav - {item_id}
        st["favourites"] = sorted(fav)
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.root / "state.json.tmp"
        tmp.write_text(json.dumps(st, indent=1), encoding="utf-8")
        os.replace(tmp, self.root / "state.json")

    # --- search
    def search(self, query: str = "", category: str = "", view: str = "all") -> List[dict]:
        """view: all | installed | favourites | updates."""
        inst, fav = self.installed(), self.favourites()
        words = query.lower().split()
        out = []
        for m in self.items():
            if category and m["category"] != category:
                continue
            if view == "installed" and m["id"] not in inst or view == "favourites" and m["id"] not in fav:
                continue
            if view == "updates" and not self.update_available(m):
                continue
            hay = " ".join([m["name"], m["category"], m["creator"], m.get("description", ""),
                            " ".join(m.get("tags", []))]).lower()
            if all(w in hay for w in words):
                out.append(m)
        return out

    # --- install / uninstall
    def install(self, m: dict, read: Optional[Reader] = None, progress: Optional[Callable[[int, int], None]] = None
                ) -> Path:
        """Check every file, then put the item in the profile. Nothing is installed unless all of it checks out."""
        _require(m)
        read = read or self.catalog_reader(m)
        dest = self.item_dir(m)
        stage = self.root / "staging" / m["id"]
        shutil.rmtree(stage, ignore_errors=True)
        done, total = 0, max(1, m["size"])
        try:
            for f in m["files"]:
                data = read(f["path"])
                if len(data) != f["size"] or hashlib.sha256(data).hexdigest() != f["sha256"]:
                    raise PackError(f"{f['path']} doesn't match its sha256; the pack was changed or damaged")
                check_content(f["path"], data)
                out = stage / f["path"]
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(data)
                done += len(data)
                if progress:
                    progress(done, total)
            clean = {k: v for k, v in m.items()}
            clean["files"] = [{k: f[k] for k in ("path", "sha256", "size")} for f in m["files"]]
            (stage / "manifest.json").write_text(json.dumps(clean, indent=1), encoding="utf-8")
            shutil.rmtree(dest, ignore_errors=True)
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.replace(stage, dest)
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        log.info("visual_shop.installed %s %s", m["id"], m["version"])
        return dest

    def import_pack(self, src, progress=None) -> dict:
        """Install a user's own pack (folder or .zip) after the same checks as everything else."""
        m, read = open_pack(src)
        self.install(m, read, progress)
        return m

    def uninstall(self, item_id: str) -> bool:
        m = self.installed().get(item_id)
        if not m:
            return False
        shutil.rmtree(self.item_dir(m))
        log.info("visual_shop.uninstalled %s", item_id)
        return True

    # --- apply
    def can_apply(self, m: dict) -> Tuple[bool, str]:
        """(possible here, reason when not). Only paths that really work are offered."""
        if m["id"] not in self.installed():
            return False, "Install it first."
        cat = m["category"]
        if cat in ("palette", "avatar", "outfit"):
            return True, ""
        if not sys.platform.startswith("linux"):
            return False, "Apply on HalOS: this needs the HalOS desktop (KDE Plasma)."
        need = {"wallpaper": "plasma-apply-wallpaperimage", "theme": "plasma-apply-colorscheme",
                "animated-wallpaper": "qdbus6"}.get(cat)
        if cat == "animated-wallpaper" and not (shutil.which("qdbus6") or shutil.which("qdbus")):
            return False, "Apply on HalOS: Plasma's qdbus isn't available."
        if need and cat != "animated-wallpaper" and not shutil.which(need):
            return False, f"Apply on HalOS: {need} isn't available."
        if not need:
            return False, "Installed to your profile; SAINT doesn't apply this kind of item yet."
        return True, ""

    def apply(self, m: dict, run=subprocess.run) -> str:
        """Apply an installed item. Returns what happened; raises PackError if it can't."""
        ok, why = self.can_apply(m)
        if not ok:
            raise PackError(why)
        d = self.item_dir(m)
        files = [d / f["path"] for f in m["files"]]
        cat = m["category"]
        if cat == "palette":
            data = json.loads(next(p for p in files if p.suffix == ".json").read_text(encoding="utf-8"))
            accent = str(data.get("accent", ""))
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
                raise PackError("this palette has no accent colour")
            from core.config import config
            config.set("appearance.accent", accent.lower())
            return f"Accent colour set to {accent.lower()}. SAINT uses it the next time it opens."
        if cat == "avatar":   # validated again by the avatar library (untrusted data), then made active
            from core.avatar import library
            from core.config import config
            src = next((p for p in files if p.suffix.lower() in (".vrm", ".glb", ".png", ".webp")), None)
            if src is None:
                raise PackError("this avatar pack has no .vrm, .glb, .png or .webp file")
            try:
                rec = library.import_file(src)
            except library.AvatarError as e:
                raise PackError(str(e))
            config.set("avatar.id", rec["id"])
            return f"{rec['name']} is now your avatar."
        if cat == "outfit":   # tints for her clothes (.json, core/avatar/outfits.py), or a dressed model (.vrm)
            from core.avatar import library, outfits
            from core.config import config
            spec = next((p for p in files if p.suffix.lower() == ".json"), None)
            try:
                if spec is not None:
                    o = outfits.install(spec)
                    config.set("avatar.outfit", o["name"])
                    return f"{o['title']} is her outfit now."
                model = next((p for p in files if p.suffix.lower() in (".vrm", ".glb")), None)
                if model is None:
                    raise PackError("this outfit has no outfit .json or .vrm in it")
                rec = library.import_file(model)
            except (outfits.OutfitError, library.AvatarError) as e:
                raise PackError(str(e))
            config.set("avatar.id", rec["id"])
            return f"She's wearing {rec['name']} now."
        if cat == "wallpaper":
            img = next(p for p in files if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"))
            _run(run, ["plasma-apply-wallpaperimage", str(img)])
            from core.config import config
            if config.get("appearance.accent_follows_wallpaper", True):
                from core import accent
                color = accent.from_image(img)
                accent.apply(color, run)
                return f"Wallpaper applied; the accent colour follows it ({color})."
            return "Wallpaper applied."
        if cat == "theme":
            scheme = next(p for p in files if p.suffix == ".colors")
            target = Path.home() / ".local/share/color-schemes" / scheme.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(scheme, target)
            _run(run, ["plasma-apply-colorscheme", scheme.stem])
            return f"Colour scheme {scheme.stem} applied."
        # animated-wallpaper: a settings preset for the HalOS living wallpaper, or a video
        preset = next((p for p in files if p.suffix == ".json"), None)
        if preset is None:
            from core import wallpaper_engine
            video = next((p for p in files if p.suffix.lower() in (".mp4", ".webm")), None)
            if video is None:
                raise PackError("this animated wallpaper has no settings or video in it")
            try:
                return wallpaper_engine.apply_video(video, run=run)
            except wallpaper_engine.EngineError as e:
                raise PackError(str(e))
        from ui.settings_pages import wallpaper
        why = wallpaper.apply_why(json.loads(preset.read_text(encoding="utf-8")), run=run)
        if why:
            raise PackError(why)
        return "Living wallpaper applied."

    def applies_on_install(self, m: dict) -> bool:
        """Wallpapers are shown as soon as they're installed (when this PC can)."""
        return m["category"] in ("wallpaper", "animated-wallpaper") and self.can_apply(m)[0]


def _run(run, argv):
    try:
        r = run(argv, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        raise PackError(f"{argv[0]} couldn't run: {e}")
    if r.returncode != 0:
        raise PackError(f"{argv[0]} failed: {(r.stderr or r.stdout or '').strip()[:200]}")


def open_shop_app(popen: Callable = subprocess.Popen, exists: Callable = os.path.exists) -> bool:
    """Open the Visual Shop window (`saint-visual-shop`), like core.store.open_store_app."""
    exe = "/usr/bin/saint-visual-shop"
    argv, cwd = ([exe], None) if exists(exe) else ([sys.executable, "-m", "ui.visual_shop"], str(PROJECT_ROOT))
    try:
        popen(argv, cwd=cwd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError as e:
        log.warning("visual_shop.open_failed %s", e)
        return False
