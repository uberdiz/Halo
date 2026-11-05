// SAINT star (KWin scripted effect): SAINT's motion for every window.
//   open   a bright burst that expands and turns into place
//   close  spins down to a point with a flash, like a star going out
//   virtual desktop switch  the arriving windows zoom in with a short glow (Plasma's slide still runs)
//
// Reduced motion:
//   - Plasma's animation speed (System Settings -> Animation speed) scales every duration (animationTime);
//     "Instant" makes it 0, and then the effect does nothing at all: no grab, no flash, windows just appear.
//   - [Effect-saint-star] ReducedMotion=true in kwinrc (or a speed slider set very fast, under 100 ms)
//     keeps a short plain fade only: no spin, no zoom, no brightness flash.
"use strict";

var BASE_MS = 280;
var REDUCED_BELOW_MS = 100;

var saintStar = {
    duration: 0,
    reduced: false,

    loadConfig: function () {
        saintStar.duration = animationTime(BASE_MS);
        saintStar.reduced = String(effect.readConfig("ReducedMotion", false)) === "true" ||
                            (saintStar.duration > 0 && saintStar.duration < REDUCED_BELOW_MS);
    },

    animated: function (w) {
        // Ordinary app windows and dialogs; not panels, menus, tooltips, notifications or the lock screen.
        return saintStar.duration > 0 &&
               (w.normalWindow || w.dialog) && !w.isOutline && !w.skipsCloseAnimation && w.visible;
    },

    opened: function (w) {
        if (!saintStar.animated(w) || effects.hasActiveFullScreenEffect) {
            return;
        }
        w.setData(Effect.WindowAddedGrabRole, effect);
        w.saintOpen = animate({
            window: w,
            duration: saintStar.duration,
            curve: saintStar.reduced ? QEasingCurve.OutQuad : QEasingCurve.OutBack,
            animations: saintStar.reduced ? [
                { type: Effect.Opacity, from: 0.0, to: 1.0 }
            ] : [
                { type: Effect.Scale, from: 0.55, to: 1.0 },
                { type: Effect.Rotation, from: -18, to: 0 },
                { type: Effect.Opacity, from: 0.0, to: 1.0, curve: QEasingCurve.OutQuad },
                { type: Effect.Brightness, from: 1.7, to: 1.0 }
            ]
        });
    },

    closed: function (w) {
        if (!saintStar.animated(w) || effects.hasActiveFullScreenEffect) {
            return;
        }
        if (w.saintOpen) {
            cancel(w.saintOpen);
            delete w.saintOpen;
        }
        w.setData(Effect.WindowClosedGrabRole, effect);
        animate({
            window: w,
            duration: saintStar.duration,
            curve: QEasingCurve.InQuad,
            animations: saintStar.reduced ? [
                { type: Effect.Opacity, to: 0.0 }
            ] : [
                { type: Effect.Scale, to: 0.0 },
                { type: Effect.Rotation, to: 30 },
                { type: Effect.Opacity, to: 0.0 },
                { type: Effect.Brightness, to: 2.2 }
            ]
        });
    },

    desktopSwitched: function () {
        if (saintStar.reduced || saintStar.duration <= 0) {
            return;                 // Plasma's own desktop switch animation is enough
        }
        var windows = effects.stackingOrder;
        for (var i = 0; i < windows.length; i++) {
            var w = windows[i];
            if (saintStar.animated(w) && w.isOnCurrentDesktop && !w.minimized) {
                animate({
                    window: w,
                    duration: saintStar.duration,
                    curve: QEasingCurve.OutCubic,
                    animations: [
                        { type: Effect.Scale, from: 0.94, to: 1.0 },
                        { type: Effect.Brightness, from: 1.35, to: 1.0 }
                    ]
                });
            }
        }
    },

    init: function () {
        saintStar.loadConfig();
        effect.configChanged.connect(saintStar.loadConfig);       // also fires when the speed slider moves
        effects.windowAdded.connect(saintStar.opened);
        effects.windowClosed.connect(saintStar.closed);
        effects.desktopChanged.connect(saintStar.desktopSwitched);
    }
};

saintStar.init();
