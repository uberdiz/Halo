"""System Overview: history store, failed units, NVIDIA stat rows, snapshot tool, "can I run a 14B model"."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core import agent_catalog, device_profile as dp, sys_history, sysinfo
from modules.agent import taskmgr_intents as ti
from tests.test_gpu_intel import fake_run


def test_history_downsamples_and_leaves_gaps(tmp_path):
    h = sys_history.History(tmp_path / "h.sqlite")
    t0 = 1_000_000_000 // 600 * 600
    for i in range(13):                                 # 10 s samples across two minutes
        h.add({"cpu": 10.0 + i, "mem": 50.0}, now=t0 + i * 10)
    now = t0 + 130
    s = h.series("5m", "cpu", now=now)
    assert len(s) == 30 and s[-13] == 10.0 and s[0] is None      # before SAINT ran: a gap, not 0
    minute = h.series("24h", "cpu", now=now)
    assert minute[-2:] == [12.5, 18.5]                            # 1-minute means of the 10 s samples
    assert h.series("1h", "gpu", now=now)[-1] is None             # no GPU reading: unknown
    h.close()


def test_history_prunes_old_points(tmp_path):
    h = sys_history.History(tmp_path / "h.sqlite")
    h.add({"cpu": 1.0}, now=0)
    h.add({"cpu": 2.0}, now=20)
    h.add({"cpu": 3.0}, now=4000)                       # an hour later: the 10 s points of t=0 are dropped
    assert h._db.execute("SELECT COUNT(*) FROM points WHERE res=10 AND t<400").fetchone()[0] == 0
    h.close()


def test_failed_units_parses_both_scopes():
    out = "ollama.service loaded failed failed Ollama\n"
    units = sysinfo.failed_units(run=lambda argv, timeout=4: out)
    assert units[0] == {"name": "ollama.service", "user": False, "description": "Ollama"} and units[1]["user"]
    assert sysinfo.failed_units(run=lambda argv, timeout=4: "") == []


def test_nvidia_stats_show_na_and_processes():
    from ui import taskmanager as tm
    stats = dict(tm._nvidia_stats(sysinfo.nvidia_detail(run=fake_run), sysinfo.gpu_processes(run=fake_run), 0))
    assert stats["Decoder"] == "N/A" and stats["Power"] == "115 W / 200 W" and stats["CUDA"] == "12.6"
    assert stats["PCIe"] == "Gen 4 x16" and "ollama" in stats["Using the GPU"]
    assert tm._nvidia_stats([], [], 0) == []


def test_task_manager_ranges_render(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ui import taskmanager as tm
    h = sys_history.History(tmp_path / "h.sqlite")
    w = tm.TaskManager()
    w._history = h
    w._refresh_performance()
    assert len(w.d_cores.values) == os.cpu_count()
    w.d_range.setCurrentIndex(tm.RANGES.index("24h"))
    assert w.d_graph.span == 1440 and "no history yet" in w.d_axis.text()
    w.d_range.setCurrentIndex(tm.RANGES.index("Live"))
    assert w.d_graph.values is w.devices["cpu"]["values"]
    w.close()
    h.close()


HW = dp.Hardware(gpu_name="RTX 5060 Ti", vram_gb=16, ram_gb=32, cpu_threads=16, disk_free_gb=500)


def test_can_run_14b_by_catalog_rules():
    r = agent_catalog.can_run("can my computer run a 14b model", hw=HW)
    assert r["id"] == "qwen2.5:14b" and r["status"] != "too_heavy" and "RTX 5060 Ti" in r["reason"]
    small = dp.Hardware(ram_gb=8, cpu_threads=4, disk_free_gb=500)
    assert agent_catalog.can_run("32B", hw=small)["status"] == "too_heavy"
    assert agent_catalog.can_run("what's the weather", hw=HW) is None


def test_can_run_intent_routes_to_tool():
    for phrase in ("can my computer run a 14B model", "could I run qwen2.5:14b", "can this pc run a 7b llm"):
        it = ti.parse_taskmgr(phrase)
        assert it is not None and it.name == "system.can_run_model", phrase
    assert ti.parse_taskmgr("can you open spotify") is None


def test_snapshot_tool_is_registered_low_and_exposed():
    from modules.automation.tools import PermissionLevel
    from modules.desktop.taskmgr import register_taskmgr_tools

    class Reg:
        tools = {}

        def register(self, t):
            self.tools[t.name] = t
    reg = Reg()
    register_taskmgr_tools(reg)
    for name in ("system.snapshot", "system.can_run_model"):
        assert reg.tools[name].llm_exposed and reg.tools[name].permission == PermissionLevel.LOW
