// SAINT star (KWin scripted effect): SAINT's motion for every window. What plays for each event is a preset:
//   OpenAnim, CloseAnim, MinimizeAnim, DesktopAnim in kwinrc [Effect-saint-star] (declared in
//   contents/config/main.xml: readConfig only sees keys declared there), each a JSON document that Control
//   Center's Animations page writes (schema: core/window_anim.py). Empty or invalid: the built-in below.
//   A preset is keyframe segments played one after another; KWin multiplies overlapping animations of one
//   property, so a segment starts only when the previous one has ended (effect.animationEnded).
//
//   The default close is Supernova: the window swells a little and collapses to a point. The burst itself is
//   painted by SAINT (ui/supernova.py), asked by the saint-shell script: a scripted effect can't draw or use
//   D-Bus. Without SAINT the window still collapses.
//
// Reduced motion:
//   - Plasma's animation speed (System Settings -> Animation speed) scales every duration (animationTime);
//     "Instant" makes it 0, and then the effect does nothing at all: no grab, no flash, windows just appear.
//   - [Effect-saint-star] ReducedMotion=true in kwinrc (or a speed slider set very fast, under 100 ms)
//     keeps a short plain fade only: no spin, no zoom, no brightness flash.
"use strict";

var BASE_MS = 280;
var REDUCED_BELOW_MS = 100;
var PLACED = "SAINT:place:";       // SAINT's helper windows (Halo, burst, notices) never animate themselves

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
    CloseAnim: { duration: 420, burst: true, segments: [
        { span: 0.3, curve: "OutQuad", scale: [1, 1.06], brightness: [1, 1.3], opacity: [1, 1] },
        { span: 0.7, curve: "InCubic", scale: [1.06, 0], brightness: [1.3, 2.4], opacity: [1, 0.85] }
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

var saintStar = {
    duration: 0,
    reduced: false,
    presets: {},

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
               String(w.caption || "").indexOf(PLACED) < 0;
    },

    animated: function (w) {
        return saintStar.eligible(w) && w.visible;
    },

    // ---- playing segments one after another
    play: function (w, duration, segments) {
        saintStar.stop(w);
        w.saintRun = { total: animationTime(duration), segments: segments, index: -1, pending: 0, ids: null };
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
        if (!saintStar.animated(w) || effects.hasActiveFullScreenEffect) {
            return;
        }
        var p = saintStar.reduced ? FADE_IN : saintStar.presets.OpenAnim;
        if (p && p.segments.length) {
            w.setData(Effect.WindowAddedGrabRole, effect);
            saintStar.play(w, p.duration, p.segments);
        }
    },

    closed: function (w) {
        if (!saintStar.animated(w) || effects.hasActiveFullScreenEffect) {
            return;
        }
        var p = saintStar.reduced ? FADE_OUT : saintStar.presets.CloseAnim;
        if (p && p.segments.length) {
            w.setData(Effect.WindowClosedGrabRole, effect);
            saintStar.play(w, p.duration, p.segments);
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

    watchMinimize: function (w) {
        if (w.minimizedChanged) {
            w.minimizedChanged.connect(function () { saintStar.minimizedChanged(w); });
        }
    },

    init: function () {
        saintStar.loadConfig();
        effect.configChanged.connect(saintStar.loadConfig);       // also fires when the speed slider moves
        effect.animationEnded.connect(saintStar.ended);
        effects.stackingOrder.forEach(saintStar.watchMinimize);
        effects.windowAdded.connect(function (w) {
            saintStar.watchMinimize(w);
            saintStar.opened(w);
        });
        effects.windowClosed.connect(saintStar.closed);
        effects.desktopChanged.connect(saintStar.desktopSwitched);
    }
};

saintStar.init();
