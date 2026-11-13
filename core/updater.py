"""
core/updater.py

SAINT updates itself in place on HalOS, from github.com/uberdiz/Halo.

As the person (SAINT, no root):
    check()                 is there a newer SAINT on the chosen channel? -> dict (also saved as the last result)
    install(found)          pkexec /usr/lib/halo/halo-update install <sha> [<asset url> <sha256>], then restart SAINT
    rollback()              pkexec /usr/lib/halo/halo-update rollback (back to the copy kept before the last update)

Channels (config ``updates.channel``): stable = the newest release, beta = the newest release or pre-release,
dev = the newest commit of ``updates.branch`` (default main). A candidate is newer when its core/version.py
VERSION is higher, or the same VERSION from another commit than the installed one.

As root (the helper runs this file with the installed venv's python, stdlib only below the user part):
    install_tree(tarball, root)   unpack, sanity-check (app.py, core/version.py), carry over files that aren't in
                                  git (the Kokoro voice), byte-compile, then swap app.new <-> app in one
                                  renameat2(RENAME_EXCHANGE) and keep the old one as app.previous
    rollback_tree(root)           swap app.previous <-> app (again: one click goes forward again)

The installed tree's .halo-update.json says which commit and version it is.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Callable, Dict, List, Optional

REPO = "uberdiz/Halo"
API = f"https://api.github.com/repos/{REPO}"
RAW = f"https://raw.githubusercontent.com/{REPO}"
CODELOAD = f"https://codeload.github.com/{REPO}/tar.gz"
ASSET_PREFIX = f"https://github.com/{REPO}/releases/download/"
ROOT = Path("/opt/saint")
HELPER = "/usr/lib/halo/halo-update"
STAMP = ".halo-update.json"
CHANNELS = ("stable", "beta", "dev")
MAX_BYTES = 300 * 1024 * 1024
KEEP = ["data/tts/kokoro-onnx"]               # in /opt/saint/app but not in git (the PKGBUILD adds them)
SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
UA = {"User-Agent": "HalOS-updater", "Accept": "application/vnd.github+json"}


# ---------------------------------------------------------------------- #
# Versions
# ---------------------------------------------------------------------- #
def parse_version(text: str) -> tuple:
    """"v2.1.0-beta.2" -> (2, 1, 0, 0, 2); "0.4.0" -> (0, 4, 0, 1, 0): a release sorts after its pre-releases."""
    m = re.match(r"^v?(\d+(?:\.\d+)*)(?:[-.]?(alpha|beta|rc|pre)\.?(\d*))?", (text or "").strip(), re.I)
    if not m:
        return ()
    nums = [int(p) for p in m[1].split(".")][:4]
    nums += [0] * (3 - len(nums)) if len(nums) < 3 else []
    return tuple(nums) + ((0, int(m[3] or 0)) if m[2] else (1, 0))


def version_in(source: str) -> str:
    m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', source or "", re.M)
    return m[1] if m else ""


def is_newer(remote_version: str, remote_sha: str, local_version: str, local_sha: str) -> bool:
    rv, lv = parse_version(remote_version), parse_version(local_version)
    if rv and lv and rv != lv:
        return rv > lv
    return bool(remote_sha and local_sha and remote_sha != local_sha and rv == lv)


def pick_release(releases: List[Dict], channel: str) -> Optional[Dict]:
    """The newest usable release for ``channel`` (stable: no pre-releases), by tag version."""
    ok = [r for r in releases if isinstance(r, dict) and r.get("tag_name") and not r.get("draft")
          and (channel == "beta" or not r.get("prerelease"))]
    return max(ok, key=lambda r: parse_version(r["tag_name"]), default=None)


def release_asset(release: Dict) -> Dict:
    """A release may carry its own SAINT tarball with a .sha256 next to it: {"url", "sha256_url"} or {}."""
    assets = {a.get("name", ""): a.get("browser_download_url", "") for a in release.get("assets") or []}
    for name, url in assets.items():
        if name.endswith(".sha256") and name[:-7] in assets and assets[name[:-7]].startswith(ASSET_PREFIX):
            return {"url": assets[name[:-7]], "sha256_url": url}
    return {}


# ---------------------------------------------------------------------- #
# The person's side
# ---------------------------------------------------------------------- #
def _fetch(url: str, limit: int = 2 * 1024 * 1024, timeout: float = 20) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"{url} is larger than expected")
    return data


def _json(url: str):
    return json.loads(_fetch(url).decode("utf-8"))


def _text(url: str) -> str:
    return _fetch(url).decode("utf-8", "replace")


def app_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def installed(app: Optional[Path] = None) -> Dict:
    """{"version", "sha"} of the running SAINT: its stamp, else the build info, else just core/version.py."""
    app = app or app_dir()
    try:
        stamp = json.loads((app / STAMP).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stamp = {}
    sha = stamp.get("sha", "")
    if not sha:
        for p in (Path("/etc/halo/build-info.json"), Path("/usr/share/saintos/build-info.json")):
            try:
                sha = json.loads(p.read_text(encoding="utf-8")).get("source_commit", "")
                break
            except (OSError, ValueError):
                continue
    try:
        version = version_in((app / "core" / "version.py").read_text(encoding="utf-8"))
    except OSError:
        version = ""
    return {"version": version, "sha": sha if SHA.match(sha or "") else ""}


def _settings() -> Dict:
    from core.config import config
    channel = config.get("updates.channel", "beta")
    return {"channel": channel if channel in CHANNELS else "stable",
            "branch": re.sub(r"[^A-Za-z0-9._/-]", "", str(config.get("updates.branch", "main") or "main"))[:80]}


def check(json_get: Callable = None, text_get: Callable = None, settings: Dict = None,
          local: Dict = None, save: bool = True) -> Dict:
    """Ask GitHub for the newest SAINT on the channel. Never raises: {"ok": False, "error"} on failure."""
    json_get, text_get = json_get or _json, text_get or _text
    s = settings or _settings()
    local = local or installed()
    out = {"ok": True, "available": False, "channel": s["channel"], "current": local["version"], "at": time.time()}
    try:
        if s["channel"] == "dev":
            commit = json_get(f"{API}/commits/{s['branch']}")
            sha, label, notes, asset = commit["sha"], s["branch"], commit.get("commit", {}).get("message", ""), {}
        else:
            rel = pick_release(json_get(f"{API}/releases?per_page=30"), s["channel"])
            if rel is None:
                return _done({**out, "message": "No release on this channel yet."}, save)
            sha = json_get(f"{API}/commits/{rel['tag_name']}")["sha"]
            label, notes, asset = rel["tag_name"], rel.get("body") or "", release_asset(rel)
        if not SHA.match(sha or ""):
            raise ValueError("GitHub sent an unexpected commit id")
        version = version_in(text_get(f"{RAW}/{sha}/core/version.py"))
        if asset:
            asset["sha256"] = (text_get(asset.pop("sha256_url")).split() or [""])[0].lower()
            if not SHA256.match(asset["sha256"]):
                asset = {}
        out.update(latest=version, ref=label, sha=sha, notes=notes[:2000], asset=asset,
                   available=is_newer(version, sha, local["version"], local["sha"]))
        out["message"] = (f"SAINT {version} ({label}) is available." if out["available"]
                          else f"SAINT is up to date ({local['version'] or 'unknown version'}).")
    except Exception as e:                      # offline, rate-limited, renamed repo...
        out.update(ok=False, error=f"Couldn't check for updates: {e}", message=f"Couldn't check for updates: {e}")
    return _done(out, save)


def _done(out: Dict, save: bool) -> Dict:
    if save:
        try:
            from core.config import config
            config.set("updates.last_check", out["at"])
            config.set("updates.last_result", {k: out.get(k) for k in ("ok", "available", "message", "latest",
                                                                        "ref", "sha", "channel", "at")})
        except Exception:
            pass
    return out


def due(now: float = None) -> bool:
    """Auto-check on and the last check over a day ago."""
    from core.config import config
    if not config.get("updates.auto_check", True):
        return False
    return (now or time.time()) - float(config.get("updates.last_check", 0) or 0) > 24 * 3600


def helper_argv(found: Dict) -> List[str]:
    if not SHA.match(found.get("sha", "")):
        raise ValueError("no update to install")
    a = found.get("asset") or {}
    extra = [a["url"], a["sha256"]] if a.get("url", "").startswith(ASSET_PREFIX) and SHA256.match(a.get("sha256", "")) else []
    return ["pkexec", HELPER, "install", found["sha"], *extra]


def _helper(argv: List[str], run=subprocess.run) -> Dict:
    if not Path(HELPER).exists():
        return {"ok": False, "message": "In-place updates need HalOS (the halo-update helper isn't installed)."}
    try:
        r = run(argv, capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "message": f"The update didn't run: {e}"}
    last = ((r.stdout or "").strip().splitlines() or [""])[-1]
    if r.returncode != 0:
        why = ((r.stderr or "").strip().splitlines() or [f"exit code {r.returncode}"])[-1]
        return {"ok": False, "message": f"The update failed: {why}"}
    return {"ok": True, "message": last or "Done."}


def install(found: Dict, run=subprocess.run) -> Dict:
    res = _helper(helper_argv(found), run)
    if res["ok"]:
        res["message"] = f"SAINT {found.get('latest', '')} is installed; SAINT restarts now."
    return res


def rollback(run=subprocess.run) -> Dict:
    res = _helper(["pkexec", HELPER, "rollback"], run)
    if res["ok"]:
        res["message"] = "SAINT is back to the version before the last update; SAINT restarts now."
    return res


def can_rollback(root: Path = ROOT) -> bool:
    return (root / "app.previous" / "app.py").is_file()


def restart_saint(run=subprocess.run, popen=subprocess.Popen) -> bool:
    """Restart SAINT on the new code. True when the caller has to quit (no systemd unit was running SAINT:
    a fresh `saint` starts 2 s later, after this one has let go of its lock)."""
    try:
        active = run(["systemctl", "--user", "is-active", "--quiet", "saint.service"], timeout=5).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        active = False
    if active:
        run(["systemctl", "--user", "--no-block", "restart", "saint.service"], timeout=10)
        return False
    popen(["sh", "-c", "sleep 2; exec /usr/bin/saint"], start_new_session=True)
    return True


def restart_now():
    """restart_saint(), and quit this SAINT when it has to (from any thread)."""
    if restart_saint():
        from PySide6.QtCore import QMetaObject, Qt
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            QMetaObject.invokeMethod(app, "quit", Qt.QueuedConnection)


# ---------------------------------------------------------------------- #
# Root side (stdlib only: runs as `python -I core/updater.py root ...` from the helper)
# ---------------------------------------------------------------------- #
def exchange(a: Path, b: Path):
    """Swap two directories in one step (renameat2 RENAME_EXCHANGE); two renames where that's missing."""
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        fn = libc.renameat2
    except (OSError, AttributeError, TypeError):      # not glibc (or not Linux)
        fn = None
    if fn is not None:
        if fn(-100, os.fsencode(str(a)), -100, os.fsencode(str(b)), 2) == 0:     # AT_FDCWD, RENAME_EXCHANGE
            return
        if ctypes.get_errno() not in (22, 38, 95):          # EINVAL / ENOSYS / EOPNOTSUPP: fall back
            raise OSError(ctypes.get_errno(), os.strerror(ctypes.get_errno()), str(a))
    tmp = b.with_name(b.name + ".swap")
    os.rename(b, tmp)
    os.rename(a, b)
    os.rename(tmp, a)


