// SAINT star (KWin scripted effect): SAINT's motion for every window. What plays for each event is a preset:
//   OpenAnim, CloseAnim, MinimizeAnim, DesktopAnim in kwinrc [Effect-saint-star] (declared in
//   contents/config/main.xml: readConfig only sees keys declared there), each a JSON document that Control
//   Center's Animations page writes (schema: core/window_anim.py). Empty or invalid: the built-in below.
//   A preset is keyframe segments played one after another; KWin multiplies overlapping animations of one
//   property, so a segment starts only when the previous one has ended (effect.animationEnded).
//
//   The default close is Fold away: the window swells a little, then shrinks to nothing with a slight turn
//   while it flashes bright. Supernova pulls the window inward, then bursts it outward and fades. The
//   "Star burst" preset collapses the window to a point instead and has SAINT paint a burst there
//   (ui/supernova.py), asked by the saint-shell script: a scripted effect can't draw or use D-Bus.
//
// Rotation is a turn in the screen's plane (Qt::ZAxis) and scale moves both axes together; KWin's defaults
// (X-axis rotation) made the star close fold on one axis only and the opening show half a window.
//
// Only real opens and closes animate. An app that swaps one window for another (a tab dragged out into its
// own window or dropped back, a player re-making its window for fullscreen), a fullscreen window, and a window
// the user is dragging are none of those; and an animation still running when its window is maximised, made
// fullscreen or dragged stops there.
//
// Reduced motion:
//   - Plasma's animation speed (System Settings -> Animation speed) scales every duration (animationTime);
//     "Instant" makes it 0, and then the effect does nothing at all: no grab, no flash, windows just appear.
//   - [Effect-saint-star] ReducedMotion=true in kwinrc (or a speed slider set very fast, under 100 ms)
//     keeps a short plain fade only: no spin, no zoom, no brightness flash.
"use strict";

var BASE_MS = 280;
var REDUCED_BELOW_MS = 100;
// Screen-capture tools: their selection overlay and the window that flashes up after a copy or save must not
// animate (it showed as a window opening and closing, and as bursts while picking a region).
var CAPTURE = /spectacle|flameshot|ksnip|gnome-screenshot|xdg-desktop-portal/i;
var PLACED = "SAINT:place:";       // SAINT's helper windows (Halo, burst, notices) never animate themselves
var REPLACE_MS = 400;              // one app's window going as another arrives within this: a swap, not open/close

var Z_AXIS = 2;                    // Qt::ZAxis
var PROPERTIES = { scale: Effect.Scale, opacity: Effect.Opacity, brightness: Effect.Brightness, rotation: Effect.Rotation };
var CURVES = {
    Linear: QEasingCurve.Linear, InQuad: QEasingCurve.InQuad, OutQuad: QEasingCurve.OutQuad,
    InOutQuad: QEasingCurve.InOutQuad, InCubic: QEasingCurve.InCubic, OutCubic: QEasingCurve.OutCubic,
    InOutCubic: QEasingCurve.InOutCubic, InBack: QEasingCurve.InBack, OutBack: QEasingCurve.OutBack
};

// Kept equal to core/window_anim.py's defaults by tests/test_halos_desktop.py.
var BUILTIN = {
    OpenAnim: { duration: 280, segments: [
        { span: 1, curve: "OutBack", curves: { opacity: "OutQuad" }, scale: [0.55, 1], rotation: [-18, 0],
          opacity: [0, 1], brightness: [1.7, 1] }
    ] },
    CloseAnim: { duration: 460, segments: [
        { span: 0.25, curve: "OutQuad", scale: [1, 1.06], brightness: [1, 1.3], rotation: [0, 0], opacity: [1, 1] },
        { span: 0.75, curve: "InCubic", curves: { opacity: "InQuad" }, scale: [1.06, 0], brightness: [1.3, 2.4],
          rotation: [0, 14], opacity: [1, 0] }
    ] },
    MinimizeAnim: null,            // Plasma's own (squash) until a preset is chosen
    DesktopAnim: { duration: 280, segments: [
        { span: 1, curve: "OutCubic", scale: [0.94, 1], brightness: [1.35, 1] }
    ] }
};
var FADE_IN = { duration: BASE_MS, segments: [{ span: 1, curve: "OutQuad", opacity: [0, 1] }] };
var FADE_OUT = { duration: BASE_MS, segments: [{ span: 1, curve: "InQuad", opacity: [1, 0] }] };

