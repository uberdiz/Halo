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
    if (!w || (w.resourceClass !== "saint" && w.resourceClass !== "halos-halo")) {
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
        if (name === AVATAR) {
            perchOn(windowUnderFeet(g));
            giveFocusBack();                  // a drag activated her; typing goes back where it was
        }
    }
}

// ---- the avatar ("SAINT Avatar"): what she stands on, focus, the pointer
// She's a companion, never a place to type: she must not keep keyboard focus (Qt's WindowDoesNotAcceptFocus
// means nothing on Wayland). Dropped on an app window she sits on its top edge, so SAINT is told which window is
// under her feet and, while she's on it, where it goes. While she's out, the pointer is reported a few times a
// second so her eyes can follow it (an app can't see the pointer outside its own windows on Wayland).
const AVATAR = "SAINT Avatar";
const CURSOR_MS = 120;
let lastActive = null;               // the app window that had focus before her
let avatarWin = null;
let perch = null;                    // the app window she's standing on
let cursorSent = 0;

function isAvatar(w) {
    return !!w && w.resourceClass === "saint" && placedName(w) === AVATAR;
}

function geo(g) {
    return Math.round(g.x) + "," + Math.round(g.y) + "," + Math.round(g.width) + "," + Math.round(g.height);
}

function windowUnderFeet(g) {
    const fx = g.x + g.width / 2, fy = g.y + g.height * 0.95;
    const order = workspace.stackingOrder;                    // bottom to top
    for (let i = order.length - 1; i >= 0; i--) {
        const o = order[i];
        if (!o.normalWindow || o.minimized || o.resourceClass === "saint" || !onThisDesktop(o)) {
            continue;
        }
        const r = o.frameGeometry;
        if (fx >= r.x && fx <= r.x + r.width && fy >= r.y - 24 && fy <= r.y + r.height) {
            return o;
        }
    }
    return null;
}

function reportPerch() {
    if (!perch || perch.minimized || perch.deleted) {
        perch = null;
        saint("PlacedOver", AVATAR + "||0,0,0,0");
        return;
    }
    const cls = String(perch.resourceClass || "").replace(/[^A-Za-z0-9._ -]/g, "").slice(0, 80);
    saint("PlacedOver", AVATAR + "|" + cls + "|" + geo(perch.frameGeometry));
}

const perchWatched = {};
function perchOn(w) {
    perch = w;
    if (w) {
        const id = String(w.internalId);
        if (!perchWatched[id]) {
            perchWatched[id] = true;
            if (w.interactiveMoveResizeFinished) {
                w.interactiveMoveResizeFinished.connect(function () { if (perch === w) reportPerch(); });
            }
            if (w.minimizedChanged) {
                w.minimizedChanged.connect(function () { if (perch === w) reportPerch(); });
            }
            if (w.closed) {
                w.closed.connect(function () { if (perch === w) { perch = null; reportPerch(); } });
            }
            if (w.maximizedChanged) {
                w.maximizedChanged.connect(function () { if (perch === w) reportPerch(); });
            }
        }
    }
    reportPerch();
}

function giveFocusBack() {
    if (lastActive && !lastActive.deleted && !lastActive.minimized && workspace.activeWindow !== lastActive
            && onThisDesktop(lastActive)) {      // never switches desktops
        workspace.activeWindow = lastActive;
    }
}

function activated(w) {
    if (!w) {
        return;
    }
    if (isAvatar(w)) {
        // A click on her (the menu) keeps focus; her showing up or being moved doesn't take it from you.
        const p = workspace.cursorPos, g = w.frameGeometry;
        if (!(p.x >= g.x && p.x <= g.x + g.width && p.y >= g.y && p.y <= g.y + g.height)) {
            giveFocusBack();
        }
        return;
    }
    if (w.normalWindow && w.resourceClass !== "saint") {
        lastActive = w;
    }
}

function sendCursor() {
    if (!avatarWin || avatarWin.deleted || avatarWin.minimized) {
        return;
    }
    const now = Date.now();
    if (now - cursorSent < CURSOR_MS) {
        return;
    }
    cursorSent = now;
    const p = workspace.cursorPos;
    saint("Cursor", Math.round(p.x) + "," + Math.round(p.y));
}

function reportAreas() {
    const parts = [];
    (workspace.screens || []).forEach(function (s) {
        parts.push(geo(workspace.clientArea(KWin.MaximizeArea, s, workspace.currentDesktop)));
    });
    saint("WorkAreas", parts.join(";"));
}

function watchAvatar(w) {
    if (isAvatar(w)) {
        avatarWin = w;
        reportAreas();
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

// SAINT's helper windows (the avatar, notices, the plan, the Halo, the mini player) never take the keyboard when
// they appear: on Wayland Qt's "don't activate" hints don't reach KWin, so the avatar popping up while you typed in
// the Store's search box got your typing. If KWin focuses one as it's mapped, focus goes straight back to the window
// you were using - on this desktop only, never switching you to another one. The overlay is the exception: it opens
// because you asked for it, to type in. A click on a helper later (dragging the avatar) is left alone.
const NO_FOCUS_MS = 1500;
const shownAt = {};
let userWindow = null;

function decorative(w) {
    const caption = String((w && w.caption) || "");
    return !!w && w.resourceClass === "saint" && caption.indexOf("SAINT overlay") !== 0 &&
           (caption.indexOf(MARK) >= 0 || caption.indexOf(HELPER) >= 0);
}

function guardFocus(w) {
    if (!w) {
        return;
    }
    if (!decorative(w)) {
        if (w.normalWindow || w.dialog) {
            userWindow = w;
        }
        return;
    }
    const since = Date.now() - (shownAt[String(w.internalId)] || 0);
    if (since > NO_FOCUS_MS || !userWindow || userWindow === w || userWindow.minimized ||
            workspace.windowList().indexOf(userWindow) < 0 || !onThisDesktop(userWindow)) {
        return;
    }
    workspace.activeWindow = userWindow;
}

function watch(w) {
    if (w && w.pid && w.normalWindow) {
        lastAdded[w.pid] = Date.now();
    }
    if (w && w.resourceClass === "saint") {
        shownAt[String(w.internalId)] = Date.now();
        if (w === workspace.activeWindow) {
            guardFocus(w);
        }
    }
    place(w);
    watchAvatar(w);
    w.captionChanged.connect(function () { place(w); watchAvatar(w); });
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
    workspace.windowActivated.connect(guardFocus);
    workspace.windowActivated.connect(activated);
}
if (workspace.cursorPosChanged) {
    workspace.cursorPosChanged.connect(sendCursor);
}
if (workspace.screensChanged) {
    workspace.screensChanged.connect(function () { if (avatarWin) reportAreas(); });
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
