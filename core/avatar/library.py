"""
core/avatar/library.py

Importing avatars. Every file here is untrusted input: it is parsed as data (the GLB header and
its JSON chunk, the first bytes of an image), size-capped, checked for the buffers and images it
needs, and copied into the profile's avatars folder. Nothing in it is ever executed.

    .vrm / .glb    binary glTF 2.0 (a .vrm must carry VRM 0.x "VRM" or 1.0 "VRMC_vrm")
    .gltf          JSON glTF 2.0 plus the relative files it names (or data: URIs)
    .png / .webp   a 2D avatar picture

The default avatar is data/avatars/saint/saint.vrm when that file ships, else SAINT.png in 2D.
"""

import hashlib
import json
import re
import shutil
import struct
from pathlib import Path, PurePosixPath
from typing import Optional

from core import paths

MAX_MODEL_BYTES = 200 * 1024 * 1024
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MODEL_EXT = (".vrm", ".glb", ".gltf")
IMAGE_EXT = (".png", ".webp")
DEFAULT_ID = "default"
_JSON, _BIN = 0x4E4F534A, 0x004E4942


class AvatarError(ValueError):
    """A file that can't be an avatar; the message is shown to the user."""


# ---------------------------------------------------------------- validation
def _check_gltf_json(doc, bin_len: Optional[int], base: Optional[Path]) -> list:
    """Check a glTF document; return the relative files it needs (for .gltf)."""
    if not isinstance(doc, dict) or not isinstance(doc.get("asset"), dict):
        raise AvatarError("Not a glTF model: the asset block is missing.")
    if not str(doc["asset"].get("version", "")).startswith("2"):
        raise AvatarError("Only glTF 2.0 models are supported.")
    needed = []

    def uri_ok(uri, what):
        if not isinstance(uri, str):
            raise AvatarError(f"{what} has an invalid uri.")
        if uri.startswith("data:"):
            return
        if base is None:
            raise AvatarError(f"{what} points to an outside file; a .glb/.vrm must contain everything.")
        rel = PurePosixPath(uri.replace("\\", "/"))
        if rel.is_absolute() or ".." in rel.parts or ":" in uri or not rel.parts:
            raise AvatarError(f"{what} points outside the model's folder.")
        if not (base / Path(*rel.parts)).is_file():
            raise AvatarError(f"{what} is missing: {uri}")
        needed.append(str(rel))

    buffers = doc.get("buffers", [])
    if not isinstance(buffers, list):
        raise AvatarError("The model's buffer list is invalid.")
    for i, b in enumerate(buffers):
        if not isinstance(b, dict) or not isinstance(b.get("byteLength"), int) or b["byteLength"] < 0:
            raise AvatarError(f"Buffer {i} is invalid.")
        if "uri" in b:
            uri_ok(b["uri"], f"Buffer {i}")
        elif i != 0 or bin_len is None:
            raise AvatarError(f"Buffer {i} is missing its data.")
        elif b["byteLength"] > bin_len:
            raise AvatarError("The model's binary data is shorter than it says.")
    views = doc.get("bufferViews", [])
    for i, v in enumerate(views if isinstance(views, list) else []):
        if not isinstance(v, dict) or not isinstance(v.get("buffer"), int) or not 0 <= v["buffer"] < len(buffers):
            raise AvatarError(f"Buffer view {i} refers to a buffer that isn't there.")
    for i, img in enumerate(doc.get("images", []) or []):
        if not isinstance(img, dict):
            raise AvatarError(f"Image {i} is invalid.")
        if "uri" in img:
            uri_ok(img["uri"], f"Image {i}")
        elif not isinstance(img.get("bufferView"), int) or not 0 <= img["bufferView"] < len(views):
            raise AvatarError(f"Image {i} has no data.")
    return needed


def vrm_meta(doc: dict) -> Optional[dict]:
    """VRM 1.0 (VRMC_vrm) or 0.x (VRM) meta as {version, title, author, license}; None if not a VRM."""
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    if isinstance(ext.get("VRMC_vrm"), dict):
        m = ext["VRMC_vrm"].get("meta") or {}
        authors = m.get("authors") or []
        return {"version": "1.0", "title": str(m.get("name", "")),
                "author": ", ".join(map(str, authors)) if isinstance(authors, list) else str(authors),
                "license": str(m.get("licenseUrl", ""))}
    if isinstance(ext.get("VRM"), dict):
        m = ext["VRM"].get("meta") or {}
        return {"version": "0.x", "title": str(m.get("title", "")), "author": str(m.get("author", "")),
                "license": str(m.get("licenseName", "") or m.get("otherLicenseUrl", ""))}
    return None


