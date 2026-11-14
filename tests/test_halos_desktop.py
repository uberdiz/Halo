"""HalOS desktop behaviour: overlay screen edge, virtual desktops, window animations, startup apps, widgets category.
Pure logic with commands faked; the KWin and Plasma JavaScript runs under node with KWin's API stubbed. What only
KWin can show (real edges, real animation chaining) is on the VM list in the branch report."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from core import evolve, kde_desktop as kde, saint_dbus, startup_apps as sa, window_anim as wa

ROOT = Path(__file__).resolve().parents[1]
FS = ROOT / "packaging/linux/rootfs"
SHELL_JS = FS / "usr/share/kwin/scripts/saint-shell/contents/code/main.js"
STAR_JS = FS / "usr/share/kwin/effects/saint-star/contents/code/main.js"
DESKTOP_JS = FS / "usr/share/plasma/shells/org.kde.plasma.desktop/contents/updates/saintos-desktop-1.js"
PKGBUILD = ROOT / "packaging/arch/pkgbuilds/saint/PKGBUILD"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node isn't installed")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


class Recorder:
    def __init__(self, answers=None):
        self.calls, self.answers = [], answers or {}

    def __call__(self, argv):
        self.calls.append(argv)
        for key, value in self.answers.items():
            if key in " ".join(argv):
                return value
        return True, ""

    def joined(self):
        return [" ".join(c) for c in self.calls]


def _run_js(harness: str, target: Path) -> dict:
    """Run target under node inside harness, which defines the stubs and prints a JSON result."""
    code = harness.replace("__SOURCE__", json.dumps(target.read_text(encoding="utf-8")))
    res = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


# --------------------------------------------------------------------------- KConfig reading
def test_parse_kconfig_groups_escapes_and_flags():
    text = '[General]\nA=1\nB[$e]=$HOME\nName[de]=skip\n\n[ActionPlugins][0]\nwheel:Vertical;NoModifier=x\n[E]\nJ={"a":"b\\\\c"}\n'
    cfg = kde.parse_kconfig(text)
    assert cfg["General"] == {"A": "1", "B": "$HOME"}
    assert cfg["ActionPlugins/0"]["wheel:Vertical;NoModifier"] == "x"
    assert cfg["E"]["J"] == '{"a":"b\\c"}'


def test_user_config_wins_over_etc_xdg(tmp_path):
    user, xdg = tmp_path / "u", tmp_path / "x"
    user.mkdir(), xdg.mkdir()
    (xdg / "kwinrc").write_text("[Desktops]\nNumber=4\nRows=1\n", encoding="utf-8")
    (user / "kwinrc").write_text("[Desktops]\nNumber=2\n", encoding="utf-8")
    assert kde.read_value("kwinrc", "Desktops", "Number", dirs=[str(user), str(xdg)]) == "2"
    assert kde.read_value("kwinrc", "Desktops", "Rows", dirs=[str(user), str(xdg)]) == "1"


# --------------------------------------------------------------------------- 1. overlay edge
def test_overlay_edge_defaults_off_on_a_fresh_install(tmp_path):
    assert kde.overlay_edge(dirs=[str(tmp_path)]) == ("off", 0)


def test_overlay_edge_ignores_nonsense(tmp_path):
    (tmp_path / "kwinrc").write_text("[Script-saint-shell]\nOverlayEdge=sideways\nOverlayEdgeDelayMs=abc\n", encoding="utf-8")
    assert kde.overlay_edge(dirs=[str(tmp_path)]) == ("off", 0)


def test_set_overlay_edge_writes_kwinrc():
    run = Recorder()
    assert kde.set_overlay_edge("topleft", 99999, run)
    assert run.calls[0] == ["kwriteconfig6", "--file", "kwinrc", "--group", "Script-saint-shell", "--key",
                            "OverlayEdge", "topleft"]
    assert run.calls[1][-1] == str(kde.MAX_EDGE_DELAY_MS)
    with pytest.raises(ValueError):
        kde.set_overlay_edge("nowhere", 0, run)


def test_shell_reload_reparses_then_reloads_the_script():
    run = Recorder()
    slept = []
    kde.reload_shell_script(run, sleep=slept.append)
    calls = run.joined()
    assert "/KWin reconfigure" in calls[0] and slept == [0.4]
    assert "org.kde.kwin.Scripting.unloadScript saint-shell" in calls[1]
    assert calls[2].endswith("org.kde.kwin.Scripting.start")


SHELL_HARNESS = r"""
const vm = require('vm');
const edges = [], dbus = [], timers = [];
const config = %s;
let removed = null;
const ctx = {
  KWin: {ElectricTop:1, ElectricTopRight:2, ElectricRight:3, ElectricBottomRight:4, ElectricBottom:5,
         ElectricBottomLeft:6, ElectricLeft:7, ElectricTopLeft:8},
  workspace: {windowList: () => [], windowAdded: {connect() {}}, windowRemoved: {connect(f) { removed = f; }},
              currentDesktop: 'here', cursorPos: %s, screenAt: () => ({geometry: {x: 0, y: 0, width: 1920, height: 1080}})},
  readConfig: (k, d) => (k in config ? config[k] : d),
  registerScreenEdge: (e, f) => edges.push([e, f]),
  callDBus: (...a) => dbus.push(a),
  QTimer: function () { this.timeout = {connect: f => { this.fire = f; }}; this.start = () => timers.push(this); },
  console
};
vm.runInNewContext(__SOURCE__, ctx);
edges.forEach(e => e[1]());
const waiting = timers.length;
timers.forEach(t => t.fire());
const closes = [{normalWindow: true, frameGeometry: {x: 100, y: 200, width: 400, height: 300}, caption: 'x', onCurrentDesktop: true},
                {normalWindow: false, frameGeometry: {x: 0, y: 0, width: 10, height: 10}, caption: 'menu', onCurrentDesktop: true},
                {normalWindow: true, frameGeometry: {x: 0, y: 0, width: 10, height: 10}, caption: 'b SAINT:place:1,1,1,1'},
                {normalWindow: true, frameGeometry: {x: 0, y: 0, width: 10, height: 10}, caption: 'elsewhere', desktops: ['there']},
                {normalWindow: true, frameGeometry: {x: 0, y: 0, width: 10, height: 10}, caption: 'video', fullScreen: true},
                {normalWindow: true, frameGeometry: {x: 0, y: 0, width: 10, height: 10}, caption: 'dragged tab', move: true}];
