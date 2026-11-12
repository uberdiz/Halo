"""
core/audio_feed.py

Sound levels for the living wallpaper: ws://127.0.0.1:47812/desktop (what's playing) or /mic (the microphone),
localhost only, read-only. Capture runs only while at least one wallpaper is connected, at 16 kHz mono through
PipeWire's Pulse server (parec), and turns each ~32 ms of sound into {"level": 0-1, "bands": [16 values 0-1]}:
nothing is recorded or stored, only these numbers leave this process.
"""

from __future__ import annotations

import json
import logging
import math
import shutil
import subprocess
import threading
from array import array
from typing import Callable, List, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QHostAddress, QTcpServer

from core.state_socket import accept_key, text_frame

log = logging.getLogger("saint.audio_feed")
PORT = 47812
RATE = 16000
FRAME = 512                                   # samples per reading (32 ms)
BANDS = 16
DEVICES = {"desktop": "@DEFAULT_MONITOR@", "mic": "@DEFAULT_SOURCE@"}


def analyse(samples: List[int], bands: int = BANDS) -> dict:
    """Loudness (RMS, on a log scale) and ``bands`` log-spaced spectrum bands, each 0-1. Pure Python + a small DFT
    over 64 bins: fast enough at 30 readings a second, no numpy needed."""
    n = len(samples)
    if not n:
        return {"level": 0.0, "bands": [0.0] * bands}
    rms = math.sqrt(sum(s * s for s in samples) / n) / 32768
    level = max(0.0, min(1.0, (20 * math.log10(rms + 1e-9) + 60) / 54))       # -60 dBFS..-6 dBFS -> 0..1
    bins = 64
    step = max(1, n // (bins * 2))
    x = samples[::step][: bins * 2]
    m = len(x)
    mags = []
    for k in range(1, bins + 1):
        re = im = 0.0
        w = 2 * math.pi * k / m
        for t, v in enumerate(x):
            re += v * math.cos(w * t)
            im -= v * math.sin(w * t)
        mags.append(math.hypot(re, im) / (m * 32768))
    edges = [int(round(bins ** (i / bands))) for i in range(bands + 1)]
    out = []
    for i in range(bands):
        lo, hi = edges[i] - 1, max(edges[i + 1] - 1, edges[i])
        v = max(mags[lo:hi] or [0.0])
        out.append(round(max(0.0, min(1.0, (20 * math.log10(v + 1e-9) + 70) / 60)), 3))
    return {"level": round(level, 3), "bands": out}


class AudioFeed(QObject):
    reading = Signal(str, str)                # (source, json) from the capture thread

    def __init__(self, port: int = PORT, parent=None, capture: Optional[Callable[[str], subprocess.Popen]] = None):
        super().__init__(parent)
        self._clients = {}                    # socket -> source
        self._threads = {}                    # source -> (thread, process)
        self._capture = capture or self._parec
        self._srv = QTcpServer(self)
        self.listening = self._srv.listen(QHostAddress.LocalHost, port)
        self._srv.newConnection.connect(self._accept)
        self.reading.connect(self._send)

    # ------------------------------------------------------------------ websocket
    def _accept(self):
        while self._srv.hasPendingConnections():
            sock = self._srv.nextPendingConnection()
            sock.setProperty("buf", b"")
            sock.readyRead.connect(lambda s=sock: self._read(s))
            sock.disconnected.connect(lambda s=sock: self._drop(s))

    def _read(self, sock):
        if sock in self._clients:
            sock.readAll()
            return
        buf = sock.property("buf") + bytes(sock.readAll())
        if len(buf) > 8192:
            sock.abort()
            return
        sock.setProperty("buf", buf)
        if b"\r\n\r\n" not in buf:
            return
        first = buf.split(b"\r\n", 1)[0].decode("ascii", "replace").split()
        source = (first[1].strip("/") if len(first) > 1 else "") or "desktop"
        headers = {}
        for line in buf.split(b"\r\n")[1:]:
            if b":" in line:
                k, v = line.split(b":", 1)
                headers[k.strip().lower()] = v.strip()
        key = headers.get(b"sec-websocket-key", b"").decode("ascii", "replace")
        if source not in DEVICES or not key or headers.get(b"upgrade", b"").lower() != b"websocket":
            sock.write(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n")
            sock.disconnectFromHost()
            return
        sock.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                    f"Sec-WebSocket-Accept: {accept_key(key)}\r\n\r\n").encode())
        self._clients[sock] = source
        self._start(source)

    def _drop(self, sock):
        source = self._clients.pop(sock, None)
        sock.deleteLater()
        if source and source not in self._clients.values():
            self._stop(source)                # nobody is listening to this source: stop capturing it

    def _send(self, source: str, msg: str):
        frame = text_frame(msg)
        for sock, src in list(self._clients.items()):
            if src == source:
                sock.write(frame)

    # ------------------------------------------------------------------ capture
    @staticmethod
    def _parec(source: str) -> Optional[subprocess.Popen]:
        exe = shutil.which("parec")
        if not exe:
            log.info("audio_feed.no_parec")
            return None
        return subprocess.Popen([exe, "-d", DEVICES[source], "--format=s16le", f"--rate={RATE}", "--channels=1",
                                 "--latency-msec=30"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def _start(self, source: str):
        if source in self._threads:
            return
        proc = self._capture(source)
        if proc is None:
            return

        def run():
            need = FRAME * 2
            while True:
                chunk = proc.stdout.read(need)
                if not chunk or len(chunk) < need:
                    break
                samples = array("h")
                samples.frombytes(chunk)
                self.reading.emit(source, json.dumps(analyse(list(samples))))
        t = threading.Thread(target=run, daemon=True, name=f"audio-feed-{source}")
        self._threads[source] = (t, proc)
        t.start()

    def _stop(self, source: str):
        t, proc = self._threads.pop(source, (None, None))
        if proc is not None:
            proc.terminate()

    def close(self):
        for source in list(self._threads):
            self._stop(source)
        self._srv.close()
