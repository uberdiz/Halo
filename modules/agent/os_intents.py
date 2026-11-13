"""
modules/agent/os_intents.py

Plain phrases -> OS actions (core/actions), with no model call: "run the command df -h", "dark mode",
"make the text bigger", "turn bluetooth off", "undo that". Everything goes through the action registry, so
trust levels, the preview-and-confirm for risky commands, the log and undo all apply.

Only phrases whose action exists on this system are claimed (most are HalOS-only), and this parser runs after
SAINT's older ones, so nothing that already worked changes. Anything less literal than these phrases is left
to the model, which reaches the same actions through the os.find_action / os.run_action tools.
"""

import re
from typing import Callable, Dict, List, Optional, Tuple

from modules.agent.router import Intent, Reply, _clean

_ON = r"(?P<on>on|off|enable|disable)"
_PROFILE = {"performance": "performance", "high performance": "performance", "balanced": "balanced",
            "power saver": "power-saver", "power saving": "power-saver", "battery saver": "power-saver",
            "low power": "power-saver"}


def _is_on(word: str) -> bool:
    return word in ("on", "enable")


def _run(action: str, params: Dict) -> Reply:
    """Run through SAINT's bridge: a risky action becomes SAINT's normal spoken "…OK?" question."""
    from core.actions import saint
    from modules.automation.tools import ToolError
    try:
        out = saint.run(action, params)
    except ToolError as e:
        return Reply(str(e), ok=False)
    if out.get("needs_confirmation"):
        return Reply(out["message"], ok=True, expects_reply=True)
    return Reply(out.get("message") or "Done.")


def _undo() -> Reply:
    from core.actions import saint
    from modules.automation.tools import ToolError
    try:
        return Reply(saint.undo().get("message") or "Undone.")
    except ToolError as e:
        return Reply(str(e), ok=False)


# (pattern, action id, match -> params). Lower-cased, "saint," and trailing punctuation already stripped.
_PHRASES: List[Tuple[re.Pattern, str, Callable]] = [(re.compile(rx), action, params) for rx, action, params in [
    (r"^(?:switch to |turn on |enable |use |go )?(?:the )?(?P<mode>dark|light) (?:mode|theme)(?: on| please)?$",
     "settings.appearance.theme", lambda m: {"mode": m["mode"]}),
    (r"^make (?:the |my )?(?:text|font|writing|letters) (?P<way>bigger|larger|smaller)$",
     "settings.appearance.text_size", lambda m: {"step": 1 if m["way"] != "smaller" else -1}),
    (r"^(?:turn |switch )?(?:the )?night (?:light|mode|colou?r) " + _ON + r"$|^(?:turn |switch )" + _ON.replace("on>", "on2>")
     + r" (?:the )?night (?:light|mode|colou?r)$",
     "settings.display.night_light", lambda m: {"on": _is_on(m["on"] or m["on2"])}),
    (r"^(?:turn |switch )?(?:the )?(?:do not disturb|dnd|focus mode) " + _ON + r"$|^(?:turn |switch )"
     + _ON.replace("on>", "on2>") + r" (?:the )?(?:do not disturb|dnd|focus mode)$",
     "settings.notifications.dnd", lambda m: {"on": _is_on(m["on"] or m["on2"])}),
    (r"^(?:turn |switch )?(?:the )?wi-?fi " + _ON + r"$|^(?:turn |switch )" + _ON.replace("on>", "on2>")
     + r" (?:the )?wi-?fi$",
     "network.wifi.power", lambda m: {"on": _is_on(m["on"] or m["on2"])}),
    (r"^(?:turn |switch )?(?:the )?bluetooth " + _ON + r"$|^(?:turn |switch )" + _ON.replace("on>", "on2>")
     + r" (?:the )?bluetooth$",
     "network.bluetooth.power", lambda m: {"on": _is_on(m["on"] or m["on2"])}),
    (r"^(?:set|change) (?:the )?(?:display |screen )?scal(?:e|ing) to (?P<pct>\d{2,3}) ?(?:%|percent)$",
     "settings.display.scale", lambda m: {"scale": int(m["pct"]) / 100}),
    (r"^(?:set|change|switch) (?:the )?power (?:mode|profile|plan) to (?P<p>" + "|".join(_PROFILE) + r")$|"
     r"^(?P<p2>" + "|".join(_PROFILE) + r") (?:power )?mode$",
     "settings.power.profile", lambda m: {"profile": _PROFILE[m["p"] or m["p2"]]}),
    (r"^(?:set|change) (?:the |my )?time ?zone to (?P<zone>[a-z_]+/[a-z_/+-]+)$",
     "settings.system.timezone", lambda m: {"zone": "/".join(p.title() if len(p) > 3 else p.upper()
                                                             for p in m["zone"].replace(" ", "_").split("/"))}),
    (r"^(?:fix|repair|troubleshoot) (?:the |my )?(?:sound|audio|speakers|microphone|mic)$|"
     r"^(?:i have |there(?:'s| is) )?no (?:sound|audio)(?: (?:at all|anymore))?$|"
     r"^(?:the |my )?(?:sound|audio) (?:isn't|is not|doesn't|does not|stopped|won't) (?:work(?:ing)?|play(?:ing)?)$",
     "audio.repair", lambda m: {}),
    (r"^(?:re)?(?:start|boot)(?: the pc| my pc| the computer)? (?:from|off|into) (?:the |my |a )?"
     r"(?P<dev>usb|network|pxe)(?: stick| drive| key| device)?$",
     "recovery.boot_device", lambda m: {"device": "network" if m["dev"] == "pxe" else m["dev"]}),
    (r"^(?:re)?(?:start|boot)(?: the pc| my pc| the computer)? (?:into|to) (?:the )?(?:bios|uefi|firmware)"
     r"(?: settings| setup)?$|^open (?:the )?(?:bios|uefi|firmware)(?: settings| setup)?$",
     "recovery.firmware_settings", lambda m: {}),
    (r"^(?:check for|are there|is there an?|any) (?:saint |halos )?updates?(?: for saint)?$|"
     r"^is (?:there )?a (?:new|newer) (?:version of )?saint(?: out)?$",
     "system.check_updates", lambda m: {}),
    (r"^update (?:saint|yourself)(?: now)?$|^install the (?:saint )?update$",
     "system.update_saint", lambda m: {}),
]]