if (removed) closes.forEach(removed);
console.log(JSON.stringify({edges: edges.map(e => e[0]), dbus, waiting, listening: !!removed}));
"""


def _shell(config: dict, cursor=None) -> dict:
    cursor = cursor or {"x": 900, "y": 0}
    return _run_js(SHELL_HARNESS % (json.dumps(config), json.dumps(cursor)), SHELL_JS)


@needs_node
def test_shell_script_registers_no_edge_by_default():
    assert _shell({})["edges"] == []


@needs_node
@pytest.mark.parametrize("name, code", [("top", 1), ("topright", 2), ("right", 3), ("bottomright", 4), ("bottom", 5),
                                        ("bottomleft", 6), ("left", 7), ("topleft", 8)])
def test_shell_script_registers_each_edge(name, code):
    out = _shell({"OverlayEdge": name, "CloseBurst": "false"})
    assert out["edges"] == [code]
    assert [c[3] for c in out["dbus"]] == ["ToggleOverlay"]


@needs_node
def test_shell_hover_delay_needs_the_cursor_to_stay():
    stayed = _shell({"OverlayEdge": "top", "OverlayEdgeDelayMs": 500, "CloseBurst": "false"}, {"x": 900, "y": 2})
    assert stayed["waiting"] == 1 and [c[3] for c in stayed["dbus"]] == ["ToggleOverlay"]
    left = _shell({"OverlayEdge": "top", "OverlayEdgeDelayMs": 500, "CloseBurst": "false"}, {"x": 900, "y": 300})
    assert left["waiting"] == 1 and left["dbus"] == []


@needs_node
def test_shell_announces_only_real_window_closes():
    out = _shell({"CloseBurst": "true"})
    assert out["dbus"] == [["org.saintos.Saint", "/Saint", "org.saintos.Saint", "PlaySupernova", "300,350"]]
    assert not _shell({"CloseBurst": "false"})["listening"]
    assert not _shell({})["listening"]                     # the default close has no burst


def test_linux_edge_tab_follows_the_setting_not_the_windows_one(monkeypatch):
    from ui import halo
    monkeypatch.setattr(halo.sys, "platform", "linux")
    assert halo.edge_tab_enabled() is False
    monkeypatch.setattr(halo.sys, "platform", "win32")
    monkeypatch.setattr(halo.config, "get", lambda k, d=None: True)
    assert halo.edge_tab_enabled() is True
    monkeypatch.setattr(halo.config, "get", lambda k, d=None: False)
    assert halo.edge_tab_enabled() is False


# --------------------------------------------------------------------------- 2. desktops
def test_image_ships_the_shortcuts_core_knows():
    text = PKGBUILD.read_text(encoding="utf-8")
    for lines in kde.skel_shortcut_lines().values():
        for line in lines:
            assert line in text, line
    assert "Switch to Desktop 1=Meta+1\\tCtrl+F1,Ctrl+F1,Switch to Desktop 1" in text
    assert "activate task manager entry 1=none,Meta+1,Activate Task Manager Entry 1" in text


def test_image_ships_four_desktops_and_meta_wheel():
    text = PKGBUILD.read_text(encoding="utf-8")
    block = text[text.index('etc/xdg/kwinrc" <<'):]
    assert "[Desktops]\nNumber=4\nRows=1" in block
    assert f"[MouseBindings]\nCommandAllWheel={kde.WHEEL_ON}" in block


LITERAL = ('[Variant: [Argument: a(uss) {[Argument: (uss) 0, "aaa-1", "Desktop 1"], '
           '[Argument: (uss) 1, "bbb-2", "Desktop 2"], [Argument: (uss) 2, "ccc-3", "Work"]}]]')


def test_parse_desktops_reads_qdbus_literal():
    assert kde.parse_desktops(LITERAL) == [(0, "aaa-1", "Desktop 1"), (1, "bbb-2", "Desktop 2"), (2, "ccc-3", "Work")]


def test_set_desktop_count_adds_at_the_end():
    run = Recorder({"--literal": (True, LITERAL)})
    ok, _ = kde.set_desktop_count(5, run)
    made = [c for c in run.calls if "org.kde.KWin.VirtualDesktopManager.createDesktop" in c]
    assert ok and [c[-2:] for c in made] == [["3", "Desktop 4"], ["4", "Desktop 5"]]


def test_set_desktop_count_removes_from_the_end():
    run = Recorder({"--literal": (True, LITERAL)})
    assert kde.set_desktop_count(1, run)[0]
    assert [c[-1] for c in run.calls if "org.kde.KWin.VirtualDesktopManager.removeDesktop" in c] == ["ccc-3", "bbb-2"]


def test_set_desktop_count_says_when_kwin_is_away():
    ok, message = kde.set_desktop_count(3, Recorder({"--literal": (False, "no KWin")}))
    assert not ok and "KWin" in message


def test_wheel_toggles():
    run = Recorder()
    assert kde.set_meta_wheel(True, run)
    assert run.calls[0][-1] == "Previous/Next Desktop" and "/KWin reconfigure" in run.joined()[1]
    run = Recorder()
    assert kde.set_background_wheel(True, run)
    assert run.calls[0] == ["kwriteconfig6", "--file", kde.APPLETSRC, "--group", "ActionPlugins", "--group", "0",
                            "--key", "wheel:Vertical;NoModifier", "org.kde.switchdesktop"]
    assert run.calls[1][:2] == ["systemctl", "--user"]
    run = Recorder()
    kde.set_background_wheel(False, run)
    assert run.calls[0][-1] == "--delete"


def test_background_wheel_state(tmp_path):
    assert not kde.background_wheel_on(dirs=[str(tmp_path)])
    (tmp_path / kde.APPLETSRC).write_text("[ActionPlugins][0]\nwheel:Vertical;NoModifier=org.kde.switchdesktop\n", encoding="utf-8")
    assert kde.background_wheel_on(dirs=[str(tmp_path)])


def test_write_shortcuts_passes_a_real_tab():
    run = Recorder()
    assert kde.write_shortcuts(run)
    values = {c[6]: c[7] for c in run.calls}
    assert values["Switch to Desktop 2"] == "Meta+2\tCtrl+F2,Ctrl+F2,Switch to Desktop 2"


PANEL_HARNESS = r"""
const vm = require('vm');
function W(type, id) { return {type, id, cfg: {}, writeConfig(k, v) { this.cfg[k] = v; }}; }
const panel = {ws: [W('org.kde.plasma.kickoff', 2), W('org.kde.plasma.icontasks', 3), W('org.kde.plasma.digitalclock', 4)%s],
  cfg: {}, writeConfig(k, v) { this.cfg[k] = v; },
  widgets(t) { return t ? this.ws.filter(w => w.type === t) : this.ws.slice(); },
  addWidget(t) { const w = W(t, 9); this.ws.push(w); return w; }};