def _unpack(tarball: Path, dest: Path):
    """The source tarball's single top folder becomes ``dest``; nothing may land outside it."""
    tmp = Path(tempfile.mkdtemp(prefix=".unpack-", dir=dest.parent))
    try:
        with tarfile.open(tarball, "r:*") as tf:
            if sys.version_info >= (3, 12):
                tf.extractall(tmp, filter="data")
            else:                                            # pragma: no cover - HalOS ships 3.12
                for m in tf.getmembers():
                    if m.name.startswith("/") or ".." in Path(m.name).parts or not (m.isfile() or m.isdir()):
                        raise ValueError(f"unsafe entry in the tarball: {m.name}")
                tf.extractall(tmp)
        tops = list(tmp.iterdir())
        src = tops[0] if len(tops) == 1 and tops[0].is_dir() else tmp
        if dest.exists():
            shutil.rmtree(dest)
        os.rename(src, dest)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def install_tree(tarball: Path, root: Path = ROOT, sha: str = "", sha256: str = "", compile_with: str = "") -> str:
    """Install the SAINT source in ``tarball`` as root/app; the old app becomes root/app.previous."""
    size = tarball.stat().st_size
    if not 1024 < size <= MAX_BYTES:
        raise ValueError(f"the download is {size} bytes, which isn't a SAINT source tarball")
    if sha256:
        got = hashlib.sha256(tarball.read_bytes()).hexdigest()
        if got != sha256:
            raise ValueError(f"checksum mismatch (expected {sha256[:12]}…, got {got[:12]}…)")
    app, new, prev = root / "app", root / "app.new", root / "app.previous"
    _unpack(tarball, new)
    version = ""
    try:
        version = version_in((new / "core" / "version.py").read_text(encoding="utf-8"))
    except OSError:
        pass
    if not (new / "app.py").is_file() or not version:
        shutil.rmtree(new, ignore_errors=True)
        raise ValueError("that isn't SAINT's source (no app.py or core/version.py)")
    for rel in KEEP:
        if (app / rel).exists() and not (new / rel).exists():
            shutil.copytree(app / rel, new / rel)
    (new / STAMP).write_text(json.dumps({"sha": sha, "version": version, "installed_at": time.time()}),
                             encoding="utf-8")
    if compile_with:
        subprocess.run([compile_with, "-m", "compileall", "-q", "-j0", str(new)], capture_output=True, timeout=600)
    if app.exists():
        exchange(new, app)                   # now app is the new tree, app.new the old one
        if prev.exists():
            shutil.rmtree(prev)
        os.rename(new, prev)
    else:
        os.rename(new, app)
    return version


