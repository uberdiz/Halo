"""Camera presence: the decisions (lock, screen off, wake, pause and resume media), carried out through the OS
actions, off by default, and the camera released when it stops. No camera is used in these tests."""
import os
import threading

import pytest

from core import presence as pr
from core.presence import Presence, Settings


def run_steps(p, steps):
    """steps: [(seconds, face, facing)] -> {second: [commands]}"""
    out = {}
    for t, face, facing in steps:
        cmds = p.step(face, facing, 1000.0 + t)
        if cmds:
            out[t] = cmds
    return out


def test_leaving_locks_then_turns_the_screen_off_and_coming_back_wakes_it():
    p = Presence(Settings(lock_after=120, long_away_after=600))
    seen = run_steps(p, [(0, True, True)] + [(t, False, False) for t in range(5, 700, 5)] + [(705, True, True)])
    assert seen == {120: ["lock"], 600: ["screen_off"], 705: ["wake_screen"]}
    assert p.state == pr.PRESENT and not p.locked


def test_a_short_gap_is_not_leaving():
    p = Presence(Settings(lock_after=120))
    seen = run_steps(p, [(0, True, True), (3, False, False), (6, False, False), (8, True, True), (200, True, True)])
    assert seen == {} and p.state == pr.PRESENT


def test_looking_away_pauses_media_and_looking_back_resumes_it():
    p = Presence(Settings(pause_media_after=6))
    seen = run_steps(p, [(0, True, True), (2, True, False), (5, True, False), (9, True, False), (12, True, False),
                         (14, True, True)])
    assert seen == {9: ["pause_media"], 14: ["resume_media"]}


def test_sleep_when_chosen_and_never_when_zero():
    p = Presence(Settings(lock_after=0, long_away_after=60, long_away="sleep"))
    assert run_steps(p, [(0, True, True)] + [(t, False, False) for t in range(10, 100, 10)]) == {60: ["sleep"]}
    q = Presence(Settings(lock_after=0, long_away_after=0, pause_media_after=0))
    assert run_steps(q, [(0, True, True), (5, True, False), (50, True, False)] +
                     [(t, False, False) for t in range(60, 2000, 60)]) == {}


def test_commands_are_carried_out_through_actions_and_tools():
    done, ran = [], []
    assert pr.carry_out("lock", run_action=lambda a, p: done.append(a) or True)
    assert done == ["power.lock"]
    fake = lambda argv, **kw: ran.append(argv) or type("R", (), {"returncode": 0})()
    assert pr.carry_out("wake_screen", run=fake) and ran[-1] == ["kscreen-doctor", "--dpms", "on"]
    assert pr.carry_out("pause_media", run=fake) and ran[-1] == ["playerctl", "pause"]
    assert not pr.carry_out("format_disk", run=fake)


def test_runner_releases_the_camera_when_stopped_and_says_when_it_is_on():
    frames, released, notes = threading.Event(), [], []

    def grab():
        frames.set()
        return "frame"
    runner = pr.PresenceRunner(Settings(lock_after=0), detector=lambda f: (True, True), camera=(grab, lambda: released.append(1)),
                               act=lambda c: None, fps=50, notify=notes.append)
    assert runner.start()
    assert frames.wait(2)
    runner.stop()
    assert released == [1] and "on" in notes[0] and "released" in notes[-1]


def test_missing_opencv_is_explained(monkeypatch):
    monkeypatch.setattr(pr, "opencv_detector", lambda: None)
    r = pr.PresenceRunner()
    assert not r.start() and "OpenCV" in r.error


def test_settings_page_is_off_by_default_and_turns_off_cleanly(monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from core.config import config
    saved = {}
    monkeypatch.setattr(config, "set", lambda k, v, persist=True: saved.__setitem__(k, v))
    monkeypatch.setattr(config, "get", lambda k, d=None: saved.get(k, d))
    from ui.settings_pages import presence as page_mod
    made = []

    class Fake:
        def __init__(self, s):
            self.presence, self.stopped, self.error = type("P", (), {"settings": s})(), False, ""
            made.append(self)

        def start(self):
            return True

        def stop(self):
            self.stopped = True
    page = page_mod.PresencePage(runner_factory=Fake)
    assert not page.on.isChecked() and not made                              # off until turned on
    page.on.setChecked(True)
    assert made and saved["presence.enabled"] is True and "On." in page.status.text()
    page.long_kind.setCurrentIndex(1)
    assert made[0].presence.settings.long_away == "sleep"
    page.on.setChecked(False)
    assert made[0].stopped and saved["presence.enabled"] is False


def test_focus_nudge_once_per_stretch_and_a_real_break_resets_it():
    p = Presence(Settings(break_after=3000, lock_after=0, long_away_after=0))
    seen = run_steps(p, [(t, True, True) for t in range(0, 3601, 60)])
    assert [t for t, c in seen.items() if "nudge_break" in c] == [3000]
    # a 2-minute gap isn't a break; 5 minutes is, and the next nudge comes 50 minutes after it
    seen = run_steps(p, [(3720, True, True), (4100, True, True)] + [(t, True, True) for t in range(4160, 7300, 60)])
    assert [t for t, c in seen.items() if "nudge_break" in c] == [4100 + 3000]
    assert not any("nudge_break" in c for c in run_steps(Presence(Settings()), [(t, True, True) for t in range(0, 9000, 60)]).values())
