// HalOS living wallpaper: a colour or gradient, and the SAINT logo where you put it, glowing and moving with
//   saint      SAINT's voice: listening, thinking, speaking (ws://127.0.0.1:47811, core/state_socket.py)
//   desktop    whatever is playing on the PC (ws://127.0.0.1:47812/desktop, core/audio_feed.py)
//   mic        the microphone (ws://127.0.0.1:47812/mic)
//   breathing  a slow pulse, no input
//   still      nothing moves and nothing redraws
// One Timer drives every animation at the chosen frame rate (Fps), and only while something can move; the audio
// feed only captures while a wallpaper is connected to it. Settings: ui/settings_pages/wallpaper.py.
import QtQuick
import QtQuick.Effects
import QtWebSockets
import org.kde.plasma.plasmoid

WallpaperItem {
    id: root
    clip: true

    readonly property var cfg: root.configuration
    readonly property string source: cfg.Source || "saint"
    readonly property real side: Math.min(width, height)
    readonly property real logoSize: side * (cfg.LogoScale || 0.28)
    readonly property color accent: cfg.Accent || "#feaa34"
    readonly property int bands: 32

    // targets from the feeds, and what is shown (eased toward the targets on each frame)
    property real targetLevel: 0
    property var targetBands: []
    property real level: 0
    property var shown: []
    property string saintState: "idle"
    property real clock: 0

    readonly property bool moving: source === "breathing" || source === "desktop" || source === "mic"
                                   || (source === "saint" && saintState !== "idle" && saintState !== "offline")

    // ---------------------------------------------------------------- background
    Rectangle { anchors.fill: parent; color: root.cfg.Color || "#0a0b0d" }
    Rectangle {
        visible: root.cfg.Background === "gradient"
        width: Math.hypot(root.width, root.height); height: width
        anchors.centerIn: parent
        rotation: root.cfg.Angle || 0
        gradient: Gradient {
            GradientStop { position: 0; color: root.cfg.Color || "#0a0b0d" }
            GradientStop { position: 1; color: root.cfg.Color2 || "#2a1a08" }
        }
    }

    // ---------------------------------------------------------------- the logo and its visualizer
    Item {
        id: mark
        visible: root.cfg.ShowLogo !== false
        width: root.logoSize; height: width
        x: (root.cfg.LogoX === undefined ? 0.5 : root.cfg.LogoX) * root.width - width / 2
        y: (root.cfg.LogoY === undefined ? 0.5 : root.cfg.LogoY) * root.height - height / 2

        Repeater {
            model: root.cfg.Bars === false ? 0 : root.bands
            Rectangle {
                readonly property real v: root.shown.length > index ? root.shown[index] : 0
                width: Math.max(2, mark.width * 0.025)
                height: mark.width * (0.03 + 0.32 * v)
                radius: width / 2
                color: root.accent
                opacity: 0.35 + 0.65 * v
                x: mark.width / 2 - width / 2
                y: -mark.width * 0.06 - height
                transform: Rotation { origin.x: width / 2; origin.y: mark.width * 0.56 + height; angle: index * 360 / root.bands }
            }
        }

        Image {
            id: logo
            anchors.centerIn: parent
            width: parent.width; height: width
            source: "file:///usr/share/icons/hicolor/512x512/apps/saint.png"
            fillMode: Image.PreserveAspectFit
            smooth: true
            mipmap: true
            scale: 1 + root.level * 0.12 * (root.cfg.Sensitivity || 1)
            visible: false
        }
        MultiEffect {
            source: logo
            anchors.fill: logo
            scale: logo.scale
            shadowEnabled: (root.cfg.Glow || 0) > 0
            shadowColor: root.accent
            shadowBlur: 1.0
            shadowScale: 1.0 + 0.15 * (root.cfg.Glow || 0) + 0.25 * root.level
            shadowOpacity: Math.min(1, (root.cfg.Glow || 0) * (0.6 + root.level))
            shadowHorizontalOffset: 0
            shadowVerticalOffset: 0
        }
    }

    // ---------------------------------------------------------------- one clock for everything that moves
    Timer {
        interval: Math.round(1000 / Math.max(5, Math.min(60, root.cfg.Fps || 30)))
        repeat: true
        running: root.moving || root.level > 0.002
        onTriggered: {
            var dt = interval / 1000;
            root.clock += dt;
            var sens = root.cfg.Sensitivity || 1;
            var target = root.targetLevel;
            if (root.source === "breathing")
                target = 0.35 + 0.35 * Math.sin(root.clock * 2 * Math.PI / 5);    // one breath every 5 s
            else if (root.source === "saint" && root.saintState === "processing")
                target = 0.3 + 0.2 * Math.sin(root.clock * 6);
            root.level += (Math.min(1, target * sens) - root.level) * 0.35;
            var out = [];
            for (var i = 0; i < root.bands; i++) {
                var t;
                if (root.targetBands.length)
                    t = root.targetBands[Math.floor(i * root.targetBands.length / root.bands)] * sens;
                else
                    t = root.level * (0.6 + 0.4 * Math.sin(root.clock * 3 + i * 0.7));
                var prev = root.shown.length > i ? root.shown[i] : 0;
                out.push(prev + (Math.min(1, Math.max(0, t)) - prev) * 0.4);
            }
            root.shown = out;
        }
    }

    // ---------------------------------------------------------------- feeds
    WebSocket {
        id: stateFeed
        url: "ws://127.0.0.1:47811/"
        active: root.source === "saint"
        onTextMessageReceived: function (message) {
            try {
                var m = JSON.parse(message);
                root.saintState = m.state || "idle";
                root.targetLevel = Math.max(0, Math.min(1, m.level || 0));
            } catch (e) {}
        }
        onStatusChanged: if (status === WebSocket.Error || status === WebSocket.Closed) { root.saintState = "idle"; root.targetLevel = 0; retry.start(); }
    }
    WebSocket {
        id: audioFeed
        url: "ws://127.0.0.1:47812/" + (root.source === "mic" ? "mic" : "desktop")
        active: root.source === "desktop" || root.source === "mic"
        onTextMessageReceived: function (message) {
            try {
                var m = JSON.parse(message);
                root.targetLevel = Math.max(0, Math.min(1, m.level || 0));
                root.targetBands = m.bands || [];
            } catch (e) {}
        }
        onStatusChanged: if (status === WebSocket.Error || status === WebSocket.Closed) { root.targetLevel = 0; root.targetBands = []; retry.start(); }
    }
    Timer {
        id: retry
        interval: 5000
        onTriggered: {
            if (root.source === "saint") { stateFeed.active = false; stateFeed.active = true; }
            if (root.source === "desktop" || root.source === "mic") { audioFeed.active = false; audioFeed.active = true; }
        }
    }
}