vm.runInNewContext(__SOURCE__, {panels: () => [panel]});
console.log(JSON.stringify({types: panel.ws.map(w => w.type), order: panel.cfg.AppletOrder || '', icon: panel.ws[0].cfg.icon}));
"""


@needs_node
def test_update_script_adds_a_pager_after_the_launcher():
    out = _run_js(PANEL_HARNESS % "", DESKTOP_JS)
    assert out["icon"] == "halos" and "org.kde.plasma.pager" in out["types"]
    assert out["order"] == "2;9;3;4"


@needs_node
def test_update_script_keeps_a_pager_already_there():
    out = _run_js(PANEL_HARNESS % ", W('org.kde.plasma.pager', 7)", DESKTOP_JS)
    assert out["types"].count("org.kde.plasma.pager") == 1 and out["order"] == ""


def test_shipped_defaults_leave_the_launcher_icon_alone():
    """6: nothing shipped configures the panel, so only the update scripts set the start button's icon."""
    for f in list((FS / "usr/share/plasma/look-and-feel").rglob("defaults")) + list((FS / "etc/xdg").glob("*")):
        if f.is_file():
            text = f.read_text(encoding="utf-8", errors="replace")
            assert "kickoff" not in text.lower() and "start-here" not in text, f
    assert not list((FS / "usr/share/plasma/look-and-feel").rglob("layout.js"))
    assert not (FS / "etc/xdg/plasma-org.kde.plasma.desktop-appletsrc").exists()


# --------------------------------------------------------------------------- 3. animations
GOOD = {"schema": 1, "name": "Soft", "event": "close", "duration": 400, "segments": [
    {"span": 1, "curve": "OutQuad", "scale": [1, 1.1]}, {"span": 3, "curve": "InCubic", "opacity": [1, 0]}]}


def test_validate_normalises_spans_and_holds_properties():
    v = wa.validate(GOOD)
    assert [s["span"] for s in v["segments"]] == [0.25, 0.75]
    assert v["segments"][0]["opacity"] == [1.0, 1.0]         # neutral before it's first used
    assert v["segments"][1]["scale"] == [1.1, 1.1]           # holds where the last segment left it


@pytest.mark.parametrize("change, expect", [
    ({"name": "../evil"}, "name"), ({"event": "launch"}, "event"), ({"duration": 5}, "duration"),
    ({"duration": True}, "duration"), ({"schema": 2}, "schema"), ({"segments": []}, "segments"),
    ({"segments": [{"span": 1, "curve": "Wobble", "scale": [1, 2]}]}, "curve"),
    ({"segments": [{"span": 1, "curve": "Linear", "scale": [1, 99]}]}, "scale"),
    ({"segments": [{"span": 1, "curve": "Linear", "scale": 2}]}, "scale"),
    ({"segments": [{"span": 1, "curve": "Linear"}]}, "animates"),
    ({"segments": [{"span": -1, "curve": "Linear", "scale": [1, 2]}]}, "span"),
    ({"segments": "x"}, "segments"),
])
def test_validate_refuses(change, expect):
    with pytest.raises(ValueError, match=expect):
        wa.validate({**GOOD, **change})


def test_all_builtins_are_valid_and_fold_away_is_the_default_close():
    for event, presets in wa.BUILTIN.items():
        for p in presets:
            if p["segments"]:
                wa.validate({**p, "event": event})
    close = wa.default_preset("close")
    assert close["id"] == "fold"
    grow, fold = close["segments"]
    assert grow["scale"] == [1, 1.06] and fold["scale"] == [1.06, 0]          # swells, then shrinks to nothing
    assert fold["rotation"][1] != 0 and fold["brightness"][1] > 2 and fold["opacity"][1] == 0
    nova = wa.builtin("close", "supernova")
    assert nova["segments"][0]["scale"][1] < 1 and nova["segments"][-1]["scale"][1] > 1


def test_custom_files_bad_ones_are_reported_not_fatal(tmp_path):
    (tmp_path / "good.json").write_text(json.dumps(GOOD), encoding="utf-8")
    (tmp_path / "broken.json").write_text("{nope", encoding="utf-8")
    (tmp_path / "wrong.json").write_text(json.dumps({**GOOD, "duration": 1}), encoding="utf-8")
    (tmp_path / "list.json").write_text("[]", encoding="utf-8")
    found, problems = wa.load_custom(tmp_path)
    assert [p["id"] for p in found["close"]] == ["custom:good"]
    assert sorted(p.split(":")[0] for p in problems) == ["broken.json", "list.json", "wrong.json"]
    assert wa.load_custom(tmp_path / "missing") == ({e: [] for e in wa.EVENTS}, [])