// A configured preset, or the fallback if it's empty or broken. Python validated it before writing it;
// this guards against a hand-edited kwinrc.
function parsePreset(text, fallback) {
    if (!text || text === "undefined") {
        return fallback;
    }
    try {
        var p = JSON.parse(text);
        if (typeof p.duration !== "number" || !(p.duration >= 0) || !Array.isArray(p.segments)) {
            throw new Error("needs duration and segments");
        }
        p.segments.forEach(function (s) {
            if (!(s.span > 0) || !(s.curve in CURVES)) {
                throw new Error("bad segment");
            }
            Object.keys(PROPERTIES).forEach(function (k) {
                if (s[k] !== undefined && !(Array.isArray(s[k]) && s[k].length === 2 && isFinite(s[k][0]) && isFinite(s[k][1]))) {
                    throw new Error("bad " + k);
                }
            });
        });
        return p;
    } catch (e) {
        console.warn("saint-star: ignoring a bad preset: " + e);
        return fallback;
    }
}

function reversed(segments) {
    return segments.slice().reverse().map(function (s) {
        var r = { span: s.span, curve: s.curve, curves: s.curves };
        Object.keys(PROPERTIES).forEach(function (k) {
            if (s[k]) {
                r[k] = [s[k][1], s[k][0]];
            }
        });
        return r;
    });
}

function on(object, signal, handler) {
    if (object && object[signal] && object[signal].connect) {
        object[signal].connect(handler);
        return true;
    }
    return false;
}