def inspect(path) -> dict:
    """Validate an avatar file and describe it: {kind: "3d"|"2d", format, meta, files}. Raises AvatarError."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext not in MODEL_EXT + IMAGE_EXT:
        raise AvatarError(f"{ext or 'That file'} isn't supported. Use .vrm, .glb, .gltf, .png or .webp.")
    if not path.is_file():
        raise AvatarError("The file doesn't exist.")
    size = path.stat().st_size
    if ext in IMAGE_EXT:
        if size > MAX_IMAGE_BYTES:
            raise AvatarError("The picture is larger than 20 MB.")
        with path.open("rb") as f:
            head = f.read(12)
        ok = head.startswith(b"\x89PNG\r\n\x1a\n") if ext == ".png" else (head[:4] == b"RIFF" and head[8:12] == b"WEBP")
        if not ok:
            raise AvatarError(f"That isn't a real {ext[1:].upper()} picture.")
        return {"kind": "2d", "format": ext[1:], "meta": {}, "files": []}
    if size > MAX_MODEL_BYTES:
        raise AvatarError("The model is larger than 200 MB.")
    if ext == ".gltf":
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise AvatarError(f"The .gltf file isn't valid JSON ({e.__class__.__name__}).")
        files = _check_gltf_json(doc, None, path.parent)
    else:
        with path.open("rb") as f:
            header = f.read(12)
            if len(header) < 12 or header[:4] != b"glTF":
                raise AvatarError("Not a binary glTF/VRM file (bad magic).")
            version, length = struct.unpack("<II", header[4:])
            if version != 2:
                raise AvatarError(f"glTF version {version} isn't supported (only 2).")
            if length != size:
                raise AvatarError("The file is truncated or has extra data.")
            chunk = f.read(8)
            if len(chunk) < 8:
                raise AvatarError("The model has no JSON chunk.")
            jlen, jtype = struct.unpack("<II", chunk)
            if jtype != _JSON or jlen > size - 20:
                raise AvatarError("The model's JSON chunk is missing or broken.")
            try:
                doc = json.loads(f.read(jlen).decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                raise AvatarError("The model's JSON chunk isn't valid JSON.")
            bin_len, chunk = None, f.read(8)
            if len(chunk) == 8:
                blen, btype = struct.unpack("<II", chunk)
                if btype == _BIN:
                    bin_len = min(blen, size - f.tell())
        files = _check_gltf_json(doc, bin_len, None)
    meta = vrm_meta(doc)
    if ext == ".vrm" and meta is None:
        raise AvatarError("This .vrm has no VRM data (neither VRM 0.x nor VRMC_vrm).")
    return {"kind": "3d", "format": "vrm" if meta else ext[1:], "meta": meta or {}, "files": files}


# ---------------------------------------------------------------- library
def avatars_dir() -> Path:
    d = paths.data_dir() / "avatars"
    d.mkdir(parents=True, exist_ok=True)
    return d


def default_avatar() -> dict:
    vrm = paths.resource_path("data", "avatars", "saint", "saint.vrm")
    if vrm.is_file():
        try:                                     # validated like any import; a broken file falls back to 2D
            meta = inspect(vrm)["meta"]
            return {"id": DEFAULT_ID, "name": "SAINT", "kind": "3d", "file": str(vrm), "meta": meta}
        except AvatarError:
            pass
    return {"id": DEFAULT_ID, "name": "SAINT (2D)", "kind": "2d", "file": str(paths.resource_path("SAINT.png")),
            "meta": {}}


def list_avatars() -> list:
    """The default first, then every imported avatar."""
    out = [default_avatar()]
    for meta_file in sorted(avatars_dir().glob("*/avatar.json")):
        try:
            info = json.loads(meta_file.read_text(encoding="utf-8"))
            info["file"] = str(meta_file.parent / info["file_name"])
            out.append(info)
        except (OSError, ValueError, KeyError):
            continue
    return out


def get(avatar_id: str) -> dict:
    return next((a for a in list_avatars() if a["id"] == avatar_id), default_avatar())


def import_file(src) -> dict:
    """Validate ``src`` and copy it (and a .gltf's files) into the avatars folder."""
    src = Path(src)
    info = inspect(src)
    digest = hashlib.sha256(src.read_bytes()).hexdigest()[:10]
    slug = re.sub(r"[^a-z0-9]+", "-", src.stem.lower()).strip("-")[:32] or "avatar"
    avatar_id = f"{slug}-{digest}"
    dest = avatars_dir() / avatar_id
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    try:
        file_name = "model" + src.suffix.lower()
        shutil.copyfile(src, dest / file_name)
        for rel in info["files"]:
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src.parent / rel, target)
        record = {"id": avatar_id, "name": info["meta"].get("title") or src.stem, "kind": info["kind"],
                  "format": info["format"], "meta": info["meta"], "file_name": file_name}
        (dest / "avatar.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    except OSError:
        shutil.rmtree(dest, ignore_errors=True)
        raise
    record["file"] = str(dest / file_name)
    return record


def remove(avatar_id: str) -> bool:
    if avatar_id == DEFAULT_ID or not re.fullmatch(r"[a-z0-9-]+", avatar_id or ""):
        return False
    target = avatars_dir() / avatar_id
    if not target.is_dir():
        return False
    shutil.rmtree(target)
    return True
