"""The package queue: "pacman is busy" is waited for, never shown as a failure."""
import threading

import pytest

from core import pkg_queue as q
from core import saintos_apps as sa


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def test_lock_states():
    assert q.lock_state(lambda p: False, lambda: []) == "free"
    assert q.lock_state(lambda p: True, lambda: ["pacman"]) == "held"
    assert q.lock_state(lambda p: True, lambda: []) == "stale"
    assert q.needs_pacman(["pkexec", "pacman", "-S", "x"]) and q.needs_pacman(["paru", "-S", "x"])
    assert not q.needs_pacman(["flatpak", "install", "x"])


def test_waits_while_pacman_is_busy_then_goes(monkeypatch):
    clock, said = Clock(), []
    busy_until = 5.0
    waited = q.wait_for_pacman(said.append, exists=lambda p: clock.t < busy_until, procs=lambda: ["pacman"],
                               sleep=clock.sleep, clock=clock.now)
    assert waited >= busy_until and said == [q.WAITING]            # said once, not once a second


def test_stale_lock_is_cleared_only_after_it_stays_ownerless():
    clock, state, removed = Clock(), {"there": True}, []

    def remove(lock):
        removed.append(clock.t)
        state["there"] = False
        return True
    q.wait_for_pacman(None, exists=lambda p: state["there"], procs=lambda: [], remove=remove, mtime=lambda p: 1.0,
                      sleep=clock.sleep, clock=clock.now, stale_after=20, poll=1)
    assert removed and removed[0] >= 20


def test_a_lock_someone_took_meanwhile_is_not_removed():
    removed = []
    assert not q.clear_stale_lock(lambda p: True, lambda: ["pacman"], lambda l: removed.append(l) or True)
    assert not q.clear_stale_lock(lambda p: True, lambda: [], lambda l: removed.append(l) or True,
                                  mtime=lambda p: 2.0, seen_mtime=1.0)             # a different lock than the stale one
    assert removed == []


def test_stale_lock_that_cannot_be_cleared_fails_with_the_reason():
    clock = Clock()
    with pytest.raises(q.QueueError, match="Restarting the PC clears it"):
        q.wait_for_pacman(None, exists=lambda p: True, procs=lambda: [], remove=lambda l: False,
                          mtime=lambda p: 1.0, sleep=clock.sleep, clock=clock.now, stale_after=3, poll=1)


def test_cancel_stops_the_wait():
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(q.QueueError, match="Cancelled"):
        q.wait_for_pacman(None, cancel, exists=lambda p: True, procs=lambda: ["pacman"], sleep=lambda s: None)


def test_turns_are_first_come_first_served_and_dead_tickets_are_dropped(tmp_path):
    alive = {111, 222}
    first = q.Turn(directory=tmp_path, pid=111, pid_alive=lambda p: p in alive)
    first.take_ticket()
    dead = q.Turn(directory=tmp_path, pid=999, pid_alive=lambda p: p in alive)
    dead.take_ticket()
    said = []
    second = q.Turn(said.append, directory=tmp_path, pid=222, pid_alive=lambda p: p in alive,
                    sleep=lambda s: first._drop())                  # the first finishes while the second waits
    second.take_ticket()
    assert second.position() == 1 and not dead.ticket.exists()      # the crashed one doesn't hold the queue up
    assert q.waiting(tmp_path, lambda p: p in alive) == 2
    second._drop()
    with second:
        assert said == [q.wait_text(1)] and "1 ahead" in said[0]
    assert q.waiting(tmp_path, lambda p: p in alive) == 0


class FakeProc:
    def __init__(self, lines, code):
        self.stdout, self._code = iter(lines), code

    def wait(self):
        return self._code


def test_a_step_that_loses_the_race_for_the_lock_runs_again(tmp_path):
    attempts, waits = [], []
    outcomes = iter([(["error: failed to init transaction (unable to lock database)"], 1), (["installed"], 0)])

    def popen(argv, **kw):
        attempts.append(argv)
        return FakeProc(*next(outcomes))
    gate = q.Gate(waits.append, wait=lambda on_wait, cancel: 0.0)
    step = sa.Step("Firefox (Arch)", ["pkexec", "pacman", "-S", "firefox"], ["firefox"], needs_admin=True)
    errors = {}
    result = q.run_plan([step], gate=gate, turn=q.Turn(directory=tmp_path), popen=popen, on_line=lambda l: None,
                        errors=errors, live=False)
    assert result == {"firefox": True} and len(attempts) == 2 and errors == {}
    assert q.WAITING in waits


def test_busy_pacman_is_not_a_blocker_any_more():
    errors, _warnings = sa.blockers(cmdline="", exists=lambda p: p == q.PACMAN_LOCK)
    assert not any("busy" in e.lower() for e in errors)


# --------------------------------------------------------------------------- what the user sees
@pytest.fixture
def qapp():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_buttons_show_busy_done_and_failed(qapp):
    from PySide6.QtWidgets import QPushButton
    from ui.widgets import set_button_state
    b = QPushButton("Install")
    set_button_state(b, "busy", "Installing…")
    assert not b.isEnabled() and b.text() == "Installing…" and b.property("state") == "busy"
    set_button_state(b, "done", "Installed")
    assert b.isEnabled() and b.property("state") == "done"
    set_button_state(b, "")
    assert b.text() == "Install" and not b.property("state")
    with pytest.raises(ValueError):
        set_button_state(b, "sparkly")


def test_store_search_shows_progress_at_once_and_per_source(qapp, monkeypatch):
    from ui.pages import store as page_mod
    monkeypatch.setattr(page_mod, "run_async", lambda *a, **k: None)          # no network, no threads
    page = page_mod.StorePage()
    page._show_searching("firefox")
    assert "firefox" in page.status.text() and set(page._source_chips) == {"repo", "flathub", "aur", "windows"}
    page._on_source(page._seq, "repo", 3)
    assert "3" in page._source_chips["repo"].text() and "Arch" not in page._search_note.text()
    page._on_source(page._seq, "aur", 0)
    assert "none" in page._source_chips["aur"].text()
    page._on_source(page._seq - 1, "flathub", 9)                              # an older search's answer is ignored
    assert "…" in page._source_chips["flathub"].text()
