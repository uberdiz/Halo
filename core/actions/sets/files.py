"""
core/actions/sets/files.py

File actions for HalOS Files and SAINT: move, copy, rename, new folder, trash, restore. Nothing here deletes
for good: "delete" means the trash (freedesktop trash through `gio` on Linux, the Recycle Bin on Windows).
Nothing is ever overwritten: a name that is taken is an error, not a silent replace.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .. import proc
from ..registry import RISKY, Action, ActionError, ActionResult, P, platform_name

_PROTECTED = ("/", "/home", "/usr", "/etc", "/boot", "/var", "/bin", "/lib", "/opt", "/root", "/sys", "/proc",
              "/dev")
_WIN_PROTECTED = ("windows", "users", "program files", "program files (x86)", "programdata")


def _path(text: str, must_exist: bool = True) -> Path:
    p = Path(os.path.expandvars(os.path.expanduser(str(text)))).absolute()
    if must_exist and not p.exists():
        raise ActionError(f"{p} doesn't exist", "NOT_FOUND")
    return p


def _guard(p: Path):
    """Refuse drive roots, the system's own folders and the home folder itself."""
    s = p.as_posix().rstrip("/") or "/"
    system = s in _PROTECTED or len(p.parts) <= 1 or p == Path.home()
    if platform_name() == "windows" and len(p.parts) == 2 and p.parts[-1].lower() in _WIN_PROTECTED:
        system = True
    if system:
        raise ActionError(f"{p} is a system folder, so I'm leaving it alone", "PROTECTED")


def _free(dest: Path):
    if dest.exists():
        raise ActionError(f"{dest} already exists", "EXISTS")


def _name(text: str) -> str:
    name = text.strip()
    if not name or name in (".", "..") or any(c in name for c in "/\\"):
        raise ActionError("that isn't a usable name", "INVALID_PARAMS")
    return name


def _folder(text: str) -> Path:
    folder = _path(text)
    if not folder.is_dir():
        raise ActionError(f"{folder} isn't a folder", "INVALID_PARAMS")
    return folder


def _move(p):
    src, folder = _path(p["path"]), _folder(p["to"])
    _guard(src)
    dest = folder / src.name
    _free(dest)
    shutil.move(str(src), str(dest))
    return ActionResult(True, f"Moved {src.name} to {folder}.", data={"path": str(dest)},
                        undo={"path": str(dest), "back": str(src)})


def _undo_move(t):
    back = Path(t["back"])
    _free(back)
    shutil.move(t["path"], str(back))
    return f"Moved {back.name} back."


def _copy(p):
    src, folder = _path(p["path"]), _folder(p["to"])
    dest = folder / src.name
    _free(dest)
    if src.is_dir():
        shutil.copytree(src, dest, symlinks=True)
    else:
        shutil.copy2(src, dest)
    return ActionResult(True, f"Copied {src.name} to {folder}.", data={"path": str(dest)},
                        undo={"path": str(dest)})


def _undo_copy(t):
    _trash_path(Path(t["path"]))
    return "The copy is in the trash."


def _rename(p):
    src = _path(p["path"])
    _guard(src)
    name = _name(p["name"])
    dest = src.with_name(name)
    _free(dest)
    src.rename(dest)
    return ActionResult(True, f"Renamed {src.name} to {name}.", data={"path": str(dest)},
                        undo={"path": str(dest), "name": src.name})


def _undo_rename(t):
    src = Path(t["path"])
    dest = src.with_name(t["name"])
    _free(dest)
    src.rename(dest)
    return f"Renamed back to {t['name']}."


def _new_folder(p):
    dest = _folder(p["in"]) / _name(p["name"])
    _free(dest)
    dest.mkdir()
    return ActionResult(True, f"Made the folder {dest.name}.", data={"path": str(dest)},
                        undo={"path": str(dest)})


def _undo_new_folder(t):
    d = Path(t["path"])
    if d.is_dir() and not any(d.iterdir()):
        d.rmdir()
        return "Removed the empty folder."
    raise ActionError("the folder isn't empty any more, so I left it", "NOT_EMPTY")


def _trash_path(path: Path):
    if platform_name() == "windows":
        from modules.files import ops
        ops.recycle([str(path)])
    else:
        proc.run(["gio", "trash", "--", str(path)], timeout=60)


def _trash(p):
    src = _path(p["path"])
    _guard(src)
    _trash_path(src)
    undo = {"path": str(src)} if platform_name() == "linux" else None
    return ActionResult(True, f"{src.name} is in the trash.", undo=undo)


def _restore(p):
    """Put a trashed file back where it was (Linux: `gio trash --restore`)."""
    target = str(_path(p["path"], must_exist=False))
    for line in proc.run(["gio", "trash", "--list"]).splitlines():
        uri, _, original = line.partition("\t")
        if original.strip() == target:
            proc.run(["gio", "trash", "--restore", uri.strip()])
            return f"Put {Path(target).name} back."
    raise ActionError(f"{target} isn't in the trash", "NOT_FOUND")


def register(registry):
    path = P("string", "full path")
    to = P("string", "destination folder")
    for a in [
        Action("files.move", "Move a file or folder", _move, {"path": path, "to": to}, risk=RISKY,
               undo=_undo_move, keywords="put relocate", preview=lambda p: f"Move {p['path']} into {p['to']}."),
        Action("files.copy", "Copy a file or folder", _copy, {"path": path, "to": to}, undo=_undo_copy,
               keywords="duplicate", preview=lambda p: f"Copy {p['path']} into {p['to']}."),
        Action("files.rename", "Rename a file or folder", _rename, {"path": path, "name": P("string", "new name")},
               risk=RISKY, undo=_undo_rename, preview=lambda p: f"Rename {p['path']} to {p['name']}."),
        Action("files.new_folder", "Make a new folder", _new_folder,
               {"in": P("string", "parent folder"), "name": P("string")}, undo=_undo_new_folder,
               keywords="create directory mkdir",
               preview=lambda p: f"Make a folder called {p['name']} in {p['in']}."),
        Action("files.trash", "Move a file or folder to the trash", _trash, {"path": path}, risk=RISKY,
               undo=_restore, keywords="delete remove bin recycle",
               preview=lambda p: f"Move {p['path']} to the trash (it can be restored)."),
        Action("files.restore", "Restore a file from the trash", _restore, {"path": P("string", "where it was")},
               platforms=("linux",), keywords="undelete recover bring back",
               preview=lambda p: f"Put {p['path']} back from the trash."),
    ]:
        registry.register(a, replace=True)