def test_save_custom_round_trips(tmp_path):
    path = wa.save_custom(wa.builtin("close", "star-burst"), "My nova", "close", tmp_path)
    found, problems = wa.load_custom(tmp_path)
    assert not problems and path.name == "close-my-nova.json"
    assert found["close"][0]["name"] == "My nova" and found["close"][0]["burst"]
    with pytest.raises(ValueError):
        wa.save_custom(wa.default_preset("close"), "../../x", "close", tmp_path)


def test_tuned_scales_movement_from_neutral():
    p = wa.tuned(wa.builtin("close", "star-burst"), 800, scale=2.0, rotation=1.0, brightness=0.0)
    assert p["duration"] == 800
    assert p["segments"][0]["scale"] == [1.0, 1.12]
    assert p["segments"][1]["scale"][1] == 0.0                # clamped at the range's end
    assert p["segments"][0]["brightness"] == [1.0, 1.0]       # 0% brightness: no flash
    assert wa.builtin("close", "star-burst")["segments"][0]["scale"] == [1, 1.06]   # the built-in is untouched


def test_sample_walks_segments():
    linear = lambda _c, x: x
    v = wa.validate(GOOD)
    assert wa.sample(v, 0.0, linear)["scale"] == 1.0
    assert wa.sample(v, 0.25, linear)["scale"] == pytest.approx(1.1)
    assert wa.sample(v, 1.0, linear)["opacity"] == 0.0
    assert wa.sample(wa.builtin("close", "none"), 0.5, linear) == wa.NEUTRAL


def test_apply_writes_every_event_and_tells_kwin():
    run = Recorder()
    chosen = {**{e: wa.default_preset(e) for e in wa.EVENTS}, "close": wa.builtin("close", "star-burst")}
    assert wa.apply(chosen, False, run)
    calls = run.joined()
    assert any("CloseAnim" in c and '"burst":true' in c for c in calls)
    assert any("--group Script-saint-shell --key CloseBurst true" in c for c in calls)
    assert any("--key MinimizeAnim --delete" in c for c in calls)            # Plasma default: no preset, squash stays
    assert any("--key squashEnabled --delete" in c for c in calls) and any("loadEffect squash" in c for c in calls)
    assert calls[-1].endswith("org.kde.kwin.Effects.reconfigureEffect saint-star")
    run = Recorder()
    assert wa.apply({**chosen, "minimize": wa.builtin("minimize", "fade"), "close": wa.builtin("close", "fade")}, True, run)
    calls = run.joined()
    assert any("--key squashEnabled false" in c for c in calls) and any("unloadEffect squash" in c for c in calls)
    assert any("--key CloseBurst false" in c for c in calls) and any("--key ReducedMotion true" in c for c in calls)


def test_serialised_preset_survives_kwinrc(tmp_path):
    text = wa.serialise(wa.tuned(wa.default_preset("close"), 500))
    assert "\n" not in text
    (tmp_path / "kwinrc").write_text(f"[Effect-saint-star]\nCloseAnim={text}\n", encoding="utf-8")
    assert wa.current("close", dirs=[str(tmp_path)])["duration"] == 500


def _kwinrc(tmp_path, body="", kdeglobals=""):
    (tmp_path / "kwinrc").write_text(body, encoding="utf-8")
    (tmp_path / "kdeglobals").write_text(kdeglobals, encoding="utf-8")
    return [str(tmp_path)]


def test_burst_delay_follows_speed_and_reduced_motion(tmp_path):
    assert wa.burst_delay_ms(_kwinrc(tmp_path)) is None      # the default close is the window itself: no burst
    star = f"[Effect-saint-star]\nCloseAnim={wa.serialise(wa.builtin('close', 'star-burst'))}\n"
    assert wa.burst_delay_ms(_kwinrc(tmp_path, star)) == int(420 * 0.92)
    assert wa.burst_delay_ms(_kwinrc(tmp_path, star, "[KDE]\nAnimationDurationFactor=0.5\n")) == int(210 * 0.92)
    assert wa.burst_delay_ms(_kwinrc(tmp_path, star, "[KDE]\nAnimationDurationFactor=0\n")) is None
    assert wa.burst_delay_ms(_kwinrc(tmp_path, star, "[KDE]\nAnimationDurationFactor=0.25\n")) is None
    assert wa.burst_delay_ms(_kwinrc(tmp_path, star + "ReducedMotion=true\n")) is None
    assert wa.burst_delay_ms(_kwinrc(tmp_path, star + "[Plugins]\nsaint-starEnabled=false\n")) is None
    other = wa.serialise(wa.builtin("close", "fade"))
    assert wa.burst_delay_ms(_kwinrc(tmp_path, f"[Effect-saint-star]\nCloseAnim={other}\n")) is None


def test_effect_declares_what_it_reads():
    xml = (STAR_JS.parents[1] / "config" / "main.xml").read_text(encoding="utf-8")
    entries = set(re.findall(r'<entry name="(\w+)"', xml))
    assert entries == {"ReducedMotion", "OpenAnim", "CloseAnim", "MinimizeAnim", "DesktopAnim"}
    assert set(wa.EVENTS.values()) < entries


