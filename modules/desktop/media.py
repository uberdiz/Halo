"""
modules/desktop/media.py

What's playing on the PC — any app, not just Spotify. Windows keeps a list
of media sessions (the same one behind the volume flyout's media controls):
a YouTube video in a browser, VLC, Apple Music, Spotify... ``media`` polls it
on a background thread and emits MEDIA_CHANGED with the session that matters
(the one playing, else the one Windows calls current), and can play/pause or
skip it.

Windows needs the ``winrt-Windows.Media.Control`` packages; without them SAINT
falls back to Spotify-only now-playing and says so in the log once. Linux (HalOS)
reads every MPRIS player with ``playerctl``: browsers (YouTube), mpv, VLC, Spotify.

Which one the mini player shows: the source you picked (widgets.media_source, an
app name like "firefox"; "" = automatic), else what has been playing the longest.
"""

import asyncio
import hashlib
import logging
import shutil
import subprocess
import sys
import threading
import time
from typing import Dict, Optional

from core.events import event_bus, EventType

log = logging.getLogger("saint.desktop.media")

_PLAYING, _PAUSED = 4, 5

# AppUserModelIDs → a readable app name
_APPS = (("spotify", "Spotify"), ("opera", "Opera"), ("chrome", "Chrome"), ("msedge", "Edge"),
         ("firefox", "Firefox"), ("brave", "Brave"), ("vivaldi", "Vivaldi"), ("vlc", "VLC"),
         ("zune", "Media Player"), ("microsoft.media", "Media Player"), ("applemusic", "Apple Music"),
         ("itunes", "iTunes"), ("tidal", "TIDAL"), ("deezer", "Deezer"), ("discord", "Discord"),
         ("netflix", "Netflix"), ("twitch", "Twitch"), ("youtube", "YouTube"), ("plex", "Plex"))


def app_label(aumid: str) -> str:
    a = (aumid or "").lower()
    return next((name for key, name in _APPS if key in a), (aumid or "").split("!")[0].split(".")[0] or "Media")


def pick(sessions: list, current_id: str = "", prefer: str = "") -> Optional[dict]:
    """The session to show: the app you picked (``prefer``, matched against the app name), else one that's
    playing — Windows' current one, else the one playing the longest ("since") — else Windows' current
    session, else the first one."""
    if not sessions:
        return None
    if prefer:
        chosen = [s for s in sessions if prefer.lower() in (s.get("app", "") + " " + s["app_id"]).lower()]
        if chosen:
            return next((s for s in chosen if s.get("is_playing")), chosen[0])
    playing = [s for s in sessions if s.get("is_playing")]
    if playing:
        cur = next((s for s in playing if s["app_id"] == current_id), None)
        return cur or min(playing, key=lambda s: s.get("since") or float("inf"))
    return next((s for s in sessions if s["app_id"] == current_id), sessions[0])


# playerctl -a metadata --format: one line per player
_FMT = "\t".join(["{{playerInstance}}", "{{playerName}}", "{{status}}", "{{xesam:title}}", "{{xesam:artist}}",
                   "{{xesam:album}}", "{{position}}", "{{mpris:length}}", "{{mpris:artUrl}}", "{{volume}}"])


def _num(x: str) -> float:
    try:
        return float(x)
    except ValueError:
        return 0.0


def parse_playerctl(text: str, now: float) -> list:
    """playerctl's lines -> sessions in the same shape as Windows' (microseconds -> ms)."""
    out = []
    for line in (text or "").splitlines():
        f = line.split("\t")
        if len(f) < 10 or not f[3].strip():
            continue
        inst, name, status, title, artist, album, pos, length, art, vol = (x.strip() for x in f[:10])
        label = app_label(name)
        out.append({"app_id": inst, "app": label if label != name else name.capitalize(),
                    "title": title, "artist": artist, "album": album, "is_playing": status == "Playing",
                    "status": _PLAYING if status == "Playing" else _PAUSED,
                    "position_ms": int(_num(pos) / 1000), "duration_ms": int(_num(length) / 1000), "at": now,
                    "art_url": art, "volume": int(round(_num(vol) * 100)) if vol else None,
                    "can_next": True, "can_previous": True, "can_play_pause": True,
                    "is_spotify": "spotify" in name.lower()})
    return out


