import QtQuick
import QtQuick3D

Node {
    id: root
    objectName: "Root"

    // Resources
    property url textureData: "maps/textureData.png"
    property url textureData6: "maps/textureData6.png"
    property url textureData152: "maps/textureData152.png"
    property url textureData157: "maps/textureData157.png"
    property url textureData165: "maps/textureData165.png"
    property url textureData171: "maps/textureData171.png"
    property url textureData177: "maps/textureData177.png"
    property url textureData183: "maps/textureData183.png"
    property url textureData189: "maps/textureData189.png"
    Texture {
        id: _1_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData
    }
    Texture {
        id: _0_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData6
    }
    Texture {
        id: _2_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData152
    }
    Texture {
        id: _3_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData157
    }
    Texture {
        id: _4_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData165
    }
    Texture {
        id: _5_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData171
    }
    Texture {
        id: _6_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData177
    }
    Texture {
        id: _7_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData183
    }
    Texture {
        id: _8_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData189
    }
    MorphTarget {
        id: viseme_sil_morphtarget
        objectName: "viseme_sil"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_SS_morphtarget
        objectName: "viseme_SS"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_TH_morphtarget
        objectName: "viseme_TH"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_U_morphtarget
        objectName: "viseme_U"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: browDownLeft_morphtarget
        objectName: "browDownLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: browDownRight_morphtarget
        objectName: "browDownRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: browInnerUp_morphtarget
        objectName: "browInnerUp"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: browOuterUpLeft_morphtarget
        objectName: "browOuterUpLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: browOuterUpRight_morphtarget
        objectName: "browOuterUpRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: cheekPuff_morphtarget
        objectName: "cheekPuff"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: cheekSquintLeft_morphtarget
        objectName: "cheekSquintLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: cheekSquintRight_morphtarget
        objectName: "cheekSquintRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeBlinkLeft_morphtarget
        objectName: "eyeBlinkLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeBlinkRight_morphtarget
        objectName: "eyeBlinkRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookDownLeft_morphtarget
        objectName: "eyeLookDownLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookDownRight_morphtarget
        objectName: "eyeLookDownRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookInLeft_morphtarget
        objectName: "eyeLookInLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookInRight_morphtarget
        objectName: "eyeLookInRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookOutLeft_morphtarget
        objectName: "eyeLookOutLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookOutRight_morphtarget
        objectName: "eyeLookOutRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookUpLeft_morphtarget
        objectName: "eyeLookUpLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookUpRight_morphtarget
        objectName: "eyeLookUpRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeSquintLeft_morphtarget
        objectName: "eyeSquintLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeSquintRight_morphtarget
        objectName: "eyeSquintRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeWideLeft_morphtarget
        objectName: "eyeWideLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeWideRight_morphtarget
        objectName: "eyeWideRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: jawForward_morphtarget
        objectName: "jawForward"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: jawLeft_morphtarget
        objectName: "jawLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: jawOpen_morphtarget
        objectName: "jawOpen"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: jawRight_morphtarget
        objectName: "jawRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthClose_morphtarget
        objectName: "mouthClose"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthDimpleLeft_morphtarget
        objectName: "mouthDimpleLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthDimpleRight_morphtarget
        objectName: "mouthDimpleRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthFrownLeft_morphtarget
        objectName: "mouthFrownLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthFrownRight_morphtarget
        objectName: "mouthFrownRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthFunnel_morphtarget
        objectName: "mouthFunnel"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthLeft_morphtarget
        objectName: "mouthLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthLowerDownLeft_morphtarget
        objectName: "mouthLowerDownLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthLowerDownRight_morphtarget
        objectName: "mouthLowerDownRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthPressLeft_morphtarget
        objectName: "mouthPressLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthPressRight_morphtarget
        objectName: "mouthPressRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthPucker_morphtarget
        objectName: "mouthPucker"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthRight_morphtarget
        objectName: "mouthRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthRollLower_morphtarget
        objectName: "mouthRollLower"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthRollUpper_morphtarget
        objectName: "mouthRollUpper"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthShrugLower_morphtarget
        objectName: "mouthShrugLower"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthShrugUpper_morphtarget
        objectName: "mouthShrugUpper"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthSmileLeft_morphtarget
        objectName: "mouthSmileLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthSmileRight_morphtarget
        objectName: "mouthSmileRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthStretchLeft_morphtarget
        objectName: "mouthStretchLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthStretchRight_morphtarget
        objectName: "mouthStretchRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthUpperUpLeft_morphtarget
        objectName: "mouthUpperUpLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthUpperUpRight_morphtarget
        objectName: "mouthUpperUpRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: noseSneerLeft_morphtarget
        objectName: "noseSneerLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: noseSneerRight_morphtarget
        objectName: "noseSneerRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: tongueOut_morphtarget
        objectName: "tongueOut"
        weight: 1
        attributes: MorphTarget.Position
    }
    PrincipledMaterial {
        id: human_eyelashes02_material
        objectName: "Human.eyelashes02"
        baseColorMap: _1_texture
        roughness: 0.699999988079071
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Blend
    }
    Skin {
        id: skin
        joints: [
            root258,
            pelvis,
            spine_01,
            spine_02,
            spine_03,
            clavicle_l,
            upperarm_l,
            lowerarm_l,
            hand_l,
            index_01_l,
            index_02_l,
            index_03_l,
            middle_01_l,
            middle_02_l,
            middle_03_l,
            pinky_01_l,
            pinky_02_l,
            pinky_03_l,
            ring_01_l,
            ring_02_l,
            ring_03_l,
            thumb_01_l,
            thumb_02_l,
            thumb_03_l,
            clavicle_r,
            upperarm_r,
            lowerarm_r,
            hand_r,
            index_01_r,
            index_02_r,
            index_03_r,
            middle_01_r,
            middle_02_r,
            middle_03_r,
            pinky_01_r,
            pinky_02_r,
            pinky_03_r,
            ring_01_r,
            ring_02_r,
            ring_03_r,
            thumb_01_r,
            thumb_02_r,
            thumb_03_r,
            neck_01,
            head,
            thigh_l,
            calf_l,
            foot_l,
            ball_l,
            thigh_r,
            calf_r,
            foot_r,
            ball_r
        ]
        inverseBindPoses: [
            Qt.matrix4x4(1, 0, 0, 0, 0, 0, -1, 0.00012047, 0, 1, 0, -0.00219757, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.819007, -0.573783, -0.719214, 0, 0.573783, 0.819007, -0.527537, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.957183, 0.289482, -0.904277, 0, -0.289482, 0.957183, 0.297001, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.989828, 0.142271, -1.00396, 0, -0.142271, 0.989828, 0.147727, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.998935, -0.0461463, -1.09842, 0, 0.0461463, 0.998935, -0.0596137, 0, 0, 0, 1),
            Qt.matrix4x4(-0.130863, -0.99029, 0.0468988, 1.32196, 0.990843, -0.132229, -0.0273041, 0.152793, 0.0332404, 0.0428962, 0.998526, -0.081064, 0, 0, 0, 1),
            Qt.matrix4x4(-0.738297, -0.673646, 0.033459, 1.00062, 0.674291, -0.738346, 0.0132477, 0.865529, 0.01578, 0.0323418, 0.999352, -0.0644723, 0, 0, 0, 1),
            Qt.matrix4x4(-0.765707, -0.640098, 0.0629875, 0.970838, 0.510608, -0.545398, 0.664696, 0.437125, -0.391117, 0.541124, 0.744454, -0.503022, 0, 0, 0, 1),
            Qt.matrix4x4(-0.185635, -0.858964, -0.477201, 1.03056, 0.324949, -0.511982, 0.795162, 0.23698, -0.927334, -0.00745617, 0.374161, 0.349591, 0, 0, 0, 1),
            Qt.matrix4x4(0.739552, -0.471616, -0.480252, 0.23834, 0.132513, -0.597516, 0.790832, 0.314759, -0.659927, -0.6485, -0.379399, 1.03284, 0, 0, 0, 1),
            Qt.matrix4x4(0.745674, -0.473786, -0.468504, 0.234317, -0.0255544, -0.722949, 0.690428, 0.512808, -0.66582, -0.502862, -0.551192, 0.943709, 0, 0, 0, 1),
            Qt.matrix4x4(0.745801, -0.501362, -0.438653, 0.251547, -0.137703, -0.760275, 0.634839, 0.595471, -0.651781, -0.41306, -0.636053, 0.877277, 0, 0, 0, 1),
            Qt.matrix4x4(0.573797, -0.387318, -0.721624, 0.271544, 0.219368, -0.776228, 0.591056, 0.498536, -0.789072, -0.497447, -0.360432, 0.941897, 0, 0, 0, 1),
            Qt.matrix4x4(0.580859, -0.448833, -0.679082, 0.314735, 0.0960212, -0.790643, 0.604701, 0.537578, -0.808321, -0.416452, -0.416155, 0.889778, 0, 0, 0, 1),
            Qt.matrix4x4(0.58986, -0.432936, -0.681638, 0.296473, -0.00401817, -0.845692, 0.533656, 0.631123, -0.807495, -0.312044, -0.50058, 0.816782, 0, 0, 0, 1),
            Qt.matrix4x4(0.261605, -0.259351, -0.929677, 0.311308, 0.281535, -0.900828, 0.330525, 0.64721, -0.923202, -0.348204, -0.162645, 0.812554, 0, 0, 0, 1),
            Qt.matrix4x4(0.272778, -0.306357, -0.911997, 0.345706, 0.111189, -0.931554, 0.346183, 0.736824, -0.95563, -0.195835, -0.220044, 0.699209, 0, 0, 0, 1),
            Qt.matrix4x4(0.263638, -0.283578, -0.921997, 0.331541, 0.13061, -0.936516, 0.325391, 0.722184, -0.955739, -0.206207, -0.209863, 0.706534, 0, 0, 0, 1),
            Qt.matrix4x4(0.474245, -0.277871, -0.835391, 0.223334, 0.322428, -0.828141, 0.4585, 0.530468, -0.819226, -0.486795, -0.303149, 0.92988, 0, 0, 0, 1),
            Qt.matrix4x4(0.481697, -0.359252, -0.799316, 0.286902, 0.168202, -0.857249, 0.486654, 0.6, -0.860044, -0.368866, -0.352507, 0.851886, 0, 0, 0, 1),
            Qt.matrix4x4(0.488519, -0.310383, -0.815482, 0.24294, 0.0955394, -0.909946, 0.403571, 0.682396, -0.867307, -0.275063, -0.414872, 0.785414, 0, 0, 0, 1),
            Qt.matrix4x4(0.696083, 0.0555694, 0.715808, -0.513222, -0.67359, -0.294516, 0.677892, 0.446993, 0.248486, -0.95403, -0.167576, 0.881568, 0, 0, 0, 1),
            Qt.matrix4x4(0.8841, 0.1694, 0.435513, -0.64056, -0.339357, -0.407966, 0.847585, 0.351996, 0.321256, -0.897144, -0.303195, 0.825812, 0, 0, 0, 1),
            Qt.matrix4x4(0.922044, 0.139458, 0.36109, -0.607502, -0.198626, -0.63021, 0.750588, 0.50444, 0.332238, -0.763797, -0.553382, 0.75543, 0, 0, 0, 1),
            Qt.matrix4x4(-0.130863, 0.99029, -0.0468988, -1.32196, -0.990843, -0.132229, -0.0273041, 0.152793, -0.0332404, 0.0428962, 0.998526, -0.081064, 0, 0, 0, 1),
            Qt.matrix4x4(-0.738297, 0.673646, -0.033459, -1.00062, -0.674291, -0.738346, 0.0132477, 0.865529, -0.01578, 0.0323418, 0.999352, -0.0644723, 0, 0, 0, 1),
            Qt.matrix4x4(-0.765707, 0.640098, -0.0629875, -0.970838, -0.510608, -0.545398, 0.664696, 0.437125, 0.391117, 0.541124, 0.744454, -0.503022, 0, 0, 0, 1),
            Qt.matrix4x4(-0.185635, 0.858964, 0.477201, -1.03056, -0.324949, -0.511982, 0.795162, 0.23698, 0.927334, -0.00745617, 0.374161, 0.349591, 0, 0, 0, 1),
            Qt.matrix4x4(0.739552, 0.471616, 0.480252, -0.23834, -0.132513, -0.597516, 0.790832, 0.314759, 0.659927, -0.6485, -0.379399, 1.03284, 0, 0, 0, 1),
            Qt.matrix4x4(0.745674, 0.473786, 0.468504, -0.234317, 0.0255544, -0.722949, 0.690428, 0.512808, 0.66582, -0.502862, -0.551192, 0.943709, 0, 0, 0, 1),
            Qt.matrix4x4(0.745801, 0.501362, 0.438653, -0.251547, 0.137703, -0.760275, 0.634839, 0.595471, 0.651781, -0.41306, -0.636053, 0.877277, 0, 0, 0, 1),
            Qt.matrix4x4(0.573797, 0.387318, 0.721624, -0.271544, -0.219368, -0.776228, 0.591056, 0.498536, 0.789072, -0.497447, -0.360432, 0.941897, 0, 0, 0, 1),
            Qt.matrix4x4(0.580859, 0.448833, 0.679082, -0.314735, -0.0960212, -0.790643, 0.604701, 0.537578, 0.808321, -0.416452, -0.416155, 0.889778, 0, 0, 0, 1),
            Qt.matrix4x4(0.58986, 0.432936, 0.681638, -0.296473, 0.00401817, -0.845692, 0.533656, 0.631123, 0.807495, -0.312044, -0.50058, 0.816782, 0, 0, 0, 1),
            Qt.matrix4x4(0.261605, 0.259351, 0.929677, -0.311308, -0.281535, -0.900828, 0.330525, 0.64721, 0.923202, -0.348204, -0.162645, 0.812554, 0, 0, 0, 1),
            Qt.matrix4x4(0.272778, 0.306357, 0.911997, -0.345706, -0.111189, -0.931554, 0.346183, 0.736824, 0.95563, -0.195835, -0.220044, 0.699209, 0, 0, 0, 1),
            Qt.matrix4x4(0.263638, 0.283578, 0.921997, -0.331541, -0.13061, -0.936516, 0.325391, 0.722184, 0.955739, -0.206207, -0.209863, 0.706534, 0, 0, 0, 1),
            Qt.matrix4x4(0.474245, 0.277871, 0.835391, -0.223334, -0.322428, -0.828141, 0.4585, 0.530468, 0.819226, -0.486795, -0.303149, 0.92988, 0, 0, 0, 1),
            Qt.matrix4x4(0.481697, 0.359252, 0.799316, -0.286902, -0.168202, -0.857249, 0.486654, 0.6, 0.860044, -0.368866, -0.352507, 0.851886, 0, 0, 0, 1),
            Qt.matrix4x4(0.488519, 0.310383, 0.815482, -0.24294, -0.0955394, -0.909946, 0.403571, 0.682396, 0.867307, -0.275063, -0.414872, 0.785414, 0, 0, 0, 1),
            Qt.matrix4x4(0.696083, -0.0555694, -0.715808, 0.513222, 0.67359, -0.294516, 0.677892, 0.446993, -0.248486, -0.95403, -0.167576, 0.881568, 0, 0, 0, 1),
            Qt.matrix4x4(0.8841, -0.1694, -0.435513, 0.64056, 0.339357, -0.407966, 0.847585, 0.351996, -0.321256, -0.897144, -0.303195, 0.825812, 0, 0, 0, 1),
            Qt.matrix4x4(0.922044, -0.139458, -0.36109, 0.607502, 0.198626, -0.63021, 0.750588, 0.50444, -0.332238, -0.763797, -0.553382, 0.75543, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.945701, 0.325038, -1.32572, 0, -0.325038, 0.945701, 0.455088, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.998745, -0.050088, -1.50706, 0, 0.050088, 0.998745, -0.113694, 0, 0, 0, 1),
            Qt.matrix4x4(0.891347, 0.0628808, -0.448939, -0.129181, 0.105089, -0.992017, 0.0697029, 0.855309, -0.440972, -0.109308, -0.89084, 0.153434, 0, 0, 0, 1),
            Qt.matrix4x4(0.997022, 0.0748843, -0.0183976, -0.169539, 0.0733902, -0.994727, -0.0716373, 0.462079, -0.0236649, 0.0700741, -0.997261, 0.0174017, 0, 0, 0, 1),
            Qt.matrix4x4(0.994534, 0.104316, 0.00440012, -0.171576, 0.0458186, -0.473923, 0.879373, 0.00894176, 0.0938182, -0.874365, -0.476112, 0.0535184, 0, 0, 0, 1),
            Qt.matrix4x4(0.64269, 0.765318, 0.0351904, -0.122289, -0.0762438, 0.0181866, 0.996923, -0.113613, 0.762323, -0.643396, 0.070039, -0.132395, 0, 0, 0, 1),
            Qt.matrix4x4(0.891347, -0.0628808, 0.448939, 0.129181, -0.105089, -0.992017, 0.0697029, 0.855309, 0.440972, -0.109308, -0.89084, 0.153434, 0, 0, 0, 1),
            Qt.matrix4x4(0.997022, -0.0748843, 0.0183976, 0.169539, -0.0733902, -0.994727, -0.0716373, 0.462079, 0.0236649, 0.0700741, -0.997261, 0.0174017, 0, 0, 0, 1),
            Qt.matrix4x4(0.994534, -0.104316, -0.00440012, 0.171576, -0.0458186, -0.473923, 0.879373, 0.00894176, -0.0938182, -0.874365, -0.476112, 0.0535184, 0, 0, 0, 1),
            Qt.matrix4x4(0.64269, -0.765318, -0.0351904, 0.122289, 0.0762438, 0.0181866, 0.996923, -0.113613, -0.762323, -0.643396, 0.070039, -0.132395, 0, 0, 0, 1)
        ]
    }
    MorphTarget {
        id: viseme_aa_morphtarget
        objectName: "viseme_aa"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_CH_morphtarget
        objectName: "viseme_CH"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_DD_morphtarget
        objectName: "viseme_DD"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_E_morphtarget
        objectName: "viseme_E"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_FF_morphtarget
        objectName: "viseme_FF"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_I_morphtarget
        objectName: "viseme_I"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_kk_morphtarget
        objectName: "viseme_kk"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_nn_morphtarget
        objectName: "viseme_nn"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_O_morphtarget
        objectName: "viseme_O"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_PP_morphtarget
        objectName: "viseme_PP"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_RR_morphtarget
        objectName: "viseme_RR"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_sil_morphtarget92
        objectName: "viseme_sil"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_SS_morphtarget93
        objectName: "viseme_SS"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_TH_morphtarget94
        objectName: "viseme_TH"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_U_morphtarget95
        objectName: "viseme_U"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: browDownLeft_morphtarget96
        objectName: "browDownLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: browDownRight_morphtarget97
        objectName: "browDownRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: browInnerUp_morphtarget98
        objectName: "browInnerUp"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: browOuterUpLeft_morphtarget99
        objectName: "browOuterUpLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: browOuterUpRight_morphtarget100
        objectName: "browOuterUpRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: cheekPuff_morphtarget101
        objectName: "cheekPuff"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: cheekSquintLeft_morphtarget102
        objectName: "cheekSquintLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: cheekSquintRight_morphtarget103
        objectName: "cheekSquintRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeBlinkLeft_morphtarget104
        objectName: "eyeBlinkLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeBlinkRight_morphtarget105
        objectName: "eyeBlinkRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookDownLeft_morphtarget106
        objectName: "eyeLookDownLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookDownRight_morphtarget107
        objectName: "eyeLookDownRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookInLeft_morphtarget108
        objectName: "eyeLookInLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookInRight_morphtarget109
        objectName: "eyeLookInRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookOutLeft_morphtarget110
        objectName: "eyeLookOutLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookOutRight_morphtarget111
        objectName: "eyeLookOutRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookUpLeft_morphtarget112
        objectName: "eyeLookUpLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookUpRight_morphtarget113
        objectName: "eyeLookUpRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeSquintLeft_morphtarget114
        objectName: "eyeSquintLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeSquintRight_morphtarget115
        objectName: "eyeSquintRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeWideLeft_morphtarget116
        objectName: "eyeWideLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeWideRight_morphtarget117
        objectName: "eyeWideRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: jawForward_morphtarget118
        objectName: "jawForward"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: jawLeft_morphtarget119
        objectName: "jawLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: jawOpen_morphtarget120
        objectName: "jawOpen"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: jawRight_morphtarget121
        objectName: "jawRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthClose_morphtarget122
        objectName: "mouthClose"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthDimpleLeft_morphtarget123
        objectName: "mouthDimpleLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthDimpleRight_morphtarget124
        objectName: "mouthDimpleRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthFrownLeft_morphtarget125
        objectName: "mouthFrownLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthFrownRight_morphtarget126
        objectName: "mouthFrownRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthFunnel_morphtarget127
        objectName: "mouthFunnel"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthLeft_morphtarget128
        objectName: "mouthLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthLowerDownLeft_morphtarget129
        objectName: "mouthLowerDownLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthLowerDownRight_morphtarget130
        objectName: "mouthLowerDownRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthPressLeft_morphtarget131
        objectName: "mouthPressLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthPressRight_morphtarget132
        objectName: "mouthPressRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthPucker_morphtarget133
        objectName: "mouthPucker"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthRight_morphtarget134
        objectName: "mouthRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthRollLower_morphtarget135
        objectName: "mouthRollLower"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthRollUpper_morphtarget136
        objectName: "mouthRollUpper"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthShrugLower_morphtarget137
        objectName: "mouthShrugLower"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthShrugUpper_morphtarget138
        objectName: "mouthShrugUpper"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthSmileLeft_morphtarget139
        objectName: "mouthSmileLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthSmileRight_morphtarget140
        objectName: "mouthSmileRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthStretchLeft_morphtarget141
        objectName: "mouthStretchLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthStretchRight_morphtarget142
        objectName: "mouthStretchRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthUpperUpLeft_morphtarget143
        objectName: "mouthUpperUpLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthUpperUpRight_morphtarget144
        objectName: "mouthUpperUpRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: noseSneerLeft_morphtarget145
        objectName: "noseSneerLeft"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: noseSneerRight_morphtarget146
        objectName: "noseSneerRight"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: tongueOut_morphtarget147
        objectName: "tongueOut"
        weight: 1
        attributes: MorphTarget.Position
    }
    PrincipledMaterial {
        id: human_female_casualsuit01_material
        objectName: "Human.female_casualsuit01"
        baseColorMap: _2_texture
        roughness: 0.8500000238418579
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Blend
        indexOfRefraction: 1.4500000476837158
    }
    PrincipledMaterial {
        id: human_eyebrow010_material
        objectName: "Human.eyebrow010"
        baseColorMap: _0_texture
        roughness: 0.699999988079071
        normalMap: _0_texture
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Blend
    }
    Skin {
        id: skin153
        joints: [
            root258,
            pelvis,
            spine_01,
            spine_02,
            spine_03,
            clavicle_l,
            upperarm_l,
            lowerarm_l,
            hand_l,
            index_01_l,
            index_02_l,
            index_03_l,
            middle_01_l,
            middle_02_l,
            middle_03_l,
            pinky_01_l,
            pinky_02_l,
            pinky_03_l,
            ring_01_l,
            ring_02_l,
            ring_03_l,
            thumb_01_l,
            thumb_02_l,
            thumb_03_l,
            clavicle_r,
            upperarm_r,
            lowerarm_r,
            hand_r,
            index_01_r,
            index_02_r,
            index_03_r,
            middle_01_r,
            middle_02_r,
            middle_03_r,
            pinky_01_r,
            pinky_02_r,
            pinky_03_r,
            ring_01_r,
            ring_02_r,
            ring_03_r,
            thumb_01_r,
            thumb_02_r,
            thumb_03_r,
            neck_01,
            head,
            thigh_l,
            calf_l,
            foot_l,
            ball_l,
            thigh_r,
            calf_r,
            foot_r,
            ball_r
        ]
        inverseBindPoses: [
            Qt.matrix4x4(1, 0, 0, 0, 0, 0, -1, 0.00012047, 0, 1, 0, -0.00219757, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.819007, -0.573783, -0.719214, 0, 0.573783, 0.819007, -0.527537, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.957183, 0.289482, -0.904277, 0, -0.289482, 0.957183, 0.297001, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.989828, 0.142271, -1.00396, 0, -0.142271, 0.989828, 0.147727, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.998935, -0.0461463, -1.09842, 0, 0.0461463, 0.998935, -0.0596137, 0, 0, 0, 1),
            Qt.matrix4x4(-0.130863, -0.99029, 0.0468988, 1.32196, 0.990843, -0.132229, -0.0273041, 0.152793, 0.0332404, 0.0428962, 0.998526, -0.081064, 0, 0, 0, 1),
            Qt.matrix4x4(-0.738297, -0.673646, 0.033459, 1.00062, 0.674291, -0.738346, 0.0132477, 0.865529, 0.01578, 0.0323418, 0.999352, -0.0644723, 0, 0, 0, 1),
            Qt.matrix4x4(-0.765707, -0.640098, 0.0629875, 0.970838, 0.510608, -0.545398, 0.664696, 0.437125, -0.391117, 0.541124, 0.744454, -0.503022, 0, 0, 0, 1),
            Qt.matrix4x4(-0.185635, -0.858964, -0.477201, 1.03056, 0.324949, -0.511982, 0.795162, 0.23698, -0.927334, -0.00745617, 0.374161, 0.349591, 0, 0, 0, 1),
            Qt.matrix4x4(0.739552, -0.471616, -0.480252, 0.23834, 0.132513, -0.597516, 0.790832, 0.314759, -0.659927, -0.6485, -0.379399, 1.03284, 0, 0, 0, 1),
            Qt.matrix4x4(0.745674, -0.473786, -0.468504, 0.234317, -0.0255544, -0.722949, 0.690428, 0.512808, -0.66582, -0.502862, -0.551192, 0.943709, 0, 0, 0, 1),
            Qt.matrix4x4(0.745801, -0.501362, -0.438653, 0.251547, -0.137703, -0.760275, 0.634839, 0.595471, -0.651781, -0.41306, -0.636053, 0.877277, 0, 0, 0, 1),
            Qt.matrix4x4(0.573797, -0.387318, -0.721624, 0.271544, 0.219368, -0.776228, 0.591056, 0.498536, -0.789072, -0.497447, -0.360432, 0.941897, 0, 0, 0, 1),
            Qt.matrix4x4(0.580859, -0.448833, -0.679082, 0.314735, 0.0960212, -0.790643, 0.604701, 0.537578, -0.808321, -0.416452, -0.416155, 0.889778, 0, 0, 0, 1),
            Qt.matrix4x4(0.58986, -0.432936, -0.681638, 0.296473, -0.00401817, -0.845692, 0.533656, 0.631123, -0.807495, -0.312044, -0.50058, 0.816782, 0, 0, 0, 1),
            Qt.matrix4x4(0.261605, -0.259351, -0.929677, 0.311308, 0.281535, -0.900828, 0.330525, 0.64721, -0.923202, -0.348204, -0.162645, 0.812554, 0, 0, 0, 1),
            Qt.matrix4x4(0.272778, -0.306357, -0.911997, 0.345706, 0.111189, -0.931554, 0.346183, 0.736824, -0.95563, -0.195835, -0.220044, 0.699209, 0, 0, 0, 1),
            Qt.matrix4x4(0.263638, -0.283578, -0.921997, 0.331541, 0.13061, -0.936516, 0.325391, 0.722184, -0.955739, -0.206207, -0.209863, 0.706534, 0, 0, 0, 1),
            Qt.matrix4x4(0.474245, -0.277871, -0.835391, 0.223334, 0.322428, -0.828141, 0.4585, 0.530468, -0.819226, -0.486795, -0.303149, 0.92988, 0, 0, 0, 1),
            Qt.matrix4x4(0.481697, -0.359252, -0.799316, 0.286902, 0.168202, -0.857249, 0.486654, 0.6, -0.860044, -0.368866, -0.352507, 0.851886, 0, 0, 0, 1),
            Qt.matrix4x4(0.488519, -0.310383, -0.815482, 0.24294, 0.0955394, -0.909946, 0.403571, 0.682396, -0.867307, -0.275063, -0.414872, 0.785414, 0, 0, 0, 1),
            Qt.matrix4x4(0.696083, 0.0555694, 0.715808, -0.513222, -0.67359, -0.294516, 0.677892, 0.446993, 0.248486, -0.95403, -0.167576, 0.881568, 0, 0, 0, 1),
            Qt.matrix4x4(0.8841, 0.1694, 0.435513, -0.64056, -0.339357, -0.407966, 0.847585, 0.351996, 0.321256, -0.897144, -0.303195, 0.825812, 0, 0, 0, 1),
            Qt.matrix4x4(0.922044, 0.139458, 0.36109, -0.607502, -0.198626, -0.63021, 0.750588, 0.50444, 0.332238, -0.763797, -0.553382, 0.75543, 0, 0, 0, 1),
            Qt.matrix4x4(-0.130863, 0.99029, -0.0468988, -1.32196, -0.990843, -0.132229, -0.0273041, 0.152793, -0.0332404, 0.0428962, 0.998526, -0.081064, 0, 0, 0, 1),
            Qt.matrix4x4(-0.738297, 0.673646, -0.033459, -1.00062, -0.674291, -0.738346, 0.0132477, 0.865529, -0.01578, 0.0323418, 0.999352, -0.0644723, 0, 0, 0, 1),
            Qt.matrix4x4(-0.765707, 0.640098, -0.0629875, -0.970838, -0.510608, -0.545398, 0.664696, 0.437125, 0.391117, 0.541124, 0.744454, -0.503022, 0, 0, 0, 1),
            Qt.matrix4x4(-0.185635, 0.858964, 0.477201, -1.03056, -0.324949, -0.511982, 0.795162, 0.23698, 0.927334, -0.00745617, 0.374161, 0.349591, 0, 0, 0, 1),
            Qt.matrix4x4(0.739552, 0.471616, 0.480252, -0.23834, -0.132513, -0.597516, 0.790832, 0.314759, 0.659927, -0.6485, -0.379399, 1.03284, 0, 0, 0, 1),
            Qt.matrix4x4(0.745674, 0.473786, 0.468504, -0.234317, 0.0255544, -0.722949, 0.690428, 0.512808, 0.66582, -0.502862, -0.551192, 0.943709, 0, 0, 0, 1),
            Qt.matrix4x4(0.745801, 0.501362, 0.438653, -0.251547, 0.137703, -0.760275, 0.634839, 0.595471, 0.651781, -0.41306, -0.636053, 0.877277, 0, 0, 0, 1),
            Qt.matrix4x4(0.573797, 0.387318, 0.721624, -0.271544, -0.219368, -0.776228, 0.591056, 0.498536, 0.789072, -0.497447, -0.360432, 0.941897, 0, 0, 0, 1),
            Qt.matrix4x4(0.580859, 0.448833, 0.679082, -0.314735, -0.0960212, -0.790643, 0.604701, 0.537578, 0.808321, -0.416452, -0.416155, 0.889778, 0, 0, 0, 1),
            Qt.matrix4x4(0.58986, 0.432936, 0.681638, -0.296473, 0.00401817, -0.845692, 0.533656, 0.631123, 0.807495, -0.312044, -0.50058, 0.816782, 0, 0, 0, 1),
            Qt.matrix4x4(0.261605, 0.259351, 0.929677, -0.311308, -0.281535, -0.900828, 0.330525, 0.64721, 0.923202, -0.348204, -0.162645, 0.812554, 0, 0, 0, 1),
            Qt.matrix4x4(0.272778, 0.306357, 0.911997, -0.345706, -0.111189, -0.931554, 0.346183, 0.736824, 0.95563, -0.195835, -0.220044, 0.699209, 0, 0, 0, 1),
            Qt.matrix4x4(0.263638, 0.283578, 0.921997, -0.331541, -0.13061, -0.936516, 0.325391, 0.722184, 0.955739, -0.206207, -0.209863, 0.706534, 0, 0, 0, 1),
            Qt.matrix4x4(0.474245, 0.277871, 0.835391, -0.223334, -0.322428, -0.828141, 0.4585, 0.530468, 0.819226, -0.486795, -0.303149, 0.92988, 0, 0, 0, 1),
            Qt.matrix4x4(0.481697, 0.359252, 0.799316, -0.286902, -0.168202, -0.857249, 0.486654, 0.6, 0.860044, -0.368866, -0.352507, 0.851886, 0, 0, 0, 1),
            Qt.matrix4x4(0.488519, 0.310383, 0.815482, -0.24294, -0.0955394, -0.909946, 0.403571, 0.682396, 0.867307, -0.275063, -0.414872, 0.785414, 0, 0, 0, 1),
            Qt.matrix4x4(0.696083, -0.0555694, -0.715808, 0.513222, 0.67359, -0.294516, 0.677892, 0.446993, -0.248486, -0.95403, -0.167576, 0.881568, 0, 0, 0, 1),
            Qt.matrix4x4(0.8841, -0.1694, -0.435513, 0.64056, 0.339357, -0.407966, 0.847585, 0.351996, -0.321256, -0.897144, -0.303195, 0.825812, 0, 0, 0, 1),
            Qt.matrix4x4(0.922044, -0.139458, -0.36109, 0.607502, 0.198626, -0.63021, 0.750588, 0.50444, -0.332238, -0.763797, -0.553382, 0.75543, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.945701, 0.325038, -1.32572, 0, -0.325038, 0.945701, 0.455088, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.998745, -0.050088, -1.50706, 0, 0.050088, 0.998745, -0.113694, 0, 0, 0, 1),
            Qt.matrix4x4(0.891347, 0.0628808, -0.448939, -0.129181, 0.105089, -0.992017, 0.0697029, 0.855309, -0.440972, -0.109308, -0.89084, 0.153434, 0, 0, 0, 1),
            Qt.matrix4x4(0.997022, 0.0748843, -0.0183976, -0.169539, 0.0733902, -0.994727, -0.0716373, 0.462079, -0.0236649, 0.0700741, -0.997261, 0.0174017, 0, 0, 0, 1),
            Qt.matrix4x4(0.994534, 0.104316, 0.00440012, -0.171576, 0.0458186, -0.473923, 0.879373, 0.00894176, 0.0938182, -0.874365, -0.476112, 0.0535184, 0, 0, 0, 1),
            Qt.matrix4x4(0.64269, 0.765318, 0.0351904, -0.122289, -0.0762438, 0.0181866, 0.996923, -0.113613, 0.762323, -0.643396, 0.070039, -0.132395, 0, 0, 0, 1),
            Qt.matrix4x4(0.891347, -0.0628808, 0.448939, 0.129181, -0.105089, -0.992017, 0.0697029, 0.855309, 0.440972, -0.109308, -0.89084, 0.153434, 0, 0, 0, 1),
            Qt.matrix4x4(0.997022, -0.0748843, 0.0183976, 0.169539, -0.0733902, -0.994727, -0.0716373, 0.462079, 0.0236649, 0.0700741, -0.997261, 0.0174017, 0, 0, 0, 1),
            Qt.matrix4x4(0.994534, -0.104316, -0.00440012, 0.171576, -0.0458186, -0.473923, 0.879373, 0.00894176, -0.0938182, -0.874365, -0.476112, 0.0535184, 0, 0, 0, 1),
            Qt.matrix4x4(0.64269, -0.765318, -0.0351904, 0.122289, 0.0762438, 0.0181866, 0.996923, -0.113613, -0.762323, -0.643396, 0.070039, -0.132395, 0, 0, 0, 1)
        ]
    }
    PrincipledMaterial {
        id: saint_eyes_001_material
        objectName: "SAINT_eyes.001"
        baseColorMap: _3_texture
        roughness: 0.25
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Opaque
    }
    Skin {
        id: skin7
        joints: [
            root258,
            pelvis,
            spine_01,
            spine_02,
            spine_03,
            clavicle_l,
            upperarm_l,
            lowerarm_l,
            hand_l,
            index_01_l,
            index_02_l,
            index_03_l,
            middle_01_l,
            middle_02_l,
            middle_03_l,
            pinky_01_l,
            pinky_02_l,
            pinky_03_l,
            ring_01_l,
            ring_02_l,
            ring_03_l,
            thumb_01_l,
            thumb_02_l,
            thumb_03_l,
            clavicle_r,
            upperarm_r,
            lowerarm_r,
            hand_r,
            index_01_r,
            index_02_r,
            index_03_r,
            middle_01_r,
            middle_02_r,
            middle_03_r,
            pinky_01_r,
            pinky_02_r,
            pinky_03_r,
            ring_01_r,
            ring_02_r,
            ring_03_r,
            thumb_01_r,
            thumb_02_r,
            thumb_03_r,
            neck_01,
            head,
            thigh_l,
            calf_l,
            foot_l,
            ball_l,
            thigh_r,
            calf_r,
            foot_r,
            ball_r
        ]
        inverseBindPoses: [
            Qt.matrix4x4(1, 0, 0, 0, 0, 0, -1, 0.00012047, 0, 1, 0, -0.00219757, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.819007, -0.573783, -0.719214, 0, 0.573783, 0.819007, -0.527537, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.957183, 0.289482, -0.904277, 0, -0.289482, 0.957183, 0.297001, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.989828, 0.142271, -1.00396, 0, -0.142271, 0.989828, 0.147727, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.998935, -0.0461463, -1.09842, 0, 0.0461463, 0.998935, -0.0596137, 0, 0, 0, 1),
            Qt.matrix4x4(-0.130863, -0.99029, 0.0468988, 1.32196, 0.990843, -0.132229, -0.0273041, 0.152793, 0.0332404, 0.0428962, 0.998526, -0.081064, 0, 0, 0, 1),
            Qt.matrix4x4(-0.738297, -0.673646, 0.033459, 1.00062, 0.674291, -0.738346, 0.0132477, 0.865529, 0.01578, 0.0323418, 0.999352, -0.0644723, 0, 0, 0, 1),
            Qt.matrix4x4(-0.765707, -0.640098, 0.0629875, 0.970838, 0.510608, -0.545398, 0.664696, 0.437125, -0.391117, 0.541124, 0.744454, -0.503022, 0, 0, 0, 1),
            Qt.matrix4x4(-0.185635, -0.858964, -0.477201, 1.03056, 0.324949, -0.511982, 0.795162, 0.23698, -0.927334, -0.00745617, 0.374161, 0.349591, 0, 0, 0, 1),
            Qt.matrix4x4(0.739552, -0.471616, -0.480252, 0.23834, 0.132513, -0.597516, 0.790832, 0.314759, -0.659927, -0.6485, -0.379399, 1.03284, 0, 0, 0, 1),
            Qt.matrix4x4(0.745674, -0.473786, -0.468504, 0.234317, -0.0255544, -0.722949, 0.690428, 0.512808, -0.66582, -0.502862, -0.551192, 0.943709, 0, 0, 0, 1),
            Qt.matrix4x4(0.745801, -0.501362, -0.438653, 0.251547, -0.137703, -0.760275, 0.634839, 0.595471, -0.651781, -0.41306, -0.636053, 0.877277, 0, 0, 0, 1),
            Qt.matrix4x4(0.573797, -0.387318, -0.721624, 0.271544, 0.219368, -0.776228, 0.591056, 0.498536, -0.789072, -0.497447, -0.360432, 0.941897, 0, 0, 0, 1),
            Qt.matrix4x4(0.580859, -0.448833, -0.679082, 0.314735, 0.0960212, -0.790643, 0.604701, 0.537578, -0.808321, -0.416452, -0.416155, 0.889778, 0, 0, 0, 1),
            Qt.matrix4x4(0.58986, -0.432936, -0.681638, 0.296473, -0.00401817, -0.845692, 0.533656, 0.631123, -0.807495, -0.312044, -0.50058, 0.816782, 0, 0, 0, 1),
            Qt.matrix4x4(0.261605, -0.259351, -0.929677, 0.311308, 0.281535, -0.900828, 0.330525, 0.64721, -0.923202, -0.348204, -0.162645, 0.812554, 0, 0, 0, 1),
            Qt.matrix4x4(0.272778, -0.306357, -0.911997, 0.345706, 0.111189, -0.931554, 0.346183, 0.736824, -0.95563, -0.195835, -0.220044, 0.699209, 0, 0, 0, 1),
            Qt.matrix4x4(0.263638, -0.283578, -0.921997, 0.331541, 0.13061, -0.936516, 0.325391, 0.722184, -0.955739, -0.206207, -0.209863, 0.706534, 0, 0, 0, 1),
            Qt.matrix4x4(0.474245, -0.277871, -0.835391, 0.223334, 0.322428, -0.828141, 0.4585, 0.530468, -0.819226, -0.486795, -0.303149, 0.92988, 0, 0, 0, 1),
            Qt.matrix4x4(0.481697, -0.359252, -0.799316, 0.286902, 0.168202, -0.857249, 0.486654, 0.6, -0.860044, -0.368866, -0.352507, 0.851886, 0, 0, 0, 1),
            Qt.matrix4x4(0.488519, -0.310383, -0.815482, 0.24294, 0.0955394, -0.909946, 0.403571, 0.682396, -0.867307, -0.275063, -0.414872, 0.785414, 0, 0, 0, 1),
            Qt.matrix4x4(0.696083, 0.0555694, 0.715808, -0.513222, -0.67359, -0.294516, 0.677892, 0.446993, 0.248486, -0.95403, -0.167576, 0.881568, 0, 0, 0, 1),
            Qt.matrix4x4(0.8841, 0.1694, 0.435513, -0.64056, -0.339357, -0.407966, 0.847585, 0.351996, 0.321256, -0.897144, -0.303195, 0.825812, 0, 0, 0, 1),
            Qt.matrix4x4(0.922044, 0.139458, 0.36109, -0.607502, -0.198626, -0.63021, 0.750588, 0.50444, 0.332238, -0.763797, -0.553382, 0.75543, 0, 0, 0, 1),
            Qt.matrix4x4(-0.130863, 0.99029, -0.0468988, -1.32196, -0.990843, -0.132229, -0.0273041, 0.152793, -0.0332404, 0.0428962, 0.998526, -0.081064, 0, 0, 0, 1),
            Qt.matrix4x4(-0.738297, 0.673646, -0.033459, -1.00062, -0.674291, -0.738346, 0.0132477, 0.865529, -0.01578, 0.0323418, 0.999352, -0.0644723, 0, 0, 0, 1),
            Qt.matrix4x4(-0.765707, 0.640098, -0.0629875, -0.970838, -0.510608, -0.545398, 0.664696, 0.437125, 0.391117, 0.541124, 0.744454, -0.503022, 0, 0, 0, 1),
            Qt.matrix4x4(-0.185635, 0.858964, 0.477201, -1.03056, -0.324949, -0.511982, 0.795162, 0.23698, 0.927334, -0.00745617, 0.374161, 0.349591, 0, 0, 0, 1),
            Qt.matrix4x4(0.739552, 0.471616, 0.480252, -0.23834, -0.132513, -0.597516, 0.790832, 0.314759, 0.659927, -0.6485, -0.379399, 1.03284, 0, 0, 0, 1),
            Qt.matrix4x4(0.745674, 0.473786, 0.468504, -0.234317, 0.0255544, -0.722949, 0.690428, 0.512808, 0.66582, -0.502862, -0.551192, 0.943709, 0, 0, 0, 1),
            Qt.matrix4x4(0.745801, 0.501362, 0.438653, -0.251547, 0.137703, -0.760275, 0.634839, 0.595471, 0.651781, -0.41306, -0.636053, 0.877277, 0, 0, 0, 1),
            Qt.matrix4x4(0.573797, 0.387318, 0.721624, -0.271544, -0.219368, -0.776228, 0.591056, 0.498536, 0.789072, -0.497447, -0.360432, 0.941897, 0, 0, 0, 1),
            Qt.matrix4x4(0.580859, 0.448833, 0.679082, -0.314735, -0.0960212, -0.790643, 0.604701, 0.537578, 0.808321, -0.416452, -0.416155, 0.889778, 0, 0, 0, 1),
            Qt.matrix4x4(0.58986, 0.432936, 0.681638, -0.296473, 0.00401817, -0.845692, 0.533656, 0.631123, 0.807495, -0.312044, -0.50058, 0.816782, 0, 0, 0, 1),
            Qt.matrix4x4(0.261605, 0.259351, 0.929677, -0.311308, -0.281535, -0.900828, 0.330525, 0.64721, 0.923202, -0.348204, -0.162645, 0.812554, 0, 0, 0, 1),
            Qt.matrix4x4(0.272778, 0.306357, 0.911997, -0.345706, -0.111189, -0.931554, 0.346183, 0.736824, 0.95563, -0.195835, -0.220044, 0.699209, 0, 0, 0, 1),
            Qt.matrix4x4(0.263638, 0.283578, 0.921997, -0.331541, -0.13061, -0.936516, 0.325391, 0.722184, 0.955739, -0.206207, -0.209863, 0.706534, 0, 0, 0, 1),
            Qt.matrix4x4(0.474245, 0.277871, 0.835391, -0.223334, -0.322428, -0.828141, 0.4585, 0.530468, 0.819226, -0.486795, -0.303149, 0.92988, 0, 0, 0, 1),
            Qt.matrix4x4(0.481697, 0.359252, 0.799316, -0.286902, -0.168202, -0.857249, 0.486654, 0.6, 0.860044, -0.368866, -0.352507, 0.851886, 0, 0, 0, 1),
            Qt.matrix4x4(0.488519, 0.310383, 0.815482, -0.24294, -0.0955394, -0.909946, 0.403571, 0.682396, 0.867307, -0.275063, -0.414872, 0.785414, 0, 0, 0, 1),
            Qt.matrix4x4(0.696083, -0.0555694, -0.715808, 0.513222, 0.67359, -0.294516, 0.677892, 0.446993, -0.248486, -0.95403, -0.167576, 0.881568, 0, 0, 0, 1),
            Qt.matrix4x4(0.8841, -0.1694, -0.435513, 0.64056, 0.339357, -0.407966, 0.847585, 0.351996, -0.321256, -0.897144, -0.303195, 0.825812, 0, 0, 0, 1),
            Qt.matrix4x4(0.922044, -0.139458, -0.36109, 0.607502, 0.198626, -0.63021, 0.750588, 0.50444, -0.332238, -0.763797, -0.553382, 0.75543, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.945701, 0.325038, -1.32572, 0, -0.325038, 0.945701, 0.455088, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.998745, -0.050088, -1.50706, 0, 0.050088, 0.998745, -0.113694, 0, 0, 0, 1),
            Qt.matrix4x4(0.891347, 0.0628808, -0.448939, -0.129181, 0.105089, -0.992017, 0.0697029, 0.855309, -0.440972, -0.109308, -0.89084, 0.153434, 0, 0, 0, 1),
            Qt.matrix4x4(0.997022, 0.0748843, -0.0183976, -0.169539, 0.0733902, -0.994727, -0.0716373, 0.462079, -0.0236649, 0.0700741, -0.997261, 0.0174017, 0, 0, 0, 1),
            Qt.matrix4x4(0.994534, 0.104316, 0.00440012, -0.171576, 0.0458186, -0.473923, 0.879373, 0.00894176, 0.0938182, -0.874365, -0.476112, 0.0535184, 0, 0, 0, 1),
            Qt.matrix4x4(0.64269, 0.765318, 0.0351904, -0.122289, -0.0762438, 0.0181866, 0.996923, -0.113613, 0.762323, -0.643396, 0.070039, -0.132395, 0, 0, 0, 1),
            Qt.matrix4x4(0.891347, -0.0628808, 0.448939, 0.129181, -0.105089, -0.992017, 0.0697029, 0.855309, 0.440972, -0.109308, -0.89084, 0.153434, 0, 0, 0, 1),
            Qt.matrix4x4(0.997022, -0.0748843, 0.0183976, 0.169539, -0.0733902, -0.994727, -0.0716373, 0.462079, 0.0236649, 0.0700741, -0.997261, 0.0174017, 0, 0, 0, 1),
            Qt.matrix4x4(0.994534, -0.104316, -0.00440012, 0.171576, -0.0458186, -0.473923, 0.879373, 0.00894176, -0.0938182, -0.874365, -0.476112, 0.0535184, 0, 0, 0, 1),
            Qt.matrix4x4(0.64269, -0.765318, -0.0351904, 0.122289, 0.0762438, 0.0181866, 0.996923, -0.113613, -0.762323, -0.643396, 0.070039, -0.132395, 0, 0, 0, 1)
        ]
    }
    MorphTarget {
        id: viseme_aa_morphtarget8
        objectName: "viseme_aa"
        weight: 1
        attributes: MorphTarget.Position
    }
    PrincipledMaterial {
        id: saint_cornea_material
        objectName: "SAINT_cornea"
        baseColor: "#14ffffff"
        roughness: 0.019999999552965164
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Blend
        opacity: 0.07999999821186066
    }
    Skin {
        id: skin160
        joints: [
            root258,
            pelvis,
            spine_01,
            spine_02,
            spine_03,
            clavicle_l,
            upperarm_l,
            lowerarm_l,
            hand_l,
            index_01_l,
            index_02_l,
            index_03_l,
            middle_01_l,
            middle_02_l,
            middle_03_l,
            pinky_01_l,
            pinky_02_l,
            pinky_03_l,
            ring_01_l,
            ring_02_l,
            ring_03_l,
            thumb_01_l,
            thumb_02_l,
            thumb_03_l,
            clavicle_r,
            upperarm_r,
            lowerarm_r,
            hand_r,
            index_01_r,
            index_02_r,
            index_03_r,
            middle_01_r,
            middle_02_r,
            middle_03_r,
            pinky_01_r,
            pinky_02_r,
            pinky_03_r,
            ring_01_r,
            ring_02_r,
            ring_03_r,
            thumb_01_r,
            thumb_02_r,
            thumb_03_r,
            neck_01,
            head,
            thigh_l,
            calf_l,
            foot_l,
            ball_l,
            thigh_r,
            calf_r,
            foot_r,
            ball_r
        ]
        inverseBindPoses: [
            Qt.matrix4x4(1, 0, 0, 0, 0, 0, -1, 0.00012047, 0, 1, 0, -0.00219757, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.819007, -0.573783, -0.719214, 0, 0.573783, 0.819007, -0.527537, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.957183, 0.289482, -0.904277, 0, -0.289482, 0.957183, 0.297001, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.989828, 0.142271, -1.00396, 0, -0.142271, 0.989828, 0.147727, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.998935, -0.0461463, -1.09842, 0, 0.0461463, 0.998935, -0.0596137, 0, 0, 0, 1),
            Qt.matrix4x4(-0.130863, -0.99029, 0.0468988, 1.32196, 0.990843, -0.132229, -0.0273041, 0.152793, 0.0332404, 0.0428962, 0.998526, -0.081064, 0, 0, 0, 1),
            Qt.matrix4x4(-0.738297, -0.673646, 0.033459, 1.00062, 0.674291, -0.738346, 0.0132477, 0.865529, 0.01578, 0.0323418, 0.999352, -0.0644723, 0, 0, 0, 1),
            Qt.matrix4x4(-0.765707, -0.640098, 0.0629875, 0.970838, 0.510608, -0.545398, 0.664696, 0.437125, -0.391117, 0.541124, 0.744454, -0.503022, 0, 0, 0, 1),
            Qt.matrix4x4(-0.185635, -0.858964, -0.477201, 1.03056, 0.324949, -0.511982, 0.795162, 0.23698, -0.927334, -0.00745617, 0.374161, 0.349591, 0, 0, 0, 1),
            Qt.matrix4x4(0.739552, -0.471616, -0.480252, 0.23834, 0.132513, -0.597516, 0.790832, 0.314759, -0.659927, -0.6485, -0.379399, 1.03284, 0, 0, 0, 1),
            Qt.matrix4x4(0.745674, -0.473786, -0.468504, 0.234317, -0.0255544, -0.722949, 0.690428, 0.512808, -0.66582, -0.502862, -0.551192, 0.943709, 0, 0, 0, 1),
            Qt.matrix4x4(0.745801, -0.501362, -0.438653, 0.251547, -0.137703, -0.760275, 0.634839, 0.595471, -0.651781, -0.41306, -0.636053, 0.877277, 0, 0, 0, 1),
            Qt.matrix4x4(0.573797, -0.387318, -0.721624, 0.271544, 0.219368, -0.776228, 0.591056, 0.498536, -0.789072, -0.497447, -0.360432, 0.941897, 0, 0, 0, 1),
            Qt.matrix4x4(0.580859, -0.448833, -0.679082, 0.314735, 0.0960212, -0.790643, 0.604701, 0.537578, -0.808321, -0.416452, -0.416155, 0.889778, 0, 0, 0, 1),
            Qt.matrix4x4(0.58986, -0.432936, -0.681638, 0.296473, -0.00401817, -0.845692, 0.533656, 0.631123, -0.807495, -0.312044, -0.50058, 0.816782, 0, 0, 0, 1),
            Qt.matrix4x4(0.261605, -0.259351, -0.929677, 0.311308, 0.281535, -0.900828, 0.330525, 0.64721, -0.923202, -0.348204, -0.162645, 0.812554, 0, 0, 0, 1),
            Qt.matrix4x4(0.272778, -0.306357, -0.911997, 0.345706, 0.111189, -0.931554, 0.346183, 0.736824, -0.95563, -0.195835, -0.220044, 0.699209, 0, 0, 0, 1),
            Qt.matrix4x4(0.263638, -0.283578, -0.921997, 0.331541, 0.13061, -0.936516, 0.325391, 0.722184, -0.955739, -0.206207, -0.209863, 0.706534, 0, 0, 0, 1),
            Qt.matrix4x4(0.474245, -0.277871, -0.835391, 0.223334, 0.322428, -0.828141, 0.4585, 0.530468, -0.819226, -0.486795, -0.303149, 0.92988, 0, 0, 0, 1),
            Qt.matrix4x4(0.481697, -0.359252, -0.799316, 0.286902, 0.168202, -0.857249, 0.486654, 0.6, -0.860044, -0.368866, -0.352507, 0.851886, 0, 0, 0, 1),
            Qt.matrix4x4(0.488519, -0.310383, -0.815482, 0.24294, 0.0955394, -0.909946, 0.403571, 0.682396, -0.867307, -0.275063, -0.414872, 0.785414, 0, 0, 0, 1),
            Qt.matrix4x4(0.696083, 0.0555694, 0.715808, -0.513222, -0.67359, -0.294516, 0.677892, 0.446993, 0.248486, -0.95403, -0.167576, 0.881568, 0, 0, 0, 1),
            Qt.matrix4x4(0.8841, 0.1694, 0.435513, -0.64056, -0.339357, -0.407966, 0.847585, 0.351996, 0.321256, -0.897144, -0.303195, 0.825812, 0, 0, 0, 1),
            Qt.matrix4x4(0.922044, 0.139458, 0.36109, -0.607502, -0.198626, -0.63021, 0.750588, 0.50444, 0.332238, -0.763797, -0.553382, 0.75543, 0, 0, 0, 1),
            Qt.matrix4x4(-0.130863, 0.99029, -0.0468988, -1.32196, -0.990843, -0.132229, -0.0273041, 0.152793, -0.0332404, 0.0428962, 0.998526, -0.081064, 0, 0, 0, 1),
            Qt.matrix4x4(-0.738297, 0.673646, -0.033459, -1.00062, -0.674291, -0.738346, 0.0132477, 0.865529, -0.01578, 0.0323418, 0.999352, -0.0644723, 0, 0, 0, 1),
            Qt.matrix4x4(-0.765707, 0.640098, -0.0629875, -0.970838, -0.510608, -0.545398, 0.664696, 0.437125, 0.391117, 0.541124, 0.744454, -0.503022, 0, 0, 0, 1),
            Qt.matrix4x4(-0.185635, 0.858964, 0.477201, -1.03056, -0.324949, -0.511982, 0.795162, 0.23698, 0.927334, -0.00745617, 0.374161, 0.349591, 0, 0, 0, 1),
            Qt.matrix4x4(0.739552, 0.471616, 0.480252, -0.23834, -0.132513, -0.597516, 0.790832, 0.314759, 0.659927, -0.6485, -0.379399, 1.03284, 0, 0, 0, 1),
            Qt.matrix4x4(0.745674, 0.473786, 0.468504, -0.234317, 0.0255544, -0.722949, 0.690428, 0.512808, 0.66582, -0.502862, -0.551192, 0.943709, 0, 0, 0, 1),
            Qt.matrix4x4(0.745801, 0.501362, 0.438653, -0.251547, 0.137703, -0.760275, 0.634839, 0.595471, 0.651781, -0.41306, -0.636053, 0.877277, 0, 0, 0, 1),
            Qt.matrix4x4(0.573797, 0.387318, 0.721624, -0.271544, -0.219368, -0.776228, 0.591056, 0.498536, 0.789072, -0.497447, -0.360432, 0.941897, 0, 0, 0, 1),
            Qt.matrix4x4(0.580859, 0.448833, 0.679082, -0.314735, -0.0960212, -0.790643, 0.604701, 0.537578, 0.808321, -0.416452, -0.416155, 0.889778, 0, 0, 0, 1),
            Qt.matrix4x4(0.58986, 0.432936, 0.681638, -0.296473, 0.00401817, -0.845692, 0.533656, 0.631123, 0.807495, -0.312044, -0.50058, 0.816782, 0, 0, 0, 1),
            Qt.matrix4x4(0.261605, 0.259351, 0.929677, -0.311308, -0.281535, -0.900828, 0.330525, 0.64721, 0.923202, -0.348204, -0.162645, 0.812554, 0, 0, 0, 1),
            Qt.matrix4x4(0.272778, 0.306357, 0.911997, -0.345706, -0.111189, -0.931554, 0.346183, 0.736824, 0.95563, -0.195835, -0.220044, 0.699209, 0, 0, 0, 1),
            Qt.matrix4x4(0.263638, 0.283578, 0.921997, -0.331541, -0.13061, -0.936516, 0.325391, 0.722184, 0.955739, -0.206207, -0.209863, 0.706534, 0, 0, 0, 1),
            Qt.matrix4x4(0.474245, 0.277871, 0.835391, -0.223334, -0.322428, -0.828141, 0.4585, 0.530468, 0.819226, -0.486795, -0.303149, 0.92988, 0, 0, 0, 1),
            Qt.matrix4x4(0.481697, 0.359252, 0.799316, -0.286902, -0.168202, -0.857249, 0.486654, 0.6, 0.860044, -0.368866, -0.352507, 0.851886, 0, 0, 0, 1),
            Qt.matrix4x4(0.488519, 0.310383, 0.815482, -0.24294, -0.0955394, -0.909946, 0.403571, 0.682396, 0.867307, -0.275063, -0.414872, 0.785414, 0, 0, 0, 1),
            Qt.matrix4x4(0.696083, -0.0555694, -0.715808, 0.513222, 0.67359, -0.294516, 0.677892, 0.446993, -0.248486, -0.95403, -0.167576, 0.881568, 0, 0, 0, 1),
            Qt.matrix4x4(0.8841, -0.1694, -0.435513, 0.64056, 0.339357, -0.407966, 0.847585, 0.351996, -0.321256, -0.897144, -0.303195, 0.825812, 0, 0, 0, 1),
            Qt.matrix4x4(0.922044, -0.139458, -0.36109, 0.607502, 0.198626, -0.63021, 0.750588, 0.50444, -0.332238, -0.763797, -0.553382, 0.75543, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.945701, 0.325038, -1.32572, 0, -0.325038, 0.945701, 0.455088, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.998745, -0.050088, -1.50706, 0, 0.050088, 0.998745, -0.113694, 0, 0, 0, 1),
            Qt.matrix4x4(0.891347, 0.0628808, -0.448939, -0.129181, 0.105089, -0.992017, 0.0697029, 0.855309, -0.440972, -0.109308, -0.89084, 0.153434, 0, 0, 0, 1),
            Qt.matrix4x4(0.997022, 0.0748843, -0.0183976, -0.169539, 0.0733902, -0.994727, -0.0716373, 0.462079, -0.0236649, 0.0700741, -0.997261, 0.0174017, 0, 0, 0, 1),
            Qt.matrix4x4(0.994534, 0.104316, 0.00440012, -0.171576, 0.0458186, -0.473923, 0.879373, 0.00894176, 0.0938182, -0.874365, -0.476112, 0.0535184, 0, 0, 0, 1),
            Qt.matrix4x4(0.64269, 0.765318, 0.0351904, -0.122289, -0.0762438, 0.0181866, 0.996923, -0.113613, 0.762323, -0.643396, 0.070039, -0.132395, 0, 0, 0, 1),
            Qt.matrix4x4(0.891347, -0.0628808, 0.448939, 0.129181, -0.105089, -0.992017, 0.0697029, 0.855309, 0.440972, -0.109308, -0.89084, 0.153434, 0, 0, 0, 1),
            Qt.matrix4x4(0.997022, -0.0748843, 0.0183976, 0.169539, -0.0733902, -0.994727, -0.0716373, 0.462079, 0.0236649, 0.0700741, -0.997261, 0.0174017, 0, 0, 0, 1),
            Qt.matrix4x4(0.994534, -0.104316, -0.00440012, 0.171576, -0.0458186, -0.473923, 0.879373, 0.00894176, -0.0938182, -0.874365, -0.476112, 0.0535184, 0, 0, 0, 1),
            Qt.matrix4x4(0.64269, -0.765318, -0.0351904, 0.122289, 0.0762438, 0.0181866, 0.996923, -0.113613, -0.762323, -0.643396, 0.070039, -0.132395, 0, 0, 0, 1)
        ]
    }
    PrincipledMaterial {
        id: human_long01_material
        objectName: "Human.long01"
        baseColorMap: _4_texture
        roughness: 0.550000011920929
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Blend
        indexOfRefraction: 1.4500000476837158
    }
    MorphTarget {
        id: viseme_CH_morphtarget9
        objectName: "viseme_CH"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_DD_morphtarget10
        objectName: "viseme_DD"
        weight: 1
        attributes: MorphTarget.Position
    }
    Skin {
        id: skin166
        joints: [
            root258,
            pelvis,
            spine_01,
            spine_02,
            spine_03,
            clavicle_l,
            upperarm_l,
            lowerarm_l,
            hand_l,
            index_01_l,
            index_02_l,
            index_03_l,
            middle_01_l,
            middle_02_l,
            middle_03_l,
            pinky_01_l,
            pinky_02_l,
            pinky_03_l,
            ring_01_l,
            ring_02_l,
            ring_03_l,
            thumb_01_l,
            thumb_02_l,
            thumb_03_l,
            clavicle_r,
            upperarm_r,
            lowerarm_r,
            hand_r,
            index_01_r,
            index_02_r,
            index_03_r,
            middle_01_r,
            middle_02_r,
            middle_03_r,
            pinky_01_r,
            pinky_02_r,
            pinky_03_r,
            ring_01_r,
            ring_02_r,
            ring_03_r,
            thumb_01_r,
            thumb_02_r,
            thumb_03_r,
            neck_01,
            head,
            thigh_l,
            calf_l,
            foot_l,
            ball_l,
            thigh_r,
            calf_r,
            foot_r,
            ball_r
        ]
        inverseBindPoses: [
            Qt.matrix4x4(1, 0, 0, 0, 0, 0, -1, 0.00012047, 0, 1, 0, -0.00219757, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.819007, -0.573783, -0.719214, 0, 0.573783, 0.819007, -0.527537, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.957183, 0.289482, -0.904277, 0, -0.289482, 0.957183, 0.297001, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.989828, 0.142271, -1.00396, 0, -0.142271, 0.989828, 0.147727, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.998935, -0.0461463, -1.09842, 0, 0.0461463, 0.998935, -0.0596137, 0, 0, 0, 1),
            Qt.matrix4x4(-0.130863, -0.99029, 0.0468988, 1.32196, 0.990843, -0.132229, -0.0273041, 0.152793, 0.0332404, 0.0428962, 0.998526, -0.081064, 0, 0, 0, 1),
            Qt.matrix4x4(-0.738297, -0.673646, 0.033459, 1.00062, 0.674291, -0.738346, 0.0132477, 0.865529, 0.01578, 0.0323418, 0.999352, -0.0644723, 0, 0, 0, 1),
            Qt.matrix4x4(-0.765707, -0.640098, 0.0629875, 0.970838, 0.510608, -0.545398, 0.664696, 0.437125, -0.391117, 0.541124, 0.744454, -0.503022, 0, 0, 0, 1),
            Qt.matrix4x4(-0.185635, -0.858964, -0.477201, 1.03056, 0.324949, -0.511982, 0.795162, 0.23698, -0.927334, -0.00745617, 0.374161, 0.349591, 0, 0, 0, 1),
            Qt.matrix4x4(0.739552, -0.471616, -0.480252, 0.23834, 0.132513, -0.597516, 0.790832, 0.314759, -0.659927, -0.6485, -0.379399, 1.03284, 0, 0, 0, 1),
            Qt.matrix4x4(0.745674, -0.473786, -0.468504, 0.234317, -0.0255544, -0.722949, 0.690428, 0.512808, -0.66582, -0.502862, -0.551192, 0.943709, 0, 0, 0, 1),
            Qt.matrix4x4(0.745801, -0.501362, -0.438653, 0.251547, -0.137703, -0.760275, 0.634839, 0.595471, -0.651781, -0.41306, -0.636053, 0.877277, 0, 0, 0, 1),
            Qt.matrix4x4(0.573797, -0.387318, -0.721624, 0.271544, 0.219368, -0.776228, 0.591056, 0.498536, -0.789072, -0.497447, -0.360432, 0.941897, 0, 0, 0, 1),
            Qt.matrix4x4(0.580859, -0.448833, -0.679082, 0.314735, 0.0960212, -0.790643, 0.604701, 0.537578, -0.808321, -0.416452, -0.416155, 0.889778, 0, 0, 0, 1),
            Qt.matrix4x4(0.58986, -0.432936, -0.681638, 0.296473, -0.00401817, -0.845692, 0.533656, 0.631123, -0.807495, -0.312044, -0.50058, 0.816782, 0, 0, 0, 1),
            Qt.matrix4x4(0.261605, -0.259351, -0.929677, 0.311308, 0.281535, -0.900828, 0.330525, 0.64721, -0.923202, -0.348204, -0.162645, 0.812554, 0, 0, 0, 1),
            Qt.matrix4x4(0.272778, -0.306357, -0.911997, 0.345706, 0.111189, -0.931554, 0.346183, 0.736824, -0.95563, -0.195835, -0.220044, 0.699209, 0, 0, 0, 1),
            Qt.matrix4x4(0.263638, -0.283578, -0.921997, 0.331541, 0.13061, -0.936516, 0.325391, 0.722184, -0.955739, -0.206207, -0.209863, 0.706534, 0, 0, 0, 1),
            Qt.matrix4x4(0.474245, -0.277871, -0.835391, 0.223334, 0.322428, -0.828141, 0.4585, 0.530468, -0.819226, -0.486795, -0.303149, 0.92988, 0, 0, 0, 1),
            Qt.matrix4x4(0.481697, -0.359252, -0.799316, 0.286902, 0.168202, -0.857249, 0.486654, 0.6, -0.860044, -0.368866, -0.352507, 0.851886, 0, 0, 0, 1),
            Qt.matrix4x4(0.488519, -0.310383, -0.815482, 0.24294, 0.0955394, -0.909946, 0.403571, 0.682396, -0.867307, -0.275063, -0.414872, 0.785414, 0, 0, 0, 1),
            Qt.matrix4x4(0.696083, 0.0555694, 0.715808, -0.513222, -0.67359, -0.294516, 0.677892, 0.446993, 0.248486, -0.95403, -0.167576, 0.881568, 0, 0, 0, 1),
            Qt.matrix4x4(0.8841, 0.1694, 0.435513, -0.64056, -0.339357, -0.407966, 0.847585, 0.351996, 0.321256, -0.897144, -0.303195, 0.825812, 0, 0, 0, 1),
            Qt.matrix4x4(0.922044, 0.139458, 0.36109, -0.607502, -0.198626, -0.63021, 0.750588, 0.50444, 0.332238, -0.763797, -0.553382, 0.75543, 0, 0, 0, 1),
            Qt.matrix4x4(-0.130863, 0.99029, -0.0468988, -1.32196, -0.990843, -0.132229, -0.0273041, 0.152793, -0.0332404, 0.0428962, 0.998526, -0.081064, 0, 0, 0, 1),
            Qt.matrix4x4(-0.738297, 0.673646, -0.033459, -1.00062, -0.674291, -0.738346, 0.0132477, 0.865529, -0.01578, 0.0323418, 0.999352, -0.0644723, 0, 0, 0, 1),
            Qt.matrix4x4(-0.765707, 0.640098, -0.0629875, -0.970838, -0.510608, -0.545398, 0.664696, 0.437125, 0.391117, 0.541124, 0.744454, -0.503022, 0, 0, 0, 1),
            Qt.matrix4x4(-0.185635, 0.858964, 0.477201, -1.03056, -0.324949, -0.511982, 0.795162, 0.23698, 0.927334, -0.00745617, 0.374161, 0.349591, 0, 0, 0, 1),
            Qt.matrix4x4(0.739552, 0.471616, 0.480252, -0.23834, -0.132513, -0.597516, 0.790832, 0.314759, 0.659927, -0.6485, -0.379399, 1.03284, 0, 0, 0, 1),
            Qt.matrix4x4(0.745674, 0.473786, 0.468504, -0.234317, 0.0255544, -0.722949, 0.690428, 0.512808, 0.66582, -0.502862, -0.551192, 0.943709, 0, 0, 0, 1),
            Qt.matrix4x4(0.745801, 0.501362, 0.438653, -0.251547, 0.137703, -0.760275, 0.634839, 0.595471, 0.651781, -0.41306, -0.636053, 0.877277, 0, 0, 0, 1),
            Qt.matrix4x4(0.573797, 0.387318, 0.721624, -0.271544, -0.219368, -0.776228, 0.591056, 0.498536, 0.789072, -0.497447, -0.360432, 0.941897, 0, 0, 0, 1),
            Qt.matrix4x4(0.580859, 0.448833, 0.679082, -0.314735, -0.0960212, -0.790643, 0.604701, 0.537578, 0.808321, -0.416452, -0.416155, 0.889778, 0, 0, 0, 1),
            Qt.matrix4x4(0.58986, 0.432936, 0.681638, -0.296473, 0.00401817, -0.845692, 0.533656, 0.631123, 0.807495, -0.312044, -0.50058, 0.816782, 0, 0, 0, 1),
            Qt.matrix4x4(0.261605, 0.259351, 0.929677, -0.311308, -0.281535, -0.900828, 0.330525, 0.64721, 0.923202, -0.348204, -0.162645, 0.812554, 0, 0, 0, 1),
            Qt.matrix4x4(0.272778, 0.306357, 0.911997, -0.345706, -0.111189, -0.931554, 0.346183, 0.736824, 0.95563, -0.195835, -0.220044, 0.699209, 0, 0, 0, 1),
            Qt.matrix4x4(0.263638, 0.283578, 0.921997, -0.331541, -0.13061, -0.936516, 0.325391, 0.722184, 0.955739, -0.206207, -0.209863, 0.706534, 0, 0, 0, 1),
            Qt.matrix4x4(0.474245, 0.277871, 0.835391, -0.223334, -0.322428, -0.828141, 0.4585, 0.530468, 0.819226, -0.486795, -0.303149, 0.92988, 0, 0, 0, 1),
            Qt.matrix4x4(0.481697, 0.359252, 0.799316, -0.286902, -0.168202, -0.857249, 0.486654, 0.6, 0.860044, -0.368866, -0.352507, 0.851886, 0, 0, 0, 1),
            Qt.matrix4x4(0.488519, 0.310383, 0.815482, -0.24294, -0.0955394, -0.909946, 0.403571, 0.682396, 0.867307, -0.275063, -0.414872, 0.785414, 0, 0, 0, 1),
            Qt.matrix4x4(0.696083, -0.0555694, -0.715808, 0.513222, 0.67359, -0.294516, 0.677892, 0.446993, -0.248486, -0.95403, -0.167576, 0.881568, 0, 0, 0, 1),
            Qt.matrix4x4(0.8841, -0.1694, -0.435513, 0.64056, 0.339357, -0.407966, 0.847585, 0.351996, -0.321256, -0.897144, -0.303195, 0.825812, 0, 0, 0, 1),
            Qt.matrix4x4(0.922044, -0.139458, -0.36109, 0.607502, 0.198626, -0.63021, 0.750588, 0.50444, -0.332238, -0.763797, -0.553382, 0.75543, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.945701, 0.325038, -1.32572, 0, -0.325038, 0.945701, 0.455088, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.998745, -0.050088, -1.50706, 0, 0.050088, 0.998745, -0.113694, 0, 0, 0, 1),
            Qt.matrix4x4(0.891347, 0.0628808, -0.448939, -0.129181, 0.105089, -0.992017, 0.0697029, 0.855309, -0.440972, -0.109308, -0.89084, 0.153434, 0, 0, 0, 1),
            Qt.matrix4x4(0.997022, 0.0748843, -0.0183976, -0.169539, 0.0733902, -0.994727, -0.0716373, 0.462079, -0.0236649, 0.0700741, -0.997261, 0.0174017, 0, 0, 0, 1),
            Qt.matrix4x4(0.994534, 0.104316, 0.00440012, -0.171576, 0.0458186, -0.473923, 0.879373, 0.00894176, 0.0938182, -0.874365, -0.476112, 0.0535184, 0, 0, 0, 1),
            Qt.matrix4x4(0.64269, 0.765318, 0.0351904, -0.122289, -0.0762438, 0.0181866, 0.996923, -0.113613, 0.762323, -0.643396, 0.070039, -0.132395, 0, 0, 0, 1),
            Qt.matrix4x4(0.891347, -0.0628808, 0.448939, 0.129181, -0.105089, -0.992017, 0.0697029, 0.855309, 0.440972, -0.109308, -0.89084, 0.153434, 0, 0, 0, 1),
            Qt.matrix4x4(0.997022, -0.0748843, 0.0183976, 0.169539, -0.0733902, -0.994727, -0.0716373, 0.462079, 0.0236649, 0.0700741, -0.997261, 0.0174017, 0, 0, 0, 1),
            Qt.matrix4x4(0.994534, -0.104316, -0.00440012, 0.171576, -0.0458186, -0.473923, 0.879373, 0.00894176, -0.0938182, -0.874365, -0.476112, 0.0535184, 0, 0, 0, 1),
            Qt.matrix4x4(0.64269, -0.765318, -0.0351904, 0.122289, 0.0762438, 0.0181866, 0.996923, -0.113613, -0.762323, -0.643396, 0.070039, -0.132395, 0, 0, 0, 1)
        ]
    }
    PrincipledMaterial {
        id: human_shoes03_material
        objectName: "Human.shoes03"
        baseColorMap: _5_texture
        roughness: 0.3499999940395355
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Blend
    }
    MorphTarget {
        id: viseme_E_morphtarget11
        objectName: "viseme_E"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_FF_morphtarget12
        objectName: "viseme_FF"
        weight: 1
        attributes: MorphTarget.Position
    }
    Skin {
        id: skin172
        joints: [
            root258,
            pelvis,
            spine_01,
            spine_02,
            spine_03,
            clavicle_l,
            upperarm_l,
            lowerarm_l,
            hand_l,
            index_01_l,
            index_02_l,
            index_03_l,
            middle_01_l,
            middle_02_l,
            middle_03_l,
            pinky_01_l,
            pinky_02_l,
            pinky_03_l,
            ring_01_l,
            ring_02_l,
            ring_03_l,
            thumb_01_l,
            thumb_02_l,
            thumb_03_l,
            clavicle_r,
            upperarm_r,
            lowerarm_r,
            hand_r,
            index_01_r,
            index_02_r,
            index_03_r,
            middle_01_r,
            middle_02_r,
            middle_03_r,
            pinky_01_r,
            pinky_02_r,
            pinky_03_r,
            ring_01_r,
            ring_02_r,
            ring_03_r,
            thumb_01_r,
            thumb_02_r,
            thumb_03_r,
            neck_01,
            head,
            thigh_l,
            calf_l,
            foot_l,
            ball_l,
            thigh_r,
            calf_r,
            foot_r,
            ball_r
        ]
        inverseBindPoses: [
            Qt.matrix4x4(1, 0, 0, 0, 0, 0, -1, 0.00012047, 0, 1, 0, -0.00219757, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.819007, -0.573783, -0.719214, 0, 0.573783, 0.819007, -0.527537, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.957183, 0.289482, -0.904277, 0, -0.289482, 0.957183, 0.297001, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.989828, 0.142271, -1.00396, 0, -0.142271, 0.989828, 0.147727, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.998935, -0.0461463, -1.09842, 0, 0.0461463, 0.998935, -0.0596137, 0, 0, 0, 1),
            Qt.matrix4x4(-0.130863, -0.99029, 0.0468988, 1.32196, 0.990843, -0.132229, -0.0273041, 0.152793, 0.0332404, 0.0428962, 0.998526, -0.081064, 0, 0, 0, 1),
            Qt.matrix4x4(-0.738297, -0.673646, 0.033459, 1.00062, 0.674291, -0.738346, 0.0132477, 0.865529, 0.01578, 0.0323418, 0.999352, -0.0644723, 0, 0, 0, 1),
            Qt.matrix4x4(-0.765707, -0.640098, 0.0629875, 0.970838, 0.510608, -0.545398, 0.664696, 0.437125, -0.391117, 0.541124, 0.744454, -0.503022, 0, 0, 0, 1),
            Qt.matrix4x4(-0.185635, -0.858964, -0.477201, 1.03056, 0.324949, -0.511982, 0.795162, 0.23698, -0.927334, -0.00745617, 0.374161, 0.349591, 0, 0, 0, 1),
            Qt.matrix4x4(0.739552, -0.471616, -0.480252, 0.23834, 0.132513, -0.597516, 0.790832, 0.314759, -0.659927, -0.6485, -0.379399, 1.03284, 0, 0, 0, 1),
            Qt.matrix4x4(0.745674, -0.473786, -0.468504, 0.234317, -0.0255544, -0.722949, 0.690428, 0.512808, -0.66582, -0.502862, -0.551192, 0.943709, 0, 0, 0, 1),
            Qt.matrix4x4(0.745801, -0.501362, -0.438653, 0.251547, -0.137703, -0.760275, 0.634839, 0.595471, -0.651781, -0.41306, -0.636053, 0.877277, 0, 0, 0, 1),
            Qt.matrix4x4(0.573797, -0.387318, -0.721624, 0.271544, 0.219368, -0.776228, 0.591056, 0.498536, -0.789072, -0.497447, -0.360432, 0.941897, 0, 0, 0, 1),
            Qt.matrix4x4(0.580859, -0.448833, -0.679082, 0.314735, 0.0960212, -0.790643, 0.604701, 0.537578, -0.808321, -0.416452, -0.416155, 0.889778, 0, 0, 0, 1),
            Qt.matrix4x4(0.58986, -0.432936, -0.681638, 0.296473, -0.00401817, -0.845692, 0.533656, 0.631123, -0.807495, -0.312044, -0.50058, 0.816782, 0, 0, 0, 1),
            Qt.matrix4x4(0.261605, -0.259351, -0.929677, 0.311308, 0.281535, -0.900828, 0.330525, 0.64721, -0.923202, -0.348204, -0.162645, 0.812554, 0, 0, 0, 1),
            Qt.matrix4x4(0.272778, -0.306357, -0.911997, 0.345706, 0.111189, -0.931554, 0.346183, 0.736824, -0.95563, -0.195835, -0.220044, 0.699209, 0, 0, 0, 1),
            Qt.matrix4x4(0.263638, -0.283578, -0.921997, 0.331541, 0.13061, -0.936516, 0.325391, 0.722184, -0.955739, -0.206207, -0.209863, 0.706534, 0, 0, 0, 1),
            Qt.matrix4x4(0.474245, -0.277871, -0.835391, 0.223334, 0.322428, -0.828141, 0.4585, 0.530468, -0.819226, -0.486795, -0.303149, 0.92988, 0, 0, 0, 1),
            Qt.matrix4x4(0.481697, -0.359252, -0.799316, 0.286902, 0.168202, -0.857249, 0.486654, 0.6, -0.860044, -0.368866, -0.352507, 0.851886, 0, 0, 0, 1),
            Qt.matrix4x4(0.488519, -0.310383, -0.815482, 0.24294, 0.0955394, -0.909946, 0.403571, 0.682396, -0.867307, -0.275063, -0.414872, 0.785414, 0, 0, 0, 1),
            Qt.matrix4x4(0.696083, 0.0555694, 0.715808, -0.513222, -0.67359, -0.294516, 0.677892, 0.446993, 0.248486, -0.95403, -0.167576, 0.881568, 0, 0, 0, 1),
            Qt.matrix4x4(0.8841, 0.1694, 0.435513, -0.64056, -0.339357, -0.407966, 0.847585, 0.351996, 0.321256, -0.897144, -0.303195, 0.825812, 0, 0, 0, 1),
            Qt.matrix4x4(0.922044, 0.139458, 0.36109, -0.607502, -0.198626, -0.63021, 0.750588, 0.50444, 0.332238, -0.763797, -0.553382, 0.75543, 0, 0, 0, 1),
            Qt.matrix4x4(-0.130863, 0.99029, -0.0468988, -1.32196, -0.990843, -0.132229, -0.0273041, 0.152793, -0.0332404, 0.0428962, 0.998526, -0.081064, 0, 0, 0, 1),
            Qt.matrix4x4(-0.738297, 0.673646, -0.033459, -1.00062, -0.674291, -0.738346, 0.0132477, 0.865529, -0.01578, 0.0323418, 0.999352, -0.0644723, 0, 0, 0, 1),
            Qt.matrix4x4(-0.765707, 0.640098, -0.0629875, -0.970838, -0.510608, -0.545398, 0.664696, 0.437125, 0.391117, 0.541124, 0.744454, -0.503022, 0, 0, 0, 1),
            Qt.matrix4x4(-0.185635, 0.858964, 0.477201, -1.03056, -0.324949, -0.511982, 0.795162, 0.23698, 0.927334, -0.00745617, 0.374161, 0.349591, 0, 0, 0, 1),
            Qt.matrix4x4(0.739552, 0.471616, 0.480252, -0.23834, -0.132513, -0.597516, 0.790832, 0.314759, 0.659927, -0.6485, -0.379399, 1.03284, 0, 0, 0, 1),
            Qt.matrix4x4(0.745674, 0.473786, 0.468504, -0.234317, 0.0255544, -0.722949, 0.690428, 0.512808, 0.66582, -0.502862, -0.551192, 0.943709, 0, 0, 0, 1),
            Qt.matrix4x4(0.745801, 0.501362, 0.438653, -0.251547, 0.137703, -0.760275, 0.634839, 0.595471, 0.651781, -0.41306, -0.636053, 0.877277, 0, 0, 0, 1),
            Qt.matrix4x4(0.573797, 0.387318, 0.721624, -0.271544, -0.219368, -0.776228, 0.591056, 0.498536, 0.789072, -0.497447, -0.360432, 0.941897, 0, 0, 0, 1),
            Qt.matrix4x4(0.580859, 0.448833, 0.679082, -0.314735, -0.0960212, -0.790643, 0.604701, 0.537578, 0.808321, -0.416452, -0.416155, 0.889778, 0, 0, 0, 1),
            Qt.matrix4x4(0.58986, 0.432936, 0.681638, -0.296473, 0.00401817, -0.845692, 0.533656, 0.631123, 0.807495, -0.312044, -0.50058, 0.816782, 0, 0, 0, 1),
            Qt.matrix4x4(0.261605, 0.259351, 0.929677, -0.311308, -0.281535, -0.900828, 0.330525, 0.64721, 0.923202, -0.348204, -0.162645, 0.812554, 0, 0, 0, 1),
            Qt.matrix4x4(0.272778, 0.306357, 0.911997, -0.345706, -0.111189, -0.931554, 0.346183, 0.736824, 0.95563, -0.195835, -0.220044, 0.699209, 0, 0, 0, 1),
            Qt.matrix4x4(0.263638, 0.283578, 0.921997, -0.331541, -0.13061, -0.936516, 0.325391, 0.722184, 0.955739, -0.206207, -0.209863, 0.706534, 0, 0, 0, 1),
            Qt.matrix4x4(0.474245, 0.277871, 0.835391, -0.223334, -0.322428, -0.828141, 0.4585, 0.530468, 0.819226, -0.486795, -0.303149, 0.92988, 0, 0, 0, 1),
            Qt.matrix4x4(0.481697, 0.359252, 0.799316, -0.286902, -0.168202, -0.857249, 0.486654, 0.6, 0.860044, -0.368866, -0.352507, 0.851886, 0, 0, 0, 1),
            Qt.matrix4x4(0.488519, 0.310383, 0.815482, -0.24294, -0.0955394, -0.909946, 0.403571, 0.682396, 0.867307, -0.275063, -0.414872, 0.785414, 0, 0, 0, 1),
            Qt.matrix4x4(0.696083, -0.0555694, -0.715808, 0.513222, 0.67359, -0.294516, 0.677892, 0.446993, -0.248486, -0.95403, -0.167576, 0.881568, 0, 0, 0, 1),
            Qt.matrix4x4(0.8841, -0.1694, -0.435513, 0.64056, 0.339357, -0.407966, 0.847585, 0.351996, -0.321256, -0.897144, -0.303195, 0.825812, 0, 0, 0, 1),
            Qt.matrix4x4(0.922044, -0.139458, -0.36109, 0.607502, 0.198626, -0.63021, 0.750588, 0.50444, -0.332238, -0.763797, -0.553382, 0.75543, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.945701, 0.325038, -1.32572, 0, -0.325038, 0.945701, 0.455088, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.998745, -0.050088, -1.50706, 0, 0.050088, 0.998745, -0.113694, 0, 0, 0, 1),
            Qt.matrix4x4(0.891347, 0.0628808, -0.448939, -0.129181, 0.105089, -0.992017, 0.0697029, 0.855309, -0.440972, -0.109308, -0.89084, 0.153434, 0, 0, 0, 1),
            Qt.matrix4x4(0.997022, 0.0748843, -0.0183976, -0.169539, 0.0733902, -0.994727, -0.0716373, 0.462079, -0.0236649, 0.0700741, -0.997261, 0.0174017, 0, 0, 0, 1),
            Qt.matrix4x4(0.994534, 0.104316, 0.00440012, -0.171576, 0.0458186, -0.473923, 0.879373, 0.00894176, 0.0938182, -0.874365, -0.476112, 0.0535184, 0, 0, 0, 1),
            Qt.matrix4x4(0.64269, 0.765318, 0.0351904, -0.122289, -0.0762438, 0.0181866, 0.996923, -0.113613, 0.762323, -0.643396, 0.070039, -0.132395, 0, 0, 0, 1),
            Qt.matrix4x4(0.891347, -0.0628808, 0.448939, 0.129181, -0.105089, -0.992017, 0.0697029, 0.855309, 0.440972, -0.109308, -0.89084, 0.153434, 0, 0, 0, 1),
            Qt.matrix4x4(0.997022, -0.0748843, 0.0183976, 0.169539, -0.0733902, -0.994727, -0.0716373, 0.462079, 0.0236649, 0.0700741, -0.997261, 0.0174017, 0, 0, 0, 1),
            Qt.matrix4x4(0.994534, -0.104316, -0.00440012, 0.171576, -0.0458186, -0.473923, 0.879373, 0.00894176, -0.0938182, -0.874365, -0.476112, 0.0535184, 0, 0, 0, 1),
            Qt.matrix4x4(0.64269, -0.765318, -0.0351904, 0.122289, 0.0762438, 0.0181866, 0.996923, -0.113613, -0.762323, -0.643396, 0.070039, -0.132395, 0, 0, 0, 1)
        ]
    }
    PrincipledMaterial {
        id: human_teeth_base_material
        objectName: "Human.teeth_base"
        baseColorMap: _6_texture
        roughness: 0.699999988079071
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Blend
    }
    MorphTarget {
        id: viseme_I_morphtarget13
        objectName: "viseme_I"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_kk_morphtarget14
        objectName: "viseme_kk"
        weight: 1
        attributes: MorphTarget.Position
    }
    Skin {
        id: skin178
        joints: [
            root258,
            pelvis,
            spine_01,
            spine_02,
            spine_03,
            clavicle_l,
            upperarm_l,
            lowerarm_l,
            hand_l,
            index_01_l,
            index_02_l,
            index_03_l,
            middle_01_l,
            middle_02_l,
            middle_03_l,
            pinky_01_l,
            pinky_02_l,
            pinky_03_l,
            ring_01_l,
            ring_02_l,
            ring_03_l,
            thumb_01_l,
            thumb_02_l,
            thumb_03_l,
            clavicle_r,
            upperarm_r,
            lowerarm_r,
            hand_r,
            index_01_r,
            index_02_r,
            index_03_r,
            middle_01_r,
            middle_02_r,
            middle_03_r,
            pinky_01_r,
            pinky_02_r,
            pinky_03_r,
            ring_01_r,
            ring_02_r,
            ring_03_r,
            thumb_01_r,
            thumb_02_r,
            thumb_03_r,
            neck_01,
            head,
            thigh_l,
            calf_l,
            foot_l,
            ball_l,
            thigh_r,
            calf_r,
            foot_r,
            ball_r
        ]
        inverseBindPoses: [
            Qt.matrix4x4(1, 0, 0, 0, 0, 0, -1, 0.00012047, 0, 1, 0, -0.00219757, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.819007, -0.573783, -0.719214, 0, 0.573783, 0.819007, -0.527537, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.957183, 0.289482, -0.904277, 0, -0.289482, 0.957183, 0.297001, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.989828, 0.142271, -1.00396, 0, -0.142271, 0.989828, 0.147727, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.998935, -0.0461463, -1.09842, 0, 0.0461463, 0.998935, -0.0596137, 0, 0, 0, 1),
            Qt.matrix4x4(-0.130863, -0.99029, 0.0468988, 1.32196, 0.990843, -0.132229, -0.0273041, 0.152793, 0.0332404, 0.0428962, 0.998526, -0.081064, 0, 0, 0, 1),
            Qt.matrix4x4(-0.738297, -0.673646, 0.033459, 1.00062, 0.674291, -0.738346, 0.0132477, 0.865529, 0.01578, 0.0323418, 0.999352, -0.0644723, 0, 0, 0, 1),
            Qt.matrix4x4(-0.765707, -0.640098, 0.0629875, 0.970838, 0.510608, -0.545398, 0.664696, 0.437125, -0.391117, 0.541124, 0.744454, -0.503022, 0, 0, 0, 1),
            Qt.matrix4x4(-0.185635, -0.858964, -0.477201, 1.03056, 0.324949, -0.511982, 0.795162, 0.23698, -0.927334, -0.00745617, 0.374161, 0.349591, 0, 0, 0, 1),
            Qt.matrix4x4(0.739552, -0.471616, -0.480252, 0.23834, 0.132513, -0.597516, 0.790832, 0.314759, -0.659927, -0.6485, -0.379399, 1.03284, 0, 0, 0, 1),
            Qt.matrix4x4(0.745674, -0.473786, -0.468504, 0.234317, -0.0255544, -0.722949, 0.690428, 0.512808, -0.66582, -0.502862, -0.551192, 0.943709, 0, 0, 0, 1),
            Qt.matrix4x4(0.745801, -0.501362, -0.438653, 0.251547, -0.137703, -0.760275, 0.634839, 0.595471, -0.651781, -0.41306, -0.636053, 0.877277, 0, 0, 0, 1),
            Qt.matrix4x4(0.573797, -0.387318, -0.721624, 0.271544, 0.219368, -0.776228, 0.591056, 0.498536, -0.789072, -0.497447, -0.360432, 0.941897, 0, 0, 0, 1),
            Qt.matrix4x4(0.580859, -0.448833, -0.679082, 0.314735, 0.0960212, -0.790643, 0.604701, 0.537578, -0.808321, -0.416452, -0.416155, 0.889778, 0, 0, 0, 1),
            Qt.matrix4x4(0.58986, -0.432936, -0.681638, 0.296473, -0.00401817, -0.845692, 0.533656, 0.631123, -0.807495, -0.312044, -0.50058, 0.816782, 0, 0, 0, 1),
            Qt.matrix4x4(0.261605, -0.259351, -0.929677, 0.311308, 0.281535, -0.900828, 0.330525, 0.64721, -0.923202, -0.348204, -0.162645, 0.812554, 0, 0, 0, 1),
            Qt.matrix4x4(0.272778, -0.306357, -0.911997, 0.345706, 0.111189, -0.931554, 0.346183, 0.736824, -0.95563, -0.195835, -0.220044, 0.699209, 0, 0, 0, 1),
            Qt.matrix4x4(0.263638, -0.283578, -0.921997, 0.331541, 0.13061, -0.936516, 0.325391, 0.722184, -0.955739, -0.206207, -0.209863, 0.706534, 0, 0, 0, 1),
            Qt.matrix4x4(0.474245, -0.277871, -0.835391, 0.223334, 0.322428, -0.828141, 0.4585, 0.530468, -0.819226, -0.486795, -0.303149, 0.92988, 0, 0, 0, 1),
            Qt.matrix4x4(0.481697, -0.359252, -0.799316, 0.286902, 0.168202, -0.857249, 0.486654, 0.6, -0.860044, -0.368866, -0.352507, 0.851886, 0, 0, 0, 1),
            Qt.matrix4x4(0.488519, -0.310383, -0.815482, 0.24294, 0.0955394, -0.909946, 0.403571, 0.682396, -0.867307, -0.275063, -0.414872, 0.785414, 0, 0, 0, 1),
            Qt.matrix4x4(0.696083, 0.0555694, 0.715808, -0.513222, -0.67359, -0.294516, 0.677892, 0.446993, 0.248486, -0.95403, -0.167576, 0.881568, 0, 0, 0, 1),
            Qt.matrix4x4(0.8841, 0.1694, 0.435513, -0.64056, -0.339357, -0.407966, 0.847585, 0.351996, 0.321256, -0.897144, -0.303195, 0.825812, 0, 0, 0, 1),
            Qt.matrix4x4(0.922044, 0.139458, 0.36109, -0.607502, -0.198626, -0.63021, 0.750588, 0.50444, 0.332238, -0.763797, -0.553382, 0.75543, 0, 0, 0, 1),
            Qt.matrix4x4(-0.130863, 0.99029, -0.0468988, -1.32196, -0.990843, -0.132229, -0.0273041, 0.152793, -0.0332404, 0.0428962, 0.998526, -0.081064, 0, 0, 0, 1),
            Qt.matrix4x4(-0.738297, 0.673646, -0.033459, -1.00062, -0.674291, -0.738346, 0.0132477, 0.865529, -0.01578, 0.0323418, 0.999352, -0.0644723, 0, 0, 0, 1),
            Qt.matrix4x4(-0.765707, 0.640098, -0.0629875, -0.970838, -0.510608, -0.545398, 0.664696, 0.437125, 0.391117, 0.541124, 0.744454, -0.503022, 0, 0, 0, 1),
            Qt.matrix4x4(-0.185635, 0.858964, 0.477201, -1.03056, -0.324949, -0.511982, 0.795162, 0.23698, 0.927334, -0.00745617, 0.374161, 0.349591, 0, 0, 0, 1),
            Qt.matrix4x4(0.739552, 0.471616, 0.480252, -0.23834, -0.132513, -0.597516, 0.790832, 0.314759, 0.659927, -0.6485, -0.379399, 1.03284, 0, 0, 0, 1),
            Qt.matrix4x4(0.745674, 0.473786, 0.468504, -0.234317, 0.0255544, -0.722949, 0.690428, 0.512808, 0.66582, -0.502862, -0.551192, 0.943709, 0, 0, 0, 1),
            Qt.matrix4x4(0.745801, 0.501362, 0.438653, -0.251547, 0.137703, -0.760275, 0.634839, 0.595471, 0.651781, -0.41306, -0.636053, 0.877277, 0, 0, 0, 1),
            Qt.matrix4x4(0.573797, 0.387318, 0.721624, -0.271544, -0.219368, -0.776228, 0.591056, 0.498536, 0.789072, -0.497447, -0.360432, 0.941897, 0, 0, 0, 1),
            Qt.matrix4x4(0.580859, 0.448833, 0.679082, -0.314735, -0.0960212, -0.790643, 0.604701, 0.537578, 0.808321, -0.416452, -0.416155, 0.889778, 0, 0, 0, 1),
            Qt.matrix4x4(0.58986, 0.432936, 0.681638, -0.296473, 0.00401817, -0.845692, 0.533656, 0.631123, 0.807495, -0.312044, -0.50058, 0.816782, 0, 0, 0, 1),
            Qt.matrix4x4(0.261605, 0.259351, 0.929677, -0.311308, -0.281535, -0.900828, 0.330525, 0.64721, 0.923202, -0.348204, -0.162645, 0.812554, 0, 0, 0, 1),
            Qt.matrix4x4(0.272778, 0.306357, 0.911997, -0.345706, -0.111189, -0.931554, 0.346183, 0.736824, 0.95563, -0.195835, -0.220044, 0.699209, 0, 0, 0, 1),
            Qt.matrix4x4(0.263638, 0.283578, 0.921997, -0.331541, -0.13061, -0.936516, 0.325391, 0.722184, 0.955739, -0.206207, -0.209863, 0.706534, 0, 0, 0, 1),
            Qt.matrix4x4(0.474245, 0.277871, 0.835391, -0.223334, -0.322428, -0.828141, 0.4585, 0.530468, 0.819226, -0.486795, -0.303149, 0.92988, 0, 0, 0, 1),
            Qt.matrix4x4(0.481697, 0.359252, 0.799316, -0.286902, -0.168202, -0.857249, 0.486654, 0.6, 0.860044, -0.368866, -0.352507, 0.851886, 0, 0, 0, 1),
            Qt.matrix4x4(0.488519, 0.310383, 0.815482, -0.24294, -0.0955394, -0.909946, 0.403571, 0.682396, 0.867307, -0.275063, -0.414872, 0.785414, 0, 0, 0, 1),
            Qt.matrix4x4(0.696083, -0.0555694, -0.715808, 0.513222, 0.67359, -0.294516, 0.677892, 0.446993, -0.248486, -0.95403, -0.167576, 0.881568, 0, 0, 0, 1),
            Qt.matrix4x4(0.8841, -0.1694, -0.435513, 0.64056, 0.339357, -0.407966, 0.847585, 0.351996, -0.321256, -0.897144, -0.303195, 0.825812, 0, 0, 0, 1),
            Qt.matrix4x4(0.922044, -0.139458, -0.36109, 0.607502, 0.198626, -0.63021, 0.750588, 0.50444, -0.332238, -0.763797, -0.553382, 0.75543, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.945701, 0.325038, -1.32572, 0, -0.325038, 0.945701, 0.455088, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.998745, -0.050088, -1.50706, 0, 0.050088, 0.998745, -0.113694, 0, 0, 0, 1),
            Qt.matrix4x4(0.891347, 0.0628808, -0.448939, -0.129181, 0.105089, -0.992017, 0.0697029, 0.855309, -0.440972, -0.109308, -0.89084, 0.153434, 0, 0, 0, 1),
            Qt.matrix4x4(0.997022, 0.0748843, -0.0183976, -0.169539, 0.0733902, -0.994727, -0.0716373, 0.462079, -0.0236649, 0.0700741, -0.997261, 0.0174017, 0, 0, 0, 1),
            Qt.matrix4x4(0.994534, 0.104316, 0.00440012, -0.171576, 0.0458186, -0.473923, 0.879373, 0.00894176, 0.0938182, -0.874365, -0.476112, 0.0535184, 0, 0, 0, 1),
            Qt.matrix4x4(0.64269, 0.765318, 0.0351904, -0.122289, -0.0762438, 0.0181866, 0.996923, -0.113613, 0.762323, -0.643396, 0.070039, -0.132395, 0, 0, 0, 1),
            Qt.matrix4x4(0.891347, -0.0628808, 0.448939, 0.129181, -0.105089, -0.992017, 0.0697029, 0.855309, 0.440972, -0.109308, -0.89084, 0.153434, 0, 0, 0, 1),
            Qt.matrix4x4(0.997022, -0.0748843, 0.0183976, 0.169539, -0.0733902, -0.994727, -0.0716373, 0.462079, 0.0236649, 0.0700741, -0.997261, 0.0174017, 0, 0, 0, 1),
            Qt.matrix4x4(0.994534, -0.104316, -0.00440012, 0.171576, -0.0458186, -0.473923, 0.879373, 0.00894176, -0.0938182, -0.874365, -0.476112, 0.0535184, 0, 0, 0, 1),
            Qt.matrix4x4(0.64269, -0.765318, -0.0351904, 0.122289, 0.0762438, 0.0181866, 0.996923, -0.113613, -0.762323, -0.643396, 0.070039, -0.132395, 0, 0, 0, 1)
        ]
    }
    PrincipledMaterial {
        id: human_tongue01_material
        objectName: "Human.tongue01"
        baseColorMap: _7_texture
        roughness: 0.699999988079071
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Blend
    }
    MorphTarget {
        id: viseme_nn_morphtarget15
        objectName: "viseme_nn"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_O_morphtarget16
        objectName: "viseme_O"
        weight: 1
        attributes: MorphTarget.Position
    }
    Skin {
        id: skin184
        joints: [
            root258,
            pelvis,
            spine_01,
            spine_02,
            spine_03,
            clavicle_l,
            upperarm_l,
            lowerarm_l,
            hand_l,
            index_01_l,
            index_02_l,
            index_03_l,
            middle_01_l,
            middle_02_l,
            middle_03_l,
            pinky_01_l,
            pinky_02_l,
            pinky_03_l,
            ring_01_l,
            ring_02_l,
            ring_03_l,
            thumb_01_l,
            thumb_02_l,
            thumb_03_l,
            clavicle_r,
            upperarm_r,
            lowerarm_r,
            hand_r,
            index_01_r,
            index_02_r,
            index_03_r,
            middle_01_r,
            middle_02_r,
            middle_03_r,
            pinky_01_r,
            pinky_02_r,
            pinky_03_r,
            ring_01_r,
            ring_02_r,
            ring_03_r,
            thumb_01_r,
            thumb_02_r,
            thumb_03_r,
            neck_01,
            head,
            thigh_l,
            calf_l,
            foot_l,
            ball_l,
            thigh_r,
            calf_r,
            foot_r,
            ball_r
        ]
        inverseBindPoses: [
            Qt.matrix4x4(1, 0, 0, 0, 0, 0, -1, 0.00012047, 0, 1, 0, -0.00219757, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.819007, -0.573783, -0.719214, 0, 0.573783, 0.819007, -0.527537, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.957183, 0.289482, -0.904277, 0, -0.289482, 0.957183, 0.297001, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.989828, 0.142271, -1.00396, 0, -0.142271, 0.989828, 0.147727, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.998935, -0.0461463, -1.09842, 0, 0.0461463, 0.998935, -0.0596137, 0, 0, 0, 1),
            Qt.matrix4x4(-0.130863, -0.99029, 0.0468988, 1.32196, 0.990843, -0.132229, -0.0273041, 0.152793, 0.0332404, 0.0428962, 0.998526, -0.081064, 0, 0, 0, 1),
            Qt.matrix4x4(-0.738297, -0.673646, 0.033459, 1.00062, 0.674291, -0.738346, 0.0132477, 0.865529, 0.01578, 0.0323418, 0.999352, -0.0644723, 0, 0, 0, 1),
            Qt.matrix4x4(-0.765707, -0.640098, 0.0629875, 0.970838, 0.510608, -0.545398, 0.664696, 0.437125, -0.391117, 0.541124, 0.744454, -0.503022, 0, 0, 0, 1),
            Qt.matrix4x4(-0.185635, -0.858964, -0.477201, 1.03056, 0.324949, -0.511982, 0.795162, 0.23698, -0.927334, -0.00745617, 0.374161, 0.349591, 0, 0, 0, 1),
            Qt.matrix4x4(0.739552, -0.471616, -0.480252, 0.23834, 0.132513, -0.597516, 0.790832, 0.314759, -0.659927, -0.6485, -0.379399, 1.03284, 0, 0, 0, 1),
            Qt.matrix4x4(0.745674, -0.473786, -0.468504, 0.234317, -0.0255544, -0.722949, 0.690428, 0.512808, -0.66582, -0.502862, -0.551192, 0.943709, 0, 0, 0, 1),
            Qt.matrix4x4(0.745801, -0.501362, -0.438653, 0.251547, -0.137703, -0.760275, 0.634839, 0.595471, -0.651781, -0.41306, -0.636053, 0.877277, 0, 0, 0, 1),
            Qt.matrix4x4(0.573797, -0.387318, -0.721624, 0.271544, 0.219368, -0.776228, 0.591056, 0.498536, -0.789072, -0.497447, -0.360432, 0.941897, 0, 0, 0, 1),
            Qt.matrix4x4(0.580859, -0.448833, -0.679082, 0.314735, 0.0960212, -0.790643, 0.604701, 0.537578, -0.808321, -0.416452, -0.416155, 0.889778, 0, 0, 0, 1),
            Qt.matrix4x4(0.58986, -0.432936, -0.681638, 0.296473, -0.00401817, -0.845692, 0.533656, 0.631123, -0.807495, -0.312044, -0.50058, 0.816782, 0, 0, 0, 1),
            Qt.matrix4x4(0.261605, -0.259351, -0.929677, 0.311308, 0.281535, -0.900828, 0.330525, 0.64721, -0.923202, -0.348204, -0.162645, 0.812554, 0, 0, 0, 1),
            Qt.matrix4x4(0.272778, -0.306357, -0.911997, 0.345706, 0.111189, -0.931554, 0.346183, 0.736824, -0.95563, -0.195835, -0.220044, 0.699209, 0, 0, 0, 1),
            Qt.matrix4x4(0.263638, -0.283578, -0.921997, 0.331541, 0.13061, -0.936516, 0.325391, 0.722184, -0.955739, -0.206207, -0.209863, 0.706534, 0, 0, 0, 1),
            Qt.matrix4x4(0.474245, -0.277871, -0.835391, 0.223334, 0.322428, -0.828141, 0.4585, 0.530468, -0.819226, -0.486795, -0.303149, 0.92988, 0, 0, 0, 1),
            Qt.matrix4x4(0.481697, -0.359252, -0.799316, 0.286902, 0.168202, -0.857249, 0.486654, 0.6, -0.860044, -0.368866, -0.352507, 0.851886, 0, 0, 0, 1),
            Qt.matrix4x4(0.488519, -0.310383, -0.815482, 0.24294, 0.0955394, -0.909946, 0.403571, 0.682396, -0.867307, -0.275063, -0.414872, 0.785414, 0, 0, 0, 1),
            Qt.matrix4x4(0.696083, 0.0555694, 0.715808, -0.513222, -0.67359, -0.294516, 0.677892, 0.446993, 0.248486, -0.95403, -0.167576, 0.881568, 0, 0, 0, 1),
            Qt.matrix4x4(0.8841, 0.1694, 0.435513, -0.64056, -0.339357, -0.407966, 0.847585, 0.351996, 0.321256, -0.897144, -0.303195, 0.825812, 0, 0, 0, 1),
            Qt.matrix4x4(0.922044, 0.139458, 0.36109, -0.607502, -0.198626, -0.63021, 0.750588, 0.50444, 0.332238, -0.763797, -0.553382, 0.75543, 0, 0, 0, 1),
            Qt.matrix4x4(-0.130863, 0.99029, -0.0468988, -1.32196, -0.990843, -0.132229, -0.0273041, 0.152793, -0.0332404, 0.0428962, 0.998526, -0.081064, 0, 0, 0, 1),
            Qt.matrix4x4(-0.738297, 0.673646, -0.033459, -1.00062, -0.674291, -0.738346, 0.0132477, 0.865529, -0.01578, 0.0323418, 0.999352, -0.0644723, 0, 0, 0, 1),
            Qt.matrix4x4(-0.765707, 0.640098, -0.0629875, -0.970838, -0.510608, -0.545398, 0.664696, 0.437125, 0.391117, 0.541124, 0.744454, -0.503022, 0, 0, 0, 1),
            Qt.matrix4x4(-0.185635, 0.858964, 0.477201, -1.03056, -0.324949, -0.511982, 0.795162, 0.23698, 0.927334, -0.00745617, 0.374161, 0.349591, 0, 0, 0, 1),
            Qt.matrix4x4(0.739552, 0.471616, 0.480252, -0.23834, -0.132513, -0.597516, 0.790832, 0.314759, 0.659927, -0.6485, -0.379399, 1.03284, 0, 0, 0, 1),
            Qt.matrix4x4(0.745674, 0.473786, 0.468504, -0.234317, 0.0255544, -0.722949, 0.690428, 0.512808, 0.66582, -0.502862, -0.551192, 0.943709, 0, 0, 0, 1),
            Qt.matrix4x4(0.745801, 0.501362, 0.438653, -0.251547, 0.137703, -0.760275, 0.634839, 0.595471, 0.651781, -0.41306, -0.636053, 0.877277, 0, 0, 0, 1),
            Qt.matrix4x4(0.573797, 0.387318, 0.721624, -0.271544, -0.219368, -0.776228, 0.591056, 0.498536, 0.789072, -0.497447, -0.360432, 0.941897, 0, 0, 0, 1),
            Qt.matrix4x4(0.580859, 0.448833, 0.679082, -0.314735, -0.0960212, -0.790643, 0.604701, 0.537578, 0.808321, -0.416452, -0.416155, 0.889778, 0, 0, 0, 1),
            Qt.matrix4x4(0.58986, 0.432936, 0.681638, -0.296473, 0.00401817, -0.845692, 0.533656, 0.631123, 0.807495, -0.312044, -0.50058, 0.816782, 0, 0, 0, 1),
            Qt.matrix4x4(0.261605, 0.259351, 0.929677, -0.311308, -0.281535, -0.900828, 0.330525, 0.64721, 0.923202, -0.348204, -0.162645, 0.812554, 0, 0, 0, 1),
            Qt.matrix4x4(0.272778, 0.306357, 0.911997, -0.345706, -0.111189, -0.931554, 0.346183, 0.736824, 0.95563, -0.195835, -0.220044, 0.699209, 0, 0, 0, 1),
            Qt.matrix4x4(0.263638, 0.283578, 0.921997, -0.331541, -0.13061, -0.936516, 0.325391, 0.722184, 0.955739, -0.206207, -0.209863, 0.706534, 0, 0, 0, 1),
            Qt.matrix4x4(0.474245, 0.277871, 0.835391, -0.223334, -0.322428, -0.828141, 0.4585, 0.530468, 0.819226, -0.486795, -0.303149, 0.92988, 0, 0, 0, 1),
            Qt.matrix4x4(0.481697, 0.359252, 0.799316, -0.286902, -0.168202, -0.857249, 0.486654, 0.6, 0.860044, -0.368866, -0.352507, 0.851886, 0, 0, 0, 1),
            Qt.matrix4x4(0.488519, 0.310383, 0.815482, -0.24294, -0.0955394, -0.909946, 0.403571, 0.682396, 0.867307, -0.275063, -0.414872, 0.785414, 0, 0, 0, 1),
            Qt.matrix4x4(0.696083, -0.0555694, -0.715808, 0.513222, 0.67359, -0.294516, 0.677892, 0.446993, -0.248486, -0.95403, -0.167576, 0.881568, 0, 0, 0, 1),
            Qt.matrix4x4(0.8841, -0.1694, -0.435513, 0.64056, 0.339357, -0.407966, 0.847585, 0.351996, -0.321256, -0.897144, -0.303195, 0.825812, 0, 0, 0, 1),
            Qt.matrix4x4(0.922044, -0.139458, -0.36109, 0.607502, 0.198626, -0.63021, 0.750588, 0.50444, -0.332238, -0.763797, -0.553382, 0.75543, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.945701, 0.325038, -1.32572, 0, -0.325038, 0.945701, 0.455088, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.998745, -0.050088, -1.50706, 0, 0.050088, 0.998745, -0.113694, 0, 0, 0, 1),
            Qt.matrix4x4(0.891347, 0.0628808, -0.448939, -0.129181, 0.105089, -0.992017, 0.0697029, 0.855309, -0.440972, -0.109308, -0.89084, 0.153434, 0, 0, 0, 1),
            Qt.matrix4x4(0.997022, 0.0748843, -0.0183976, -0.169539, 0.0733902, -0.994727, -0.0716373, 0.462079, -0.0236649, 0.0700741, -0.997261, 0.0174017, 0, 0, 0, 1),
            Qt.matrix4x4(0.994534, 0.104316, 0.00440012, -0.171576, 0.0458186, -0.473923, 0.879373, 0.00894176, 0.0938182, -0.874365, -0.476112, 0.0535184, 0, 0, 0, 1),
            Qt.matrix4x4(0.64269, 0.765318, 0.0351904, -0.122289, -0.0762438, 0.0181866, 0.996923, -0.113613, 0.762323, -0.643396, 0.070039, -0.132395, 0, 0, 0, 1),
            Qt.matrix4x4(0.891347, -0.0628808, 0.448939, 0.129181, -0.105089, -0.992017, 0.0697029, 0.855309, 0.440972, -0.109308, -0.89084, 0.153434, 0, 0, 0, 1),
            Qt.matrix4x4(0.997022, -0.0748843, 0.0183976, 0.169539, -0.0733902, -0.994727, -0.0716373, 0.462079, 0.0236649, 0.0700741, -0.997261, 0.0174017, 0, 0, 0, 1),
            Qt.matrix4x4(0.994534, -0.104316, -0.00440012, 0.171576, -0.0458186, -0.473923, 0.879373, 0.00894176, -0.0938182, -0.874365, -0.476112, 0.0535184, 0, 0, 0, 1),
            Qt.matrix4x4(0.64269, -0.765318, -0.0351904, 0.122289, 0.0762438, 0.0181866, 0.996923, -0.113613, -0.762323, -0.643396, 0.070039, -0.132395, 0, 0, 0, 1)
        ]
    }
    PrincipledMaterial {
        id: saint_skin_001_material
        objectName: "SAINT_skin.001"
        baseColorMap: _8_texture
        roughness: 0.5
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Opaque
    }
    MorphTarget {
        id: viseme_PP_morphtarget17
        objectName: "viseme_PP"
        weight: 1
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_RR_morphtarget18
        objectName: "viseme_RR"
        weight: 1
        attributes: MorphTarget.Position
    }
    Skin {
        id: skin190
        joints: [
            root258,
            pelvis,
            spine_01,
            spine_02,
            spine_03,
            clavicle_l,
            upperarm_l,
            lowerarm_l,
            hand_l,
            index_01_l,
            index_02_l,
            index_03_l,
            middle_01_l,
            middle_02_l,
            middle_03_l,
            pinky_01_l,
            pinky_02_l,
            pinky_03_l,
            ring_01_l,
            ring_02_l,
            ring_03_l,
            thumb_01_l,
            thumb_02_l,
            thumb_03_l,
            clavicle_r,
            upperarm_r,
            lowerarm_r,
            hand_r,
            index_01_r,
            index_02_r,
            index_03_r,
            middle_01_r,
            middle_02_r,
            middle_03_r,
            pinky_01_r,
            pinky_02_r,
            pinky_03_r,
            ring_01_r,
            ring_02_r,
            ring_03_r,
            thumb_01_r,
            thumb_02_r,
            thumb_03_r,
            neck_01,
            head,
            thigh_l,
            calf_l,
            foot_l,
            ball_l,
            thigh_r,
            calf_r,
            foot_r,
            ball_r
        ]
        inverseBindPoses: [
            Qt.matrix4x4(1, 0, 0, 0, 0, 0, -1, 0.00012047, 0, 1, 0, -0.00219757, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.819007, -0.573783, -0.719214, 0, 0.573783, 0.819007, -0.527537, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.957183, 0.289482, -0.904277, 0, -0.289482, 0.957183, 0.297001, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.989828, 0.142271, -1.00396, 0, -0.142271, 0.989828, 0.147727, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.998935, -0.0461463, -1.09842, 0, 0.0461463, 0.998935, -0.0596137, 0, 0, 0, 1),
            Qt.matrix4x4(-0.130863, -0.99029, 0.0468988, 1.32196, 0.990843, -0.132229, -0.0273041, 0.152793, 0.0332404, 0.0428962, 0.998526, -0.081064, 0, 0, 0, 1),
            Qt.matrix4x4(-0.738297, -0.673646, 0.033459, 1.00062, 0.674291, -0.738346, 0.0132477, 0.865529, 0.01578, 0.0323418, 0.999352, -0.0644723, 0, 0, 0, 1),
            Qt.matrix4x4(-0.765707, -0.640098, 0.0629875, 0.970838, 0.510608, -0.545398, 0.664696, 0.437125, -0.391117, 0.541124, 0.744454, -0.503022, 0, 0, 0, 1),
            Qt.matrix4x4(-0.185635, -0.858964, -0.477201, 1.03056, 0.324949, -0.511982, 0.795162, 0.23698, -0.927334, -0.00745617, 0.374161, 0.349591, 0, 0, 0, 1),
            Qt.matrix4x4(0.739552, -0.471616, -0.480252, 0.23834, 0.132513, -0.597516, 0.790832, 0.314759, -0.659927, -0.6485, -0.379399, 1.03284, 0, 0, 0, 1),
            Qt.matrix4x4(0.745674, -0.473786, -0.468504, 0.234317, -0.0255544, -0.722949, 0.690428, 0.512808, -0.66582, -0.502862, -0.551192, 0.943709, 0, 0, 0, 1),
            Qt.matrix4x4(0.745801, -0.501362, -0.438653, 0.251547, -0.137703, -0.760275, 0.634839, 0.595471, -0.651781, -0.41306, -0.636053, 0.877277, 0, 0, 0, 1),
            Qt.matrix4x4(0.573797, -0.387318, -0.721624, 0.271544, 0.219368, -0.776228, 0.591056, 0.498536, -0.789072, -0.497447, -0.360432, 0.941897, 0, 0, 0, 1),
            Qt.matrix4x4(0.580859, -0.448833, -0.679082, 0.314735, 0.0960212, -0.790643, 0.604701, 0.537578, -0.808321, -0.416452, -0.416155, 0.889778, 0, 0, 0, 1),
            Qt.matrix4x4(0.58986, -0.432936, -0.681638, 0.296473, -0.00401817, -0.845692, 0.533656, 0.631123, -0.807495, -0.312044, -0.50058, 0.816782, 0, 0, 0, 1),
            Qt.matrix4x4(0.261605, -0.259351, -0.929677, 0.311308, 0.281535, -0.900828, 0.330525, 0.64721, -0.923202, -0.348204, -0.162645, 0.812554, 0, 0, 0, 1),
            Qt.matrix4x4(0.272778, -0.306357, -0.911997, 0.345706, 0.111189, -0.931554, 0.346183, 0.736824, -0.95563, -0.195835, -0.220044, 0.699209, 0, 0, 0, 1),
            Qt.matrix4x4(0.263638, -0.283578, -0.921997, 0.331541, 0.13061, -0.936516, 0.325391, 0.722184, -0.955739, -0.206207, -0.209863, 0.706534, 0, 0, 0, 1),
            Qt.matrix4x4(0.474245, -0.277871, -0.835391, 0.223334, 0.322428, -0.828141, 0.4585, 0.530468, -0.819226, -0.486795, -0.303149, 0.92988, 0, 0, 0, 1),
            Qt.matrix4x4(0.481697, -0.359252, -0.799316, 0.286902, 0.168202, -0.857249, 0.486654, 0.6, -0.860044, -0.368866, -0.352507, 0.851886, 0, 0, 0, 1),
            Qt.matrix4x4(0.488519, -0.310383, -0.815482, 0.24294, 0.0955394, -0.909946, 0.403571, 0.682396, -0.867307, -0.275063, -0.414872, 0.785414, 0, 0, 0, 1),
            Qt.matrix4x4(0.696083, 0.0555694, 0.715808, -0.513222, -0.67359, -0.294516, 0.677892, 0.446993, 0.248486, -0.95403, -0.167576, 0.881568, 0, 0, 0, 1),
            Qt.matrix4x4(0.8841, 0.1694, 0.435513, -0.64056, -0.339357, -0.407966, 0.847585, 0.351996, 0.321256, -0.897144, -0.303195, 0.825812, 0, 0, 0, 1),
            Qt.matrix4x4(0.922044, 0.139458, 0.36109, -0.607502, -0.198626, -0.63021, 0.750588, 0.50444, 0.332238, -0.763797, -0.553382, 0.75543, 0, 0, 0, 1),
            Qt.matrix4x4(-0.130863, 0.99029, -0.0468988, -1.32196, -0.990843, -0.132229, -0.0273041, 0.152793, -0.0332404, 0.0428962, 0.998526, -0.081064, 0, 0, 0, 1),
            Qt.matrix4x4(-0.738297, 0.673646, -0.033459, -1.00062, -0.674291, -0.738346, 0.0132477, 0.865529, -0.01578, 0.0323418, 0.999352, -0.0644723, 0, 0, 0, 1),
            Qt.matrix4x4(-0.765707, 0.640098, -0.0629875, -0.970838, -0.510608, -0.545398, 0.664696, 0.437125, 0.391117, 0.541124, 0.744454, -0.503022, 0, 0, 0, 1),
            Qt.matrix4x4(-0.185635, 0.858964, 0.477201, -1.03056, -0.324949, -0.511982, 0.795162, 0.23698, 0.927334, -0.00745617, 0.374161, 0.349591, 0, 0, 0, 1),
            Qt.matrix4x4(0.739552, 0.471616, 0.480252, -0.23834, -0.132513, -0.597516, 0.790832, 0.314759, 0.659927, -0.6485, -0.379399, 1.03284, 0, 0, 0, 1),
            Qt.matrix4x4(0.745674, 0.473786, 0.468504, -0.234317, 0.0255544, -0.722949, 0.690428, 0.512808, 0.66582, -0.502862, -0.551192, 0.943709, 0, 0, 0, 1),
            Qt.matrix4x4(0.745801, 0.501362, 0.438653, -0.251547, 0.137703, -0.760275, 0.634839, 0.595471, 0.651781, -0.41306, -0.636053, 0.877277, 0, 0, 0, 1),
            Qt.matrix4x4(0.573797, 0.387318, 0.721624, -0.271544, -0.219368, -0.776228, 0.591056, 0.498536, 0.789072, -0.497447, -0.360432, 0.941897, 0, 0, 0, 1),
            Qt.matrix4x4(0.580859, 0.448833, 0.679082, -0.314735, -0.0960212, -0.790643, 0.604701, 0.537578, 0.808321, -0.416452, -0.416155, 0.889778, 0, 0, 0, 1),
            Qt.matrix4x4(0.58986, 0.432936, 0.681638, -0.296473, 0.00401817, -0.845692, 0.533656, 0.631123, 0.807495, -0.312044, -0.50058, 0.816782, 0, 0, 0, 1),
            Qt.matrix4x4(0.261605, 0.259351, 0.929677, -0.311308, -0.281535, -0.900828, 0.330525, 0.64721, 0.923202, -0.348204, -0.162645, 0.812554, 0, 0, 0, 1),
            Qt.matrix4x4(0.272778, 0.306357, 0.911997, -0.345706, -0.111189, -0.931554, 0.346183, 0.736824, 0.95563, -0.195835, -0.220044, 0.699209, 0, 0, 0, 1),
            Qt.matrix4x4(0.263638, 0.283578, 0.921997, -0.331541, -0.13061, -0.936516, 0.325391, 0.722184, 0.955739, -0.206207, -0.209863, 0.706534, 0, 0, 0, 1),
            Qt.matrix4x4(0.474245, 0.277871, 0.835391, -0.223334, -0.322428, -0.828141, 0.4585, 0.530468, 0.819226, -0.486795, -0.303149, 0.92988, 0, 0, 0, 1),
            Qt.matrix4x4(0.481697, 0.359252, 0.799316, -0.286902, -0.168202, -0.857249, 0.486654, 0.6, 0.860044, -0.368866, -0.352507, 0.851886, 0, 0, 0, 1),
            Qt.matrix4x4(0.488519, 0.310383, 0.815482, -0.24294, -0.0955394, -0.909946, 0.403571, 0.682396, 0.867307, -0.275063, -0.414872, 0.785414, 0, 0, 0, 1),
            Qt.matrix4x4(0.696083, -0.0555694, -0.715808, 0.513222, 0.67359, -0.294516, 0.677892, 0.446993, -0.248486, -0.95403, -0.167576, 0.881568, 0, 0, 0, 1),
            Qt.matrix4x4(0.8841, -0.1694, -0.435513, 0.64056, 0.339357, -0.407966, 0.847585, 0.351996, -0.321256, -0.897144, -0.303195, 0.825812, 0, 0, 0, 1),
            Qt.matrix4x4(0.922044, -0.139458, -0.36109, 0.607502, 0.198626, -0.63021, 0.750588, 0.50444, -0.332238, -0.763797, -0.553382, 0.75543, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.945701, 0.325038, -1.32572, 0, -0.325038, 0.945701, 0.455088, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.998745, -0.050088, -1.50706, 0, 0.050088, 0.998745, -0.113694, 0, 0, 0, 1),
            Qt.matrix4x4(0.891347, 0.0628808, -0.448939, -0.129181, 0.105089, -0.992017, 0.0697029, 0.855309, -0.440972, -0.109308, -0.89084, 0.153434, 0, 0, 0, 1),
            Qt.matrix4x4(0.997022, 0.0748843, -0.0183976, -0.169539, 0.0733902, -0.994727, -0.0716373, 0.462079, -0.0236649, 0.0700741, -0.997261, 0.0174017, 0, 0, 0, 1),
            Qt.matrix4x4(0.994534, 0.104316, 0.00440012, -0.171576, 0.0458186, -0.473923, 0.879373, 0.00894176, 0.0938182, -0.874365, -0.476112, 0.0535184, 0, 0, 0, 1),
            Qt.matrix4x4(0.64269, 0.765318, 0.0351904, -0.122289, -0.0762438, 0.0181866, 0.996923, -0.113613, 0.762323, -0.643396, 0.070039, -0.132395, 0, 0, 0, 1),
            Qt.matrix4x4(0.891347, -0.0628808, 0.448939, 0.129181, -0.105089, -0.992017, 0.0697029, 0.855309, 0.440972, -0.109308, -0.89084, 0.153434, 0, 0, 0, 1),
            Qt.matrix4x4(0.997022, -0.0748843, 0.0183976, 0.169539, -0.0733902, -0.994727, -0.0716373, 0.462079, 0.0236649, 0.0700741, -0.997261, 0.0174017, 0, 0, 0, 1),
            Qt.matrix4x4(0.994534, -0.104316, -0.00440012, 0.171576, -0.0458186, -0.473923, 0.879373, 0.00894176, -0.0938182, -0.874365, -0.476112, 0.0535184, 0, 0, 0, 1),
            Qt.matrix4x4(0.64269, -0.765318, -0.0351904, 0.122289, 0.0762438, 0.0181866, 0.996923, -0.113613, -0.762323, -0.643396, 0.070039, -0.132395, 0, 0, 0, 1)
        ]
    }
    MorphTarget {
        id: viseme_aa_morphtarget191
        objectName: "viseme_aa"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_CH_morphtarget192
        objectName: "viseme_CH"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_DD_morphtarget193
        objectName: "viseme_DD"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_E_morphtarget194
        objectName: "viseme_E"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_FF_morphtarget195
        objectName: "viseme_FF"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_I_morphtarget196
        objectName: "viseme_I"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_kk_morphtarget197
        objectName: "viseme_kk"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_nn_morphtarget198
        objectName: "viseme_nn"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_O_morphtarget199
        objectName: "viseme_O"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_PP_morphtarget200
        objectName: "viseme_PP"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_RR_morphtarget201
        objectName: "viseme_RR"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_sil_morphtarget202
        objectName: "viseme_sil"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_SS_morphtarget203
        objectName: "viseme_SS"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_TH_morphtarget204
        objectName: "viseme_TH"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: viseme_U_morphtarget205
        objectName: "viseme_U"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: browDownLeft_morphtarget206
        objectName: "browDownLeft"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: browDownRight_morphtarget207
        objectName: "browDownRight"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: browInnerUp_morphtarget208
        objectName: "browInnerUp"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: browOuterUpLeft_morphtarget209
        objectName: "browOuterUpLeft"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: browOuterUpRight_morphtarget210
        objectName: "browOuterUpRight"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: cheekPuff_morphtarget211
        objectName: "cheekPuff"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: cheekSquintLeft_morphtarget212
        objectName: "cheekSquintLeft"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: cheekSquintRight_morphtarget213
        objectName: "cheekSquintRight"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeBlinkLeft_morphtarget214
        objectName: "eyeBlinkLeft"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeBlinkRight_morphtarget215
        objectName: "eyeBlinkRight"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookDownLeft_morphtarget216
        objectName: "eyeLookDownLeft"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookDownRight_morphtarget217
        objectName: "eyeLookDownRight"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookInLeft_morphtarget218
        objectName: "eyeLookInLeft"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookInRight_morphtarget219
        objectName: "eyeLookInRight"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookOutLeft_morphtarget220
        objectName: "eyeLookOutLeft"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookOutRight_morphtarget221
        objectName: "eyeLookOutRight"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookUpLeft_morphtarget222
        objectName: "eyeLookUpLeft"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeLookUpRight_morphtarget223
        objectName: "eyeLookUpRight"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeSquintLeft_morphtarget224
        objectName: "eyeSquintLeft"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeSquintRight_morphtarget225
        objectName: "eyeSquintRight"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeWideLeft_morphtarget226
        objectName: "eyeWideLeft"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: eyeWideRight_morphtarget227
        objectName: "eyeWideRight"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: jawForward_morphtarget228
        objectName: "jawForward"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: jawLeft_morphtarget229
        objectName: "jawLeft"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: jawOpen_morphtarget230
        objectName: "jawOpen"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: jawRight_morphtarget231
        objectName: "jawRight"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthClose_morphtarget232
        objectName: "mouthClose"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthDimpleLeft_morphtarget233
        objectName: "mouthDimpleLeft"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthDimpleRight_morphtarget234
        objectName: "mouthDimpleRight"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthFrownLeft_morphtarget235
        objectName: "mouthFrownLeft"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthFrownRight_morphtarget236
        objectName: "mouthFrownRight"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthFunnel_morphtarget237
        objectName: "mouthFunnel"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthLeft_morphtarget238
        objectName: "mouthLeft"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthLowerDownLeft_morphtarget239
        objectName: "mouthLowerDownLeft"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthLowerDownRight_morphtarget240
        objectName: "mouthLowerDownRight"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthPressLeft_morphtarget241
        objectName: "mouthPressLeft"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthPressRight_morphtarget242
        objectName: "mouthPressRight"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthPucker_morphtarget243
        objectName: "mouthPucker"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthRight_morphtarget244
        objectName: "mouthRight"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthRollLower_morphtarget245
        objectName: "mouthRollLower"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthRollUpper_morphtarget246
        objectName: "mouthRollUpper"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthShrugLower_morphtarget247
        objectName: "mouthShrugLower"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthShrugUpper_morphtarget248
        objectName: "mouthShrugUpper"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthSmileLeft_morphtarget249
        objectName: "mouthSmileLeft"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthSmileRight_morphtarget250
        objectName: "mouthSmileRight"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthStretchLeft_morphtarget251
        objectName: "mouthStretchLeft"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthStretchRight_morphtarget252
        objectName: "mouthStretchRight"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthUpperUpLeft_morphtarget253
        objectName: "mouthUpperUpLeft"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: mouthUpperUpRight_morphtarget254
        objectName: "mouthUpperUpRight"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: noseSneerLeft_morphtarget255
        objectName: "noseSneerLeft"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: noseSneerRight_morphtarget256
        objectName: "noseSneerRight"
        attributes: MorphTarget.Position
    }
    MorphTarget {
        id: tongueOut_morphtarget257
        objectName: "tongueOut"
        attributes: MorphTarget.Position
    }

    // Nodes:
    Node {
        id: human_rig_rt
        objectName: "Human.rig_rt"
        Model {
            id: human_eyebrow010_rt
            objectName: "Human.eyebrow010_rt"
            source: "meshes/eyebrow010_003_mesh.mesh"
            skin: skin7
            materials: [
                human_eyebrow010_material
            ]
            morphTargets: [
                viseme_aa_morphtarget8,
                viseme_CH_morphtarget9,
                viseme_DD_morphtarget10,
                viseme_E_morphtarget11,
                viseme_FF_morphtarget12,
                viseme_I_morphtarget13,
                viseme_kk_morphtarget14,
                viseme_nn_morphtarget15,
                viseme_O_morphtarget16,
                viseme_PP_morphtarget17,
                viseme_RR_morphtarget18,
                viseme_sil_morphtarget,
                viseme_SS_morphtarget,
                viseme_TH_morphtarget,
                viseme_U_morphtarget,
                browDownLeft_morphtarget,
                browDownRight_morphtarget,
                browInnerUp_morphtarget,
                browOuterUpLeft_morphtarget,
                browOuterUpRight_morphtarget,
                cheekPuff_morphtarget,
                cheekSquintLeft_morphtarget,
                cheekSquintRight_morphtarget,
                eyeBlinkLeft_morphtarget,
                eyeBlinkRight_morphtarget,
                eyeLookDownLeft_morphtarget,
                eyeLookDownRight_morphtarget,
                eyeLookInLeft_morphtarget,
                eyeLookInRight_morphtarget,
                eyeLookOutLeft_morphtarget,
                eyeLookOutRight_morphtarget,
                eyeLookUpLeft_morphtarget,
                eyeLookUpRight_morphtarget,
                eyeSquintLeft_morphtarget,
                eyeSquintRight_morphtarget,
                eyeWideLeft_morphtarget,
                eyeWideRight_morphtarget,
                jawForward_morphtarget,
                jawLeft_morphtarget,
                jawOpen_morphtarget,
                jawRight_morphtarget,
                mouthClose_morphtarget,
                mouthDimpleLeft_morphtarget,
                mouthDimpleRight_morphtarget,
                mouthFrownLeft_morphtarget,
                mouthFrownRight_morphtarget,
                mouthFunnel_morphtarget,
                mouthLeft_morphtarget,
                mouthLowerDownLeft_morphtarget,
                mouthLowerDownRight_morphtarget,
                mouthPressLeft_morphtarget,
                mouthPressRight_morphtarget,
                mouthPucker_morphtarget,
                mouthRight_morphtarget,
                mouthRollLower_morphtarget,
                mouthRollUpper_morphtarget,
                mouthShrugLower_morphtarget,
                mouthShrugUpper_morphtarget,
                mouthSmileLeft_morphtarget,
                mouthSmileRight_morphtarget,
                mouthStretchLeft_morphtarget,
                mouthStretchRight_morphtarget,
                mouthUpperUpLeft_morphtarget,
                mouthUpperUpRight_morphtarget,
                noseSneerLeft_morphtarget,
                noseSneerRight_morphtarget,
                tongueOut_morphtarget
            ]
        }
        Model {
            id: human_eyelashes02_rt
            objectName: "Human.eyelashes02_rt"
            source: "meshes/eyelashes02_003_mesh.mesh"
            skin: skin
            materials: [
                human_eyelashes02_material
            ]
            morphTargets: [
                viseme_aa_morphtarget,
                viseme_CH_morphtarget,
                viseme_DD_morphtarget,
                viseme_E_morphtarget,
                viseme_FF_morphtarget,
                viseme_I_morphtarget,
                viseme_kk_morphtarget,
                viseme_nn_morphtarget,
                viseme_O_morphtarget,
                viseme_PP_morphtarget,
                viseme_RR_morphtarget,
                viseme_sil_morphtarget92,
                viseme_SS_morphtarget93,
                viseme_TH_morphtarget94,
                viseme_U_morphtarget95,
                browDownLeft_morphtarget96,
                browDownRight_morphtarget97,
                browInnerUp_morphtarget98,
                browOuterUpLeft_morphtarget99,
                browOuterUpRight_morphtarget100,
                cheekPuff_morphtarget101,
                cheekSquintLeft_morphtarget102,
                cheekSquintRight_morphtarget103,
                eyeBlinkLeft_morphtarget104,
                eyeBlinkRight_morphtarget105,
                eyeLookDownLeft_morphtarget106,
                eyeLookDownRight_morphtarget107,
                eyeLookInLeft_morphtarget108,
                eyeLookInRight_morphtarget109,
                eyeLookOutLeft_morphtarget110,
                eyeLookOutRight_morphtarget111,
                eyeLookUpLeft_morphtarget112,
                eyeLookUpRight_morphtarget113,
                eyeSquintLeft_morphtarget114,
                eyeSquintRight_morphtarget115,
                eyeWideLeft_morphtarget116,
                eyeWideRight_morphtarget117,
                jawForward_morphtarget118,
                jawLeft_morphtarget119,
                jawOpen_morphtarget120,
                jawRight_morphtarget121,
                mouthClose_morphtarget122,
                mouthDimpleLeft_morphtarget123,
                mouthDimpleRight_morphtarget124,
                mouthFrownLeft_morphtarget125,
                mouthFrownRight_morphtarget126,
                mouthFunnel_morphtarget127,
                mouthLeft_morphtarget128,
                mouthLowerDownLeft_morphtarget129,
                mouthLowerDownRight_morphtarget130,
                mouthPressLeft_morphtarget131,
                mouthPressRight_morphtarget132,
                mouthPucker_morphtarget133,
                mouthRight_morphtarget134,
                mouthRollLower_morphtarget135,
                mouthRollUpper_morphtarget136,
                mouthShrugLower_morphtarget137,
                mouthShrugUpper_morphtarget138,
                mouthSmileLeft_morphtarget139,
                mouthSmileRight_morphtarget140,
                mouthStretchLeft_morphtarget141,
                mouthStretchRight_morphtarget142,
                mouthUpperUpLeft_morphtarget143,
                mouthUpperUpRight_morphtarget144,
                noseSneerLeft_morphtarget145,
                noseSneerRight_morphtarget146,
                tongueOut_morphtarget147
            ]
        }
        Model {
            id: human_female_casualsuit01_rt
            objectName: "Human.female_casualsuit01_rt"
            source: "meshes/female_casualsuit01_003_mesh.mesh"
            skin: skin153
            materials: [
                human_female_casualsuit01_material
            ]
        }
        Model {
            id: human_high_poly_rt
            objectName: "Human.high-poly_rt"
            source: "meshes/human_high_poly_rt_mesh.mesh"
            skin: skin160
            materials: [
                saint_eyes_001_material,
                saint_cornea_material
            ]
        }
        Model {
            id: human_long01_rt
            objectName: "Human.long01_rt"
            source: "meshes/long01_003_mesh.mesh"
            skin: skin166
            materials: [
                human_long01_material
            ]
        }
        Model {
            id: human_shoes03_rt
            objectName: "Human.shoes03_rt"
            source: "meshes/shoes03_003_mesh.mesh"
            skin: skin172
            materials: [
                human_shoes03_material
            ]
        }
        Model {
            id: human_teeth_base_rt
            objectName: "Human.teeth_base_rt"
            source: "meshes/teeth_base_003_mesh.mesh"
            skin: skin178
            materials: [
                human_teeth_base_material
            ]
        }
        Model {
            id: human_tongue01_rt
            objectName: "Human.tongue01_rt"
            source: "meshes/tongue01_003_mesh.mesh"
            skin: skin184
            materials: [
                human_tongue01_material
            ]
        }
        Model {
            id: human_rt
            objectName: "Human_rt"
            source: "meshes/base_180_mesh.mesh"
            skin: skin190
            materials: [
                saint_skin_001_material
            ]
            morphTargets: [
                viseme_aa_morphtarget191,
                viseme_CH_morphtarget192,
                viseme_DD_morphtarget193,
                viseme_E_morphtarget194,
                viseme_FF_morphtarget195,
                viseme_I_morphtarget196,
                viseme_kk_morphtarget197,
                viseme_nn_morphtarget198,
                viseme_O_morphtarget199,
                viseme_PP_morphtarget200,
                viseme_RR_morphtarget201,
                viseme_sil_morphtarget202,
                viseme_SS_morphtarget203,
                viseme_TH_morphtarget204,
                viseme_U_morphtarget205,
                browDownLeft_morphtarget206,
                browDownRight_morphtarget207,
                browInnerUp_morphtarget208,
                browOuterUpLeft_morphtarget209,
                browOuterUpRight_morphtarget210,
                cheekPuff_morphtarget211,
                cheekSquintLeft_morphtarget212,
                cheekSquintRight_morphtarget213,
                eyeBlinkLeft_morphtarget214,
                eyeBlinkRight_morphtarget215,
                eyeLookDownLeft_morphtarget216,
                eyeLookDownRight_morphtarget217,
                eyeLookInLeft_morphtarget218,
                eyeLookInRight_morphtarget219,
                eyeLookOutLeft_morphtarget220,
                eyeLookOutRight_morphtarget221,
                eyeLookUpLeft_morphtarget222,
                eyeLookUpRight_morphtarget223,
                eyeSquintLeft_morphtarget224,
                eyeSquintRight_morphtarget225,
                eyeWideLeft_morphtarget226,
                eyeWideRight_morphtarget227,
                jawForward_morphtarget228,
                jawLeft_morphtarget229,
                jawOpen_morphtarget230,
                jawRight_morphtarget231,
                mouthClose_morphtarget232,
                mouthDimpleLeft_morphtarget233,
                mouthDimpleRight_morphtarget234,
                mouthFrownLeft_morphtarget235,
                mouthFrownRight_morphtarget236,
                mouthFunnel_morphtarget237,
                mouthLeft_morphtarget238,
                mouthLowerDownLeft_morphtarget239,
                mouthLowerDownRight_morphtarget240,
                mouthPressLeft_morphtarget241,
                mouthPressRight_morphtarget242,
                mouthPucker_morphtarget243,
                mouthRight_morphtarget244,
                mouthRollLower_morphtarget245,
                mouthRollUpper_morphtarget246,
                mouthShrugLower_morphtarget247,
                mouthShrugUpper_morphtarget248,
                mouthSmileLeft_morphtarget249,
                mouthSmileRight_morphtarget250,
                mouthStretchLeft_morphtarget251,
                mouthStretchRight_morphtarget252,
                mouthUpperUpLeft_morphtarget253,
                mouthUpperUpRight_morphtarget254,
                noseSneerLeft_morphtarget255,
                noseSneerRight_morphtarget256,
                tongueOut_morphtarget257
            ]
        }
        Node {
            id: root258
            objectName: "Root"
            position: Qt.vector3d(0, 0.00219757, 0.00012047)
            rotation: Qt.quaternion(0.707107, -0.707107, 0, 0)
            scale: Qt.vector3d(1, 1, 1)
            Node {
                id: pelvis
                objectName: "pelvis"
                position: Qt.vector3d(0, -0.0192632, 0.889536)
                rotation: Qt.quaternion(0.887069, 0.461637, 0, 0)
                Node {
                    id: spine_01
                    objectName: "spine_01"
                    position: Qt.vector3d(0, 0.0730177, 3.72529e-08)
                    rotation: Qt.quaternion(0.8994, 0.437127, 0, 0)
                    scale: Qt.vector3d(1, 1, 1)
                    Node {
                        id: spine_02
                        objectName: "spine_02"
                        position: Qt.vector3d(0, 0.0660608, -3.0268e-09)
                        rotation: Qt.quaternion(0.997154, -0.0753935, 0, 0)
                        scale: Qt.vector3d(1, 1, 1)
                        Node {
                            id: spine_03
                            objectName: "spine_03"
                            position: Qt.vector3d(0, 0.0861123, -9.31323e-10)
                            rotation: Qt.quaternion(0.995542, -0.0943188, 0, 0)
                            scale: Qt.vector3d(1, 1, 1)
                            Node {
                                id: clavicle_l
                                objectName: "clavicle_l"
                                position: Qt.vector3d(0.0242971, 0.231897, 0.0249837)
                                rotation: Qt.quaternion(0.659119, -0.0114354, 0.0121715, -0.751853)
                                scale: Qt.vector3d(1, 1, 1)
                                Node {
                                    id: upperarm_l
                                    objectName: "upperarm_l"
                                    position: Qt.vector3d(9.60426e-08, 0.133076, -8.3819e-09)
                                    rotation: Qt.quaternion(0.939477, 0.00529468, 0.00872935, -0.34246)
                                    scale: Qt.vector3d(1, 1, 1)
                                    Node {
                                        id: lowerarm_l
                                        objectName: "lowerarm_l"
                                        position: Qt.vector3d(1.16415e-09, 0.248087, 1.86265e-09)
                                        rotation: Qt.quaternion(0.936713, 0.349116, -0.0216231, -0.0148195)
                                        scale: Qt.vector3d(1, 1, 1)
                                        Node {
                                            id: hand_l
                                            objectName: "hand_l"
                                            position: Qt.vector3d(2.8871e-08, 0.225322, -1.49012e-08)
                                            rotation: Qt.quaternion(0.904545, 0.112918, 0.410665, -0.0200351)
                                            scale: Qt.vector3d(1, 1, 1)
                                            Node {
                                                id: index_01_l
                                                objectName: "index_01_l"
                                                position: Qt.vector3d(-0.0117705, 0.095545, 0.00873204)
                                                rotation: Qt.quaternion(0.858729, 0.105265, 0.501491, -0.00330801)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: index_02_l
                                                    objectName: "index_02_l"
                                                    position: Qt.vector3d(4.47035e-08, 0.0233769, 5.96046e-08)
                                                    rotation: Qt.quaternion(0.993621, 0.112571, 0.00416415, 0.00526405)
                                                    scale: Qt.vector3d(1, 1, 1)
                                                    Node {
                                                        id: index_03_l
                                                        objectName: "index_03_l"
                                                        position: Qt.vector3d(2.98023e-08, 0.0208884, 7.45058e-08)
                                                        rotation: Qt.quaternion(0.997862, 0.062121, 0.00259303, 0.0201533)
                                                        scale: Qt.vector3d(1, 1, 1)
                                                    }
                                                }
                                            }
                                            Node {
                                                id: middle_01_l
                                                objectName: "middle_01_l"
                                                position: Qt.vector3d(0.00170934, 0.0919226, -0.0107932)
                                                rotation: Qt.quaternion(0.881731, 0.0884159, 0.438054, -0.151132)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: middle_02_l
                                                    objectName: "middle_02_l"
                                                    position: Qt.vector3d(1.49012e-08, 0.0307261, 3.72529e-08)
                                                    rotation: Qt.quaternion(0.998043, 0.0500003, -0.00298074, 0.0374442)
                                                    scale: Qt.vector3d(1, 1, 1)
                                                    Node {
                                                        id: middle_03_l
                                                        objectName: "middle_03_l"
                                                        position: Qt.vector3d(2.98023e-08, 0.0251488, -2.98023e-08)
                                                        rotation: Qt.quaternion(0.997719, 0.066872, 0.00595907, -0.0070398)
                                                        scale: Qt.vector3d(1, 1, 1)
                                                    }
                                                }
                                            }
                                            Node {
                                                id: pinky_01_l
                                                objectName: "pinky_01_l"
                                                position: Qt.vector3d(0.0279728, 0.0754939, -0.0309178)
                                                rotation: Qt.quaternion(0.89878, 0.0334779, 0.31615, -0.301865)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: pinky_02_l
                                                    objectName: "pinky_02_l"
                                                    position: Qt.vector3d(1.49012e-08, 0.0193893, 1.11759e-08)
                                                    rotation: Qt.quaternion(0.996217, 0.0830081, 0.000548356, 0.0257186)
                                                    scale: Qt.vector3d(1, 1, 1)
                                                    Node {
                                                        id: pinky_03_l
                                                        objectName: "pinky_03_l"
                                                        position: Qt.vector3d(0, 0.014153, 5.96046e-08)
                                                        rotation: Qt.quaternion(0.999891, -0.00654746, -0.00315322, -0.0128709)
                                                        scale: Qt.vector3d(1, 1, 1)
                                                    }
                                                }
                                            }
                                            Node {
                                                id: ring_01_l
                                                objectName: "ring_01_l"
                                                position: Qt.vector3d(0.0135985, 0.085188, -0.0228431)
                                                rotation: Qt.quaternion(0.879281, 0.0388833, 0.41658, -0.227628)
                                                Node {
                                                    id: ring_02_l
                                                    objectName: "ring_02_l"
                                                    position: Qt.vector3d(2.98023e-08, 0.0270123, 7.45058e-09)
                                                    rotation: Qt.quaternion(0.996781, 0.0665729, -0.00839414, 0.0438688)
                                                    scale: Qt.vector3d(1, 1, 1)
                                                    Node {
                                                        id: ring_03_l
                                                        objectName: "ring_03_l"
                                                        position: Qt.vector3d(1.04308e-07, 0.0224721, -7.45058e-09)
                                                        rotation: Qt.quaternion(0.998098, 0.0559073, 0.00772635, -0.0247853)
                                                        scale: Qt.vector3d(1, 1, 1)
                                                    }
                                                }
                                            }
                                            Node {
                                                id: thumb_01_l
                                                objectName: "thumb_01_l"
                                                position: Qt.vector3d(-0.0121973, 0.0357646, 0.0141237)
                                                rotation: Qt.quaternion(0.408163, 0.27228, 0.754236, 0.436342)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: thumb_02_l
                                                    objectName: "thumb_02_l"
                                                    position: Qt.vector3d(-6.70552e-08, 0.0279148, -6.33299e-08)
                                                    rotation: Qt.quaternion(0.980614, 0.0817234, -0.0072288, -0.177949)
                                                    scale: Qt.vector3d(1, 1, 1)
                                                    Node {
                                                        id: thumb_03_l
                                                        objectName: "thumb_03_l"
                                                        position: Qt.vector3d(-2.98023e-08, 0.032763, -5.21541e-08)
                                                        rotation: Qt.quaternion(0.989509, 0.137489, -0.0349361, -0.0273545)
                                                        scale: Qt.vector3d(1, 1, 1)
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            Node {
                                id: clavicle_r
                                objectName: "clavicle_r"
                                position: Qt.vector3d(-0.0242971, 0.231897, 0.0249837)
                                rotation: Qt.quaternion(0.659119, -0.0114354, -0.0121715, 0.751853)
                                scale: Qt.vector3d(1, 1, 1)
                                Node {
                                    id: upperarm_r
                                    objectName: "upperarm_r"
                                    position: Qt.vector3d(-9.60426e-08, 0.133076, -8.3819e-09)
                                    rotation: Qt.quaternion(0.939477, 0.00529468, -0.00872935, 0.34246)
                                    scale: Qt.vector3d(1, 1, 1)
                                    Node {
                                        id: lowerarm_r
                                        objectName: "lowerarm_r"
                                        position: Qt.vector3d(-1.16415e-09, 0.248087, 1.86265e-09)
                                        rotation: Qt.quaternion(0.936713, 0.349116, 0.0216231, 0.0148195)
                                        scale: Qt.vector3d(1, 1, 1)
                                        Node {
                                            id: hand_r
                                            objectName: "hand_r"
                                            position: Qt.vector3d(-2.8871e-08, 0.225322, -1.49012e-08)
                                            rotation: Qt.quaternion(0.904545, 0.112918, -0.410665, 0.0200351)
                                            scale: Qt.vector3d(1, 1, 1)
                                            Node {
                                                id: index_01_r
                                                objectName: "index_01_r"
                                                position: Qt.vector3d(0.0117705, 0.095545, 0.00873204)
                                                rotation: Qt.quaternion(0.858729, 0.105265, -0.501491, 0.00330801)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: index_02_r
                                                    objectName: "index_02_r"
                                                    position: Qt.vector3d(-4.47035e-08, 0.0233769, 5.96046e-08)
                                                    rotation: Qt.quaternion(0.993621, 0.112571, -0.00416415, -0.00526405)
                                                    scale: Qt.vector3d(1, 1, 1)
                                                    Node {
                                                        id: index_03_r
                                                        objectName: "index_03_r"
                                                        position: Qt.vector3d(-2.98023e-08, 0.0208884, 7.45058e-08)
                                                        rotation: Qt.quaternion(0.997862, 0.062121, -0.00259303, -0.0201533)
                                                        scale: Qt.vector3d(1, 1, 1)
                                                    }
                                                }
                                            }
                                            Node {
                                                id: middle_01_r
                                                objectName: "middle_01_r"
                                                position: Qt.vector3d(-0.00170934, 0.0919226, -0.0107932)
                                                rotation: Qt.quaternion(0.881731, 0.0884159, -0.438054, 0.151132)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: middle_02_r
                                                    objectName: "middle_02_r"
                                                    position: Qt.vector3d(-1.49012e-08, 0.0307261, 3.72529e-08)
                                                    rotation: Qt.quaternion(0.998043, 0.0500003, 0.00298074, -0.0374442)
                                                    scale: Qt.vector3d(1, 1, 1)
                                                    Node {
                                                        id: middle_03_r
                                                        objectName: "middle_03_r"
                                                        position: Qt.vector3d(-2.98023e-08, 0.0251488, -2.98023e-08)
                                                        rotation: Qt.quaternion(0.997719, 0.066872, -0.00595907, 0.0070398)
                                                        scale: Qt.vector3d(1, 1, 1)
                                                    }
                                                }
                                            }
                                            Node {
                                                id: pinky_01_r
                                                objectName: "pinky_01_r"
                                                position: Qt.vector3d(-0.0279728, 0.0754939, -0.0309178)
                                                rotation: Qt.quaternion(0.89878, 0.0334779, -0.31615, 0.301865)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: pinky_02_r
                                                    objectName: "pinky_02_r"
                                                    position: Qt.vector3d(-1.49012e-08, 0.0193893, 1.11759e-08)
                                                    rotation: Qt.quaternion(0.996217, 0.0830081, -0.000548356, -0.0257186)
                                                    scale: Qt.vector3d(1, 1, 1)
                                                    Node {
                                                        id: pinky_03_r
                                                        objectName: "pinky_03_r"
                                                        position: Qt.vector3d(0, 0.014153, 5.96046e-08)
                                                        rotation: Qt.quaternion(0.999891, -0.00654746, 0.00315322, 0.0128709)
                                                        scale: Qt.vector3d(1, 1, 1)
                                                    }
                                                }
                                            }
                                            Node {
                                                id: ring_01_r
                                                objectName: "ring_01_r"
                                                position: Qt.vector3d(-0.0135985, 0.085188, -0.0228431)
                                                rotation: Qt.quaternion(0.879281, 0.0388833, -0.41658, 0.227628)
                                                Node {
                                                    id: ring_02_r
                                                    objectName: "ring_02_r"
                                                    position: Qt.vector3d(-2.98023e-08, 0.0270123, 7.45058e-09)
                                                    rotation: Qt.quaternion(0.996781, 0.0665729, 0.00839414, -0.0438688)
                                                    scale: Qt.vector3d(1, 1, 1)
                                                    Node {
                                                        id: ring_03_r
                                                        objectName: "ring_03_r"
                                                        position: Qt.vector3d(-1.04308e-07, 0.0224721, -7.45058e-09)
                                                        rotation: Qt.quaternion(0.998098, 0.0559073, -0.00772635, 0.0247853)
                                                        scale: Qt.vector3d(1, 1, 1)
                                                    }
                                                }
                                            }
                                            Node {
                                                id: thumb_01_r
                                                objectName: "thumb_01_r"
                                                position: Qt.vector3d(0.0121973, 0.0357646, 0.0141237)
                                                rotation: Qt.quaternion(-0.408163, -0.27228, 0.754236, 0.436342)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: thumb_02_r
                                                    objectName: "thumb_02_r"
                                                    position: Qt.vector3d(6.70552e-08, 0.0279148, -6.33299e-08)
                                                    rotation: Qt.quaternion(0.980614, 0.0817234, 0.0072288, 0.177949)
                                                    scale: Qt.vector3d(1, 1, 1)
                                                    Node {
                                                        id: thumb_03_r
                                                        objectName: "thumb_03_r"
                                                        position: Qt.vector3d(2.98023e-08, 0.032763, -5.21541e-08)
                                                        rotation: Qt.quaternion(0.989509, 0.137489, 0.0349361, 0.0273545)
                                                        scale: Qt.vector3d(1, 1, 1)
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            Node {
                                id: neck_01
                                objectName: "neck_01"
                                position: Qt.vector3d(0, 0.301717, 0.00559989)
                                rotation: Qt.quaternion(0.982266, 0.187491, 0, 0)
                                Node {
                                    id: head
                                    objectName: "head"
                                    position: Qt.vector3d(0, 0.115472, -1.86265e-08)
                                    rotation: Qt.quaternion(0.981894, -0.189429, 0, 0)
                                    scale: Qt.vector3d(1, 1, 1)
                                }
                            }
                        }
                    }
                }
                Node {
                    id: thigh_l
                    objectName: "thigh_l"
                    position: Qt.vector3d(0.0929215, -0.0148574, -0.0107879)
                    rotation: Qt.quaternion(-0.248274, 0.940231, 0.110128, -0.205422)
                    scale: Qt.vector3d(1, 1, 1)
                    Node {
                        id: calf_l
                        objectName: "calf_l"
                        position: Qt.vector3d(0, 0.405493, -1.49012e-08)
                        rotation: Qt.quaternion(0.972412, 0.0724229, 0.221736, -0.00149628)
                        Node {
                            id: foot_l
                            objectName: "foot_l"
                            position: Qt.vector3d(-2.34868e-08, 0.404321, 4.65661e-10)
                            rotation: Qt.quaternion(0.840002, -0.542263, 0.0170939, -0.00747222)
                            scale: Qt.vector3d(1, 1, 1)
                            Node {
                                id: ball_l
                                objectName: "ball_l"
                                position: Qt.vector3d(1.62981e-09, 0.123346, 3.72529e-09)
                                rotation: Qt.quaternion(0.892253, -0.25193, 0.369003, -0.0652186)
                                scale: Qt.vector3d(1, 1, 1)
                            }
                        }
                    }
                }
                Node {
                    id: thigh_r
                    objectName: "thigh_r"
                    position: Qt.vector3d(-0.0929215, -0.0148574, -0.0107879)
                    rotation: Qt.quaternion(-0.248274, 0.940231, -0.110128, 0.205422)
                    scale: Qt.vector3d(1, 1, 1)
                    Node {
                        id: calf_r
                        objectName: "calf_r"
                        position: Qt.vector3d(0, 0.405493, -1.49012e-08)
                        rotation: Qt.quaternion(0.972412, 0.0724229, -0.221736, 0.00149628)
                        Node {
                            id: foot_r
                            objectName: "foot_r"
                            position: Qt.vector3d(2.34868e-08, 0.404321, 4.65661e-10)
                            rotation: Qt.quaternion(0.840002, -0.542263, -0.0170939, 0.00747222)
                            scale: Qt.vector3d(1, 1, 1)
                            Node {
                                id: ball_r
                                objectName: "ball_r"
                                position: Qt.vector3d(-1.62981e-09, 0.123346, 3.72529e-09)
                                rotation: Qt.quaternion(0.892253, -0.25193, -0.369003, 0.0652186)
                                scale: Qt.vector3d(1, 1, 1)
                            }
                        }
                    }
                }
            }
        }
    }

    // Animations:
}