STAR_HARNESS = r"""
const vm = require('vm');
const config = %s;
const anims = [], cancelled = [];
let ended = null, added = null, closedCb = null, desktop = null;
const effect = {readConfig: (k, d) => (k in config ? config[k] : d), configChanged: {connect() {}},
                animationEnded: {connect(f) { ended = f; }}};
const ctx = {
  Effect: {Scale: 'scale', Opacity: 'opacity', Brightness: 'brightness', Rotation: 'rotation',
           WindowAddedGrabRole: 'added', WindowClosedGrabRole: 'closed'},
  QEasingCurve: {Linear: 'Linear', InQuad: 'InQuad', OutQuad: 'OutQuad', InOutQuad: 'InOutQuad', InCubic: 'InCubic',
                 OutCubic: 'OutCubic', InOutCubic: 'InOutCubic', InBack: 'InBack', OutBack: 'OutBack'},
  animationTime: ms => ms * %s,
  animate: a => { anims.push(a); return a.animations.map((_, i) => anims.length * 10 + i); },
  cancel: ids => cancelled.push(ids),
  effect,
  effects: {stackingOrder: [], hasActiveFullScreenEffect: false, windowAdded: {connect(f) { added = f; }},
            windowClosed: {connect(f) { closedCb = f; }}, desktopChanged: {connect(f) { desktop = f; }}},
  console: {warn() {}, log() {}}
};
vm.runInNewContext(__SOURCE__, ctx);
function win(extra) { return Object.assign({normalWindow: true, visible: true, caption: 'App', data: {},
    setData(k, v) { this.data[k] = v; }}, extra); }
function stages(fire, w) {
  anims.length = 0; fire(w);
  for (let guard = 0, seen = 0; guard < 20 && seen < anims.length; guard++) {
    const a = anims[seen++];
    for (let i = 0; i < a.animations.length; i++) ended(w);
  }
  return anims.map(a => ({duration: a.duration, curve: a.curve,
    props: Object.fromEntries(a.animations.map(x => [x.type, [num(x.from), num(x.to)]]))}));
}
// A two-axis value ({value1, value2}) must move both axes alike; the tests compare its single number.
function num(v) {
  if (v && typeof v === 'object') { if (v.value1 !== v.value2) throw new Error('one-axis scale'); return v.value1; }
  return v;
}
function raw(fire, w) { anims.length = 0; fire(w); return anims.map(a => ({keepAlive: a.keepAlive, animations: a.animations})); }
const out = {};
const closing = win();
out.close = stages(closedCb, closing);
out.closeGrab = 'closed' in closing.data;
const opening = win();
out.open = stages(added, opening);
out.openGrab = 'added' in opening.data;
out.panel = stages(closedCb, win({normalWindow: false}));
out.placed = stages(closedCb, win({caption: 'SAINT burst SAINT:place:1,2,3,4'}));
const running = win();
anims.length = 0; added(running); closedCb(running);
out.interrupted = cancelled.length;
// W10: only real opens and closes animate
out.fullscreenClose = stages(closedCb, win({fullScreen: true}));
out.fullscreenOpen = stages(added, win({fullScreen: true}));
out.draggedClose = stages(closedCb, win({move: true}));
const tornOut = win({pid: 7}), source = win({pid: 7});
added(tornOut);
out.swapClose = stages(closedCb, source);                 // a tab dragged out: the new window came, the old one went
const old = win({pid: 8}), remade = win({pid: 8});
closedCb(old);
const before = cancelled.length;
out.swapOpen = stages(added, remade);                     // fullscreen re-made the window: the old one went first
out.swapStopsOld = cancelled.length - before;
out.otherAppClose = stages(closedCb, win({pid: 9})).length;
const signals = {};
const live = win({pid: 10});
['minimizedChanged', 'windowStartUserMovedResized', 'windowFinishUserMovedResized', 'windowMaximizedStateChanged',
 'windowFullScreenChanged'].forEach(n => { live[n] = {connect(f) { signals[n] = f; }}; });
anims.length = 0; added(live);
const mid = cancelled.length;
signals.windowMaximizedStateChanged();                    // opened maximised: the opening keeps playing
out.maximiseStopsOpen = cancelled.length - mid;
signals.windowFullScreenChanged();                        // going fullscreen stops it
out.fullscreenStopsOpen = cancelled.length - mid;
signals.windowFullScreenChanged();                        // nothing is running any more: nothing to stop
out.idleStateChange = cancelled.length - mid;
out.rawOpen = raw(added, win());
out.rawClose = raw(closedCb, win());
console.log(JSON.stringify(out));
"""


def _star(config=None, factor=1) -> dict:
    return _run_js(STAR_HARNESS % (json.dumps(config or {}), factor), STAR_JS)


def _as_stages(preset):
    """What the effect should run for a validated preset: per-segment duration, curve and property ranges."""
    total = preset["duration"]
    spans = sum(s["span"] for s in preset["segments"])
    return [{"duration": round(total * s["span"] / spans), "curve": s["curve"],
             "props": {k: s[k] for k in wa.RANGES if k in s}} for s in preset["segments"]]


@needs_node
def test_effect_builtins_match_python_defaults():
    out = _star()
    assert out["close"] == _as_stages(wa.default_preset("close"))
    assert out["open"] == _as_stages(wa.default_preset("open"))
    assert out["closeGrab"] and out["openGrab"]


@needs_node
def test_effect_leaves_panels_menus_and_saint_helpers_alone():
    out = _star()
    assert out["panel"] == [] and out["placed"] == []


@needs_node
def test_effect_plays_segments_in_order_and_interrupts_cleanly():
    out = _star({"CloseAnim": wa.serialise(wa.validate({**wa.builtin("close", "supernova"), "event": "close"}))})
    assert len(out["close"]) == 2 and out["close"][0]["props"]["scale"] == [1, 0.84]      # pulls inward
    assert out["close"][1]["props"]["scale"] == [0.84, 1.3]                                # then bursts outward
    assert out["close"][1]["props"]["opacity"] == [1, 0]
    assert out["interrupted"] == 1


def test_supernova_close_is_the_window_pulling_in_then_bursting_out():
    close = wa.builtin("close", "supernova")
    first, last = close["segments"][0]["scale"], close["segments"][-1]["scale"]
    assert first[1] < first[0] and last[1] > 1 > last[0] and close["segments"][-1]["opacity"][1] == 0
    assert not close.get("burst")                           # the window, not the logo
    assert wa.validate({**close, "event": "close"})["segments"]
    assert 'readConfig("CloseBurst", "false")' in SHELL_JS.read_text(encoding="utf-8")


