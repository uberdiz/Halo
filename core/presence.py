"""
core/presence.py

Camera presence: opt-in (off until you turn it on in Settings > Camera presence), and everything stays on this PC.
A few low-resolution frames a second are checked for a face, then thrown away: no picture is stored or sent.

    you leave         -> after a while the screen locks; after longer, the screen turns off (or the PC sleeps,
                         if you chose that)
    you come back     -> the screen wakes to the lock screen (it is never unlocked for you)
    you look away     -> media you're watching pauses, and plays again when you look back
    focus nudge       -> optional: after a long stretch at the screen, a suggestion to take a short break
    camera in use     -> a notice says so while it runs, and one switch turns it all off

What a camera can't do: a PC that is asleep (suspended) has its camera off, so it can't notice you come back. To
wake on your return, choose "turn the screen off" rather than "sleep" as the long-away step.

The decisions are a pure state machine (Presence.step); PresenceRunner feeds it from the camera and carries out
what it decides through the OS actions (lock, screen, media), so the log shows what happened and why.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

log = logging.getLogger("saint.presence")

PRESENT, LOOKING_AWAY, AWAY = "present", "looking_away", "away"


@dataclass
class Settings:
    lock_after: float = 120.0          # seconds with nobody there, then lock (0 = never)
    long_away_after: float = 600.0     # then the long-away step (0 = never)
    long_away: str = "screen_off"      # screen_off | sleep
    pause_media_after: float = 6.0     # seconds looking away before media pauses (0 = never)
    wake_on_return: bool = True
    break_after: float = 0.0           # focus nudge: seconds at the screen before suggesting a break (0 = never)


BREAK_RESETS = 300.0                   # five minutes away counts as a break


@dataclass
class Presence:
    """Feed it one observation at a time: (face seen, facing the screen). It returns what to do now."""
    settings: Settings = field(default_factory=Settings)
    state: str = PRESENT
    since: float = 0.0                 # when the current state began
    last_seen: float = 0.0
    locked: bool = False
    long_done: bool = False
    paused_media: bool = False
    sitting_since: float = 0.0         # start of the current stretch at the screen (focus nudge)
    nudged: bool = False

    def step(self, face: bool, facing: bool, now: float) -> List[str]:
        s, out = self.settings, []
        if not self.since:
            self.since = self.last_seen = now
        if face:
            if not self.sitting_since or now - self.last_seen >= BREAK_RESETS:
                self.sitting_since, self.nudged = now, False
            if s.break_after and not self.nudged and now - self.sitting_since >= s.break_after:
                out.append("nudge_break")
                self.nudged = True
            self.last_seen = now
            if self.state == AWAY:
                if s.wake_on_return and (self.locked or self.long_done):
                    out.append("wake_screen")
                self.locked = self.long_done = False
                self._enter(PRESENT if facing else LOOKING_AWAY, now)
            elif facing and self.state == LOOKING_AWAY:
                if self.paused_media:
                    out.append("resume_media")
                    self.paused_media = False
                self._enter(PRESENT, now)
            elif not facing and self.state == PRESENT:
                self._enter(LOOKING_AWAY, now)
            if self.state == LOOKING_AWAY and s.pause_media_after and not self.paused_media \
                    and now - self.since >= s.pause_media_after:
                out.append("pause_media")
                self.paused_media = True
            return out
        # nobody there: a short gap (a blink, turning round) isn't leaving
        gone = now - self.last_seen
        if self.state != AWAY and gone >= min(10.0, s.lock_after or 10.0):
            self._enter(AWAY, self.last_seen)
        if self.state == AWAY:
            if s.lock_after and not self.locked and gone >= s.lock_after:
                out.append("lock")
                self.locked = True
            if s.long_away_after and not self.long_done and gone >= s.long_away_after:
                out.append("sleep" if s.long_away == "sleep" else "screen_off")
                self.long_done = True
        return out

    def _enter(self, state: str, now: float):
        if state != self.state:
            log.info("presence.%s", state)
        self.state, self.since = state, now


# --------------------------------------------------------------------------- the camera side
def opencv_detector():
    """(frame) -> (face, facing) with OpenCV's bundled face models: a frontal face means facing the screen, only a
    profile means looking away. Returns None when OpenCV isn't installed."""
    try:
        import cv2
    except ImportError:
        return None
    front = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    side = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")

    def detect(frame) -> Tuple[bool, bool]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        if len(front.detectMultiScale(gray, 1.2, 5, minSize=(40, 40))):
            return True, True
        flipped = cv2.flip(gray, 1)
        if len(side.detectMultiScale(gray, 1.2, 4, minSize=(40, 40))) or \
                len(side.detectMultiScale(flipped, 1.2, 4, minSize=(40, 40))):
            return True, False
        return False, False
    return detect


def opencv_camera(index: int = 0):
    """A function returning one small frame (or None), and a function to release the camera."""
    import cv2
    cap = cv2.VideoCapture(index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

    def grab():
        ok, frame = cap.read()
        return frame if ok else None
    return grab, cap.release


COMMANDS = {"lock": ("power.lock", {}), "sleep": ("power.sleep", {})}


def carry_out(command: str, run_action: Optional[Callable] = None, run=None) -> bool:
    """Do one decision. Lock and sleep go through the OS actions (logged); the screen and media through their tools."""
    import subprocess
    run = run or subprocess.run
    if command in COMMANDS:
        if run_action is None:
            from core import actions
            run_action = lambda a, p: actions.execute(a, p, source="saint", confirmed=True).ok
        return run_action(*COMMANDS[command])
    argv = {"screen_off": ["kscreen-doctor", "--dpms", "off"], "wake_screen": ["kscreen-doctor", "--dpms", "on"],
            "pause_media": ["playerctl", "pause"], "resume_media": ["playerctl", "play"]}.get(command)
    if not argv:
        return False
    try:
        return run(argv, capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


class PresenceRunner:
    """Looks a few times a second while on. Stops cleanly; releases the camera when stopped."""

    def __init__(self, settings: Optional[Settings] = None, detector=None, camera=None, act=carry_out,
                 fps: float = 3.0, notify: Optional[Callable[[str], None]] = None):
        self.presence = Presence(settings or Settings())
        self.detector, self.camera, self.act, self.fps = detector, camera, act, fps
        self.notify = notify or (lambda text: None)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.error = ""

    def start(self) -> bool:
        detect = self.detector or opencv_detector()
        if detect is None:
            self.error = "Camera presence needs OpenCV, which isn't installed."
            return False
        try:
            grab, release = self.camera or opencv_camera()
        except Exception as e:
            self.error = f"The camera couldn't be opened: {e}"
            return False
        self.notify("Camera presence is on: SAINT checks for a face a few times a second, on this PC only.")

        def loop():
            try:
                while not self._stop.is_set():
                    frame = grab()
                    face, facing = detect(frame) if frame is not None else (False, False)
                    for command in self.presence.step(face, facing, time.time()):
                        log.info("presence.do %s", command)
                        if command == "nudge_break":
                            mins = round((time.time() - self.presence.sitting_since) / 60)
                            self.notify(f"You've been at the screen for {mins} minutes. A five-minute break helps you "
                                        "focus when you come back.")
                        else:
                            self.act(command)
                    self._stop.wait(1.0 / self.fps)
            finally:
                release()
                self.notify("Camera presence is off; the camera is released.")
        self._stop.clear()
        self._thread = threading.Thread(target=loop, daemon=True, name="presence")
        self._thread.start()
        return True

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
