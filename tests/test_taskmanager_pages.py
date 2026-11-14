"""Task Manager pages other than Processes: the same table look, sorting by the real value (not the text), plain
words, empty states, buttons that follow the selection, and a screenshot of every page."""
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "dev"))
import taskmanager_screenshots as shots  # noqa: E402  (sets the offscreen platform and a throwaway settings folder)


@pytest.fixture
def win(monkeypatch):
    _app, w = shots.window(monkeypatch.setattr)
    yield w
    w.close()


def _col(table, c):
    return [table.item(r, c).text() for r in range(table.rowCount())]


def _page(w, name):
    from ui.taskmanager import PAGES
    w.nav.setCurrentRow(PAGES.index(name))


def test_app_history_sorts_by_time_not_text_and_searches(win):
    from PySide6.QtCore import Qt
    _page(win, "App history")
    t = win.hist_table
    assert _col(t, 0)[:3] == ["firefox", "kwin_wayland", "plasmashell"]      # 1h 10m > 30m > 10m
    t.sortByColumn(1, Qt.AscendingOrder)
    assert _col(t, 0)[:2] == ["dolphin", "konsole"]                          # 3.9 s < 12.3 s, though "3" > "1"
    win.hist_search.setText("STEAM")
    assert _col(t, 0) == ["steam"] and "1 shown of 8 apps" in win.hist_status.text()


def test_users_use_the_processes_page_numbers(win):
    from ui.taskmanager import USAGE_ROLE
    _page(win, "Users")
    t = win.user_table
    assert _col(t, 0) == ["alex", "ollama", "root"]                          # most memory first: 5.1 GB, 2.2 GB, 410 MB
    row = _col(t, 0).index("alex")
    assert t.item(row, 4).text() == f"{31.0 / win.model.ncpu:.1f} %"        # a share of the whole PC, like Processes
    assert t.item(row, 5).data(USAGE_ROLE) > 0 and t.item(_col(t, 0).index("root"), 1).text() == "No (system)"


def test_startup_words_and_buttons_follow_the_selection(win, monkeypatch):
    from core import sysinfo
    _page(win, "Startup apps")
    t = win.start_table
    assert _col(t, 0) == ["File Indexer", "KDE Connect", "SAINT", "Steam"]
    assert _col(t, 2)[1] == "Everyone (changed for you)" and _col(t, 1)[1] == "Off"
    assert not win.start_on.isEnabled() and not win.start_off.isEnabled()  # nothing selected yet
    t.selectRow(1)
    assert win.start_on.isEnabled() and not win.start_off.isEnabled()
    changed = []
    monkeypatch.setattr(sysinfo, "set_autostart", lambda e, on: changed.append((e["file"], on)) or "done")
    win._toggle_startup(True)
    assert changed == [("org.kde.kdeconnect.daemon.desktop", True)]
    assert win.start_table.key(win.start_table.currentRow()) == "org.kde.kdeconnect.daemon.desktop"   # still selected


def test_services_in_plain_words_act_on_the_real_unit(win, monkeypatch):
    import subprocess
    _page(win, "Services")
    t = win.svc_table
    names = _col(t, 0)
    assert "bluetooth" in names and not any(n.endswith(".service") for n in names)
    status = dict(zip(names, _col(t, 2)))
    assert status["tlp"] == "Failed" and status["cups"] == "Stopped" and status["systemd-tmpfiles-setup"] == "Done"
    assert dict(zip(names, _col(t, 3)))["systemd-tmpfiles-setup"] == "When needed"
    win.svc_show.setCurrentText("Running")
    assert set(_col(t, 2)) == {"Running"} and t.rowCount() == 4
    win.svc_show.setCurrentText("All")
    t.selectRow(_col(t, 0).index("bluetooth"))
    b = win.svc_buttons
    assert b["stop"].isEnabled() and not b["start"].isEnabled() and not b["enable"].isEnabled()
    ran = []
    monkeypatch.setattr(subprocess, "run", lambda argv, **k: ran.append(argv) or subprocess.CompletedProcess(argv, 0))
    win._service_action("restart")
    assert ran == [["pkexec", "systemctl", "restart", "bluetooth.service"]]
    win.svc_scope.setCurrentIndex(1)                                          # "My services": none
    assert t.rowCount() == 0 and t.empty_text


def test_system_information_has_sections_and_copies_as_text(win):
    from ui.taskmanager import GROUP_ROLE
    _page(win, "System information")
    t = win.sys_table
    sections = [t.item(r, 0).text() for r in range(t.rowCount()) if t.item(r, 0).data(GROUP_ROLE)]
    assert sections == ["This PC", "Running", "Hardware", "Health"]
    text = win._system_text()
    assert "Operating system: HalOS 2.2" in text and "Failed services: tlp.service" in text


def test_every_page_screenshots(tmp_path, monkeypatch):
    files = shots.shoot(tmp_path, monkeypatch.setattr)
    assert len(files) == 7 and all(f.stat().st_size > 10_000 for f in files)
