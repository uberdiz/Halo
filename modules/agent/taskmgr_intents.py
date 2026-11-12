"""
modules/agent/taskmgr_intents.py

Task Manager by voice (modules/desktop/taskmgr.py). Everything is answered
from the process list — Task Manager itself is only opened when asked for
("open task manager"), so a game or editor in front stays in front.
"""

import re
from typing import Optional

from modules.agent.router import Intent, Reply, _clean, run_tool

_PC = r"(?:(?:my|the|this)\s+)?(?:pc|computer|laptop|machine|system)"


def _mb(mb: float) -> str:
    return f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{int(mb)} MB"


def _processes_reply(r) -> str:
    ps = r["processes"]
    if not ps:
        return "Nothing much is running."
    if r["sort"] == "memory_mb":
        items = [f"{p['name']} ({_mb(p['memory_mb'])})" for p in ps[:5]]
        return "Using the most memory: " + ", ".join(items) + "."
    busy = [p for p in ps if p["cpu"] >= 1]
    if not busy:
        items = [f"{p['name']} ({_mb(p['memory_mb'])})" for p in sorted(ps, key=lambda x: -x["memory_mb"])[:5]]
        return "Nothing is working the CPU hard right now. The biggest programs are " + ", ".join(items) + "."
    return "Using the most CPU: " + ", ".join(f"{p['name']} ({p['cpu']:.0f}%)" for p in busy[:5]) + "."


def _health_reply(r) -> str:
    parts = [f"CPU {r['cpu_percent']}%", f"memory {r['memory_percent']}% ({r['memory_used_gb']} of "
                                         f"{r['memory_total_gb']} GB)"]
    g = r.get("gpu")
    if g:
        parts.append(f"GPU {g['percent']}% at {g['temp_c']}°C")
    text = "Your PC: " + ", ".join(parts) + "."
    if r.get("battery"):
        b = r["battery"]
        text += f" Battery {b['percent']}%{' and charging' if b['plugged'] else ''}."
    if r["warnings"]:
        text += " Heads up: " + "; ".join(r["warnings"]) + "."
    else:
        low = min(r["disks"], key=lambda d: d["free_gb"], default=None)
        text += " Everything looks healthy" + (f"; the fullest drive is {low['drive']} with {low['free_gb']} GB free"
                                               if low else "") + "."
    top = [x for x in r["top_cpu"] if x["cpu"] >= 5]
    if top:
        text += f" {top[0]['name']} is the busiest program ({top[0]['cpu']:.0f}% CPU)."
    if r["uptime_h"] >= 72:
        text += f" It's been on for {r['uptime_h'] / 24:.0f} days — a restart might help."
    return text


def _gpu_reply(r, focus: str = "") -> str:
    gs = r["gpus"]
    if not gs:
        return "I can't see an NVIDIA GPU (nvidia-smi isn't answering), so I have no GPU details to give."
    procs = r["processes"]
    g = gs[0]
    used, total = g.get("memory.used"), g.get("memory.total")
    vram = f"{_mb(used)} of {_mb(total)} VRAM in use" if used is not None and total else "VRAM use not available"
    if focus == "ollama":
        hit = [p for p in procs if "ollama" in p["name"].lower()]
        return (f"Yes — Ollama holds {_mb(hit[0]['memory_mb'])} on the {g['name']}, so models run on CUDA."
                if hit and hit[0]["memory_mb"] else
                f"No — Ollama isn't holding any memory on the {g['name']} right now, so a loaded model would be on "
                "the CPU (or no model is loaded).")
    text = f"{g['name']}: {g['utilization.gpu']:.0f}% busy, {vram}" if g.get("utilization.gpu") is not None \
        else f"{g['name']}: {vram}"
    if g.get("temperature.gpu") is not None:
        text += f", {g['temperature.gpu']:.0f}°C"
    if g.get("power.draw") is not None:
        text += f", drawing {g['power.draw']:.0f} W" + (f" of {g['power.limit']:.0f} W" if g.get("power.limit") else "")
    text += "."
    if g.get("thermal_throttle"):
        text += " It is thermal throttling right now."
    elif focus == "throttle" and g.get("thermal_throttle") is False:
        text += " It isn't thermal throttling."
    if procs:
        text += " Using it: " + ", ".join(f"{p['name']} ({_mb(p['memory_mb'])})" if p["memory_mb"] else p["name"]
                                          for p in procs[:5]) + "."
    elif focus != "throttle":
        text += " No process is holding GPU memory."
    return text