def rollback_tree(root: Path = ROOT) -> str:
    app, prev = root / "app", root / "app.previous"
    if not (prev / "app.py").is_file():
        raise ValueError("there's no earlier SAINT to go back to")
    exchange(prev, app)
    try:
        return version_in((app / "core" / "version.py").read_text(encoding="utf-8"))
    except OSError:
        return ""


def _root_main(args: List[str]) -> int:
    """halo-update install <sha> [<asset url> <sha256>] | rollback. Everything else is refused."""
    try:
        if args[:1] == ["rollback"] and len(args) == 1:
            print(f"SAINT {rollback_tree()} restored")
            return 0
        if args[:1] != ["install"] or len(args) not in (2, 4) or not SHA.match(args[1]):
            print("usage: halo-update install <40-hex commit> [<release asset url> <sha256>] | rollback",
                  file=sys.stderr)
            return 64
        sha, url, digest = args[1], CODELOAD + "/" + args[1], ""
        if len(args) == 4:
            if not args[2].startswith(ASSET_PREFIX) or not SHA256.match(args[3]) or ".." in args[2]:
                print("halo-update: not one of HalOS's release files", file=sys.stderr)
                return 65
            url, digest = args[2], args[3]
        with tempfile.TemporaryDirectory(prefix="halo-update-") as tmp:
            tarball = Path(tmp) / "saint.tar.gz"
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "HalOS-updater"}),
                                        timeout=60) as r, open(tarball, "wb") as f:
                got = 0
                while chunk := r.read(1 << 20):
                    got += len(chunk)
                    if got > MAX_BYTES:
                        raise ValueError("the download is too large")
                    f.write(chunk)
            py = str(ROOT / "venv" / "bin" / "python")
            version = install_tree(tarball, ROOT, sha, digest, py if os.path.exists(py) else "")
        print(f"SAINT {version} installed")
        return 0
    except Exception as e:
        print(f"halo-update: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__" and sys.argv[1:2] == ["root"]:
    sys.exit(_root_main(sys.argv[2:]))
