// SAINT Visualizer: the living wallpaper's logo and visualizer as a desktop widget on a clear background, so it
// sits over any wallpaper (a picture, a slideshow, Wallpaper Engine). Drag and resize it like any widget.
//   saint      SAINT's voice: listening, thinking, speaking (ws://127.0.0.1:47811, core/state_socket.py)
//   desktop    whatever is playing on the PC (ws://127.0.0.1:47812/desktop, core/audio_feed.py)
//   mic        the microphone (ws://127.0.0.1:47812/mic)
//   breathing  a slow pulse, no input
// visualizer.js is the living wallpaper's own (tests keep the two files equal). One Timer, only while something
// moves and the widget is visible; the audio feed only captures while something is connected to it.
import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import QtWebSockets
import org.kde.kirigami as Kirigami
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasmoid
import "visualizer.js" as Viz

PlasmoidItem {
    id: root

    readonly property var cfg: Plasmoid.configuration
    readonly property string source: cfg.Source || "saint"
    readonly property string barStyle: cfg.BarStyle === "ring" ? "ring" : "bars"
    readonly property color accent: cfg.UseThemeColor ? Kirigami.Theme.highlightColor
                                    : (/^#[0-9a-fA-F]{6}$/.test(cfg.Accent || "") ? cfg.Accent : "#feaa34")
    readonly property int bands: 32
    readonly property int rowBars: 32

    property real targetLevel: 0
    property var targetBands: []
    property real level: 0
    property var shown: []
    property string saintState: "offline"
    property real clock: 0

    readonly property bool moving: source === "breathing" || source === "desktop" || source === "mic"
                                   || (source === "saint" && saintState !== "idle" && saintState !== "offline")

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground | PlasmaCore.Types.ConfigurableBackground
    preferredRepresentation: fullRepresentation
    toolTipMainText: "SAINT Visualizer"
    toolTipSubText: source === "saint" ? (saintState === "offline" ? "SAINT isn't running" : "SAINT: " + saintState)
                    : source === "breathing" ? "A slow breath" : source === "mic" ? "Microphone" : "Music and sound"

    fullRepresentation: Item {
        id: stage
        Layout.minimumWidth: Kirigami.Units.gridUnit * 5
        Layout.minimumHeight: Kirigami.Units.gridUnit * 5
        Layout.preferredWidth: Kirigami.Units.gridUnit * 16
        Layout.preferredHeight: Kirigami.Units.gridUnit * 14

        readonly property real side: Math.min(width, height)
        readonly property bool ring: root.barStyle === "ring"
        readonly property real logoSize: ring ? side * 0.5 : side * 0.48

        Item {
            id: mark
            visible: root.cfg.ShowLogo !== false
            width: stage.logoSize; height: width
            x: (stage.width - width) / 2
            y: stage.ring ? (stage.height - height) / 2 : stage.height * 0.08

            Repeater {
                model: stage.ring ? root.bands : 0
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

        // bars mirrored around a baseline under the logo (or in the middle without it)
        Item {
            id: row
            visible: !stage.ring
            readonly property real maxH: Math.min(stage.height * 0.18, stage.logoSize * 0.4)
            readonly property real pitch: width / root.rowBars
            width: stage.width * 0.9; height: maxH * 2
            x: (stage.width - width) / 2
            y: mark.visible ? mark.y + mark.height + stage.logoSize * 0.06 : (stage.height - height) / 2

            Repeater {
                model: row.visible ? root.rowBars : 0
                Item {
                    readonly property real v: {
                        var b = Viz.bandFor(index, root.rowBars, root.bands);
                        return root.shown.length > b ? root.shown[b] : 0;
                    }
                    readonly property real h: Math.max(row.pitch * 0.5, row.maxH * (0.04 + 0.96 * v))
                    x: index * row.pitch + row.pitch * 0.2
                    width: row.pitch * 0.6; height: row.height
                    Rectangle {
                        width: parent.width; height: parent.h
                        y: row.maxH - height
                        radius: width / 2
                        color: root.accent
                        opacity: 0.45 + 0.55 * parent.v
                    }
                    Rectangle {
                        width: parent.width; height: parent.h * 0.7
                        y: row.maxH + row.pitch * 0.25
                        radius: width / 2
                        color: root.accent
                        opacity: 0.12 + 0.22 * parent.v
                    }
                }
            }
        }
    }

    Timer {
        interval: Math.round(1000 / Math.max(5, Math.min(60, root.cfg.Fps || 30)))
        repeat: true
        running: (root.moving || root.level > 0.002) && Kirigami.Units.longDuration > 0
        onTriggered: {
            var dt = interval / 1000;
            root.clock += dt;
            var sens = root.cfg.Sensitivity || 1;
            var target = root.targetLevel;
            if (root.source === "breathing")
                target = 0.35 + 0.35 * Math.sin(root.clock * 2 * Math.PI / 5);
            else if (root.source === "saint" && root.saintState === "processing")
                target = 0.3 + 0.2 * Math.sin(root.clock * 6);
            root.level += (Math.min(1, target * sens) - root.level) * Viz.ease(0.3, dt);
            root.shown = Viz.step(root.shown, root.targetBands, root.bands, root.level, root.clock, dt, sens);
        }
    }

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
        onStatusChanged: if (status === WebSocket.Error || status === WebSocket.Closed) { root.saintState = "offline"; root.targetLevel = 0; retry.start(); }
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
