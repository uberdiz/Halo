"""
modules/link/photos.py

Your PC's photos on your phone, while the PC is on and online: a paired phone (SAINT Link, permission "photos",
own devices only by default) can list the photos in Pictures, get small thumbnails, and ask for a full photo,
which comes over SAINT Link's normal file transfer.

    photos.list  {offset, limit}  -> {"photos": [{"path", "name", "size", "time"}], "total"}   newest first
    photos.thumb {path}           -> {"jpeg": <base64>, "w", "h"}                             at most 256 px
    photos.get   {path}           -> {"sent": true}                                           the file follows

Paths are relative to the Pictures folder and checked: nothing outside it can be listed or sent, links are not
followed, and only image and video files are offered.
"""

from __future__ import annotations

import base64
import io
import os
from pathlib import Path
from typing import Dict, List, Optional

from modules.link.wire import LinkError

EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".gif", ".tif", ".tiff", ".bmp", ".dng", ".raw",
        ".mov", ".mp4", ".m4v"}
THUMB = 256
MAX_LIST = 500


def pictures_dir() -> Path:
    try:
        from modules.files.paths import known_folder
        p = known_folder("pictures")
        if p:
            return Path(p)
    except Exception:
        pass
    return Path.home() / "Pictures"


def _inside(root: Path, rel: str) -> Path:
    """root/rel, refused when it leaves root, goes through a link, or isn't a photo or video."""
    rel = (rel or "").replace("\\", "/").lstrip("/")
    if not rel or any(part in ("", ".", "..") for part in rel.split("/")):
        raise LinkError("That isn't a photo here.", "invalid")
    path = root / rel
    cur = root
    for part in rel.split("/"):
        cur = cur / part
        if cur.is_symlink():
            raise LinkError("That isn't a photo here.", "invalid")
    if path.suffix.lower() not in EXTS or not path.is_file():
        raise LinkError("That isn't a photo here.", "invalid")
    return path


def list_photos(root: Optional[Path] = None, offset: int = 0, limit: int = 100) -> Dict:
    root = root or pictures_dir()
    found: List[Dict] = []
    for dirpath, dirnames, files in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for f in files:
            p = Path(dirpath) / f
            if p.suffix.lower() in EXTS and not p.is_symlink():
                st = p.stat()
                found.append({"path": p.relative_to(root).as_posix(), "name": f, "size": st.st_size,
                              "time": st.st_mtime})
    found.sort(key=lambda x: -x["time"])
    limit = max(1, min(MAX_LIST, int(limit or 100)))
    offset = max(0, int(offset or 0))
    return {"photos": found[offset:offset + limit], "total": len(found)}


def thumbnail(rel: str, root: Optional[Path] = None) -> Dict:
    path = _inside(root or pictures_dir(), rel)
    try:
        from PIL import Image, ImageOps
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im)
            im.thumbnail((THUMB, THUMB))
            buf = io.BytesIO()
            im.convert("RGB").save(buf, "JPEG", quality=70)
            return {"jpeg": base64.b64encode(buf.getvalue()).decode("ascii"), "w": im.width, "h": im.height}
    except Exception:
        return {"jpeg": "", "w": 0, "h": 0}          # a video or a format Pillow can't read: the phone shows an icon


def register(service) -> None:
    """Add the three handlers to a running SAINT Link service (modules/link/service.py)."""
    n = service.node

    def listing(ctx, data):
        ctx.require("photos", "see your photos")
        return list_photos(offset=data.get("offset", 0), limit=data.get("limit", 100))

    def thumb(ctx, data):
        ctx.require("photos", "see your photos")
        return thumbnail(str(data.get("path", "")))

    def get(ctx, data):
        ctx.require("photos", "download a photo")
        path = _inside(pictures_dir(), str(data.get("path", "")))
        service.node.send_file(ctx.peer.id, str(path))
        return {"sent": True}

    n.register("photos.list", listing)
    n.register("photos.thumb", thumb)
    n.register("photos.get", get)
