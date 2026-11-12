"""
core/sys_history.py

The System Overview's history graphs (5m / 1h / 24h / 7d), kept while SAINT runs.

A daemon thread samples every 10 s with the samplers Task Manager already uses (psutil, RateSampler,
sysinfo.gpus — nvidia-smi every 10 s, well under the 2 s floor) and stores averaged points in a small
sqlite file under the data dir at three resolutions: 10 s for an hour, 1 min for a day, 10 min for a week.
Nothing is sampled when SAINT isn't running, so those stretches are simply empty.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("saint.sys_history")

METRICS = ("cpu", "mem", "gpu", "vram", "disk", "net")       # %, %, %, %, bytes/s, bytes/s
# resolution (s) -> kept for (s)
RESOLUTIONS = {10: 3600, 60: 86400, 600: 7 * 86400}
RANGES = {"5m": (300, 10), "1h": (3600, 10), "24h": (86400, 60), "7d": (7 * 86400, 600)}
INTERVAL = 10


def _db_path() -> Path:
    from core.paths import data_dir
    return data_dir() / "sys_history.sqlite"


class History:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else _db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS points (res INTEGER, t INTEGER, " +
                         ", ".join(f"{m} REAL" for m in METRICS) + ", PRIMARY KEY (res, t))")
        self._lock = threading.Lock()
        self._acc: Dict[int, Tuple[int, List[Dict]]] = {}      # res -> (bucket, samples)

    def add(self, sample: Dict, now: Optional[float] = None):
        """One sample; each resolution writes its mean when its bucket closes."""
        now = time.time() if now is None else now
        with self._lock:
            for res, keep in RESOLUTIONS.items():
                bucket = int(now // res * res)
                cur, items = self._acc.get(res, (bucket, []))
                if cur != bucket and items:
                    self._write(res, cur, items)
                    self._db.execute("DELETE FROM points WHERE res=? AND t<?", (res, int(now - keep)))
                    items = []
                self._acc[res] = (bucket, items + [sample])
            self._db.commit()

    def _write(self, res: int, t: int, items: List[Dict]):
        means = []
        for m in METRICS:
            vals = [s[m] for s in items if s.get(m) is not None]
            means.append(sum(vals) / len(vals) if vals else None)
        self._db.execute(f"INSERT OR REPLACE INTO points VALUES (?, ?, {', '.join('?' * len(METRICS))})",
                         (res, t, *means))

    def series(self, rng: str, metric: str, now: Optional[float] = None) -> List[Optional[float]]:
        """Values oldest first, one per bucket across the range; None where SAINT wasn't running."""
        span, res = RANGES[rng]
        if metric not in METRICS:
            raise ValueError(metric)
        now = time.time() if now is None else now
        start = int((now - span) // res * res)
        with self._lock:
            rows = dict(self._db.execute(f"SELECT t, {metric} FROM points WHERE res=? AND t>=?", (res, start)))
        return [rows.get(t) for t in range(start, int(now // res * res), res)]

    def close(self):
        self._db.close()


def sample(rates, gpus=None) -> Dict:
    """One reading from the existing samplers (RateSampler for disk/network, sysinfo.gpus for the GPU)."""
    import psutil
    from core import sysinfo
    r = rates.sample()
    g = (gpus if gpus is not None else sysinfo.gpus()) or [{}]
    used, total = g[0].get("memory_used"), g[0].get("memory_total")
    disks = [d for d in r["disks"].values() if d["read"] is not None]
    nets = [n for n in r["networks"].values() if n["recv"] is not None]
    return {"cpu": psutil.cpu_percent(), "mem": psutil.virtual_memory().percent, "gpu": g[0].get("percent"),
            "vram": 100.0 * used / total if used is not None and total else None,
            "disk": sum(d["read"] + (d["write"] or 0) for d in disks) if disks else None,
            "net": sum(n["recv"] + (n["sent"] or 0) for n in nets) if nets else None}


_started = False


def start_sampler(history: Optional[History] = None, interval: float = INTERVAL) -> bool:
    """Start the background sampler once (SAINT calls this at startup)."""
    global _started
    if _started:
        return False
    _started = True

    def loop():
        from core import sysinfo
        try:
            h = history or History()
        except Exception as e:
            log.warning("system history disabled: %s", e)
            return
        rates = sysinfo.RateSampler()
        rates.sample()
        while True:
            time.sleep(interval)
            try:
                h.add(sample(rates))
            except Exception as e:                     # a bad read skips one point, never the thread
                log.debug("history sample failed: %s", e)
    threading.Thread(target=loop, daemon=True, name="sys-history").start()
    return True
