// SAINT's 3D avatar.
//  - `component`: a balsam-converted QML scene (the default SAINT ships this way). Its MorphTargets are named
//    after the face keys (eyeBlinkLeft, viseme_aa, mouthSmileLeft …) and Python drives their weights.
//  - `source`: any imported .vrm/.glb, loaded at runtime as plain glTF (no scripts; VRM extensions ignored).
// Python sets `level` (0..1 speech/mic level) and `motion` (false = reduce motion).
// `failed` tells Python to fall back to the 2D picture.
import QtQuick
import QtQuick3D
import QtQuick3D.AssetUtils

Item {
    id: root
    property url source
    property url component
    property real level: 0
    property bool motion: true
    property bool flip: false     // VRM 0.x faces -Z; VRM 1.0 and plain glTF face +Z
    property real headY: 1.47     // eye height of the component model, metres (SAINT)
    property bool usesComponent: component.toString() !== ""
    property bool failed: usesComponent ? scene.status === Loader.Error : loader.status === RuntimeLoader.Error
    property alias sceneItem: scene.item
    property real t: 0

    NumberAnimation on t { from: 0; to: 1000; duration: 1000000; loops: Animation.Infinite; running: root.motion }

    View3D {
        anchors.fill: parent
        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
        }
        // soft three-point light: key, fill, rim
        DirectionalLight { eulerRotation.x: -20; eulerRotation.y: 25; brightness: 1.6 }
        DirectionalLight { eulerRotation.x: -5; eulerRotation.y: -40; brightness: 0.7 }
        DirectionalLight { eulerRotation.x: -15; eulerRotation.y: 180; brightness: 0.6 }

        PerspectiveCamera {
            id: cam
            property var b: loader.bounds
            property real h: b ? b.maximum.y - b.minimum.y : 1.7
            position: root.usesComponent ? Qt.vector3d(0, root.headY - 0.05, 0.85)
                     : Qt.vector3d(b ? (b.maximum.x + b.minimum.x) / 2 : 0, b ? b.maximum.y - h * 0.10 : 1.5,
                                   b ? b.maximum.z + h * 0.55 : 1.0)
            fieldOfView: 30
            clipNear: 0.01
        }

        Node {
            // idle: slow sway and breathing; speaking adds a small nod with the voice level
            eulerRotation.y: (root.flip ? 180 : 0) + (root.motion ? Math.sin(root.t * 0.5) * 4 : 0)
            eulerRotation.x: root.motion ? root.level * 3 : 0
            scale: Qt.vector3d(1, 1 + (root.motion ? Math.sin(root.t * 1.6) * 0.004 : 0), 1)

            Loader3D { id: scene; active: root.usesComponent; source: root.component }
            RuntimeLoader { id: loader; source: root.usesComponent ? "" : root.source }
        }
    }
}
