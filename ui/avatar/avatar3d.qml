// SAINT's 3D avatar: a .vrm/.glb loaded at runtime as plain glTF (no scripts; VRM extensions are ignored).
// Python sets `source`, `level` (0..1 speech/mic level) and `motion` (false = reduce motion).
// `failed` tells Python to fall back to the 2D picture.
import QtQuick
import QtQuick3D
import QtQuick3D.AssetUtils

Item {
    id: root
    property url source
    property real level: 0
    property bool motion: true
    property bool flip: false     // VRM 0.x faces -Z; VRM 1.0 and plain glTF face +Z
    property bool failed: loader.status === RuntimeLoader.Error
    property real t: 0

    NumberAnimation on t { from: 0; to: 1000; duration: 1000000; loops: Animation.Infinite; running: root.motion }

    View3D {
        anchors.fill: parent
        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
        }
        DirectionalLight { eulerRotation.x: -25; eulerRotation.y: 20; brightness: 1.2 }
        DirectionalLight { eulerRotation.x: -10; eulerRotation.y: 200; brightness: 0.4 }

        // Frame the top of the model (head and shoulders) from its bounds once it has loaded.
        PerspectiveCamera {
            id: cam
            property var b: loader.bounds
            property real h: b ? b.maximum.y - b.minimum.y : 1.7
            position: Qt.vector3d(b ? (b.maximum.x + b.minimum.x) / 2 : 0, b ? b.maximum.y - h * 0.10 : 1.5,
                                  b ? b.maximum.z + h * 0.55 : 1.0)
            fieldOfView: 30
            clipNear: 0.01
        }

        RuntimeLoader {
            id: loader
            source: root.source
            // idle: slow sway and breathing; speaking adds a small nod with the voice level
            eulerRotation.y: (root.flip ? 180 : 0) + (root.motion ? Math.sin(root.t * 0.5) * 6 : 0)
            eulerRotation.x: root.motion ? root.level * 4 : 0
            scale: Qt.vector3d(1, 1 + (root.motion ? Math.sin(root.t * 1.6) * 0.004 : 0), 1)
        }
    }
}
