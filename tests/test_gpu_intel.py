"""NVIDIA detail parsing (core/sysinfo) and the deterministic GPU answers (taskmgr_intents)."""
from core import sysinfo
from modules.agent import taskmgr_intents as ti

ROW = ("0, NVIDIA GeForce RTX 4070, GPU-abc, 560.35, 4, 16, 37, 20, 0, [N/A], 12282, 9000, 64, 115.2, 200.00, "
       "2475, 10501, 41, 0x0000000000000040")
SMI = "| NVIDIA-SMI 560.35   Driver Version: 560.35   CUDA Version: 12.6 |"
APPS = "4242, GPU-abc, 7800, /usr/bin/ollama\n99, GPU-abc, 300, /usr/bin/kwin_wayland\n"


def fake_run(argv, timeout=4):
    q = argv[1] if len(argv) > 1 else ""
    return ROW if q.startswith("--query-gpu") else APPS if q.startswith("--query-compute") else SMI


def snapshot():
    return {"gpus": sysinfo.nvidia_detail(run=fake_run), "processes": sysinfo.gpu_processes(run=fake_run)}


def test_detail_parses_real_and_missing_fields():
    g = sysinfo.nvidia_detail(run=fake_run)[0]
    assert g["name"] == "NVIDIA GeForce RTX 4070" and g["memory.used"] == 9000 and g["power.limit"] == 200
    assert g["utilization.decoder"] is None          # [N/A] stays unknown, never 0
    assert g["cuda"] == "12.6" and g["thermal_throttle"] is True


def test_no_nvidia_means_empty():
    assert sysinfo.nvidia_detail(run=lambda a, timeout=4: "") == []
    assert "can't see an NVIDIA GPU" in ti._gpu_reply({"gpus": [], "processes": []})


def test_processes_sorted_and_replies():
    r = snapshot()
    assert [p["name"] for p in r["processes"]] == ["ollama", "kwin_wayland"]
    assert "Using it: ollama (7.6 GB)" in ti._gpu_reply(r)
    assert ti._gpu_reply(r, "ollama").startswith("Yes")
    assert ti._gpu_reply({**r, "processes": r["processes"][1:]}, "ollama").startswith("No")


def test_phrases_route_to_gpu():
    for p in ["What's using my GPU?", "why is my VRAM almost full", "Is Ollama using my NVIDIA GPU?",
              "is my gpu thermal throttling", "how much GPU power am I using", "is my model running on CPU or CUDA"]:
        i = ti.parse_taskmgr(p)
        assert i and i.name == "system.gpu", p
    assert ti.parse_taskmgr("how do I install cuda") is None or ti.parse_taskmgr("how do I install cuda").name != "system.gpu"
