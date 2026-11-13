// SAINT shell (KWin script). On Wayland an app can't place its own windows, so SAINT asks here:
//   a SAINT window whose title contains "SAINT:place:<x>,<y>,<w>,<h>" is put at that geometry (global
//   logical pixels), kept above, and left off the taskbar, pager and Alt+Tab. SAINT changes the title
//   to move it (ui/placement.py: wayland_place). These are overlays (the Halo, notices), never the SAINT app's
//   window: a click on SAINT's taskbar icon can't reach them, and one that got minimised anyway comes back.
// It also reports back over D-Bus (core/saint_dbus.py): where a dragged SAINT helper window landed (PlacedMoved), and
// the focused app window's geometry (ActiveWindow), which the avatar uses to sit on title bars and climb edges.
// Settings, kwinrc [Script-saint-shell], written by Control Center (core/kde_desktop.py), which reloads this
// script through /Scripting unloadScript + start, so they're only read once, here:
//   OverlayEdge         off (the default), top, topright, right, bottomright, bottom, bottomleft, left, topleft
//   OverlayEdgeDelayMs  how long the cursor must stay at that edge before SAINT's overlay opens (0: at once)
//   CloseBurst          the close animation has a star burst (off by default): tell SAINT where a window closed,
//                       so it paints it (ui/supernova.py). Here and not in the saint-star effect: effects have
//                       no callDBus. Like the effect, only for a real close: not a fullscreen window, one being
//                       dragged, or one its app swaps for another (a tab dragged out or dropped back).
//   A SAINT window whose title contains "SAINT:helper" (ui/placement.py: wayland_helper) only gets the
//   off-the-taskbar part: it isn't placed.
const MARK = "SAINT:place:";
const HELPER = "SAINT:helper";
const CAPTURE = /spectacle|flameshot|ksnip|gnome-screenshot|xdg-desktop-portal/i;    // no burst for screenshot tools
const REPLACE_MS = 400;
const lastAdded = {};              // pid -> when that app's newest ordinary window arrived
const STAY_PX = 8;                 // the cursor counts as still at the edge within this distance of it

const EDGES = {
    top: KWin.ElectricTop, topright: KWin.ElectricTopRight, right: KWin.ElectricRight,
    bottomright: KWin.ElectricBottomRight, bottom: KWin.ElectricBottom, bottomleft: KWin.ElectricBottomLeft,
    left: KWin.ElectricLeft, topleft: KWin.ElectricTopLeft
};

function place(w) {
    if (!w || w.resourceClass !== "saint") {
        return;
    }
    const caption = w.caption || "";
    const at = caption.indexOf(MARK);
    if (at < 0) {
        if (caption.indexOf(HELPER) >= 0) {
            w.skipTaskbar = true;
            w.skipPager = true;
            w.skipSwitcher = true;
        }
        return;
    }
    const g = caption.slice(at + MARK.length).split(",").map(Number);
    if (g.length !== 4 || g.some(isNaN) || g[2] <= 0 || g[3] <= 0) {
        return;
    }
    w.skipTaskbar = true;
    w.skipPager = true;
    w.skipSwitcher = true;
    w.keepAbove = true;
    if (w.minimized) {
        w.minimized = false;
    }
    w.frameGeometry = { x: g[0], y: g[1], width: g[2], height: g[3] };
}

// The name part of a placed window's title ("SAINT Avatar SAINT:place:..." -> "SAINT Avatar").
function placedName(w) {
    const caption = w.caption || "";
    const at = caption.indexOf(MARK);
    return at < 0 ? "" : caption.slice(0, at).trim();
}

// A SAINT helper the person dragged (the avatar, via startSystemMove): tell SAINT where it landed, so it remembers.
function moved(w) {
    const name = placedName(w);
    if (w.resourceClass === "saint" && name) {
        const g = w.frameGeometry;
        saint("PlacedMoved", name + "|" + Math.round(g.x) + "," + Math.round(g.y));
    }
}

// The focused app window and where it is, for the avatar sitting on title bars and climbing window edges.
function reportActive(w) {
    if (!w || !w.normalWindow || w.resourceClass === "saint" || w.fullScreen) {
        return;
    }
    const g = w.frameGeometry;
    const cls = String(w.resourceClass || "").replace(/[^A-Za-z0-9._ -]/g, "").slice(0, 80);
    saint("ActiveWindow", cls + "|" + Math.round(g.x) + "," + Math.round(g.y) + "," +
          Math.round(g.width) + "," + Math.round(g.height));
}