class MediaWatcher:
    def __init__(self, interval: float = 1.2):
        self.interval = interval
        self._lock = threading.Lock()
        self._state: Dict = {}
        self._thumbs: Dict[str, bytes] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._sessions = {}           # app_id -> winrt session (loop thread only)
        self.available: Optional[bool] = None

    # ------------------------------------------------------------------ #
    @property
    def state(self) -> Dict:
        with self._lock:
            return dict(self._state)

    def thumbnail(self, key: str) -> bytes:
        with self._lock:
            return self._thumbs.get(key, b"")

    def start(self):
        from core.config import config
        if not config.get("widgets.any_media", True) or (self._thread and self._thread.is_alive()):
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="media-watcher", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    # ------------------------------------------------------------------ #
    def _run(self):
        if sys.platform.startswith("linux"):
            return self._run_linux()
        try:
            from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as M
        except Exception as e:
            self.available = False
            log.info("media.unavailable %s (pip install winrt-Windows.Media.Control)", e)
            return
        self.available = True
        loop = asyncio.new_event_loop()
        self._loop = loop
        try:
            loop.run_until_complete(self._poll(M))
        except Exception:
            log.exception("media.watcher_crashed")
        finally:
            loop.close()
            self._loop = None

    # ---- Linux: MPRIS players through playerctl ---------------------------------------------------- #
    def _run_linux(self):
        if not shutil.which("playerctl"):
            self.available = False
            log.info("media.unavailable playerctl is missing (pacman -S playerctl)")
            return
        self.available = True
        since: Dict[str, float] = {}          # app_id -> when it started playing (the longest-playing one wins)
        last_sig = None
        while not self._stop.is_set():
            try:
                now = time.time()
                r = subprocess.run(["playerctl", "-a", "metadata", "--format", _FMT], capture_output=True,
                                   text=True, timeout=4)
                sessions = parse_playerctl(r.stdout, now)
                for x in sessions:
                    since[x["app_id"]] = since.get(x["app_id"]) or now if x["is_playing"] else 0
                    x["since"] = since[x["app_id"]] or None
                    self._linux_thumb(x)
                from core.config import config
                chosen = pick(sessions, "", str(config.get("widgets.media_source", "") or "")) or {}
                sig = (chosen.get("app_id"), chosen.get("title"), chosen.get("artist"), chosen.get("is_playing"),
                       chosen.get("thumb"), round((chosen.get("position_ms") or 0) / 4000), len(sessions))
                with self._lock:
                    self._state = dict(chosen, sessions=sessions)
                if sig != last_sig:
                    last_sig = sig
                    event_bus.emit_event(EventType.MEDIA_CHANGED, dict(chosen, sessions=len(sessions)))
            except Exception as e:
                log.debug("media.poll_failed %s", e)
            self._stop.wait(self.interval)

    def _linux_thumb(self, x: dict):
        """The player's cover art (a file:// path, or an https URL from Spotify / YouTube) as media://<hash>."""
        url = x.pop("art_url", "")
        x["thumb"] = ""
        if not url:
            return
        key = "media://" + hashlib.md5(url.encode("utf-8", "ignore")).hexdigest()
        with self._lock:
            have = key in self._thumbs
        if not have:
            data = b""
            try:
                if url.startswith("file://"):
                    from urllib.parse import unquote
                    with open(unquote(url[7:]), "rb") as f:
                        data = f.read(8 * 1024 * 1024)
                elif url.startswith("https://"):
                    import requests
                    r = requests.get(url, timeout=4)
                    data = r.content if r.ok and len(r.content) < 8 * 1024 * 1024 else b""
            except Exception as e:
                log.debug("media.thumb_failed %s", e)
            if not data:
                return
            with self._lock:
                self._thumbs[key] = data
                while len(self._thumbs) > 12:
                    self._thumbs.pop(next(iter(self._thumbs)))
        x["thumb"] = key

    async def _poll(self, M):
        mgr = await M.request_async()
        last_sig = None
        while not self._stop.is_set():
            try:
                cur = mgr.get_current_session()
                current_id = cur.source_app_user_model_id if cur is not None else ""
                sessions, handles = [], {}
                for s in mgr.get_sessions():
                    info = await self._describe(s)
                    if info and info.get("title"):
                        sessions.append(info)
                        handles[info["app_id"]] = s
                self._sessions = handles
                chosen = pick(sessions, current_id) or {}
                sig = (chosen.get("app_id"), chosen.get("title"), chosen.get("artist"), chosen.get("is_playing"),
                       chosen.get("thumb"), round((chosen.get("position_ms") or 0) / 4000))
                with self._lock:
                    self._state = dict(chosen, sessions=[{k: v for k, v in x.items() if k != "thumb_bytes"}
                                                          for x in sessions])
                if sig != last_sig:
                    last_sig = sig
                    payload = {k: v for k, v in chosen.items() if k != "thumb_bytes"}
                    payload["sessions"] = len(sessions)
                    event_bus.emit_event(EventType.MEDIA_CHANGED, payload)
            except Exception as e:
                log.debug("media.poll_failed %s", e)
            await asyncio.sleep(self.interval)

    async def _describe(self, s) -> Optional[Dict]:
        try:
            props = await s.try_get_media_properties_async()
        except Exception:
            return None
        pb = s.get_playback_info()
        tl = s.get_timeline_properties()
        app_id = s.source_app_user_model_id or ""
        title = (props.title or "").strip()
        artist = (props.artist or "").strip()
        thumb = ""
        if props.thumbnail is not None:
            thumb = f"media://{hashlib.md5((app_id + title + artist).encode('utf-8', 'ignore')).hexdigest()}"
            with self._lock:
                have = thumb in self._thumbs
            if not have:
                data = await self._read_thumb(props.thumbnail)
                if data:
                    with self._lock:
                        self._thumbs[thumb] = data
                        while len(self._thumbs) > 12:
                            self._thumbs.pop(next(iter(self._thumbs)))
                else:
                    thumb = ""

        def ms(td):
            try:
                return int(td.total_seconds() * 1000)
            except Exception:
                return 0
        try:
            # The position is as of Windows' last timeline update (browsers only
            # report on play / pause / seek) — progress interpolates from then.
            at = tl.last_updated_time.timestamp()
        except Exception:
            at = time.time()
        ctl = pb.controls
        return {
            "app_id": app_id, "app": app_label(app_id), "title": title, "artist": artist,
            "album": (props.album_title or "").strip(), "is_playing": pb.playback_status == _PLAYING,
            "status": int(pb.playback_status), "position_ms": ms(tl.position), "duration_ms": ms(tl.end_time),
            "at": min(at, time.time()), "thumb": thumb,
            "can_next": bool(ctl.is_next_enabled), "can_previous": bool(ctl.is_previous_enabled),
            "can_play_pause": bool(ctl.is_play_pause_toggle_enabled),
            "is_spotify": "spotify" in app_id.lower(),
        }

    @staticmethod
    async def _read_thumb(ref) -> bytes:
        try:
            from winrt.windows.storage.streams import Buffer, InputStreamOptions
            stream = await ref.open_read_async()
            size = int(stream.size)
            if not size or size > 8 * 1024 * 1024:
                return b""
            buf = Buffer(size)
            got = await stream.read_async(buf, size, InputStreamOptions.READ_AHEAD)
            return bytes(got)
        except Exception as e:
            log.debug("media.thumb_failed %s", e)
            return b""

    # ------------------------------------------------------------------ #
    def control(self, action: str, app_id: str = "") -> bool:
        """play_pause / next / previous (Linux also volume_up / volume_down) on the shown (or named) session."""
        app_id = app_id or self.state.get("app_id", "")
        if sys.platform.startswith("linux"):
            return self._control_linux(action, app_id)
        loop = self._loop
        if loop is None:
            return False

        async def go():
            s = self._sessions.get(app_id)
            if s is None:
                return False
            fn = {"play_pause": s.try_toggle_play_pause_async, "next": s.try_skip_next_async,
                  "previous": s.try_skip_previous_async, "play": s.try_play_async,
                  "pause": s.try_pause_async}.get(action)
            return bool(await fn()) if fn else False
        try:
            ok = asyncio.run_coroutine_threadsafe(go(), loop).result(timeout=3)
        except Exception as e:
            log.info("media.control_failed %s %s", action, e)
            return False
        with self._lock:
            if ok and action in ("play_pause", "play", "pause") and self._state.get("app_id") == app_id:
                playing = {"play": True, "pause": False}.get(action, not self._state.get("is_playing"))
                self._state.update(is_playing=playing)
        return ok


    def _control_linux(self, action: str, app_id: str) -> bool:
        cmd = {"play_pause": ["play-pause"], "next": ["next"], "previous": ["previous"], "play": ["play"],
               "pause": ["pause"], "volume_up": ["volume", "0.05+"], "volume_down": ["volume", "0.05-"]}.get(action)
        if not cmd or not app_id:
            return False
        try:
            ok = subprocess.run(["playerctl", "-p", app_id, *cmd], capture_output=True, timeout=4).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False
        with self._lock:
            if ok and action in ("play_pause", "play", "pause") and self._state.get("app_id") == app_id:
                playing = {"play": True, "pause": False}.get(action, not self._state.get("is_playing"))
                self._state.update(is_playing=playing)
        return ok


media = MediaWatcher()
