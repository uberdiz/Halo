"""
ui/pages/system.py

Health, speed and modules in one place: live resource use, every subsystem's state from core/health.py
(Working / Degraded / Missing / Failed / Not tested, with the reason, and a Repair button backed by
core/deps.py), the AI model's download progress, voice-pipeline latency against its goal, and module status.
"""

import platform
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from core.analytics import analytics
from core.state import app_state
from ui.theme import current_palette
from ui.widgets import Card, ElidedLabel, Page, chip, run_async, set_chip

# (title, analytics key, goal ms)
LATENCY = [("Overall response", "avg_overall_ms", 250), ("Speech-to-text", "avg_stt_ms", 100),
           ("Model", "avg_model_ms", 800), ("First token", "avg_ai_first_token_ms", 400),
           ("Intent routing", "avg_intent_ms", 50), ("Text-to-speech", "avg_tts_inference_ms", 150)]
LIGHT_EVERY = 30          # seconds between light health checks while the page is open


class Tile(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setObjectName("StatCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 13, 16, 13)
        lay.setSpacing(3)
        t = QLabel(title.upper())
        t.setObjectName("CardTitle")
        self.value = ElidedLabel("—")
        self.value.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.sub = ElidedLabel("")
        self.sub.setObjectName("Faint")
        for w in (t, self.value, self.sub):
            lay.addWidget(w)

    def set(self, value, sub="", tone=""):
        p = current_palette()
        self.value.setText(str(value))
        self.value.setStyleSheet(f"font-size: 18px; font-weight: 600; color: {getattr(p, tone, p.text)};")
        self.sub.setText(sub)


def chip_kind(state: str) -> str:
    from core import health
    return {health.WORKING: "ok", health.DEGRADED: "warn", health.MISSING: "warn",
            health.FAILED: "err"}.get(state, "")


class SystemPage(Page):
    def __init__(self, shell=None):
        super().__init__("System", "Health, speed and modules.")
        self.shell = shell
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        body = QVBoxLayout(inner)
        body.setContentsMargins(0, 0, 8, 0)
        body.setSpacing(16)
        scroll.setWidget(inner)
        self.root.addWidget(scroll, 1)

        grid = QGridLayout()
        grid.setSpacing(12)
        names = ["Status", "CPU", "Memory", "Uptime", "Wake word"]
        self.t = {n: Tile(n) for n in names}
        for i, n in enumerate(names):
            grid.addWidget(self.t[n], 0, i)
        body.addLayout(grid)

        # Every subsystem in one vocabulary (core/health.py); the heavy checks run on "Run full check".
        from core import health
        hc = Card("Subsystem health")
        self.health_summary = QLabel("")
        self.health_summary.setObjectName("Faint")
        self.full_btn = QPushButton("Run full check")
        self.full_btn.setObjectName("Ghost")
        self.full_btn.setToolTip("Also asks the AI model for a reply, synthesises Kokoro speech and transcribes "
                                 "it with Whisper (up to two minutes)")
        self.full_btn.clicked.connect(lambda: self.check_health(full=True))
        hc.header.addWidget(self.health_summary)
        hc.header.addWidget(self.full_btn)
        self.rows = {}
        for key, label, _heavy in health.SUBSYSTEMS:
            row = QHBoxLayout()
            name = QLabel(label)
            name.setStyleSheet("font-weight: 600;")
            name.setFixedWidth(150)
            state = chip(health.LABELS[health.NOT_TESTED])
            detail = ElidedLabel("Checking…")
            detail.setObjectName("Muted")
            fix = QPushButton("Repair")
            fix.setObjectName("Ghost")
            fix.setToolTip("Install what's missing (asks first), then check again")
            fix.clicked.connect(lambda _c=False, k=key: self.repair(k))
            fix.hide()
            row.addWidget(name)
            row.addWidget(state)
            row.addWidget(detail, 1)
            row.addWidget(fix)
            hc.body.addLayout(row)
            self.rows[key] = (state, detail, fix)
        body.addWidget(hc)
        self._health = {}
        self._checking = False
        self._last_light = 0.0

        # What started and what didn't (core/startup.py): the reason, and Retry / Use CPU / Settings.
        from ui.components.health_panel import HealthPanel
        self.health = HealthPanel(shell, compact=False)
        body.addWidget(self.health)

        lat = Card("Voice pipeline latency")
        lg = QGridLayout()
        lg.setSpacing(12)
        self.lat = {}
        for i, (title, key, goal) in enumerate(LATENCY):
            tile = Tile(title)
            self.lat[key] = (tile, goal)
            lg.addWidget(tile, i // 3, i % 3)
        lat.body.addLayout(lg)
        body.addWidget(lat)

        mods = Card("Modules")
        self.mod_rows = QVBoxLayout()
        self.mod_rows.setSpacing(10)
        mods.body.addLayout(self.mod_rows)
        from core.module_manager import module_manager
        self._chips = {}
        for key, m in module_manager.modules.items():
            row = QHBoxLayout()
            name = QLabel(m.name)
            name.setStyleSheet("font-weight: 600;")
            name.setFixedWidth(110)
            desc = ElidedLabel(m.description)
            desc.setObjectName("Muted")
            c = chip("")
            self._chips[key] = (m, c)
            row.addWidget(name)
            row.addWidget(desc, 1)
            row.addWidget(c)
            self.mod_rows.addLayout(row)
        body.addWidget(mods)
        body.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()
        self.timer.start(3000)

    def hideEvent(self, e):
        super().hideEvent(e)
        self.timer.stop()

    def refresh(self):
        from core.module_manager import module_manager
        errors, crashes = app_state.error_count, app_state.module_crash_count
        ok = errors == 0 and crashes == 0
        self.t["Status"].set("Healthy" if ok else "Degraded", f"{errors} errors · {crashes} crashes",
                             "success" if ok else "warning")
        self.t["CPU"].set(f"{app_state.cpu_percent():.0f}%", f"{platform.processor()[:28] or platform.machine()}")
        self.t["Memory"].set(f"{app_state.ram_mb():.0f} MB", "SAINT process")
        self.t["Uptime"].set(app_state.uptime_formatted(), f"Python {platform.python_version()}")

        voice = module_manager.get("voice")
        w = voice.wake_status() if voice else {}
        if not w.get("enabled"):
            self.t["Wake word"].set("Off", "responds to all speech", "warning")
        else:
            self.t["Wake word"].set("Ready" if w.get("ready") else "Unavailable",
                                    f"{w.get('avg_infer_ms', '—')} ms/frame" if w.get("ready") else w.get("error", ""),
                                    "success" if w.get("ready") else "danger")

        snap = analytics.snapshot()
        for key, (tile, goal) in self.lat.items():
            v = float(snap.get(key, 0.0) or 0.0)
            if v <= 0:
                tile.set("—", f"goal {goal} ms")
            else:
                tone = "success" if v <= goal else "" if v <= goal * 1.3 else "warning"
                tile.set(f"{v:.0f} ms", f"goal {goal} ms", tone)

        for key, (m, c) in self._chips.items():
            set_chip(c, "On" if m.enabled else "Off", "ok" if m.enabled else "")
        self.health.refresh()
        if time.monotonic() - self._last_light > LIGHT_EVERY:
            self.check_health(full=False)
        self._show_pull()

    # ------------------------------------------------------------------ subsystem health
    def check_health(self, full: bool = False):
        """Run core/health.py's checks off the GUI thread and show them; ``full`` adds the heavy ones."""
        from core import health
        if self._checking:
            return
        self._checking = True
        self._last_light = time.monotonic()
        if full:
            self.full_btn.setEnabled(False)
            self.health_summary.setText("Running the full check…")

        def done(results):
            self._checking = False
            self.full_btn.setEnabled(True)
            for r in results:
                self._health[r["key"]] = r
                self.show_result(r["key"], r)
            self.health_summary.setText(health.summary(results))
            self._show_pull()

        def failed(err):
            self._checking = False
            self.full_btn.setEnabled(True)
            self.health_summary.setText(f"Health check failed: {err}")
        run_async(lambda: health.run_all(full=full), done, failed)

    def show_result(self, key: str, r: dict):
        from core import deps, health
        state, detail, fix = self.rows[key]
        set_chip(state, health.LABELS[r["state"]], chip_kind(r["state"]))
        detail.setText(r["detail"])
        detail.setToolTip(f"{r['detail']}\nChecked {r.get('at', '')}")
        fix.setVisible(r["state"] in (health.MISSING, health.FAILED, health.DEGRADED)
                       and bool(deps.MANIFESTS.get(key, {}).get("deps")))

    def _show_pull(self):
        """While the AI model downloads, its progress is the Language model line (core/model_pull.py)."""
        from core import health, model_pull
        s = model_pull.state()
        if not s.get("model"):
            return
        state, detail, fix = self.rows["ollama"]
        if s.get("running"):
            set_chip(state, "Downloading", "accent")
            detail.setText(model_pull.describe(s))
            fix.hide()
        elif s.get("done") and self._health.get("ollama", {}).get("state") != health.WORKING:
            self._last_light = 0.0                       # just finished: check again on the next tick

    def repair(self, key: str):
        """core/deps.py: say what would be installed, install only after Yes, then verify and test."""
        from core import deps
        state, detail, fix = self.rows[key]
        fix.setEnabled(False)
        detail.setText("Working out what's missing…")

        def planned(actions):
            fix.setEnabled(True)
            if not actions:
                detail.setText("Nothing to install — " + self._health.get(key, {}).get("detail", ""))
                return
            steps = "\n".join(f"• {a.label}" for a in actions)
            admin = "Your password is asked for the system steps.\n\n" if any(a.needs_admin for a in actions) else ""
            if QMessageBox.question(self, f"Repair {deps.MANIFESTS[key]['label']}",
                                    f"SAINT will:\n\n{steps}\n\n{admin}Go ahead?") != QMessageBox.Yes:
                detail.setText("Repair cancelled.")
                return
            fix.setEnabled(False)
            detail.setText("Installing…")
            # Confirmed just now for this plan; deps.install still runs nothing it didn't plan.
            run_async(lambda: deps.install(key, confirm=lambda _a: True), finished,
                      lambda e: (fix.setEnabled(True), detail.setText(f"Repair failed: {e}")))

        def finished(res):
            fix.setEnabled(True)
            r = res.get("test") or res.get("verify")
            if r:
                self._health[key] = {**r, "key": key}
                self.show_result(key, r)
            if res["errors"]:
                detail.setText("Repair failed: " + "; ".join(f"{d}: {w}" for d, w in res["errors"].items()))
            ok = res["status"] in ("ok", "nothing to do")
            if self.shell is not None and hasattr(self.shell, "toast"):
                self.shell.toast(deps.MANIFESTS[key]["label"], "Repaired and checked." if ok else
                                 "The repair didn't finish — the reason is on the System page.",
                                 "ok" if ok else "error")
        run_async(lambda: deps.plan(key), planned,
                  lambda e: (fix.setEnabled(True), detail.setText(f"Couldn't check: {e}")))