def parse_taskmgr(text: str) -> Optional[Intent]:
    t = _clean(text).lower().strip(" .!?")
    if not t:
        return None

    # ---- can this PC run a model (catalog rules, no LLM) ---------------------------------------
    m = re.search(rf"^(?:can|could|will|would)\s+(?:i|{_PC})\s+(?:run|handle|use)\s+(?:an?\s+|the\s+)?"
                  r"(?P<m>.*?\d+(?:\.\d+)?\s*b\b.*?|(?:llama|qwen)\S*)(?:\s+(?:model|llm|locally))*$", t)
    if m:
        model = m.group("m")
        return Intent("system.can_run_model", lambda: run_tool(
            "system.can_run_model", "check the model against your hardware",
            lambda r: (f"Yes — {r['name']} " if r["status"] != "too_heavy" else f"Not well — {r['name']} ") +
            (f"(the nearest size I know to {r['asked_b']:g}B) " if r["asked_b"] and r["params_b"]
             and abs(r["params_b"] - r["asked_b"]) > 1 else "") + f"is “{r['label']}”. {r['reason']}",
            model=model), "system")

    # ---- GPU (NVML via nvidia-smi) -----------------------------------------------------------
    if re.search(r"\b(gpu|vram|graphics card|cuda)\b", t) and re.search(
            r"\b(what|which|who|why|is|how|show|check)\b", t) and not re.search(
            r"\b(kill|end|stop|close|install|download|update|buy|driver|drivers|setting|settings)\b", t):
        focus = "ollama" if re.search(r"\bollama\b|\bmodel\b.*\b(cpu|cuda|gpu)\b", t) else \
            "throttle" if re.search(r"throttl", t) else ""
        return Intent("system.gpu", lambda: run_tool("system.gpu", "check your GPU",
                                                     lambda r: _gpu_reply(r, focus)), "system")

    # ---- end task -------------------------------------------------------------------------
    m = re.match(r"^(?:end\s+(?:the\s+)?task(?:\s+(?:on|for))?|end\s+(?:the\s+)?process(?:es)?(?:\s+(?:of|for))?|"
                 r"kill\s+(?:the\s+)?process(?:es)?(?:\s+(?:of|for))?|force\s+(?:quit|close|kill|stop))\s+"
                 r"(?:the\s+|my\s+)?(?P<a>.+?)(?:\s+(?:app|process(?:es)?|program))?$|"
                 r"^(?:end|kill)\s+(?:the\s+|my\s+)?(?P<b>.+?)\s+(?:task|process(?:es)?)$", t)
    if m:
        name = (m.group("a") or m.group("b")).strip()
        if name and name not in ("it", "this", "that", "everything", "all"):
            return Intent("system.end_task", lambda: run_tool(
                "system.end_task", f"end {name} (like Task Manager's End task)",
                lambda r: f"Ended {r['name']}" + (f" ({r['ended']} processes)." if r["ended"] > 1 else ".")
                + (f" {r['denied']} of them needed admin rights and are still running." if r["denied"] else ""),
                name=name), "system")

    # ---- what's running -----------------------------------------------------------------------
    if re.match(r"^(?:what(?:'?s| is| are)|which)\s+(?:programs?\s+|apps?\s+|processes\s+|stuff\s+)?"
                r"(?:(?:is|are)\s+)?(?:running|open in the background|using\s+(?:the\s+most\s+|all\s+(?:my\s+|the\s+)?"
                r"|up\s+(?:my\s+|all\s+my\s+)?|my\s+)?(?:cpu|processor|memory|ram|resources))", t) or \
            re.match(r"^(?:show|list|tell)\s+(?:me\s+)?(?:what(?:'?s| is)\s+running|(?:the\s+|my\s+)?(?:running\s+)?"
                     r"(?:processes|programs|tasks))(?:\s+(?:running|open))?$", t) or \
            re.match(rf"^(?:why is|what(?:'?s| is))\s+{_PC}\s+(?:so\s+)?(?:slow|laggy|lagging)|"
                     rf"^what(?:'?s| is)\s+slowing\s+(?:down\s+)?{_PC}", t):
        sort = "memory" if re.search(r"\b(memory|ram)\b", t) else "cpu"
        return Intent("system.processes", lambda: run_tool(
            "system.processes", "see what's running", _processes_reply, sort=sort, limit=8), "system")

    # ---- device health ------------------------------------------------------------------------
    if re.match(rf"^(?:(?:check|show|give me|run)\s+(?:(?:on|me)\s+)?)?(?:the\s+|my\s+)?(?:device|pc|computer|system)\s+"
                rf"(?:health|status|performance|stats)(?:\s+(?:check|report))?$|"
                rf"^how(?:'?s| is| are)\s+{_PC}\s+(?:doing|holding up|running|performing)$|"
                rf"^(?:how much|what(?:'?s| is))\s+(?:(?:my|the)\s+)?(?:cpu|gpu|ram|memory)(?:\s+(?:usage|use|load|"
                rf"temp(?:erature)?))?(?:\s+(?:at|am i using|is being used|right now))*$|"
                rf"^(?:check|run a)\s+(?:health\s+)?(?:check(?:\s*up)?|diagnostics?)\s+(?:on\s+)?{_PC}$", t):
        return Intent("system.health", lambda: run_tool("system.health", "check your PC", _health_reply), "system")

    # ---- startup apps -------------------------------------------------------------------------
    if re.match(r"^(?:what|which)\s+(?:apps|programs)\s+(?:start|open|run|launch)\s+(?:with|when)\s+(?:windows|"
                r"(?:i|my pc|the pc|my computer)\s+(?:start|boot|turn)s?(?:\s+on|\s+up)?)|"
                r"^(?:show|list)\s+(?:me\s+)?(?:my\s+)?startup\s+(?:apps|programs)$", t):
        return Intent("system.startup_apps", lambda: run_tool(
            "system.startup_apps", "list startup apps",
            lambda r: ("These start with Windows: " + ", ".join(r["apps"][:12]) + ".") if r["apps"]
            else "Nothing extra starts with Windows."), "system")
    return None