_COMMAND = re.compile(r"^(?:run|execute)\s+(?:the\s+|this\s+)?(?:(?:linux|shell|terminal|bash)\s+)?command[:\s]\s*"
                      r"[`\"'“]?(?P<a>.+?)[`\"'”]?$|"
                      r"^(?:run|execute)\s+[`\"“](?P<b>.+?)[`\"”](?:\s+in\s+(?:the\s+|a\s+)?(?:terminal|shell|console))?$|"
                      r"^(?:run|execute)\s+(?P<c>.+?)\s+in\s+(?:the\s+|a\s+)?(?:terminal|shell|console)$", re.I)
_DOWNLOADS = re.compile(r"^(?:what(?:'s| is| are)|is (?:anything|something)|are (?:any )?(?:things|apps|games))\s+"
                        r"(?:currently |still |being )?(?:downloading|updating|installing)(?: (?:right )?now| right| on (?:my|this) "
                        r"(?:pc|computer))?$|^(?:show|list) (?:my |the )?downloads$")
_AGENT = re.compile(r"^(?:ask claude(?: code)? to|have claude(?: code)?|have the agent|tell the agent to|agent[:,])\s+(?P<task>.{4,})$",
                    re.I)
_TILE = re.compile(r"^(?:tile|split|arrange)\s+(?:all\s+|my\s+|the\s+)*(?:open\s+)?windows(?:\s+on\s+(?:this|the)\s+screen)?$|"
                   r"^split\s+(?:the|my)\s+screen$")
_BG_LOOK = re.compile(r"^(?:show me|let me see) (?:the )?(?:background desktop|what you(?:'re| are) doing in the background)$")
_UNDO = re.compile(r"^undo (?:that|it|this|the last (?:thing|change|action|one)|what you (?:just )?did)$")


def _available(action_id: str) -> bool:
    from core import actions
    actions.load_builtin()
    a = actions.registry.get(action_id)
    return a is not None and a.available()


def parse_os(text: str) -> Optional[Intent]:
    raw = _clean(text).strip().rstrip(".!?")           # a command keeps its own capitals
    t = raw.lower()
    if not t:
        return None
    m = _COMMAND.match(raw)
    if m and _available("shell.run"):
        command = (m["a"] or m["b"] or m["c"]).strip()
        return Intent("os.shell.run", lambda: _run("shell.run", {"command": command}), "system")
    m = _AGENT.match(raw)
    if m:
        task = m["task"].strip()

        def hand_over():
            from core import claude_agent
            run = claude_agent.start(task)
            if run.status == "failed":
                return Reply(run.error, ok=False)
            return Reply("On it. Claude Code is working on that in the background; the steps show at the top right "
                         "and on the Agent page.")
        return Intent("os.agent", hand_over, "system")
    if _TILE.match(t) and _available("windows.tile"):
        return Intent("os.windows.tile", lambda: _run("windows.tile", {}), "system")
    if _BG_LOOK.match(t):
        def show():
            import subprocess
            import sys
            subprocess.Popen([sys.executable, "-m", "ui.background_view"])
            return Reply("Here's SAINT's background desktop. Your own windows aren't touched.")
        return Intent("os.background.show", show, "system")
    if _DOWNLOADS.match(t):
        def answer():
            from core import downloads
            return Reply(downloads.summary())
        return Intent("os.downloads", answer, "system")
    if _UNDO.match(t):
        return Intent("os.undo", _undo, "system")
    for pattern, action, params in _PHRASES:
        m = pattern.match(t)
        if m and _available(action):
            p = params(m)
            return Intent(f"os.{action}", lambda a=action, p=p: _run(a, p), "system")
    return None
