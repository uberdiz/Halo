// SAINT's 3D avatar.
//  - `component`: a balsam-converted QML scene (the default SAINT ships this way). Its MorphTargets are named
//    after the face keys (eyeBlinkLeft, viseme_aa, mouthSmileLeft …) and Python drives their weights.
//  - `source`: any imported .vrm/.glb, loaded at runtime as plain glTF (no scripts; VRM extensions ignored).
//  - `hologram`: draw it as a glowing projection on a pedestal, tinted `tint` (the avatar accent colour);
//    otherwise it is drawn with its own materials.
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
    property bool flip: false       // VRM 0.x faces -Z; VRM 1.0 and plain glTF face +Z
    property bool hologram: false
    property color tint: "#ff9a1f"  // HalOS orange
    property real headY: 1.47       // eye height of the component model, metres (SAINT)
    property real cutY: 1.17        // the bust fades out below this height (above the shirt hem)
    property bool usesComponent: component.toString() !== ""
    property bool failed: usesComponent ? scene.status === Loader.Error : loader.status === RuntimeLoader.Error
    property alias sceneItem: scene.item
    property real t: 0

    NumberAnimation on t { from: 0; to: 1000; duration: 1000000; loops: Animation.Infinite; running: root.motion }

    property real armDown: 62       // degrees: lowers the arms from the A-pose so the hologram reads as a bust

    function applyLook(node) {
        // Hologram: every model gets its own hologram material carrying its texture; the mouth interior is
        // hidden (it would show through); the arms come down. Realistic: the model is left as it is.
        if (!node || !root.hologram) return
        var name = node.objectName || ""
        if (name === "upperarm_l" || name === "upperarm_r") {
            var e = node.eulerRotation
            node.eulerRotation = Qt.vector3d(e.x, e.y, e.z + (name === "upperarm_l" ? -root.armDown : root.armDown))
        }
        if (node.materials !== undefined && node.source !== undefined) {
            if (/teeth|tongue/.test(name)) node.visible = false
            var old = node.materials.length ? node.materials[0] : null
            var m = holoComp.createObject(node)
            if (old && old.baseColorMap) m.baseMap.texture = old.baseColorMap
            node.materials = [m]
        }
        for (var i = 0; i < node.children.length; ++i) applyLook(node.children[i])
    }

    Texture { id: whiteTex; source: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==" }
    Component {
        id: holoComp
        CustomMaterial {
            shadingMode: CustomMaterial.Shaded
            sourceBlend: CustomMaterial.SrcAlpha
            destinationBlend: CustomMaterial.OneMinusSrcAlpha
            depthDrawMode: Material.AlwaysDepthDraw          // opaque above the bust line: nothing shows through
            cullMode: Material.BackFaceCulling
            fragmentShader: "hologram.frag"
            property TextureInput baseMap: TextureInput { texture: whiteTex }
            property color uTint: root.tint
            property real uTime: root.t
            property real uCutY: root.cutY
        }
    }
    View3D {
        anchors.fill: parent
        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
        }
        // soft three-point light (used by the realistic look and the pedestal)
        DirectionalLight { eulerRotation.x: -20; eulerRotation.y: 25; brightness: 1.6 }
        DirectionalLight { eulerRotation.x: -5; eulerRotation.y: -40; brightness: 0.7 }
        DirectionalLight { eulerRotation.x: -15; eulerRotation.y: 180; brightness: 0.6 }

        PerspectiveCamera {
            id: cam
            property var b: loader.bounds
            property real h: b ? b.maximum.y - b.minimum.y : 1.7
            position: root.usesComponent
                      ? (root.hologram ? Qt.vector3d(0, root.headY - 0.16, 1.72) : Qt.vector3d(0, root.headY - 0.05, 0.85))
                      : Qt.vector3d(b ? (b.maximum.x + b.minimum.x) / 2 : 0, b ? b.maximum.y - h * 0.10 : 1.5,
                                    b ? b.maximum.z + h * 0.55 : 1.0)
            eulerRotation.x: root.hologram && root.usesComponent ? -3 : 0
            fieldOfView: 30
            clipNear: 0.01
        }

        Node {
            // idle: slow sway and breathing; speaking adds a small nod with the voice level
            eulerRotation.y: (root.flip ? 180 : 0) + (root.motion ? Math.sin(root.t * 0.5) * 4 : 0)
            eulerRotation.x: root.motion ? root.level * 3 : 0
            scale: Qt.vector3d(1, 1 + (root.motion ? Math.sin(root.t * 1.6) * 0.004 : 0), 1)

            Loader3D { id: scene; active: root.usesComponent; source: root.component
                       onLoaded: root.applyLook(item) }
            RuntimeLoader { id: loader; source: root.usesComponent ? "" : root.source
                            onStatusChanged: if (status === RuntimeLoader.Success) root.applyLook(loader) }
        }

        // the projector: a dark disc with glowing, pulsing rings
        Node {
            id: pedestal
            visible: root.hologram
            y: root.cutY - 0.22
            Model {      // base
                source: "#Cylinder"
                scale: Qt.vector3d(0.0062, 0.0006, 0.0062)
                materials: PrincipledMaterial { baseColor: "#121317"; metalness: 0.3; roughness: 0.7 }
            }
            Model {      // glowing rings on top
                source: "#Rectangle"
                y: 0.031
                eulerRotation.x: -90
                scale: Qt.vector3d(0.0058, 0.0058, 1)
                materials: CustomMaterial {
                    shadingMode: CustomMaterial.Unshaded
                    sourceBlend: CustomMaterial.One
                    destinationBlend: CustomMaterial.One
                    depthDrawMode: Material.NeverDepthDraw
                    cullMode: Material.NoCulling
                    vertexShader: "pad.vert"
                    fragmentShader: "pad.frag"
                    property color uTint: root.tint
                    property real uTime: root.t
                }
            }
        }
    }
}