var saintStar = {
    duration: 0,
    reduced: false,
    presets: {},
    lastOpened: {},                // pid -> { t, w }: the app's newest ordinary window
    lastClosed: {},

    // An app swapping windows: an ordinary window of the same process came or went a moment ago.
    swapped: function (w, others) {
        var other = w.pid && w.normalWindow ? others[w.pid] : null;
        return other && Date.now() - other.t < REPLACE_MS ? other : null;
    },

    note: function (w, into) {
        if (w.pid && w.normalWindow) {
            into[w.pid] = { t: Date.now(), w: w };
        }
    },

    realOpen: function (w) {
        var gone = saintStar.swapped(w, saintStar.lastClosed);
        saintStar.note(w, saintStar.lastOpened);
        if (gone) {
            try {
                saintStar.stop(gone.w);       // the window it replaces must not linger as a close animation
            } catch (e) {
                // already destroyed
            }
            return false;
        }
        return !w.fullScreen;
    },

    realClose: function (w) {
        var came = saintStar.swapped(w, saintStar.lastOpened);
        saintStar.note(w, saintStar.lastClosed);
        return !came && !w.fullScreen && !w.saintMoving && !w.move && !w.resize;
    },

    // Maximised, fullscreen or dragged while still animating: the animation ends there. A closing window is left
    // to finish.
    // An app that opens its window maximised maximises it a moment after it appears: that must not cut the
    // opening short (it did, and windows stopped halfway open). Dragging or going fullscreen still stops it.
    stateChanged: function (w, maximised) {
        if (w.saintRun && !w.deleted && !(maximised && w.saintRun.kind === "open")) {
            saintStar.stop(w);
        }
    },

    loadConfig: function () {
        saintStar.duration = animationTime(BASE_MS);
        saintStar.reduced = String(effect.readConfig("ReducedMotion", false)) === "true" ||
                            (saintStar.duration > 0 && saintStar.duration < REDUCED_BELOW_MS);
        Object.keys(BUILTIN).forEach(function (key) {
            saintStar.presets[key] = parsePreset(String(effect.readConfig(key, "")), BUILTIN[key]);
        });
    },

    eligible: function (w) {
        // Ordinary app windows and dialogs; not panels, menus, tooltips, notifications or the lock screen.
        return saintStar.duration > 0 &&
               (w.normalWindow || w.dialog) && !w.isOutline && !w.skipsCloseAnimation &&
               !CAPTURE.test(String(w.windowClass || "")) &&
               String(w.caption || "").indexOf(PLACED) < 0;
    },

    animated: function (w) {
        return saintStar.eligible(w) && w.visible;
    },

    // ---- playing segments one after another
    play: function (w, duration, segments, kind) {
        saintStar.stop(w);
        w.saintRun = { total: animationTime(duration), segments: segments, index: -1, pending: 0, ids: null,
                       kind: kind || "", closing: kind === "close" };
        saintStar.nextSegment(w);
    },

    nextSegment: function (w) {
        var run = w.saintRun;
        run.index++;
        if (run.index >= run.segments.length) {
            w.saintRun = null;
            return;
        }
        var s = run.segments[run.index];
        var animations = [];
        Object.keys(PROPERTIES).forEach(function (k) {
            if (s[k]) {
                var a = { type: PROPERTIES[k], from: s[k][0], to: s[k][1] };
                if (k === "scale") {
                    // Both axes spelled out: the window grows and shrinks as a whole, never along one side only.
                    a.from = { value1: s[k][0], value2: s[k][0] };
                    a.to = { value1: s[k][1], value2: s[k][1] };
                } else if (k === "rotation") {
                    // AnimationEffect rotates about Qt::XAxis (0) unless told otherwise: a 3D hinge that squashed the
                    // window on one axis and showed half of it while opening. The presets mean a turn in the
                    // screen's plane, which is Qt::ZAxis.
                    a.axis = Z_AXIS;
                }
                if (s.curves && CURVES[s.curves[k]] !== undefined) {
                    a.curve = CURVES[s.curves[k]];
                }
                animations.push(a);
            }
        });
        if (animations.length === 0) {
            saintStar.nextSegment(w);
            return;
        }
        run.pending = animations.length;
        run.ids = animate({
            window: w,
            duration: Math.max(1, Math.round(run.total * s.span)),
            curve: CURVES[s.curve],
            keepAlive: run.closing,    // only a closed window has to be kept until its animation ends
            animations: animations
        });
    },

    ended: function (w) {
        var run = w.saintRun;
        if (run && --run.pending <= 0) {
            saintStar.nextSegment(w);
        }
    },

    stop: function (w) {
        var run = w.saintRun;
        w.saintRun = null;
        if (run && run.ids) {
            cancel(run.ids);
        }
    },

    // ---- events
    opened: function (w) {
        if (!saintStar.animated(w) || effects.hasActiveFullScreenEffect || !saintStar.realOpen(w)) {
            return;
        }
        var p = saintStar.reduced ? FADE_IN : saintStar.presets.OpenAnim;
        if (p && p.segments.length) {
            w.setData(Effect.WindowAddedGrabRole, effect);
            saintStar.play(w, p.duration, p.segments, "open");
        }
    },

    closed: function (w) {
        if (!saintStar.animated(w) || effects.hasActiveFullScreenEffect) {
            return;
        }
        if (!saintStar.realClose(w)) {
            saintStar.stop(w);
            return;
        }
        var p = saintStar.reduced ? FADE_OUT : saintStar.presets.CloseAnim;
        if (p && p.segments.length) {
            w.setData(Effect.WindowClosedGrabRole, effect);
            saintStar.play(w, p.duration, p.segments, "close");
        } else {
            saintStar.stop(w);
        }
    },

    minimizedChanged: function (w) {
        var p = saintStar.presets.MinimizeAnim;
        if (!p || !p.segments.length || !saintStar.eligible(w) || effects.hasActiveFullScreenEffect) {
            return;                 // Plasma's own minimize animation, or none
        }
        var segments = saintStar.reduced ? FADE_OUT.segments : p.segments;
        saintStar.play(w, saintStar.reduced ? BASE_MS : p.duration, w.minimized ? segments : reversed(segments));
    },

    desktopSwitched: function () {
        if (saintStar.reduced || saintStar.duration <= 0) {
            return;                 // Plasma's own desktop switch animation is enough
        }
        var p = saintStar.presets.DesktopAnim;
        if (!p || !p.segments.length) {
            return;
        }
        var windows = effects.stackingOrder;
        for (var i = 0; i < windows.length; i++) {
            var w = windows[i];
            if (saintStar.animated(w)) {       // w.visible: on the current desktop and not minimized
                saintStar.play(w, p.duration, p.segments);
            }
        }
    },

    watch: function (w) {
        on(w, "minimizedChanged", function () { saintStar.minimizedChanged(w); });
        on(w, "windowStartUserMovedResized", function () { w.saintMoving = true; saintStar.stateChanged(w); });
        on(w, "windowFinishUserMovedResized", function () { w.saintMoving = false; });
        on(w, "windowMaximizedStateChanged", function () { saintStar.stateChanged(w, true); });
        on(w, "windowFullScreenChanged", function () { saintStar.stateChanged(w); });
    },

    init: function () {
        saintStar.loadConfig();
        effect.configChanged.connect(saintStar.loadConfig);       // also fires when the speed slider moves
        effect.animationEnded.connect(saintStar.ended);
        effects.stackingOrder.forEach(saintStar.watch);
        effects.windowAdded.connect(function (w) {
            saintStar.watch(w);
            saintStar.opened(w);
        });
        effects.windowClosed.connect(saintStar.closed);
        effects.desktopChanged.connect(saintStar.desktopSwitched);
    }
};

saintStar.init();
