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
    property real hop: 0            // a clip's jump 0..1 (hop, cheer, climb) and size pulse (pop-in): Python sets them
    property real popScale: 1
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

    property real armDown: 68       // degrees: lowers a VRoid model's arms from its T-pose

    // face: name -> [MorphTarget …] (each mesh has its own copy); Python sets `faceWeights` every frame
    property var morphMap: ({})
    property var faceWeights: ({})
    property var lastFace: []
    property int morphCount: 0
    property bool vroid: false
    // body: Python sends {bone: [w, x, y, z]} (parent-frame rotation) every frame; applied on the rest rotation
    property var boneMap: ({})
    property var restMap: ({})
    property int boneCount: 0
    property var bodyRot: ({})
    onBodyRotChanged: {
        var names = Object.keys(bodyRot)
        for (var i = 0; i < names.length; ++i) {
            var n = boneMap[names[i]]
            if (!n) continue
            var q = bodyRot[names[i]]
            n.rotation = Qt.quaternion(q[0], q[1], q[2], q[3]).times(restMap[names[i]])
        }
    }
    // full body or head-and-shoulders, and the task props drawn around her
    property string view: "portrait"
    property bool props: true
    property string activity: "idle"
    property string taskTitle: ""
    property var taskSteps: []
    property int taskIndex: -1
    onFaceWeightsChanged: {
        var names = Object.keys(faceWeights)
        for (var i = 0; i < lastFace.length; ++i)
            if (!(lastFace[i] in faceWeights)) setMorph(lastFace[i], 0)
        for (var j = 0; j < names.length; ++j) setMorph(names[j], faceWeights[names[j]])
        lastFace = names
    }
    function setMorph(name, w) {
        var list = morphMap[name]
        if (list) for (var i = 0; i < list.length; ++i) list[i].weight = w
    }
    function indexMorphs(node) {
        if (!node) return
        if (node.morphTargets !== undefined) {
            for (var i = 0; i < node.morphTargets.length; ++i) {
                var mt = node.morphTargets[i]
                mt.weight = 0                                   // balsam starts every target at 1
                if (!morphMap[mt.objectName]) morphMap[mt.objectName] = []
                morphMap[mt.objectName].push(mt)
                morphCount++
                if (mt.objectName.indexOf("Fcl_") === 0) vroid = true
            }
        }
        if (node.objectName === "J_Bip_C_Head") headY = node.scenePosition.y + 0.06
        if (node.objectName && node.objectName.indexOf("J_Bip_") === 0) {
            boneMap[node.objectName] = node
            var r = node.rotation                              // a copy: a stored value-type reference would
            restMap[node.objectName] = Qt.quaternion(r.scalar, r.x, r.y, r.z)   // follow the bone and compound
            boneCount++
        }
        for (var k = 0; k < node.children.length; ++k) indexMorphs(node.children[k])
    }

    function applyLook(node) {
        // Hologram: every model gets its own hologram material carrying its texture; the mouth interior is
        // hidden (it would show through); the arms come down. Realistic: the model is left as it is.
        if (!node) return
        var name = node.objectName || ""
        if (!root.usesComponent && (name === "J_Bip_L_UpperArm" || name === "J_Bip_R_UpperArm")) {
            // an imported VRoid model has no body driver: just bring its T-pose arms down
            var e = node.eulerRotation
            node.eulerRotation = Qt.vector3d(e.x, e.y, e.z + (name === "J_Bip_L_UpperArm" ? -root.armDown : root.armDown))
        }
        if (!root.hologram) {
            for (var j = 0; j < node.children.length; ++j) applyLook(node.children[j])
            return
        }
        if (node.materials !== undefined && node.source !== undefined) {
            if (/teeth|tongue/.test(name)) node.visible = false
            var mats = []                                      // one hologram material per part (VRoid meshes
            for (var i = 0; i < Math.max(1, node.materials.length); ++i) {   // have one per body/clothes/hair part)
                var old = node.materials.length ? node.materials[i] : null
                var m = holoComp.createObject(node)
                if (old && old.baseColorMap) m.baseMap.texture = old.baseColorMap
                mats.push(m)
            }
            node.materials = mats
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
            cullMode: Material.NoCulling          // VRoid clothes are often single-sided
            fragmentShader: "hologram.frag"
            property TextureInput baseMap: TextureInput { texture: whiteTex }
            property color uTint: root.tint
            property real uTime: root.t
            property real uCutY: root.view === "full" ? -10.0 : root.cutY
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
            position: root.usesComponent && root.view === "full"
                      ? Qt.vector3d(0, (root.headY + 0.1) * 0.52, (root.headY + 0.1) * 2.15)
                      : root.usesComponent
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
            y: root.hop * 0.10
            scale: Qt.vector3d(root.popScale, root.popScale * (1 + (root.motion ? Math.sin(root.t * 1.6) * 0.004 : 0)),
                               root.popScale)

            Loader3D { id: scene; active: root.usesComponent; source: root.component
                       onLoaded: { root.morphMap = {}; root.morphCount = 0; root.boneMap = {}; root.restMap = {}; root.boneCount = 0
                                   root.indexMorphs(item); root.applyLook(item) } }
            RuntimeLoader { id: loader; source: root.usesComponent ? "" : root.source
                            onStatusChanged: if (status === RuntimeLoader.Success) root.applyLook(loader) }
        }

        // the projector: a dark disc with glowing, pulsing rings
        Node {
            id: pedestal
            visible: root.hologram
            y: root.view === "full" ? -0.03 : root.cutY - 0.22
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

    // ---- task props: 2D layer over the 3D view, in the accent colour, shown for the current activity
    Item {
        id: hud
        anchors.fill: parent
        visible: root.props && root.usesComponent
        property color c: root.tint
        property bool full: root.view === "full"
        // rough screen anchors for her head and hands in each framing
        property real headX: width * 0.5
        property real headYpx: full ? height * 0.13 : height * 0.30
        property real handsYpx: full ? height * 0.50 : height * 0.95

        component Glass: Rectangle {
            radius: 8; color: Qt.rgba(0.04, 0.05, 0.07, 0.72)
            border.color: Qt.rgba(hud.c.r, hud.c.g, hud.c.b, 0.65); border.width: 1
            Behavior on opacity { NumberAnimation { duration: 350 } }
        }

        // working: a floating screen of scrolling code above a glowing keyboard under her hands
        Glass {
            id: screen
            opacity: root.activity === "working" ? 1 : 0; visible: opacity > 0.01
            width: hud.width * 0.4; height: hud.full ? hud.height * 0.15 : hud.height * 0.3
            x: hud.width * 0.58; y: hud.handsYpx - height - hud.height * 0.1    // beside her, not in front
            clip: true
            Column {
                id: code
                x: 10; spacing: 3
                y: 8 - ((root.t * 22) % (lines.count * 9))
                Repeater {
                    id: lines
                    model: 24
                    Rectangle {
                        height: 6; radius: 3
                        width: (screen.width - 20) * (0.25 + ((index * 37) % 60) / 100)
                        x: ((index * 13) % 4) * 12
                        color: Qt.rgba(hud.c.r, hud.c.g, hud.c.b, index % 5 === 0 ? 0.95 : 0.45)
                    }
                }
            }
        }
        Rectangle {
            opacity: root.activity === "working" ? 0.9 : 0; visible: opacity > 0.01
            Behavior on opacity { NumberAnimation { duration: 350 } }
            width: hud.width * 0.5; height: 6; radius: 3
            x: (hud.width - width) / 2; y: hud.handsYpx + 6
            color: hud.c
            layer.enabled: true
        }

        // planning: the plan's steps as cards on her right (your left), the current one lit
        Column {
            opacity: root.activity === "planning" && root.taskSteps.length ? 1 : 0; visible: opacity > 0.01
            Behavior on opacity { NumberAnimation { duration: 350 } }
            spacing: 6
            x: hud.width * 0.03; y: hud.headYpx
            width: hud.width * 0.34
            Repeater {
                model: Math.min(4, root.taskSteps.length)
                Glass {
                    property int stepIndex: Math.max(0, Math.min(root.taskIndex - 1, root.taskSteps.length - 4)) + index
                    width: parent.width; height: label.implicitHeight + 12
                    border.width: stepIndex === root.taskIndex ? 2 : 1
                    opacity: stepIndex < root.taskIndex ? 0.55 : 1
                    Text {
                        id: label
                        x: 8; y: 6; width: parent.width - 16
                        text: (stepIndex < root.taskIndex ? "✓ " : (stepIndex + 1) + ". ") + (root.taskSteps[stepIndex] || "")
                        color: stepIndex === root.taskIndex ? hud.c : "#d8dbe2"
                        font.pixelSize: Math.max(9, hud.width * 0.035); elide: Text.ElideRight
                    }
                }
            }
        }

        // thinking: three dots orbiting above her head
        Repeater {
            model: 3
            Rectangle {
                opacity: root.activity === "thinking" ? 0.9 : 0; visible: opacity > 0.01
                Behavior on opacity { NumberAnimation { duration: 300 } }
                width: 8; height: 8; radius: 4; color: hud.c
                x: hud.headX + Math.cos(root.t * 2.4 + index * 2.09) * hud.width * 0.12 - 4
                y: hud.headYpx - hud.height * (hud.full ? 0.08 : 0.2) + Math.sin(root.t * 2.4 + index * 2.09) * 6
            }
        }

        // listening / speaking: sound rings beside her head that follow the level
        Repeater {
            model: 3
            Rectangle {
                opacity: (root.activity === "listening" || root.activity === "speaking") ? (0.7 - index * 0.2) : 0
                visible: opacity > 0.01
                Behavior on opacity { NumberAnimation { duration: 300 } }
                property real r: hud.width * (0.05 + index * 0.035) * (1 + root.level * 1.5)
                width: 2 * r; height: 2 * r; radius: r
                x: hud.headX + hud.width * 0.2 - r; y: hud.headYpx - r
                color: "transparent"; border.color: hud.c; border.width: 2
            }
        }

        // success / warning / error: a badge by her head
        Rectangle {
            property string kind: root.activity
            opacity: (kind === "success" || kind === "warning" || kind === "error") ? 1 : 0; visible: opacity > 0.01
            Behavior on opacity { NumberAnimation { duration: 250 } }
            width: hud.width * 0.13; height: width; radius: width / 2
            x: hud.headX - hud.width * 0.3; y: hud.headYpx - height
            scale: 1 + 0.06 * Math.sin(root.t * 6)
            color: kind === "success" ? "#2e9d5b" : kind === "warning" ? "#d99a1e" : "#d04545"
            Text { anchors.centerIn: parent; color: "white"; font.bold: true; font.pixelSize: parent.width * 0.55
                   text: parent.kind === "success" ? "✓" : "!" }
        }

        // caption: what she is doing right now
        Glass {
            opacity: root.taskTitle !== "" && root.activity !== "idle" && root.activity !== "offline" ? 1 : 0
            visible: opacity > 0.01
            width: Math.min(hud.width - 16, caption.implicitWidth + 20); height: caption.implicitHeight + 10
            x: (hud.width - width) / 2; y: hud.height - height - 6
            Text { id: caption; anchors.centerIn: parent; text: root.taskTitle; color: "#e8eaf0"
                   font.pixelSize: Math.max(9, hud.width * 0.036); elide: Text.ElideRight
                   width: Math.min(implicitWidth, hud.width - 36) }
        }
    }
}
