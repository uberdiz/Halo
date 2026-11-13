"""Task Manager processes page: grouping (Apps / Background / SAINT / System), sorting inside groups, folding a
group, usage bars, and "End process tree" (children first)."""
import os

import pytest

from core import sysinfo


def _p(pid, name, user="me", cpu=0.0, mem=0, cmd="", ppid=1, app=False):
    return {"pid": pid, "name": name, "user": user, "status": "running", "cpu": cpu, "memory": mem, "threads": 1,
            "ppid": ppid, "started": 0, "command": cmd, "disk_read": None, "disk_write": None,
            "critical": name in sysinfo.CRITICAL, "app": app}


PROCS = [_p(10, "firefox", cpu=12.0, mem=900, app=True), _p(11, "kwin_wayland", cpu=3.0),
         _p(12, "sshd", user="root", cpu=50.0), _p(13, "baloo_file", cpu=1.0, mem=50),
         _p(14, "python", cmd="python /opt/saint/app/app.py", cpu=2.0), _p(15, "saint-taskmgr"),
         _p(16, "konsole", cpu=0.5, mem=5000, app=True)]


def test_app_scope_from_cgroup():
    assert sysinfo.is_app_scope("0::/user.slice/user-1000.slice/user@1000.service/app.slice/"
                                "app-org.kde.konsole-1234.scope")
    assert sysinfo.is_app_scope("0::/user.slice/.../app.slice/app-firefox@0a1b.service")
    assert not sysinfo.is_app_scope("0::/user.slice/.../app.slice/app-baloo_file@autostart.service")
    assert not sysinfo.is_app_scope("0::/user.slice/.../session.slice/plasma-plasmashell.service")
    assert not sysinfo.is_app_scope("")


def test_groups_in_order_and_sorted_inside():
    groups = sysinfo.group_processes(PROCS, me="me", sort="cpu")
    assert [g for g, _ in groups] == ["Apps", "Background", "SAINT", "System"]
    by = {g: [p["pid"] for p in ps] for g, ps in groups}
    assert by == {"Apps": [10, 16], "Background": [13], "SAINT": [14, 15], "System": [12, 11]}
    by_mem = dict(sysinfo.group_processes(PROCS, me="me", sort="memory"))
    assert [p["pid"] for p in by_mem["Apps"]] == [16, 10]
    assert [g for g, _ in sysinfo.group_processes([PROCS[3]], me="me")] == ["Background"]   # empty groups left out


def test_descendants_and_end_tree_children_first():
    procs = [_p(1, "systemd", ppid=0), _p(20, "steam"), _p(21, "steamwebhelper", ppid=20),
             _p(22, "gpu-helper", ppid=21), _p(30, "other")]
    assert [p["pid"] for p in sysinfo.descendants(procs, 20)] == [21, 22]

    order = []

    class FakeProc:
        def __init__(self, pid):
            self.pid = pid

        def name(self):
            return "steam"

        def children(self, recursive=False):
            return [FakeProc(21), FakeProc(22)]

        def terminate(self):
            order.append(self.pid)

        kill = terminate

    class FakePsutil:
        NoSuchProcess = type("NoSuchProcess", (Exception,), {})
        AccessDenied = type("AccessDenied", (Exception,), {})
        Process = FakeProc

        @staticmethod
        def wait_procs(procs, timeout):
            return procs, []

    msg = sysinfo.end_process_tree(20, psutil_mod=FakePsutil)
    assert order == [22, 21, 20] and "2 processes it started" in msg


@pytest.fixture
def window(monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ui import taskmanager
    monkeypatch.setattr(taskmanager.TaskManager, "showEvent", lambda self, e: None)
    w = taskmanager.TaskManager()
    monkeypatch.setattr(w, "_me", lambda: "me")
    w.procs = list(PROCS)
    w._refresh_processes()
    yield w
    w.close()


def test_page_groups_folds_and_sorts(window):
    from PySide6.QtCore import Qt
    from ui.taskmanager import GROUP_ROLE, USAGE_ROLE
    m = window.model
    groups = [m.data(m.index(r, 0), GROUP_ROLE) for r in range(m.rowCount()) if m.process(r) is None]
    assert groups == ["Apps", "Background", "SAINT", "System"]
    assert "System" in m.collapsed and m.row_of(12) == -1          # the system's processes start folded away
    m.toggle("System")
    assert m.row_of(12) > m.row_of(10)
    m.sort(5, Qt.DescendingOrder)                                     # Memory, biggest first, inside each group
    assert m.row_of(16) < m.row_of(10)
    assert m.data(m.index(m.row_of(10), 4), USAGE_ROLE) == pytest.approx(min(1.0, 12.0 / m.ncpu / 100))
    assert "Apps" in m.data(m.index(0, 0)) and "(2)" in m.data(m.index(0, 0))


def test_selection_survives_refresh_and_group_rows_select_nothing(window):
    window.table.selectRow(window.model.row_of(13))
    window._refresh_processes()
    assert window._selected_pid() == 13
    window.table.selectRow(0)                                          # the "Apps" header
    assert window._selected_pid() is None