@needs_node
def test_effect_only_animates_real_opens_and_closes():
    out = _star()
    assert out["fullscreenClose"] == [] and out["fullscreenOpen"] == [] and out["draggedClose"] == []
    assert out["swapClose"] == [] and out["swapOpen"] == [] and out["swapStopsOld"] == 1
    assert out["otherAppClose"] == 2                        # another app's window still closes with the animation
    assert out["maximiseStopsOpen"] == 0 and out["fullscreenStopsOpen"] == 1 and out["idleStateChange"] == 1


@needs_node
def test_effect_scales_both_axes_and_turns_in_the_screen_plane():
    """The star close folded on one axis and the open showed half a window: KWin rotates about the X axis and
    the scale must name both axes. Rotation now asks for Qt::ZAxis (2)."""
    out = _star()
    for stage in out["rawOpen"] + out["rawClose"]:
        for a in stage["animations"]:
            if a["type"] == "scale":
                assert a["from"]["value1"] == a["from"]["value2"] and a["to"]["value1"] == a["to"]["value2"]
            if a["type"] == "rotation":
                assert a["axis"] == 2
    assert all(s["keepAlive"] for s in out["rawClose"]) and not any(s["keepAlive"] for s in out["rawOpen"])


@needs_node
def test_effect_uses_a_configured_preset():
    text = wa.serialise(wa.validate({**GOOD, "duration": 1000}))
    assert _star({"CloseAnim": text})["close"][1]["duration"] == 750


@needs_node
@pytest.mark.parametrize("bad", ["{nope", '{"duration":1}', '{"duration":100,"segments":[{"span":0,"curve":"Linear"}]}',
                                 '{"duration":100,"segments":[{"span":1,"curve":"Boing"}]}',
                                 '{"duration":100,"segments":[{"span":1,"curve":"Linear","scale":"big"}]}'])
def test_effect_falls_back_on_a_bad_preset(bad):
    assert _star({"CloseAnim": bad})["close"] == _as_stages(wa.default_preset("close"))


@needs_node
def test_effect_reduced_motion_is_a_fade_and_instant_is_nothing():
    reduced = _star({"ReducedMotion": True})
    assert list(reduced["close"][0]["props"]) == ["opacity"] and len(reduced["close"]) == 1
    assert list(_star(factor=0.25)["close"][0]["props"]) == ["opacity"]       # the speed slider set very fast
    instant = _star(factor=0)
    assert instant["close"] == [] and not instant["closeGrab"]


def test_supernova_dbus_point_is_checked():
    assert saint_dbus.supernova_command("640,480") == "supernova:640,480"
    assert saint_dbus.supernova_command("-100,20") == "supernova:-100,20"
    for bad in ("", "1,2,3", "x,y", "1;quit", "1,2\nquit", "9999999,1"):
        assert saint_dbus.supernova_command(bad) == ""


