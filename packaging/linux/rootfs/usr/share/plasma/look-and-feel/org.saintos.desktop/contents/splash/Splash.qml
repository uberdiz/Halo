// HalOS login splash: the HalOS icon on near-black, a thin bar that fills, then the desktop.
// KSplash advances `stage` as Plasma starts (1..6).
import QtQuick

Rectangle {
    id: root
    color: "#0a0b0d"
    property int stage

    Image {
        id: mark
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -root.height * 0.04
        width: Math.min(root.width, root.height) * 0.26
        height: width
        source: "file:///usr/share/icons/hicolor/512x512/apps/halos.png"
        sourceSize.width: 512
        sourceSize.height: 512
        fillMode: Image.PreserveAspectFit
        smooth: true
    }
    Rectangle {
        id: track
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: mark.bottom
        anchors.topMargin: root.height * 0.03
        width: mark.width * 0.8
        height: Math.max(2, root.height / 360)
        radius: height / 2
        color: "#2efeaa34"
        Rectangle {
            width: parent.width * Math.max(0.02, Math.min(1, root.stage / 6))
            height: parent.height
            radius: parent.radius
            color: "#feaa34"
            Behavior on width { NumberAnimation { duration: 240; easing.type: Easing.OutQuad } }
        }
    }
    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: root.height * 0.12
        text: "HalOS"
        color: "#eceef2"
        font.pixelSize: Math.max(18, root.height / 28)
        font.letterSpacing: 6
        font.weight: Font.Light
    }
}