function watch(w) {
    if (w && w.pid && w.normalWindow) {
        lastAdded[w.pid] = Date.now();
    }
    place(w);
    w.captionChanged.connect(function () { place(w); });
    if (w.minimizedChanged) {
        w.minimizedChanged.connect(function () { place(w); });
    }
    if (w.interactiveMoveResizeFinished) {
        w.interactiveMoveResizeFinished.connect(function () {
            moved(w);
            if (w === workspace.activeWindow) {
                reportActive(w);
            }
        });
    }
}

workspace.windowList().forEach(watch);
workspace.windowAdded.connect(watch);
if (workspace.windowActivated) {
    workspace.windowActivated.connect(reportActive);
}

function saint(method, arg) {
    // Fails quietly when SAINT isn't running.
    if (arg === undefined) {
        callDBus("org.saintos.Saint", "/Saint", "org.saintos.Saint", method);
    } else {
        callDBus("org.saintos.Saint", "/Saint", "org.saintos.Saint", method, arg);
    }
}

// Is point p still at this edge or corner of a screen with geometry g?
function atEdge(name, p, g) {
    const nearTop = p.y <= g.y + STAY_PX, nearBottom = p.y >= g.y + g.height - 1 - STAY_PX;
    const nearLeft = p.x <= g.x + STAY_PX, nearRight = p.x >= g.x + g.width - 1 - STAY_PX;
    return (name.indexOf("top") < 0 || nearTop) && (name.indexOf("bottom") < 0 || nearBottom) &&
           (name.indexOf("left") < 0 || nearLeft) && (name.indexOf("right") < 0 || nearRight);
}

function cursorStayed(name) {
    const p = workspace.cursorPos;
    const screen = workspace.screenAt(p);
    return !screen || atEdge(name, p, screen.geometry);
}

function setUpOverlayEdge() {
    const name = String(readConfig("OverlayEdge", "off")).toLowerCase();
    const delay = Math.max(0, Number(readConfig("OverlayEdgeDelayMs", 0)) || 0);
    if (!Object.prototype.hasOwnProperty.call(EDGES, name)) {
        return;                                 // "off", or something this version doesn't know
    }
    let waiting = false;
    registerScreenEdge(EDGES[name], function () {
        if (delay <= 0 || typeof QTimer === "undefined") {
            saint("ToggleOverlay");
            return true;
        }
        if (waiting) {
            return true;
        }
        waiting = true;
        const timer = new QTimer();
        timer.singleShot = true;
        timer.interval = delay;
        timer.timeout.connect(function () {
            waiting = false;
            if (cursorStayed(name)) {
                saint("ToggleOverlay");
            }
        });
        timer.start();
        return true;
    });
}

function onThisDesktop(w) {
    const desktops = w.desktops;
    if (w.onAllDesktops || !desktops || !desktops.length) {
        return true;
    }
    for (let i = 0; i < desktops.length; i++) {
        if (desktops[i] === workspace.currentDesktop) {
            return true;
        }
    }
    return false;
}

function setUpCloseBurst() {
    if (String(readConfig("CloseBurst", "false")) !== "true") {
        return;
    }
    workspace.windowRemoved.connect(function (w) {
        // The same windows the saint-star effect animates: never panels, menus, tooltips or SAINT's helpers.
        if (!(w.normalWindow || w.dialog) || w.skipsCloseAnimation || w.minimized || !onThisDesktop(w) ||
                CAPTURE.test(String(w.resourceClass || "")) || String(w.caption || "").indexOf(MARK) >= 0) {
            return;
        }
        const swapped = w.pid && w.normalWindow && Date.now() - (lastAdded[w.pid] || 0) < REPLACE_MS;
        if (swapped || w.fullScreen || w.move || w.resize) {
            return;
        }
        const g = w.frameGeometry;
        // One string: D-Bus signatures are strict and a JavaScript number may go out as an int or a double.
        saint("PlaySupernova", Math.round(g.x + g.width / 2) + "," + Math.round(g.y + g.height / 2));
    });
}

setUpOverlayEdge();
setUpCloseBurst();