def test_burst_is_click_through_and_finishes(qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter
    from ui import supernova
    b = supernova.Burst(500, 400)
    flags = b.windowFlags()
    assert flags & Qt.WindowTransparentForInput and flags & Qt.WindowDoesNotAcceptFocus
    assert b.testAttribute(Qt.WA_ShowWithoutActivating)
    supernova._live.append(b)
    b.finish()
    assert b not in supernova._live

    img = QImage(200, 200, QImage.Format_ARGB32_Premultiplied)
    img.fill(0)
    g = QPainter(img)
    supernova.paint_burst(g, 100, 100, 98, 0.2)
    g.end()
    assert img.pixelColor(100, 100).alpha() > 0
    corner = img.pixelColor(1, 1).alpha()
    assert corner == 0


def test_burst_respects_settings(monkeypatch, qapp):
    from ui import supernova
    spawned = []
    monkeypatch.setattr(supernova, "_spawn", lambda x, y: spawned.append((x, y)))
    monkeypatch.setattr(supernova.window_anim, "burst_delay_ms", lambda: None)
    supernova.play(1, 2)
    qapp.processEvents()
    assert spawned == []


# --------------------------------------------------------------------------- 4. widgets
def test_all_plasmoids_are_in_the_halos_category():
    found = list((FS / "usr/share/plasma/plasmoids").glob("*/metadata.json"))
    assert len(found) >= 3
    for f in found:
        data = json.loads(f.read_text(encoding="utf-8"))
        assert data["KPlugin"]["Category"] == "HalOS", f


def test_evolve_tells_agents_about_the_category():
    assert '"Category" to "HalOS"' in evolve.AGENT_GUIDE
    evolve.AGENT_GUIDE.format(request="x", home="h", system="s", reloads="r")     # still formats


# --------------------------------------------------------------------------- 5. startup apps
def _desktop(path: Path, **fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[Desktop Entry]\n" + "".join(f"{k}={v}\n" for k, v in fields.items()), encoding="utf-8")


def test_rows_merge_system_and_user_and_hide_internal(tmp_path):
    system, user = tmp_path / "xdg", tmp_path / "user"
    _desktop(system / "tray.desktop", Name="Tray", Exec="tray")
    _desktop(system / "saintos-firstrun.desktop", Name="Welcome", Exec="firstrun")
    _desktop(system / "gnomey.desktop", Name="Gnomey", Exec="g", NotShowIn="KDE;")
    _desktop(user / "mine.desktop", Name="Mine", Exec="mine")
    rows = sa.autostart_rows(str(user), (str(system),))
    assert [(r["name"], r["removable"]) for r in rows] == [("Mine", True), ("Tray", False)]


def test_switching_off_a_system_entry_writes_a_hidden_override(tmp_path):
    system, user = tmp_path / "xdg", tmp_path / "user"
    _desktop(system / "tray.desktop", Name="Tray", Exec="tray")
    row = sa.autostart_rows(str(user), (str(system),))[0]
    sa.set_enabled(row, False, udir=str(user))
    assert "Hidden=true" in (user / "tray.desktop").read_text(encoding="utf-8")
    row = sa.autostart_rows(str(user), (str(system),))[0]
    assert row["enabled"] is False and row["removable"] is False     # still a system entry, only switched off
    with pytest.raises(ValueError):
        sa.remove(row, str(user))
    sa.set_enabled(row, True, udir=str(user))
    assert sa.autostart_rows(str(user), (str(system),))[0]["enabled"] is True


def test_remove_only_your_own_and_only_a_clean_name(tmp_path):
    user = tmp_path / "user"
    _desktop(user / "mine.desktop", Name="Mine", Exec="mine")
    row = sa.autostart_rows(str(user), ())[0]
    with pytest.raises(ValueError):
        sa.remove({**row, "file": "../../.bashrc"}, str(user))
    sa.remove(row, str(user))
    assert not (user / "mine.desktop").exists()


@pytest.mark.parametrize("command, expect", [
    ("", "one line"), ("foo\nbar", "one line"), ('foo "bar', "quotes"), ("foo | bar", "Shell syntax"),
    ("foo && bar", "Shell syntax"), ("foo `id`", "Shell syntax"), ("foo $(id)", "Shell syntax"), ("foo ; bar", "Shell syntax"),
    ("sh -c 'rm -rf /'", "shell can't"), ("/bin/bash x", "shell can't"), ("nosuchprogram", "no program"),
])
def test_parse_command_refuses(command, expect):
    which = lambda p: None if p == "nosuchprogram" else f"/usr/bin/{p}"
    with pytest.raises(ValueError, match=expect):
        sa.parse_command(command, which)


def test_add_command_writes_a_quoted_exec_and_runs_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("nothing may run"))
    path = sa.add_command("My Sync!", 'sync --dir "/a b" --pct 50%', str(tmp_path), lambda p: "/usr/bin/sync")
    assert path.name == "halos-my-sync.desktop"
    text = path.read_text(encoding="utf-8")
    assert 'Exec=sync --dir "/a b" --pct 50%%\n' in text and "Name=My Sync!\n" in text
    with pytest.raises(ValueError, match="already"):
        sa.add_command("My Sync!", "sync", str(tmp_path), lambda p: "/usr/bin/sync")
    with pytest.raises(ValueError, match="1-64"):
        sa.add_command("x\ny", "sync", str(tmp_path), lambda p: "/usr/bin/sync")


def test_installed_apps_and_adding_one(tmp_path):
    apps = tmp_path / "apps"
    _desktop(apps / "foo.desktop", Name="Foo", Exec="foo %U", Icon="foo", Comment="A foo")
    _desktop(apps / "hidden.desktop", Name="Hidden", Exec="h", NoDisplay="true")
    _desktop(apps / "link.desktop", Name="Link", Type="Link")
    _desktop(apps / "gnome.desktop", Name="G", Exec="g", OnlyShowIn="GNOME;")
    found = sa.installed_apps([str(apps)])
    assert [a["name"] for a in found] == ["Foo"]
    user = tmp_path / "user"
    text = sa.add_app(found[0], str(user)).read_text(encoding="utf-8")
    assert "Exec=foo\n" in text and "Icon=foo\n" in text
    assert sa.autostart_rows(str(user), ())[0]["removable"] is True


def test_service_rows_only_own_ones(tmp_path):
    (tmp_path / "mine.service").write_text("", encoding="utf-8")
    listing = ("saint.service enabled enabled\nhalo-remote.service disabled disabled\n"
               "pipewire.service enabled enabled\nmine.service disabled enabled\nstatic-thing.service static -\n")
    rows = sa.service_rows(Recorder({"list-unit-files": (True, listing)}), str(tmp_path))
    assert {r["file"]: r["enabled"] for r in rows} == {"saint.service": True, "halo-remote.service": False,
                                                       "mine.service": False}
    assert next(r for r in rows if r["file"] == "saint.service")["name"] == "SAINT"


def test_service_toggle_uses_systemctl_without_a_shell():
    run = Recorder()
    row = {"kind": "service", "file": "saint.service", "name": "SAINT"}
    sa.set_enabled(row, False, run)
    assert run.calls == [["systemctl", "--user", "disable", "saint.service"]]
    with pytest.raises(ValueError):
        sa.set_enabled({**row, "file": "x; rm -rf /"}, True, run)
    with pytest.raises(ValueError, match="nope"):
        sa.set_enabled(row, True, Recorder({"enable": (False, "nope")}))


# --------------------------------------------------------------------------- the pages build
@pytest.mark.parametrize("name", ["desktop", "animations", "startup_apps"])
def test_settings_pages_build_without_plasma(name, qapp, monkeypatch, tmp_path):
    import importlib
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    mod = importlib.import_module(f"ui.settings_pages.{name}")
    assert mod.TITLE and mod.ICON
    monkeypatch.setattr(kde, "_run", lambda argv: (False, "no plasma"))
    monkeypatch.setattr(sa, "_run", lambda argv: (False, "no plasma"))
    assert mod.build() is not None


def test_settings_pages_are_discovered():
    from ui import settings_pages
    titles = [m.TITLE for m in settings_pages.discover()]
    assert {"Desktop", "Animations", "Startup apps"} <= set(titles)


def _anim_page(monkeypatch, tmp_path):
    from ui.settings_pages import animations
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    applied, shown = [], []
    monkeypatch.setattr(animations.wa, "apply",
                        lambda chosen, reduced, run=None: applied.append((chosen, reduced)) or True)
    monkeypatch.setattr(animations.kde, "reload_shell_script", lambda *a, **k: True)
    monkeypatch.setattr(animations, "_spawn", lambda work: work())
    monkeypatch.setattr(animations, "_test_window", lambda event="close": shown.append(event) or object())
    monkeypatch.setattr(animations, "TUNE_SETTLE_MS", 0)
    return animations.Page(), applied, shown


def test_animations_page_saves_a_custom_preset(qapp, monkeypatch, tmp_path):
    page, applied, _shown = _anim_page(monkeypatch, tmp_path)
    page.event.setCurrentIndex(page.event.findData("close"))
    assert page.preset.currentData() == "fold"                      # the default close
    page.preset.setCurrentIndex(page.preset.findData("star-burst"))
    page.preset.activated.emit(page.preset.currentIndex())
    assert page.build_current()["burst"] is True
    page.preview.play(page.build_current())
    page.preview.grab()                                    # paints a frame without KWin
    page.duration.setValue(600)
    page.save_named("Slow nova")
    assert (tmp_path / "halos/animations/close-slow-nova.json").exists()
    assert page.preset.currentData() == "custom:close-slow-nova"
    assert applied == []                                   # kept as a file, not put on windows yet
    assert page.save("Nova profile")
    chosen, _reduced = applied[-1]
    assert chosen["close"]["duration"] == 600 and chosen["close"]["burst"] is True
    page.save_named("../bad")
    assert "Not saved" in page.msg.text()


def test_animations_page_previews_and_only_save_applies(qapp, monkeypatch, tmp_path):
    """A slower speed being tried must not reach every window: sliders and presets only change the draft, Save
    writes it, Revert puts the saved one back."""
    from PySide6.QtTest import QTest
    page, applied, shown = _anim_page(monkeypatch, tmp_path)
    page.event.setCurrentIndex(page.event.findData("open"))
    assert not page.save_btn.isEnabled()

    page.duration.setValue(2500)                           # not a drag: the wheel, the keys or a click on the groove
    page.scale.setValue(50)
    QTest.qWait(50)
    assert applied == [] and page.dirty() and page.save_btn.isEnabled()
    assert page.chosen["open"]["tune"]["scale"] == 50 and page.chosen["open"]["segments"][0]["scale"] == [0.775, 1.0]
    assert page.preview._timer.isActive()                  # previewed

    for i in range(page.preset.count()):                   # every preset of the event can be chosen
        page.preset.setCurrentIndex(i)
        page.preset.activated.emit(i)
        assert page.chosen["open"]["id"] == page.preset.itemData(i)
    page.preset.setCurrentIndex(page.preset.findData("fade"))
    page.preset.activated.emit(page.preset.currentIndex())
    assert not page.scale.isEnabled() and page.duration.isEnabled()      # Fade has no scale to change
    assert applied == []

    page.revert()
    assert not page.dirty() and page.chosen["open"]["id"] == "saint-star" and applied == []

    page.preset.setCurrentIndex(page.preset.findData("pop"))
    page.preset.activated.emit(page.preset.currentIndex())
    page.try_real()                                        # the draft plays on one test window...
    assert shown == ["open"] and applied[-1][0]["open"]["id"] == "pop"
    page.end_try()                                         # ...then the saved animations come back
    assert applied[-1][0]["open"]["id"] == "saint-star" and page.dirty()

    assert page.save("Popping")                            # a changed built-in becomes a profile of yours
    assert applied[-1][0]["open"]["id"] == "pop" and not page.dirty()
    assert page.active == "Popping" and "Popping" in wa.load_profiles()[0]
    assert wa.load_profiles()[1] == "Popping"


def test_animation_profiles_create_rename_delete(qapp, monkeypatch, tmp_path):
    page, applied, _shown = _anim_page(monkeypatch, tmp_path)
    assert {"SAINT", "Snappy", "Calm", "Off"} <= set(page.builtins)
    page.pick_profile("Snappy")                            # previews; nothing applied
    assert page.chosen["close"]["id"] == "shrink" and page.chosen["close"]["duration"] == 130 and applied == []
    page.event.setCurrentIndex(page.event.findData("close"))
    assert page.duration.value() == 130                    # each event keeps its own speed
    page.event.setCurrentIndex(page.event.findData("open"))
    assert page.duration.value() == 150
    assert page.save() and page.active == "Snappy" and applied[-1][0]["minimize"]["id"] == "collapse"

    assert page.new_profile("Work")
    assert not page.new_profile("Work") and "already" in page.msg.text()
    assert not page.new_profile("SAINT")                   # built-in names are taken
    page.event.setCurrentIndex(page.event.findData("desktop"))
    page.preset.setCurrentIndex(page.preset.findData("none"))
    page.preset.activated.emit(page.preset.currentIndex())
    assert page.save() and page.active == "Work"
    mine, active = wa.load_profiles()
    assert active == "Work" and mine["Work"]["desktop"]["segments"] == [] and mine["Work"]["close"]["id"] == "shrink"

    assert page.rename_profile("Work", "Focus") and page.active == "Focus"
    assert set(wa.load_profiles()[0]) == {"Focus"} and wa.load_profiles()[1] == "Focus"
    assert page.rename_btn.isEnabled() and page.delete_btn.isEnabled()          # yours can be changed
    page.fill_profiles("SAINT")
    assert not page.rename_btn.isEnabled() and not page.delete_btn.isEnabled()  # built-ins can't
    page.fill_profiles("Focus")
    assert page.delete_profile("Focus") and wa.load_profiles() == ({}, "SAINT")
    assert not page.delete_profile("SAINT")


def test_profiles_file_rejects_broken_entries(tmp_path):
    f = tmp_path / "p.json"
    good = {e: wa.default_preset(e) for e in wa.EVENTS}
    f.write_text(json.dumps({"active": "Mine", "profiles": {
        "Mine": good, "SAINT": good, "../x": good,
        "Bad": {"open": {"id": "x", "duration": 99999, "segments": [{"span": 1, "scale": [0, 1]}]}},
        "Sys": {"open": {"id": wa.SYSTEM}}}}), encoding="utf-8")
    mine, active = wa.load_profiles(f)
    assert set(mine) == {"Mine"} and active == "Mine"
    assert wa.same(mine["Mine"], good)
    f.write_text("{nope", encoding="utf-8")
    assert wa.load_profiles(f) == ({}, "SAINT")
    for name, prof in wa.builtin_profiles().items():       # every built-in profile is valid
        assert wa.same(wa.clean_profile(prof), prof), name

