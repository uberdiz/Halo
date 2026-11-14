.pragma library
// The living wallpaper's visualizer maths, kept out of main.qml so it runs under node in tests/.
//   step()     one frame: targets in, shown values out. Neighbouring bands are blended (no lone spikes), rises
//              are quick and falls are slow (a peak decays instead of snapping back), and both are frame-rate
//              independent, so 20 fps and 60 fps look the same, only smoother.
//   bandFor()  which band a bar shows in the "bars" style: low notes in the middle, high ones toward the ends,
//              so the row is symmetric.

var ATTACK = 0.55;     // share of the way to a higher target covered per 1/60 s
var DECAY = 0.10;      // share of the way down per 1/60 s

function ease(rate, dt) {
    return 1 - Math.pow(1 - rate, Math.max(0, dt) * 60);
}

function clamp01(v) {
    return v < 0 ? 0 : v > 1 ? 1 : v;
}

// targets: the band levels the feed sent (any length, may be empty), or null to make them from level and clock.
function step(shown, targets, count, level, clock, dt, sens) {
    var raw = [], out = [], i;
    for (i = 0; i < count; i++) {
        var t;
        if (targets && targets.length)
            t = targets[Math.floor(i * targets.length / count)] * sens;
        else
            t = level * (0.55 + 0.45 * Math.sin(clock * 2.2 + i * 0.55) * Math.sin(clock * 0.9 + i * 0.21));
        raw.push(clamp01(t));
    }
    var up = ease(ATTACK, dt), down = ease(DECAY, dt);
    for (i = 0; i < count; i++) {
        var l = raw[i > 0 ? i - 1 : i], r = raw[i < count - 1 ? i + 1 : i];
        var target = 0.25 * l + 0.5 * raw[i] + 0.25 * r;
        var prev = shown && shown.length > i ? shown[i] : 0;
        out.push(prev + (target - prev) * (target > prev ? up : down));
    }
    return out;
}

function bandFor(i, n, count) {
    if (n <= 1)
        return 0;
    var half = (n - 1) / 2;
    return Math.min(count - 1, Math.floor(Math.abs(i - half) / half * count));
}
