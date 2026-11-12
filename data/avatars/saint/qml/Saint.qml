import QtQuick
import QtQuick3D

Node {
    id: root
    objectName: "Root"

    // Resources
    property url textureData: "maps/textureData.png"
    property url textureData631: "maps/textureData631.png"
    property url textureData140: "maps/textureData140.png"
    property url textureData634: "maps/textureData634.png"
    property url textureData142: "maps/textureData142.png"
    property url textureData629: "maps/textureData629.png"
    property url textureData144: "maps/textureData144.png"
    property url textureData161: "maps/textureData161.png"
    property url textureData636: "maps/textureData636.png"
    property url textureData147: "maps/textureData147.png"
    property url textureData639: "maps/textureData639.png"
    property url textureData642: "maps/textureData642.png"
    property url textureData150: "maps/textureData150.png"
    property url textureData645: "maps/textureData645.png"
    property url textureData648: "maps/textureData648.png"
    property url textureData153: "maps/textureData153.png"
    property url textureData651: "maps/textureData651.png"
    property url textureData155: "maps/textureData155.png"
    property url textureData164: "maps/textureData164.png"
    property url textureData658: "maps/textureData658.png"
    property url textureData158: "maps/textureData158.png"
    property url textureData167: "maps/textureData167.png"
    property url textureData660: "maps/textureData660.png"
    Texture {
        id: _8_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData161
    }
    Texture {
        id: _0_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData140
    }
    Texture {
        id: _1_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData142
    }
    Texture {
        id: _3_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData147
    }
    Texture {
        id: _10_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData167
    }
    Texture {
        id: _4_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData150
    }
    Texture {
        id: _9_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData164
    }
    Texture {
        id: _5_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData153
    }
    Texture {
        id: _6_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData155
    }
    Texture {
        id: _7_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData158
    }
    Texture {
        id: _11_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData629
    }
    Texture {
        id: _17_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData645
    }
    Texture {
        id: _13_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData634
    }
    Texture {
        id: _18_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData648
    }
    Texture {
        id: _15_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData639
    }
    Texture {
        id: _19_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData651
    }
    Texture {
        id: _12_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData631
    }
    Texture {
        id: _2_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData144
    }
    Texture {
        id: _16_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData642
    }
    Texture {
        id: _21_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData660
    }
    Texture {
        id: _14_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData636
    }
    Texture {
        id: _22_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData
    }
    Texture {
        id: _20_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: root.textureData658
    }
    MorphTarget {
        id: fcl_EYE_Close_R_morphtarget
        objectName: "Fcl_EYE_Close_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_L_morphtarget
        objectName: "Fcl_EYE_Close_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Fun_morphtarget
        objectName: "Fcl_EYE_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_morphtarget
        objectName: "Fcl_EYE_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_R_morphtarget
        objectName: "Fcl_EYE_Joy_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_L_morphtarget
        objectName: "Fcl_EYE_Joy_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Sorrow_morphtarget
        objectName: "Fcl_EYE_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Surprised_morphtarget
        objectName: "Fcl_EYE_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Spread_morphtarget
        objectName: "Fcl_EYE_Spread"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Iris_Hide_morphtarget
        objectName: "Fcl_EYE_Iris_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Highlight_Hide_morphtarget
        objectName: "Fcl_EYE_Highlight_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Close_morphtarget
        objectName: "Fcl_MTH_Close"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Up_morphtarget
        objectName: "Fcl_MTH_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Down_morphtarget
        objectName: "Fcl_MTH_Down"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Angry_morphtarget
        objectName: "Fcl_MTH_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Small_morphtarget
        objectName: "Fcl_MTH_Small"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Large_morphtarget
        objectName: "Fcl_MTH_Large"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Neutral_morphtarget
        objectName: "Fcl_MTH_Neutral"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Fun_morphtarget
        objectName: "Fcl_MTH_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Joy_morphtarget
        objectName: "Fcl_MTH_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Sorrow_morphtarget
        objectName: "Fcl_MTH_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Surprised_morphtarget
        objectName: "Fcl_MTH_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_morphtarget
        objectName: "Fcl_MTH_SkinFung"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_R_morphtarget
        objectName: "Fcl_MTH_SkinFung_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_L_morphtarget
        objectName: "Fcl_MTH_SkinFung_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_A_morphtarget
        objectName: "Fcl_MTH_A"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_I_morphtarget
        objectName: "Fcl_MTH_I"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_U_morphtarget
        objectName: "Fcl_MTH_U"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_E_morphtarget
        objectName: "Fcl_MTH_E"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_O_morphtarget
        objectName: "Fcl_MTH_O"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Hide_morphtarget
        objectName: "Fcl_HA_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_morphtarget
        objectName: "Fcl_HA_Fung1"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_Low_morphtarget
        objectName: "Fcl_HA_Fung1_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_Up_morphtarget
        objectName: "Fcl_HA_Fung1_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_morphtarget
        objectName: "Fcl_HA_Fung2"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_Low_morphtarget
        objectName: "Fcl_HA_Fung2_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_Up_morphtarget
        objectName: "Fcl_HA_Fung2_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_morphtarget
        objectName: "Fcl_HA_Fung3"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_Up_morphtarget
        objectName: "Fcl_HA_Fung3_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_Low_morphtarget
        objectName: "Fcl_HA_Fung3_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_morphtarget
        objectName: "Fcl_HA_Short"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_Up_morphtarget
        objectName: "Fcl_HA_Short_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_Low_morphtarget
        objectName: "Fcl_HA_Short_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Neutral_morphtarget
        objectName: "Fcl_ALL_Neutral"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Angry_morphtarget
        objectName: "Fcl_ALL_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Fun_morphtarget
        objectName: "Fcl_ALL_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Joy_morphtarget
        objectName: "Fcl_ALL_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Sorrow_morphtarget
        objectName: "Fcl_ALL_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Surprised_morphtarget
        objectName: "Fcl_ALL_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Angry_morphtarget
        objectName: "Fcl_BRW_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Fun_morphtarget
        objectName: "Fcl_BRW_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Joy_morphtarget
        objectName: "Fcl_BRW_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Sorrow_morphtarget
        objectName: "Fcl_BRW_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Surprised_morphtarget
        objectName: "Fcl_BRW_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Natural_morphtarget
        objectName: "Fcl_EYE_Natural"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Angry_morphtarget
        objectName: "Fcl_EYE_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_morphtarget
        objectName: "Fcl_EYE_Close"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_R_morphtarget241
        objectName: "Fcl_EYE_Close_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_L_morphtarget242
        objectName: "Fcl_EYE_Close_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Fun_morphtarget243
        objectName: "Fcl_EYE_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_morphtarget244
        objectName: "Fcl_EYE_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_R_morphtarget245
        objectName: "Fcl_EYE_Joy_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_L_morphtarget246
        objectName: "Fcl_EYE_Joy_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Sorrow_morphtarget247
        objectName: "Fcl_EYE_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Surprised_morphtarget248
        objectName: "Fcl_EYE_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Spread_morphtarget249
        objectName: "Fcl_EYE_Spread"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Iris_Hide_morphtarget250
        objectName: "Fcl_EYE_Iris_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Highlight_Hide_morphtarget251
        objectName: "Fcl_EYE_Highlight_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Close_morphtarget252
        objectName: "Fcl_MTH_Close"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Up_morphtarget253
        objectName: "Fcl_MTH_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Down_morphtarget254
        objectName: "Fcl_MTH_Down"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Angry_morphtarget255
        objectName: "Fcl_MTH_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Small_morphtarget256
        objectName: "Fcl_MTH_Small"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Large_morphtarget257
        objectName: "Fcl_MTH_Large"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Neutral_morphtarget258
        objectName: "Fcl_MTH_Neutral"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Fun_morphtarget259
        objectName: "Fcl_MTH_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Joy_morphtarget260
        objectName: "Fcl_MTH_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Sorrow_morphtarget261
        objectName: "Fcl_MTH_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Surprised_morphtarget262
        objectName: "Fcl_MTH_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_morphtarget263
        objectName: "Fcl_MTH_SkinFung"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_R_morphtarget264
        objectName: "Fcl_MTH_SkinFung_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_L_morphtarget265
        objectName: "Fcl_MTH_SkinFung_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_A_morphtarget266
        objectName: "Fcl_MTH_A"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_I_morphtarget267
        objectName: "Fcl_MTH_I"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_U_morphtarget268
        objectName: "Fcl_MTH_U"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_E_morphtarget269
        objectName: "Fcl_MTH_E"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_O_morphtarget270
        objectName: "Fcl_MTH_O"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Hide_morphtarget271
        objectName: "Fcl_HA_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_morphtarget272
        objectName: "Fcl_HA_Fung1"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_Low_morphtarget273
        objectName: "Fcl_HA_Fung1_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_Up_morphtarget274
        objectName: "Fcl_HA_Fung1_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_morphtarget275
        objectName: "Fcl_HA_Fung2"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_Low_morphtarget276
        objectName: "Fcl_HA_Fung2_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_Up_morphtarget277
        objectName: "Fcl_HA_Fung2_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_morphtarget278
        objectName: "Fcl_HA_Fung3"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_Up_morphtarget279
        objectName: "Fcl_HA_Fung3_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_Low_morphtarget280
        objectName: "Fcl_HA_Fung3_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_morphtarget281
        objectName: "Fcl_HA_Short"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_Up_morphtarget282
        objectName: "Fcl_HA_Short_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_Low_morphtarget283
        objectName: "Fcl_HA_Short_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Neutral_morphtarget284
        objectName: "Fcl_ALL_Neutral"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Angry_morphtarget285
        objectName: "Fcl_ALL_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Fun_morphtarget286
        objectName: "Fcl_ALL_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Joy_morphtarget287
        objectName: "Fcl_ALL_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Sorrow_morphtarget288
        objectName: "Fcl_ALL_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Surprised_morphtarget289
        objectName: "Fcl_ALL_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Angry_morphtarget290
        objectName: "Fcl_BRW_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Fun_morphtarget291
        objectName: "Fcl_BRW_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Joy_morphtarget292
        objectName: "Fcl_BRW_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Sorrow_morphtarget293
        objectName: "Fcl_BRW_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Surprised_morphtarget294
        objectName: "Fcl_BRW_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Natural_morphtarget295
        objectName: "Fcl_EYE_Natural"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Angry_morphtarget296
        objectName: "Fcl_EYE_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_morphtarget297
        objectName: "Fcl_EYE_Close"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_R_morphtarget298
        objectName: "Fcl_EYE_Close_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_L_morphtarget299
        objectName: "Fcl_EYE_Close_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Fun_morphtarget300
        objectName: "Fcl_EYE_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_morphtarget301
        objectName: "Fcl_EYE_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_R_morphtarget302
        objectName: "Fcl_EYE_Joy_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_L_morphtarget303
        objectName: "Fcl_EYE_Joy_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Sorrow_morphtarget304
        objectName: "Fcl_EYE_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Surprised_morphtarget305
        objectName: "Fcl_EYE_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Spread_morphtarget306
        objectName: "Fcl_EYE_Spread"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Iris_Hide_morphtarget307
        objectName: "Fcl_EYE_Iris_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Highlight_Hide_morphtarget308
        objectName: "Fcl_EYE_Highlight_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Close_morphtarget309
        objectName: "Fcl_MTH_Close"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Up_morphtarget310
        objectName: "Fcl_MTH_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Down_morphtarget311
        objectName: "Fcl_MTH_Down"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Angry_morphtarget312
        objectName: "Fcl_MTH_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Small_morphtarget313
        objectName: "Fcl_MTH_Small"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Large_morphtarget314
        objectName: "Fcl_MTH_Large"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Neutral_morphtarget315
        objectName: "Fcl_MTH_Neutral"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Fun_morphtarget316
        objectName: "Fcl_MTH_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Joy_morphtarget317
        objectName: "Fcl_MTH_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Sorrow_morphtarget318
        objectName: "Fcl_MTH_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Surprised_morphtarget319
        objectName: "Fcl_MTH_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_morphtarget320
        objectName: "Fcl_MTH_SkinFung"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_R_morphtarget321
        objectName: "Fcl_MTH_SkinFung_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_L_morphtarget322
        objectName: "Fcl_MTH_SkinFung_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_A_morphtarget323
        objectName: "Fcl_MTH_A"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_I_morphtarget324
        objectName: "Fcl_MTH_I"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_U_morphtarget325
        objectName: "Fcl_MTH_U"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_E_morphtarget326
        objectName: "Fcl_MTH_E"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_O_morphtarget327
        objectName: "Fcl_MTH_O"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Hide_morphtarget328
        objectName: "Fcl_HA_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_morphtarget329
        objectName: "Fcl_HA_Fung1"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_Low_morphtarget330
        objectName: "Fcl_HA_Fung1_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_Up_morphtarget331
        objectName: "Fcl_HA_Fung1_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_morphtarget332
        objectName: "Fcl_HA_Fung2"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_Low_morphtarget333
        objectName: "Fcl_HA_Fung2_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_Up_morphtarget334
        objectName: "Fcl_HA_Fung2_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_morphtarget335
        objectName: "Fcl_HA_Fung3"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_Up_morphtarget336
        objectName: "Fcl_HA_Fung3_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_Low_morphtarget337
        objectName: "Fcl_HA_Fung3_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_morphtarget338
        objectName: "Fcl_HA_Short"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_Up_morphtarget339
        objectName: "Fcl_HA_Short_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_Low_morphtarget340
        objectName: "Fcl_HA_Short_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Neutral_morphtarget341
        objectName: "Fcl_ALL_Neutral"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Angry_morphtarget342
        objectName: "Fcl_ALL_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Fun_morphtarget343
        objectName: "Fcl_ALL_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Joy_morphtarget344
        objectName: "Fcl_ALL_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Sorrow_morphtarget345
        objectName: "Fcl_ALL_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Surprised_morphtarget346
        objectName: "Fcl_ALL_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Angry_morphtarget347
        objectName: "Fcl_BRW_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Fun_morphtarget348
        objectName: "Fcl_BRW_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Joy_morphtarget349
        objectName: "Fcl_BRW_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Sorrow_morphtarget350
        objectName: "Fcl_BRW_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Surprised_morphtarget351
        objectName: "Fcl_BRW_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Natural_morphtarget352
        objectName: "Fcl_EYE_Natural"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Angry_morphtarget353
        objectName: "Fcl_EYE_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_morphtarget354
        objectName: "Fcl_EYE_Close"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_R_morphtarget355
        objectName: "Fcl_EYE_Close_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_L_morphtarget356
        objectName: "Fcl_EYE_Close_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Fun_morphtarget357
        objectName: "Fcl_EYE_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_morphtarget358
        objectName: "Fcl_EYE_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_R_morphtarget359
        objectName: "Fcl_EYE_Joy_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_L_morphtarget360
        objectName: "Fcl_EYE_Joy_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Sorrow_morphtarget361
        objectName: "Fcl_EYE_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Surprised_morphtarget362
        objectName: "Fcl_EYE_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Spread_morphtarget363
        objectName: "Fcl_EYE_Spread"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Iris_Hide_morphtarget364
        objectName: "Fcl_EYE_Iris_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Highlight_Hide_morphtarget365
        objectName: "Fcl_EYE_Highlight_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Close_morphtarget366
        objectName: "Fcl_MTH_Close"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Up_morphtarget367
        objectName: "Fcl_MTH_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Down_morphtarget368
        objectName: "Fcl_MTH_Down"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Angry_morphtarget369
        objectName: "Fcl_MTH_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Small_morphtarget370
        objectName: "Fcl_MTH_Small"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Large_morphtarget371
        objectName: "Fcl_MTH_Large"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Neutral_morphtarget372
        objectName: "Fcl_MTH_Neutral"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Fun_morphtarget373
        objectName: "Fcl_MTH_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Joy_morphtarget374
        objectName: "Fcl_MTH_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Sorrow_morphtarget375
        objectName: "Fcl_MTH_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Surprised_morphtarget376
        objectName: "Fcl_MTH_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_morphtarget377
        objectName: "Fcl_MTH_SkinFung"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_R_morphtarget378
        objectName: "Fcl_MTH_SkinFung_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_L_morphtarget379
        objectName: "Fcl_MTH_SkinFung_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_A_morphtarget380
        objectName: "Fcl_MTH_A"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_I_morphtarget381
        objectName: "Fcl_MTH_I"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_U_morphtarget382
        objectName: "Fcl_MTH_U"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_E_morphtarget383
        objectName: "Fcl_MTH_E"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_O_morphtarget384
        objectName: "Fcl_MTH_O"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Hide_morphtarget385
        objectName: "Fcl_HA_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_morphtarget386
        objectName: "Fcl_HA_Fung1"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_Low_morphtarget387
        objectName: "Fcl_HA_Fung1_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_Up_morphtarget388
        objectName: "Fcl_HA_Fung1_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_morphtarget389
        objectName: "Fcl_HA_Fung2"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_Low_morphtarget390
        objectName: "Fcl_HA_Fung2_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_Up_morphtarget391
        objectName: "Fcl_HA_Fung2_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_morphtarget392
        objectName: "Fcl_HA_Fung3"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_Up_morphtarget393
        objectName: "Fcl_HA_Fung3_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_Low_morphtarget394
        objectName: "Fcl_HA_Fung3_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_morphtarget395
        objectName: "Fcl_HA_Short"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_Up_morphtarget396
        objectName: "Fcl_HA_Short_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_Low_morphtarget397
        objectName: "Fcl_HA_Short_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Neutral_morphtarget398
        objectName: "Fcl_ALL_Neutral"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Angry_morphtarget399
        objectName: "Fcl_ALL_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Fun_morphtarget400
        objectName: "Fcl_ALL_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Joy_morphtarget401
        objectName: "Fcl_ALL_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Sorrow_morphtarget402
        objectName: "Fcl_ALL_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Surprised_morphtarget403
        objectName: "Fcl_ALL_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Angry_morphtarget404
        objectName: "Fcl_BRW_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Fun_morphtarget405
        objectName: "Fcl_BRW_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Joy_morphtarget406
        objectName: "Fcl_BRW_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Sorrow_morphtarget407
        objectName: "Fcl_BRW_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Surprised_morphtarget408
        objectName: "Fcl_BRW_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Natural_morphtarget409
        objectName: "Fcl_EYE_Natural"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Angry_morphtarget410
        objectName: "Fcl_EYE_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_morphtarget411
        objectName: "Fcl_EYE_Close"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_R_morphtarget412
        objectName: "Fcl_EYE_Close_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_L_morphtarget413
        objectName: "Fcl_EYE_Close_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Fun_morphtarget414
        objectName: "Fcl_EYE_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_morphtarget415
        objectName: "Fcl_EYE_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_R_morphtarget416
        objectName: "Fcl_EYE_Joy_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_L_morphtarget417
        objectName: "Fcl_EYE_Joy_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Sorrow_morphtarget418
        objectName: "Fcl_EYE_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Surprised_morphtarget419
        objectName: "Fcl_EYE_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Spread_morphtarget420
        objectName: "Fcl_EYE_Spread"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Iris_Hide_morphtarget421
        objectName: "Fcl_EYE_Iris_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Highlight_Hide_morphtarget422
        objectName: "Fcl_EYE_Highlight_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Close_morphtarget423
        objectName: "Fcl_MTH_Close"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Up_morphtarget424
        objectName: "Fcl_MTH_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Down_morphtarget425
        objectName: "Fcl_MTH_Down"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Angry_morphtarget426
        objectName: "Fcl_MTH_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Small_morphtarget427
        objectName: "Fcl_MTH_Small"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Large_morphtarget428
        objectName: "Fcl_MTH_Large"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Neutral_morphtarget429
        objectName: "Fcl_MTH_Neutral"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Fun_morphtarget430
        objectName: "Fcl_MTH_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Joy_morphtarget431
        objectName: "Fcl_MTH_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Sorrow_morphtarget432
        objectName: "Fcl_MTH_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Surprised_morphtarget433
        objectName: "Fcl_MTH_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_morphtarget434
        objectName: "Fcl_MTH_SkinFung"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_R_morphtarget435
        objectName: "Fcl_MTH_SkinFung_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_L_morphtarget436
        objectName: "Fcl_MTH_SkinFung_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_A_morphtarget437
        objectName: "Fcl_MTH_A"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_I_morphtarget438
        objectName: "Fcl_MTH_I"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_U_morphtarget439
        objectName: "Fcl_MTH_U"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_E_morphtarget440
        objectName: "Fcl_MTH_E"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_O_morphtarget441
        objectName: "Fcl_MTH_O"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Hide_morphtarget442
        objectName: "Fcl_HA_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_morphtarget443
        objectName: "Fcl_HA_Fung1"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_Low_morphtarget444
        objectName: "Fcl_HA_Fung1_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_Up_morphtarget445
        objectName: "Fcl_HA_Fung1_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_morphtarget446
        objectName: "Fcl_HA_Fung2"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_Low_morphtarget447
        objectName: "Fcl_HA_Fung2_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_Up_morphtarget448
        objectName: "Fcl_HA_Fung2_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_morphtarget449
        objectName: "Fcl_HA_Fung3"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_Up_morphtarget450
        objectName: "Fcl_HA_Fung3_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_Low_morphtarget451
        objectName: "Fcl_HA_Fung3_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_morphtarget452
        objectName: "Fcl_HA_Short"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_Up_morphtarget453
        objectName: "Fcl_HA_Short_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_Low_morphtarget454
        objectName: "Fcl_HA_Short_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Neutral_morphtarget455
        objectName: "Fcl_ALL_Neutral"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Angry_morphtarget456
        objectName: "Fcl_ALL_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Fun_morphtarget457
        objectName: "Fcl_ALL_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Joy_morphtarget458
        objectName: "Fcl_ALL_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Sorrow_morphtarget459
        objectName: "Fcl_ALL_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Surprised_morphtarget460
        objectName: "Fcl_ALL_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Angry_morphtarget461
        objectName: "Fcl_BRW_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Fun_morphtarget462
        objectName: "Fcl_BRW_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Joy_morphtarget463
        objectName: "Fcl_BRW_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Sorrow_morphtarget464
        objectName: "Fcl_BRW_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Surprised_morphtarget465
        objectName: "Fcl_BRW_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Natural_morphtarget466
        objectName: "Fcl_EYE_Natural"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Angry_morphtarget467
        objectName: "Fcl_EYE_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_morphtarget468
        objectName: "Fcl_EYE_Close"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_R_morphtarget469
        objectName: "Fcl_EYE_Close_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_L_morphtarget470
        objectName: "Fcl_EYE_Close_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Fun_morphtarget471
        objectName: "Fcl_EYE_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_morphtarget472
        objectName: "Fcl_EYE_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_R_morphtarget473
        objectName: "Fcl_EYE_Joy_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_L_morphtarget474
        objectName: "Fcl_EYE_Joy_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Sorrow_morphtarget475
        objectName: "Fcl_EYE_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Surprised_morphtarget476
        objectName: "Fcl_EYE_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Spread_morphtarget477
        objectName: "Fcl_EYE_Spread"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Iris_Hide_morphtarget478
        objectName: "Fcl_EYE_Iris_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Highlight_Hide_morphtarget479
        objectName: "Fcl_EYE_Highlight_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Close_morphtarget480
        objectName: "Fcl_MTH_Close"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Up_morphtarget481
        objectName: "Fcl_MTH_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Down_morphtarget482
        objectName: "Fcl_MTH_Down"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Angry_morphtarget483
        objectName: "Fcl_MTH_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Small_morphtarget484
        objectName: "Fcl_MTH_Small"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Large_morphtarget485
        objectName: "Fcl_MTH_Large"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Neutral_morphtarget486
        objectName: "Fcl_MTH_Neutral"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Fun_morphtarget487
        objectName: "Fcl_MTH_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Joy_morphtarget488
        objectName: "Fcl_MTH_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Sorrow_morphtarget489
        objectName: "Fcl_MTH_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Surprised_morphtarget490
        objectName: "Fcl_MTH_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_morphtarget491
        objectName: "Fcl_MTH_SkinFung"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_R_morphtarget492
        objectName: "Fcl_MTH_SkinFung_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_L_morphtarget493
        objectName: "Fcl_MTH_SkinFung_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_A_morphtarget494
        objectName: "Fcl_MTH_A"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_I_morphtarget495
        objectName: "Fcl_MTH_I"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_U_morphtarget496
        objectName: "Fcl_MTH_U"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_E_morphtarget497
        objectName: "Fcl_MTH_E"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_O_morphtarget498
        objectName: "Fcl_MTH_O"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Hide_morphtarget499
        objectName: "Fcl_HA_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_morphtarget500
        objectName: "Fcl_HA_Fung1"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_Low_morphtarget501
        objectName: "Fcl_HA_Fung1_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_Up_morphtarget502
        objectName: "Fcl_HA_Fung1_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_morphtarget503
        objectName: "Fcl_HA_Fung2"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_Low_morphtarget504
        objectName: "Fcl_HA_Fung2_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_Up_morphtarget505
        objectName: "Fcl_HA_Fung2_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_morphtarget506
        objectName: "Fcl_HA_Fung3"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_Up_morphtarget507
        objectName: "Fcl_HA_Fung3_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_Low_morphtarget508
        objectName: "Fcl_HA_Fung3_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_morphtarget509
        objectName: "Fcl_HA_Short"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_Up_morphtarget510
        objectName: "Fcl_HA_Short_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_Low_morphtarget511
        objectName: "Fcl_HA_Short_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Neutral_morphtarget512
        objectName: "Fcl_ALL_Neutral"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Angry_morphtarget513
        objectName: "Fcl_ALL_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Fun_morphtarget514
        objectName: "Fcl_ALL_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Joy_morphtarget515
        objectName: "Fcl_ALL_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Sorrow_morphtarget516
        objectName: "Fcl_ALL_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Surprised_morphtarget517
        objectName: "Fcl_ALL_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Angry_morphtarget518
        objectName: "Fcl_BRW_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Fun_morphtarget519
        objectName: "Fcl_BRW_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Joy_morphtarget520
        objectName: "Fcl_BRW_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Sorrow_morphtarget521
        objectName: "Fcl_BRW_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Surprised_morphtarget522
        objectName: "Fcl_BRW_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Natural_morphtarget523
        objectName: "Fcl_EYE_Natural"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Angry_morphtarget524
        objectName: "Fcl_EYE_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_morphtarget525
        objectName: "Fcl_EYE_Close"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_R_morphtarget526
        objectName: "Fcl_EYE_Close_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_L_morphtarget527
        objectName: "Fcl_EYE_Close_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Fun_morphtarget528
        objectName: "Fcl_EYE_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_morphtarget529
        objectName: "Fcl_EYE_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_R_morphtarget530
        objectName: "Fcl_EYE_Joy_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_L_morphtarget531
        objectName: "Fcl_EYE_Joy_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Sorrow_morphtarget532
        objectName: "Fcl_EYE_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Surprised_morphtarget533
        objectName: "Fcl_EYE_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Spread_morphtarget534
        objectName: "Fcl_EYE_Spread"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Iris_Hide_morphtarget535
        objectName: "Fcl_EYE_Iris_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Highlight_Hide_morphtarget536
        objectName: "Fcl_EYE_Highlight_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Close_morphtarget537
        objectName: "Fcl_MTH_Close"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Up_morphtarget538
        objectName: "Fcl_MTH_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Down_morphtarget539
        objectName: "Fcl_MTH_Down"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Angry_morphtarget540
        objectName: "Fcl_MTH_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Small_morphtarget541
        objectName: "Fcl_MTH_Small"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Large_morphtarget542
        objectName: "Fcl_MTH_Large"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Neutral_morphtarget543
        objectName: "Fcl_MTH_Neutral"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Fun_morphtarget544
        objectName: "Fcl_MTH_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Joy_morphtarget545
        objectName: "Fcl_MTH_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Sorrow_morphtarget546
        objectName: "Fcl_MTH_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Surprised_morphtarget547
        objectName: "Fcl_MTH_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_morphtarget548
        objectName: "Fcl_MTH_SkinFung"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_R_morphtarget549
        objectName: "Fcl_MTH_SkinFung_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_L_morphtarget550
        objectName: "Fcl_MTH_SkinFung_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_A_morphtarget551
        objectName: "Fcl_MTH_A"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_I_morphtarget552
        objectName: "Fcl_MTH_I"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_U_morphtarget553
        objectName: "Fcl_MTH_U"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_E_morphtarget554
        objectName: "Fcl_MTH_E"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_O_morphtarget555
        objectName: "Fcl_MTH_O"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Hide_morphtarget556
        objectName: "Fcl_HA_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_morphtarget557
        objectName: "Fcl_HA_Fung1"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_Low_morphtarget558
        objectName: "Fcl_HA_Fung1_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_Up_morphtarget559
        objectName: "Fcl_HA_Fung1_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_morphtarget560
        objectName: "Fcl_HA_Fung2"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_Low_morphtarget561
        objectName: "Fcl_HA_Fung2_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_Up_morphtarget562
        objectName: "Fcl_HA_Fung2_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_morphtarget563
        objectName: "Fcl_HA_Fung3"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_Up_morphtarget564
        objectName: "Fcl_HA_Fung3_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_Low_morphtarget565
        objectName: "Fcl_HA_Fung3_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_morphtarget566
        objectName: "Fcl_HA_Short"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_Up_morphtarget567
        objectName: "Fcl_HA_Short_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_Low_morphtarget568
        objectName: "Fcl_HA_Short_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Neutral_morphtarget569
        objectName: "Fcl_ALL_Neutral"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Angry_morphtarget570
        objectName: "Fcl_ALL_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Fun_morphtarget571
        objectName: "Fcl_ALL_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Joy_morphtarget572
        objectName: "Fcl_ALL_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Sorrow_morphtarget573
        objectName: "Fcl_ALL_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Surprised_morphtarget574
        objectName: "Fcl_ALL_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Angry_morphtarget575
        objectName: "Fcl_BRW_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Fun_morphtarget576
        objectName: "Fcl_BRW_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Joy_morphtarget577
        objectName: "Fcl_BRW_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Sorrow_morphtarget578
        objectName: "Fcl_BRW_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Surprised_morphtarget579
        objectName: "Fcl_BRW_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Natural_morphtarget580
        objectName: "Fcl_EYE_Natural"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Angry_morphtarget581
        objectName: "Fcl_EYE_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_morphtarget582
        objectName: "Fcl_EYE_Close"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_R_morphtarget583
        objectName: "Fcl_EYE_Close_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_L_morphtarget584
        objectName: "Fcl_EYE_Close_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Fun_morphtarget585
        objectName: "Fcl_EYE_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_morphtarget586
        objectName: "Fcl_EYE_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_R_morphtarget587
        objectName: "Fcl_EYE_Joy_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Joy_L_morphtarget588
        objectName: "Fcl_EYE_Joy_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Sorrow_morphtarget589
        objectName: "Fcl_EYE_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Surprised_morphtarget590
        objectName: "Fcl_EYE_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Spread_morphtarget591
        objectName: "Fcl_EYE_Spread"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Iris_Hide_morphtarget592
        objectName: "Fcl_EYE_Iris_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Highlight_Hide_morphtarget593
        objectName: "Fcl_EYE_Highlight_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Close_morphtarget594
        objectName: "Fcl_MTH_Close"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Up_morphtarget595
        objectName: "Fcl_MTH_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Down_morphtarget596
        objectName: "Fcl_MTH_Down"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Angry_morphtarget597
        objectName: "Fcl_MTH_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Small_morphtarget598
        objectName: "Fcl_MTH_Small"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Large_morphtarget599
        objectName: "Fcl_MTH_Large"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Neutral_morphtarget600
        objectName: "Fcl_MTH_Neutral"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Fun_morphtarget601
        objectName: "Fcl_MTH_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Joy_morphtarget602
        objectName: "Fcl_MTH_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Sorrow_morphtarget603
        objectName: "Fcl_MTH_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_Surprised_morphtarget604
        objectName: "Fcl_MTH_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_morphtarget605
        objectName: "Fcl_MTH_SkinFung"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_R_morphtarget606
        objectName: "Fcl_MTH_SkinFung_R"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_SkinFung_L_morphtarget607
        objectName: "Fcl_MTH_SkinFung_L"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_A_morphtarget608
        objectName: "Fcl_MTH_A"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_I_morphtarget609
        objectName: "Fcl_MTH_I"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_U_morphtarget610
        objectName: "Fcl_MTH_U"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_E_morphtarget611
        objectName: "Fcl_MTH_E"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_MTH_O_morphtarget612
        objectName: "Fcl_MTH_O"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Hide_morphtarget613
        objectName: "Fcl_HA_Hide"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_morphtarget614
        objectName: "Fcl_HA_Fung1"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_Low_morphtarget615
        objectName: "Fcl_HA_Fung1_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung1_Up_morphtarget616
        objectName: "Fcl_HA_Fung1_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_morphtarget617
        objectName: "Fcl_HA_Fung2"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_Low_morphtarget618
        objectName: "Fcl_HA_Fung2_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung2_Up_morphtarget619
        objectName: "Fcl_HA_Fung2_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_morphtarget620
        objectName: "Fcl_HA_Fung3"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_Up_morphtarget621
        objectName: "Fcl_HA_Fung3_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Fung3_Low_morphtarget622
        objectName: "Fcl_HA_Fung3_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_morphtarget623
        objectName: "Fcl_HA_Short"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_Up_morphtarget624
        objectName: "Fcl_HA_Short_Up"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_HA_Short_Low_morphtarget625
        objectName: "Fcl_HA_Short_Low"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    PrincipledMaterial {
        id: n00_000_00_Body_00_SKIN__Instance__material
        objectName: "N00_000_00_Body_00_SKIN (Instance)"
        baseColorMap: _11_texture
        roughness: 0.8999999761581421
        normalMap: _12_texture
        emissiveMap: _2_texture
        alphaMode: PrincipledMaterial.Mask
        depthDrawMode: PrincipledMaterial.OpaquePrePassDepthDraw
        lighting: PrincipledMaterial.NoLighting
    }
    PrincipledMaterial {
        id: n00_000_00_FaceMouth_00_FACE__Instance__material
        objectName: "N00_000_00_FaceMouth_00_FACE (Instance)"
        baseColorMap: _0_texture
        roughness: 0.8999999761581421
        normalMap: _1_texture
        emissiveMap: _2_texture
        alphaMode: PrincipledMaterial.Mask
        depthDrawMode: PrincipledMaterial.OpaquePrePassDepthDraw
        lighting: PrincipledMaterial.NoLighting
    }
    PrincipledMaterial {
        id: n00_000_00_EyeIris_00_EYE__Instance__material
        objectName: "N00_000_00_EyeIris_00_EYE (Instance)"
        baseColorMap: _3_texture
        roughness: 0.8999999761581421
        normalMap: _1_texture
        emissiveMap: _2_texture
        alphaMode: PrincipledMaterial.Blend
        lighting: PrincipledMaterial.NoLighting
    }
    PrincipledMaterial {
        id: n00_000_00_EyeHighlight_00_EYE__Instance__material
        objectName: "N00_000_00_EyeHighlight_00_EYE (Instance)"
        baseColorMap: _4_texture
        roughness: 0.8999999761581421
        normalMap: _1_texture
        emissiveMap: _2_texture
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Blend
        lighting: PrincipledMaterial.NoLighting
    }
    PrincipledMaterial {
        id: n00_000_00_Face_00_SKIN__Instance__material
        objectName: "N00_000_00_Face_00_SKIN (Instance)"
        baseColorMap: _5_texture
        roughness: 0.8999999761581421
        normalMap: _6_texture
        emissiveMap: _2_texture
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Mask
        depthDrawMode: PrincipledMaterial.OpaquePrePassDepthDraw
        lighting: PrincipledMaterial.NoLighting
    }
    PrincipledMaterial {
        id: n00_000_00_HairBack_00_HAIR__Instance__material
        objectName: "N00_000_00_HairBack_00_HAIR (Instance)"
        baseColorMap: _13_texture
        roughness: 0.8999999761581421
        normalMap: _14_texture
        emissiveMap: _2_texture
        emissiveFactor: Qt.vector3d(0.858824, 0.694118, 0.694118)
        alphaMode: PrincipledMaterial.Mask
        depthDrawMode: PrincipledMaterial.OpaquePrePassDepthDraw
        lighting: PrincipledMaterial.NoLighting
    }
    PrincipledMaterial {
        id: n00_000_00_EyeWhite_00_EYE__Instance__material
        objectName: "N00_000_00_EyeWhite_00_EYE (Instance)"
        baseColorMap: _7_texture
        roughness: 0.8999999761581421
        normalMap: _1_texture
        emissiveMap: _2_texture
        alphaMode: PrincipledMaterial.Mask
        depthDrawMode: PrincipledMaterial.OpaquePrePassDepthDraw
        lighting: PrincipledMaterial.NoLighting
    }
    PrincipledMaterial {
        id: n00_000_00_FaceBrow_00_FACE__Instance__material
        objectName: "N00_000_00_FaceBrow_00_FACE (Instance)"
        baseColorMap: _8_texture
        roughness: 0.8999999761581421
        normalMap: _1_texture
        emissiveMap: _2_texture
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Blend
        lighting: PrincipledMaterial.NoLighting
    }
    PrincipledMaterial {
        id: n00_000_00_FaceEyelash_00_FACE__Instance__material
        objectName: "N00_000_00_FaceEyelash_00_FACE (Instance)"
        baseColorMap: _9_texture
        roughness: 0.8999999761581421
        normalMap: _1_texture
        emissiveMap: _2_texture
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Blend
        lighting: PrincipledMaterial.NoLighting
    }
    PrincipledMaterial {
        id: n00_000_00_FaceEyeline_00_FACE__Instance__material
        objectName: "N00_000_00_FaceEyeline_00_FACE (Instance)"
        baseColorMap: _10_texture
        roughness: 0.8999999761581421
        normalMap: _1_texture
        emissiveMap: _2_texture
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Blend
        lighting: PrincipledMaterial.NoLighting
    }
    PrincipledMaterial {
        id: n00_001_02_Bottoms_01_CLOTH__Instance__material
        objectName: "N00_001_02_Bottoms_01_CLOTH (Instance)"
        baseColorMap: _15_texture
        roughness: 0.8999999761581421
        normalMap: _1_texture
        emissiveMap: _2_texture
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Mask
        depthDrawMode: PrincipledMaterial.OpaquePrePassDepthDraw
        lighting: PrincipledMaterial.NoLighting
    }
    Skin {
        id: skin
        joints: [
            root2,
            j_Bip_C_Hips,
            j_Sec_L_SkirtSide0_01,
            j_Sec_L_SkirtSide1_01,
            j_Sec_L_SkirtSide2_01,
            j_Sec_L_SkirtSide2_end_01,
            j_Sec_R_SkirtSide0_01,
            j_Sec_R_SkirtSide1_01,
            j_Sec_R_SkirtSide2_01,
            j_Sec_R_SkirtSide2_end_01,
            j_Bip_C_Spine,
            j_Bip_C_Chest,
            j_Bip_C_UpperChest,
            j_Sec_L_Bust1,
            j_Sec_L_Bust2,
            j_Sec_R_Bust1,
            j_Sec_R_Bust2,
            j_Bip_C_Neck,
            j_Bip_C_Head,
            j_Adj_L_FaceEye,
            j_Adj_R_FaceEye,
            j_Sec_Hair1_01,
            j_Sec_Hair2_01,
            j_Sec_Hair3_01,
            j_Sec_Hair1_02,
            j_Sec_Hair2_02,
            j_Sec_Hair3_02,
            j_Sec_Hair1_03,
            j_Sec_Hair2_03,
            j_Sec_Hair3_03,
            j_Sec_Hair1_04,
            j_Sec_Hair2_04,
            j_Sec_Hair3_04,
            j_Sec_Hair1_05,
            j_Sec_Hair2_05,
            j_Sec_Hair3_05,
            j_Sec_Hair1_06,
            j_Sec_Hair2_06,
            j_Sec_Hair3_06,
            j_Sec_Hair1_07,
            j_Sec_Hair2_07,
            j_Sec_Hair3_07,
            j_Sec_Hair1_08,
            j_Sec_Hair2_08,
            j_Sec_Hair3_08,
            j_Bip_L_Shoulder,
            j_Bip_L_UpperArm,
            j_Bip_L_LowerArm,
            j_Sec_L_LowerSleeve_01,
            j_Sec_L_LowerSleeve_end_01,
            j_Bip_L_Hand,
            j_Bip_L_Index1,
            j_Bip_L_Index2,
            j_Bip_L_Index3,
            j_Bip_L_Little1,
            j_Bip_L_Little2,
            j_Bip_L_Little3,
            j_Bip_L_Middle1,
            j_Bip_L_Middle2,
            j_Bip_L_Middle3,
            j_Bip_L_Ring1,
            j_Bip_L_Ring2,
            j_Bip_L_Ring3,
            j_Bip_L_Thumb1,
            j_Bip_L_Thumb2,
            j_Bip_L_Thumb3,
            j_Sec_L_TipSleeve_01,
            j_Sec_L_TipSleeve_end_01,
            j_Bip_R_Shoulder,
            j_Bip_R_UpperArm,
            j_Bip_R_LowerArm,
            j_Sec_R_LowerSleeve_01,
            j_Sec_R_LowerSleeve_end_01,
            j_Bip_R_Hand,
            j_Bip_R_Index1,
            j_Bip_R_Index2,
            j_Bip_R_Index3,
            j_Bip_R_Little1,
            j_Bip_R_Little2,
            j_Bip_R_Little3,
            j_Bip_R_Middle1,
            j_Bip_R_Middle2,
            j_Bip_R_Middle3,
            j_Bip_R_Ring1,
            j_Bip_R_Ring2,
            j_Bip_R_Ring3,
            j_Bip_R_Thumb1,
            j_Bip_R_Thumb2,
            j_Bip_R_Thumb3,
            j_Sec_R_TipSleeve_01,
            j_Sec_R_TipSleeve_end_01,
            j_Bip_L_UpperLeg,
            j_Sec_L_SkirtBack0_01,
            j_Sec_L_SkirtBack1_01,
            j_Sec_L_SkirtBack2_01,
            j_Sec_L_SkirtBack2_end_01,
            j_Sec_L_SkirtFront0_01,
            j_Sec_L_SkirtFront1_01,
            j_Sec_L_SkirtFront2_01,
            j_Sec_L_SkirtFront2_end_01,
            j_Bip_L_LowerLeg,
            j_Bip_L_Foot,
            j_Bip_L_ToeBase,
            j_Bip_R_UpperLeg,
            j_Sec_R_SkirtBack0_01,
            j_Sec_R_SkirtBack1_01,
            j_Sec_R_SkirtBack2_01,
            j_Sec_R_SkirtBack2_end_01,
            j_Sec_R_SkirtFront0_01,
            j_Sec_R_SkirtFront1_01,
            j_Sec_R_SkirtFront2_01,
            j_Sec_R_SkirtFront2_end_01,
            j_Bip_R_LowerLeg,
            j_Bip_R_Foot,
            j_Bip_R_ToeBase
        ]
        inverseBindPoses: [
            Qt.matrix4x4(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.992088, 0.125548, -0.938575, 0, -0.125548, 0.992088, 0.115172, 0, 0, 0, 1),
            Qt.matrix4x4(-9.53675e-07, 0.0631874, -0.998002, -0.0467744, -0.388588, 0.91957, 0.0582219, -0.778062, 0.921412, 0.387812, 0.024553, -0.538367, 0, 0, 0, 1),
            Qt.matrix4x4(-9.53675e-07, 0.0631874, -0.998002, -0.0467744, -0.388588, 0.91957, 0.0582219, -0.778062, 0.921412, 0.387812, 0.024553, -0.538367, 0, 0, 0, 1),
            Qt.matrix4x4(-0.000345111, 0.0572343, -0.998361, -0.0421997, -0.312835, 0.948244, 0.0544693, -0.674806, 0.949808, 0.312341, 0.0175776, -0.481274, 0, 0, 0, 1),
            Qt.matrix4x4(0.000344098, -0.0572343, 0.998361, 0.0421997, -0.312835, 0.948244, 0.054469, -0.539394, -0.949807, -0.312341, -0.0175786, 0.481152, 0, 0, 0, 1),
            Qt.matrix4x4(-9.53675e-07, -0.0631874, 0.998002, 0.0467744, 0.388588, 0.91957, 0.0582219, -0.778062, -0.921412, 0.387812, 0.024553, -0.538367, 0, 0, 0, 1),
            Qt.matrix4x4(-9.53675e-07, -0.0631874, 0.998002, 0.0467744, 0.388588, 0.91957, 0.0582219, -0.778062, -0.921412, 0.387812, 0.024553, -0.538367, 0, 0, 0, 1),
            Qt.matrix4x4(-0.000345111, -0.0572343, 0.998361, 0.0421997, 0.312835, 0.948244, 0.0544693, -0.674807, -0.949808, 0.312341, 0.0175776, -0.481274, 0, 0, 0, 1),
            Qt.matrix4x4(-0.000345111, -0.0572342, 0.998361, 0.0421997, 0.312835, 0.948244, 0.0544693, -0.539394, -0.949808, 0.312341, 0.0175776, -0.481151, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 6.43536e-32, 0, 0.98855, 0.150896, -0.989285, 0, -0.150896, 0.98855, 0.134586, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -2.17976e-17, 0, 0.992589, -0.121518, -1.10196, 0, 0.121518, 0.992589, -0.15437, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 9.66503e-18, 0, 0.943357, -0.33178, -1.15073, 0, 0.33178, 0.943357, -0.409491, 0, 0, 0, 1),
            Qt.matrix4x4(0.890608, -0.047434, -0.45229, 0.0428981, -0.00726396, 0.992935, -0.118438, -1.1963, 0.454713, 0.108767, 0.883972, -0.222347, 0, 0, 0, 1),
            Qt.matrix4x4(0.890608, -0.047434, -0.45229, 0.0429639, -0.00726397, 0.992935, -0.118438, -1.1963, 0.454713, 0.108767, 0.883972, -0.275712, 0, 0, 0, 1),
            Qt.matrix4x4(0.890608, 0.047434, 0.45229, -0.0428981, 0.00726396, 0.992935, -0.118438, -1.1963, -0.454713, 0.108767, 0.883972, -0.222347, 0, 0, 0, 1),
            Qt.matrix4x4(0.890608, 0.047434, 0.45229, -0.0429639, 0.00726397, 0.992935, -0.118438, -1.1963, -0.454713, 0.108767, 0.883972, -0.275712, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.08406e-16, 0, 0.992864, 0.119252, -1.34143, 0, -0.119252, 0.992864, 0.195647, 0, 0, 0, 1),
            Qt.matrix4x4(1, 5.25951e-08, -4.37914e-07, -8.48482e-08, -4.78589e-08, 0.999942, 0.0108084, -1.42959, 4.38457e-07, -0.0108084, 0.999942, 0.0403668, 0, 0, 0, 1),
            Qt.matrix4x4(0.926238, -0.000104815, -0.376938, -0.0152009, 0.016399, 0.999064, 0.0400189, -1.48877, 0.376581, -0.0432485, 0.925373, 0.0637776, 0, 0, 0, 1),
            Qt.matrix4x4(0.926239, 0.000104929, 0.376937, 0.0152007, -0.0163991, 0.999064, 0.040019, -1.48877, -0.37658, -0.0432485, 0.925374, 0.0637777, 0, 0, 0, 1),
            Qt.matrix4x4(-0.983841, -0.178717, -0.0108568, 0.305734, 0.179046, -0.982031, -0.0596592, 1.51661, 4.03263e-07, -0.060639, 0.99816, 0.0182112, 0, 0, 0, 1),
            Qt.matrix4x4(-0.900025, -0.379103, -0.215028, 0.621468, 0.43584, -0.782861, -0.444042, 1.20439, 2.83122e-07, -0.493367, 0.869821, 0.683586, 0, 0, 0, 1),
            Qt.matrix4x4(-0.900025, -0.379103, -0.215028, 0.621054, 0.43584, -0.782861, -0.444042, 1.17498, 2.45869e-07, -0.493367, 0.869821, 0.683586, 0, 0, 0, 1),
            Qt.matrix4x4(-0.991273, 0.131317, 0.0116454, -0.231379, -0.131832, -0.987398, -0.0875603, 1.52608, 4.97792e-07, -0.0883314, 0.996091, 0.0600014, 0, 0, 0, 1),
            Qt.matrix4x4(-0.873316, 0.410201, 0.262783, -0.667429, -0.487155, -0.735363, -0.471086, 1.1304, 5.51343e-07, -0.539423, 0.842035, 0.753084, 0, 0, 0, 1),
            Qt.matrix4x4(-0.873316, 0.410201, 0.262783, -0.666965, -0.487155, -0.735363, -0.471086, 1.10007, 5.0664e-07, -0.539423, 0.842035, 0.753085, 0, 0, 0, 1),
            Qt.matrix4x4(-0.758365, 0.620086, -0.20094, -0.841492, -0.651831, -0.721431, 0.233782, 1.09979, 4.91738e-07, 0.308271, 0.951298, -0.497027, 0, 0, 0, 1),
            Qt.matrix4x4(-0.97833, -0.198381, -0.0592934, 0.345044, 0.207052, -0.937357, -0.280165, 1.35639, 2.55182e-07, -0.28637, 0.958119, 0.360782, 0, 0, 0, 1),
            Qt.matrix4x4(-0.97833, -0.198381, -0.0592934, 0.344866, 0.207052, -0.937356, -0.280165, 1.3319, 2.96161e-07, -0.28637, 0.958119, 0.360782, 0, 0, 0, 1),
            Qt.matrix4x4(-0.881908, -0.469668, -0.0406426, 0.635118, 0.471423, -0.878624, -0.0760325, 1.32773, 4.13507e-07, -0.0862136, 0.996277, 0.067105, 0, 0, 0, 1),
            Qt.matrix4x4(-0.794149, 0.477562, 0.375849, -0.751027, -0.607724, -0.624059, -0.491144, 0.897236, 2.23518e-07, -0.618454, 0.785821, 0.846868, 0, 0, 0, 1),
            Qt.matrix4x4(-0.794149, 0.477562, 0.375849, -0.75056, -0.607724, -0.624059, -0.491144, 0.870476, 2.83122e-07, -0.618454, 0.785821, 0.846868, 0, 0, 0, 1),
            Qt.matrix4x4(-0.999327, -0.0353718, -0.00986531, 0.141476, 0.0367218, -0.962587, -0.268479, 1.42998, 3.71132e-07, -0.26866, 0.963235, 0.434951, 0, 0, 0, 1),
            Qt.matrix4x4(-0.99935, 0.0347394, 0.00962639, 0.041794, -0.0360485, -0.963062, -0.266855, 1.37142, 4.22821e-07, -0.267029, 0.963688, 0.432634, 0, 0, 0, 1),
            Qt.matrix4x4(-0.99935, 0.0347394, 0.00962639, 0.041879, -0.0360485, -0.963062, -0.266855, 1.30529, 4.21889e-07, -0.267029, 0.963688, 0.432634, 0, 0, 0, 1),
            Qt.matrix4x4(-0.99589, -0.0905452, 0.00232404, 0.166901, 0.0905751, -0.995562, 0.0255478, 1.47886, 4.90225e-07, 0.0256533, 0.999671, 0.0898075, 0, 0, 0, 1),
            Qt.matrix4x4(-0.99587, -0.090772, 0.00219743, 0.167023, 0.0907986, -0.995578, 0.0240945, 1.42134, 6.06873e-07, 0.0241945, 0.999707, 0.0918953, 0, 0, 0, 1),
            Qt.matrix4x4(-0.99587, -0.090772, 0.00219743, 0.166837, 0.0907986, -0.995578, 0.0240945, 1.36399, 6.05476e-07, 0.0241945, 0.999707, 0.0918953, 0, 0, 0, 1),
            Qt.matrix4x4(-0.998613, -0.0525937, -0.00242336, 0.0310654, 0.0526495, -0.997555, -0.0459681, 1.47908, 2.00002e-07, -0.046032, 0.99894, 0.187857, 0, 0, 0, 1),
            Qt.matrix4x4(-0.998251, -0.059098, -0.00191901, 0.0403218, 0.0591291, -0.997725, -0.0324023, 1.42337, 2.69036e-07, -0.0324591, 0.999473, 0.16854, 0, 0, 0, 1),
            Qt.matrix4x4(-0.998251, -0.059098, -0.001919, 0.0401998, 0.0591291, -0.997725, -0.0324023, 1.36545, 2.71946e-07, -0.0324591, 0.999473, 0.16854, 0, 0, 0, 1),
            Qt.matrix4x4(-0.999307, 0.0362453, 0.00854644, -0.144734, -0.0372393, -0.972637, -0.229328, 1.44248, 5.26197e-07, -0.229487, 0.973312, 0.376786, 0, 0, 0, 1),
            Qt.matrix4x4(-0.999888, -0.0146086, -0.00337737, -0.072408, 0.014994, -0.974185, -0.225256, 1.38651, 5.10132e-07, -0.225282, 0.974294, 0.370807, 0, 0, 0, 1),
            Qt.matrix4x4(-0.999888, -0.0146086, -0.00337737, -0.0724419, 0.014994, -0.974185, -0.225256, 1.32315, 5.10132e-07, -0.225282, 0.974294, 0.370807, 0, 0, 0, 1),
            Qt.matrix4x4(0.990027, -0.140878, 3.88206e-09, 0.16484, 0.140878, 0.990027, 3.77144e-08, -1.31821, -9.15645e-09, -3.67914e-08, 1, 0.0257993, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.107344, 0, 1, 0, -1.31614, 0, 0, 1, 0.0257993, 0, 0, 0, 1),
            Qt.matrix4x4(0.999999, 2.70291e-08, 0.00169146, -0.329591, -2.71817e-08, 1, 9.02343e-08, -1.31614, -0.00169146, -9.02802e-08, 0.999999, 0.0263748, 0, 0, 0, 1),
            Qt.matrix4x4(0.0707804, -0.995133, 0.0685649, 1.26045, 0.958645, 0.048867, -0.280378, -0.485931, 0.275662, 0.0855747, 0.957438, -0.208315, 0, 0, 0, 1),
            Qt.matrix4x4(0.070781, -0.995133, 0.0685649, 1.18146, 0.958645, 0.0488677, -0.280378, -0.485735, 0.275662, 0.0855748, 0.957438, -0.208259, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.545423, 0, 1, 0, -1.31614, 0, 0, 1, 0.0254191, 0, 0, 0, 1),
            Qt.matrix4x4(0.999811, -1.77738e-09, -0.0194199, -0.610542, 2.64541e-09, 1, 4.4672e-08, -1.32311, 0.0194199, -4.4715e-08, 0.999811, -0.00610924, 0, 0, 0, 1),
            Qt.matrix4x4(0.998841, -0.0288736, -0.0385161, -0.604919, 0.0288734, 0.999583, -0.000560868, -1.34115, 0.0385163, -0.000551876, 0.999258, -0.0176686, 0, 0, 0, 1),
            Qt.matrix4x4(0.99884, -0.0347321, -0.0333433, -0.617503, 0.0347257, 0.999397, -0.000771367, -1.34482, 0.0333499, -0.000387397, 0.999444, -0.0144819, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.606187, 0, 1, 0, -1.32311, 0, 0, 1, 0.0546114, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.637458, 0, 1, 0, -1.32311, 0, 0, 1, 0.0546114, 0, 0, 0, 1),
            Qt.matrix4x4(0.999695, 0.0155363, 0.0192181, -0.674786, -0.0155363, 0.999879, -0.000149271, -1.31278, -0.0192181, -0.000149353, 0.999815, 0.0673955, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.611433, 0, 1, 0, -1.32311, 0, 0, 1, 0.023371, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.648286, 0, 1, 0, -1.32311, 0, 0, 1, 0.023371, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.671022, 0, 1, 0, -1.32311, 0, 0, 1, 0.023371, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.610681, 0, 1, 0, -1.32311, 0, 0, 1, 0.039015, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.644867, 0, 1, 0, -1.32311, 0, 0, 1, 0.039015, 0, 0, 0, 1),
            Qt.matrix4x4(0.999661, -0.012432, -0.0228667, -0.648809, 0.012432, 0.999922, -0.00014206, -1.33128, 0.0228667, -0.000142268, 0.999738, 0.0239918, 0, 0, 0, 1),
            Qt.matrix4x4(0.759128, -0.0442635, 0.649435, -0.352733, -0.6499, -0.107936, 0.752316, 0.504894, 0.0367976, -0.993172, -0.110704, 1.27652, 0, 0, 0, 1),
            Qt.matrix4x4(0.787202, -0.0338466, 0.615765, -0.428478, -0.615327, -0.109564, 0.78062, 0.486107, 0.0410442, -0.993403, -0.107076, 1.27439, 0, 0, 0, 1),
            Qt.matrix4x4(0.735822, -0.0584441, 0.674648, -0.396082, -0.676539, -0.106614, 0.728648, 0.521239, 0.0293419, -0.992581, -0.117989, 1.2809, 0, 0, 0, 1),
            Qt.matrix4x4(0.979067, -0.150702, -0.136807, -0.337845, 0.145611, 0.988246, -0.0465488, -1.36613, 0.142214, 0.0256538, 0.989503, -0.076949, 0, 0, 0, 1),
            Qt.matrix4x4(0.979067, -0.150702, -0.136807, -0.383194, 0.145611, 0.988246, -0.0465488, -1.36889, 0.142214, 0.0256538, 0.989503, -0.0809002, 0, 0, 0, 1),
            Qt.matrix4x4(0.990027, 0.140878, -3.88206e-09, -0.16484, -0.140878, 0.990027, 3.77144e-08, -1.31821, 9.15645e-09, -3.67914e-08, 1, 0.0257993, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.107344, 0, 1, 0, -1.31614, 0, 0, 1, 0.0257993, 0, 0, 0, 1),
            Qt.matrix4x4(0.999999, -2.70291e-08, -0.00169146, 0.329591, 2.71817e-08, 1, 9.02343e-08, -1.31614, 0.00169146, -9.02802e-08, 0.999999, 0.0263748, 0, 0, 0, 1),
            Qt.matrix4x4(0.0707804, 0.995133, -0.0685649, -1.26045, -0.958645, 0.048867, -0.280378, -0.485931, -0.275662, 0.0855747, 0.957438, -0.208315, 0, 0, 0, 1),
            Qt.matrix4x4(0.070781, 0.995133, -0.0685649, -1.18146, -0.958645, 0.0488677, -0.280378, -0.485735, -0.275662, 0.0855748, 0.957438, -0.208259, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.545423, 0, 1, 0, -1.31614, 0, 0, 1, 0.0254191, 0, 0, 0, 1),
            Qt.matrix4x4(0.999811, 1.77738e-09, 0.0194199, 0.610542, -2.64541e-09, 1, 4.4672e-08, -1.32311, -0.0194199, -4.4715e-08, 0.999811, -0.00610924, 0, 0, 0, 1),
            Qt.matrix4x4(0.998841, 0.0288736, 0.0385161, 0.604919, -0.0288734, 0.999583, -0.000560868, -1.34115, -0.0385163, -0.000551876, 0.999258, -0.0176686, 0, 0, 0, 1),
            Qt.matrix4x4(0.99884, 0.0347321, 0.0333433, 0.617503, -0.0347257, 0.999397, -0.000771367, -1.34482, -0.0333499, -0.000387397, 0.999444, -0.0144819, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.606187, 0, 1, 0, -1.32311, 0, 0, 1, 0.0546114, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.637458, 0, 1, 0, -1.32311, 0, 0, 1, 0.0546114, 0, 0, 0, 1),
            Qt.matrix4x4(0.999695, -0.0155363, -0.0192181, 0.674786, 0.0155363, 0.999879, -0.000149271, -1.31278, 0.0192181, -0.000149353, 0.999815, 0.0673955, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.611433, 0, 1, 0, -1.32311, 0, 0, 1, 0.023371, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.648286, 0, 1, 0, -1.32311, 0, 0, 1, 0.023371, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.671022, 0, 1, 0, -1.32311, 0, 0, 1, 0.023371, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.610681, 0, 1, 0, -1.32311, 0, 0, 1, 0.039015, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.644867, 0, 1, 0, -1.32311, 0, 0, 1, 0.039015, 0, 0, 0, 1),
            Qt.matrix4x4(0.999661, 0.012432, 0.0228667, 0.648809, -0.012432, 0.999922, -0.00014206, -1.33128, -0.0228667, -0.000142268, 0.999738, 0.0239918, 0, 0, 0, 1),
            Qt.matrix4x4(0.759128, 0.0442635, -0.649435, 0.352733, 0.6499, -0.107936, 0.752316, 0.504894, -0.0367976, -0.993172, -0.110704, 1.27652, 0, 0, 0, 1),
            Qt.matrix4x4(0.787202, 0.0338466, -0.615765, 0.428478, 0.615327, -0.109564, 0.78062, 0.486107, -0.0410442, -0.993403, -0.107076, 1.27439, 0, 0, 0, 1),
            Qt.matrix4x4(0.735822, 0.0584441, -0.674648, 0.396082, 0.676539, -0.106614, 0.728648, 0.521239, -0.0293419, -0.992581, -0.117989, 1.2809, 0, 0, 0, 1),
            Qt.matrix4x4(0.979067, 0.150702, 0.136807, 0.337845, -0.145611, 0.988246, -0.0465488, -1.36613, -0.142214, 0.0256538, 0.989503, -0.076949, 0, 0, 0, 1),
            Qt.matrix4x4(0.979067, 0.150702, 0.136807, 0.383194, -0.145611, 0.988246, -0.0465488, -1.36889, -0.142214, 0.0256538, 0.989503, -0.0809002, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0775518, 0, 0.999781, 0.0209207, -0.905186, 0, -0.0209207, 0.999781, 0.0190642, 0, 0, 0, 1),
            Qt.matrix4x4(-0.944987, -0.105431, -0.309654, 0.13233, -0.227874, 0.891326, 0.391933, -0.769215, 0.234681, 0.440933, -0.866316, -0.546666, 0, 0, 0, 1),
            Qt.matrix4x4(-0.944987, -0.105431, -0.309654, 0.13233, -0.227874, 0.891326, 0.391933, -0.769215, 0.234681, 0.440933, -0.866316, -0.546666, 0, 0, 0, 1),
            Qt.matrix4x4(-0.945495, -0.113147, -0.305349, 0.139453, -0.223875, 0.906802, 0.357198, -0.648573, 0.236475, 0.406089, -0.882707, -0.520743, 0, 0, 0, 1),
            Qt.matrix4x4(-0.945495, -0.113147, -0.305349, 0.139409, -0.223875, 0.906802, 0.357198, -0.509035, 0.236475, 0.406089, -0.882707, -0.520051, 0, 0, 0, 1),
            Qt.matrix4x4(0.895808, 0.0882061, -0.4356, -0.0827121, -0.171718, 0.972688, -0.156174, -0.849282, 0.409928, 0.214702, 0.886489, -0.354161, 0, 0, 0, 1),
            Qt.matrix4x4(0.895808, 0.0882061, -0.4356, -0.0827121, -0.171718, 0.972688, -0.156174, -0.849282, 0.409928, 0.214702, 0.886489, -0.354161, 0, 0, 0, 1),
            Qt.matrix4x4(0.89608, 0.0859134, -0.435499, -0.0809376, -0.170259, 0.972575, -0.158458, -0.718107, 0.409942, 0.216139, 0.886133, -0.354844, 0, 0, 0, 1),
            Qt.matrix4x4(-0.89608, -0.0859134, 0.435499, 0.080912, -0.170259, 0.972575, -0.158458, -0.558339, -0.409942, -0.216139, -0.886133, 0.354372, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0775518, 0, 0.997787, 0.0664965, -0.540239, 0, -0.0664965, 0.997787, 0.0440483, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0775518, 0, 0.999985, 0.00548092, -0.11721, 0, -0.00548092, 0.999985, 0.0339149, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0775518, 0, 0.999952, 0.00981418, -0.054431, 0, -0.00981418, 0.999952, -0.0767572, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.0775518, 0, 0.999781, 0.0209207, -0.905186, 0, -0.0209207, 0.999781, 0.0190642, 0, 0, 0, 1),
            Qt.matrix4x4(-0.944987, 0.105431, 0.309655, -0.13233, 0.227874, 0.891326, 0.391933, -0.769215, -0.234681, 0.440933, -0.866316, -0.546667, 0, 0, 0, 1),
            Qt.matrix4x4(-0.944987, 0.105431, 0.309655, -0.13233, 0.227874, 0.891326, 0.391933, -0.769215, -0.234681, 0.440933, -0.866316, -0.546667, 0, 0, 0, 1),
            Qt.matrix4x4(-0.945495, 0.113147, 0.305349, -0.139453, 0.223875, 0.906802, 0.357198, -0.648573, -0.236475, 0.406089, -0.882707, -0.520743, 0, 0, 0, 1),
            Qt.matrix4x4(-0.945495, 0.113147, 0.305349, -0.13941, 0.223875, 0.906802, 0.357198, -0.509035, -0.236475, 0.406089, -0.882707, -0.520052, 0, 0, 0, 1),
            Qt.matrix4x4(0.895808, -0.0882061, 0.4356, 0.082712, 0.171718, 0.972688, -0.156174, -0.849282, -0.409928, 0.214702, 0.886489, -0.354162, 0, 0, 0, 1),
            Qt.matrix4x4(0.895808, -0.0882061, 0.4356, 0.082712, 0.171718, 0.972688, -0.156174, -0.849282, -0.409928, 0.214702, 0.886489, -0.354162, 0, 0, 0, 1),
            Qt.matrix4x4(0.89608, -0.0859134, 0.435499, 0.0809376, 0.170259, 0.972575, -0.158458, -0.718107, -0.409942, 0.216139, 0.886133, -0.354844, 0, 0, 0, 1),
            Qt.matrix4x4(0.89608, -0.0859134, 0.435499, 0.0809115, 0.170259, 0.972575, -0.158458, -0.558339, -0.409942, 0.216139, 0.886133, -0.354372, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.0775518, 0, 0.997787, 0.0664965, -0.540239, 0, -0.0664965, 0.997787, 0.0440483, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.0775518, 0, 0.999985, 0.00548092, -0.11721, 0, -0.00548092, 0.999985, 0.0339149, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.0775518, 0, 0.999952, 0.00981418, -0.054431, 0, -0.00981418, 0.999952, -0.0767572, 0, 0, 0, 1)
        ]
    }
    PrincipledMaterial {
        id: n00_002_01_Tops_01_CLOTH__Instance__material
        objectName: "N00_002_01_Tops_01_CLOTH (Instance)"
        baseColorMap: _16_texture
        roughness: 0.8999999761581421
        normalMap: _1_texture
        emissiveMap: _2_texture
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Mask
        depthDrawMode: PrincipledMaterial.OpaquePrePassDepthDraw
        lighting: PrincipledMaterial.NoLighting
    }
    MorphTarget {
        id: fcl_ALL_Neutral_morphtarget170
        objectName: "Fcl_ALL_Neutral"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Angry_morphtarget171
        objectName: "Fcl_ALL_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    PrincipledMaterial {
        id: n00_008_01_Shoes_01_CLOTH_01__Instance__material
        objectName: "N00_008_01_Shoes_01_CLOTH_01 (Instance)"
        baseColorMap: _17_texture
        roughness: 0.8999999761581421
        normalMap: _1_texture
        emissiveMap: _2_texture
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Mask
        depthDrawMode: PrincipledMaterial.OpaquePrePassDepthDraw
        lighting: PrincipledMaterial.NoLighting
    }
    MorphTarget {
        id: fcl_ALL_Fun_morphtarget172
        objectName: "Fcl_ALL_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Joy_morphtarget173
        objectName: "Fcl_ALL_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    PrincipledMaterial {
        id: n00_008_01_Shoes_01_CLOTH_02__Instance__material
        objectName: "N00_008_01_Shoes_01_CLOTH_02 (Instance)"
        baseColorMap: _18_texture
        roughness: 0.8999999761581421
        normalMap: _1_texture
        emissiveMap: _2_texture
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Mask
        depthDrawMode: PrincipledMaterial.OpaquePrePassDepthDraw
        lighting: PrincipledMaterial.NoLighting
    }
    MorphTarget {
        id: fcl_ALL_Sorrow_morphtarget174
        objectName: "Fcl_ALL_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_ALL_Surprised_morphtarget175
        objectName: "Fcl_ALL_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    PrincipledMaterial {
        id: n00_010_01_Onepiece_00_CLOTH__Instance__material
        objectName: "N00_010_01_Onepiece_00_CLOTH (Instance)"
        baseColorMap: _19_texture
        roughness: 0.8999999761581421
        normalMap: _1_texture
        emissiveMap: _2_texture
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Mask
        depthDrawMode: PrincipledMaterial.OpaquePrePassDepthDraw
        lighting: PrincipledMaterial.NoLighting
    }
    MorphTarget {
        id: fcl_BRW_Angry_morphtarget176
        objectName: "Fcl_BRW_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Fun_morphtarget177
        objectName: "Fcl_BRW_Fun"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    Skin {
        id: skin653
        joints: [
            root2,
            j_Bip_C_Hips,
            j_Sec_L_SkirtSide0_01,
            j_Sec_L_SkirtSide1_01,
            j_Sec_L_SkirtSide2_01,
            j_Sec_L_SkirtSide2_end_01,
            j_Sec_R_SkirtSide0_01,
            j_Sec_R_SkirtSide1_01,
            j_Sec_R_SkirtSide2_01,
            j_Sec_R_SkirtSide2_end_01,
            j_Bip_C_Spine,
            j_Bip_C_Chest,
            j_Bip_C_UpperChest,
            j_Sec_L_Bust1,
            j_Sec_L_Bust2,
            j_Sec_R_Bust1,
            j_Sec_R_Bust2,
            j_Bip_C_Neck,
            j_Bip_C_Head,
            j_Adj_L_FaceEye,
            j_Adj_R_FaceEye,
            j_Sec_Hair1_01,
            j_Sec_Hair2_01,
            j_Sec_Hair3_01,
            j_Sec_Hair1_02,
            j_Sec_Hair2_02,
            j_Sec_Hair3_02,
            j_Sec_Hair1_03,
            j_Sec_Hair2_03,
            j_Sec_Hair3_03,
            j_Sec_Hair1_04,
            j_Sec_Hair2_04,
            j_Sec_Hair3_04,
            j_Sec_Hair1_05,
            j_Sec_Hair2_05,
            j_Sec_Hair3_05,
            j_Sec_Hair1_06,
            j_Sec_Hair2_06,
            j_Sec_Hair3_06,
            j_Sec_Hair1_07,
            j_Sec_Hair2_07,
            j_Sec_Hair3_07,
            j_Sec_Hair1_08,
            j_Sec_Hair2_08,
            j_Sec_Hair3_08,
            j_Bip_L_Shoulder,
            j_Bip_L_UpperArm,
            j_Bip_L_LowerArm,
            j_Sec_L_LowerSleeve_01,
            j_Sec_L_LowerSleeve_end_01,
            j_Bip_L_Hand,
            j_Bip_L_Index1,
            j_Bip_L_Index2,
            j_Bip_L_Index3,
            j_Bip_L_Little1,
            j_Bip_L_Little2,
            j_Bip_L_Little3,
            j_Bip_L_Middle1,
            j_Bip_L_Middle2,
            j_Bip_L_Middle3,
            j_Bip_L_Ring1,
            j_Bip_L_Ring2,
            j_Bip_L_Ring3,
            j_Bip_L_Thumb1,
            j_Bip_L_Thumb2,
            j_Bip_L_Thumb3,
            j_Sec_L_TipSleeve_01,
            j_Sec_L_TipSleeve_end_01,
            j_Bip_R_Shoulder,
            j_Bip_R_UpperArm,
            j_Bip_R_LowerArm,
            j_Sec_R_LowerSleeve_01,
            j_Sec_R_LowerSleeve_end_01,
            j_Bip_R_Hand,
            j_Bip_R_Index1,
            j_Bip_R_Index2,
            j_Bip_R_Index3,
            j_Bip_R_Little1,
            j_Bip_R_Little2,
            j_Bip_R_Little3,
            j_Bip_R_Middle1,
            j_Bip_R_Middle2,
            j_Bip_R_Middle3,
            j_Bip_R_Ring1,
            j_Bip_R_Ring2,
            j_Bip_R_Ring3,
            j_Bip_R_Thumb1,
            j_Bip_R_Thumb2,
            j_Bip_R_Thumb3,
            j_Sec_R_TipSleeve_01,
            j_Sec_R_TipSleeve_end_01,
            j_Bip_L_UpperLeg,
            j_Sec_L_SkirtBack0_01,
            j_Sec_L_SkirtBack1_01,
            j_Sec_L_SkirtBack2_01,
            j_Sec_L_SkirtBack2_end_01,
            j_Sec_L_SkirtFront0_01,
            j_Sec_L_SkirtFront1_01,
            j_Sec_L_SkirtFront2_01,
            j_Sec_L_SkirtFront2_end_01,
            j_Bip_L_LowerLeg,
            j_Bip_L_Foot,
            j_Bip_L_ToeBase,
            j_Bip_R_UpperLeg,
            j_Sec_R_SkirtBack0_01,
            j_Sec_R_SkirtBack1_01,
            j_Sec_R_SkirtBack2_01,
            j_Sec_R_SkirtBack2_end_01,
            j_Sec_R_SkirtFront0_01,
            j_Sec_R_SkirtFront1_01,
            j_Sec_R_SkirtFront2_01,
            j_Sec_R_SkirtFront2_end_01,
            j_Bip_R_LowerLeg,
            j_Bip_R_Foot,
            j_Bip_R_ToeBase
        ]
        inverseBindPoses: [
            Qt.matrix4x4(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.992088, 0.125548, -0.938575, 0, -0.125548, 0.992088, 0.115172, 0, 0, 0, 1),
            Qt.matrix4x4(-9.53675e-07, 0.0631874, -0.998002, -0.0467744, -0.388588, 0.91957, 0.0582219, -0.778062, 0.921412, 0.387812, 0.024553, -0.538367, 0, 0, 0, 1),
            Qt.matrix4x4(-9.53675e-07, 0.0631874, -0.998002, -0.0467744, -0.388588, 0.91957, 0.0582219, -0.778062, 0.921412, 0.387812, 0.024553, -0.538367, 0, 0, 0, 1),
            Qt.matrix4x4(-0.000345111, 0.0572343, -0.998361, -0.0421997, -0.312835, 0.948244, 0.0544693, -0.674806, 0.949808, 0.312341, 0.0175776, -0.481274, 0, 0, 0, 1),
            Qt.matrix4x4(0.000344098, -0.0572343, 0.998361, 0.0421997, -0.312835, 0.948244, 0.054469, -0.539394, -0.949807, -0.312341, -0.0175786, 0.481152, 0, 0, 0, 1),
            Qt.matrix4x4(-9.53675e-07, -0.0631874, 0.998002, 0.0467744, 0.388588, 0.91957, 0.0582219, -0.778062, -0.921412, 0.387812, 0.024553, -0.538367, 0, 0, 0, 1),
            Qt.matrix4x4(-9.53675e-07, -0.0631874, 0.998002, 0.0467744, 0.388588, 0.91957, 0.0582219, -0.778062, -0.921412, 0.387812, 0.024553, -0.538367, 0, 0, 0, 1),
            Qt.matrix4x4(-0.000345111, -0.0572343, 0.998361, 0.0421997, 0.312835, 0.948244, 0.0544693, -0.674807, -0.949808, 0.312341, 0.0175776, -0.481274, 0, 0, 0, 1),
            Qt.matrix4x4(-0.000345111, -0.0572342, 0.998361, 0.0421997, 0.312835, 0.948244, 0.0544693, -0.539394, -0.949808, 0.312341, 0.0175776, -0.481151, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 6.43536e-32, 0, 0.98855, 0.150896, -0.989285, 0, -0.150896, 0.98855, 0.134586, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -2.17976e-17, 0, 0.992589, -0.121518, -1.10196, 0, 0.121518, 0.992589, -0.15437, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 9.66503e-18, 0, 0.943357, -0.33178, -1.15073, 0, 0.33178, 0.943357, -0.409491, 0, 0, 0, 1),
            Qt.matrix4x4(0.890608, -0.047434, -0.45229, 0.0428981, -0.00726396, 0.992935, -0.118438, -1.1963, 0.454713, 0.108767, 0.883972, -0.222347, 0, 0, 0, 1),
            Qt.matrix4x4(0.890608, -0.047434, -0.45229, 0.0429639, -0.00726397, 0.992935, -0.118438, -1.1963, 0.454713, 0.108767, 0.883972, -0.275712, 0, 0, 0, 1),
            Qt.matrix4x4(0.890608, 0.047434, 0.45229, -0.0428981, 0.00726396, 0.992935, -0.118438, -1.1963, -0.454713, 0.108767, 0.883972, -0.222347, 0, 0, 0, 1),
            Qt.matrix4x4(0.890608, 0.047434, 0.45229, -0.0429639, 0.00726397, 0.992935, -0.118438, -1.1963, -0.454713, 0.108767, 0.883972, -0.275712, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.08406e-16, 0, 0.992864, 0.119252, -1.34143, 0, -0.119252, 0.992864, 0.195647, 0, 0, 0, 1),
            Qt.matrix4x4(1, 5.25951e-08, -4.37914e-07, -8.48482e-08, -4.78589e-08, 0.999942, 0.0108084, -1.42959, 4.38457e-07, -0.0108084, 0.999942, 0.0403668, 0, 0, 0, 1),
            Qt.matrix4x4(0.926238, -0.000104815, -0.376938, -0.0152009, 0.016399, 0.999064, 0.0400189, -1.48877, 0.376581, -0.0432485, 0.925373, 0.0637776, 0, 0, 0, 1),
            Qt.matrix4x4(0.926239, 0.000104929, 0.376937, 0.0152007, -0.0163991, 0.999064, 0.040019, -1.48877, -0.37658, -0.0432485, 0.925374, 0.0637777, 0, 0, 0, 1),
            Qt.matrix4x4(-0.983841, -0.178717, -0.0108568, 0.305734, 0.179046, -0.982031, -0.0596592, 1.51661, 4.03263e-07, -0.060639, 0.99816, 0.0182112, 0, 0, 0, 1),
            Qt.matrix4x4(-0.900025, -0.379103, -0.215028, 0.621468, 0.43584, -0.782861, -0.444042, 1.20439, 2.83122e-07, -0.493367, 0.869821, 0.683586, 0, 0, 0, 1),
            Qt.matrix4x4(-0.900025, -0.379103, -0.215028, 0.621054, 0.43584, -0.782861, -0.444042, 1.17498, 2.45869e-07, -0.493367, 0.869821, 0.683586, 0, 0, 0, 1),
            Qt.matrix4x4(-0.991273, 0.131317, 0.0116454, -0.231379, -0.131832, -0.987398, -0.0875603, 1.52608, 4.97792e-07, -0.0883314, 0.996091, 0.0600014, 0, 0, 0, 1),
            Qt.matrix4x4(-0.873316, 0.410201, 0.262783, -0.667429, -0.487155, -0.735363, -0.471086, 1.1304, 5.51343e-07, -0.539423, 0.842035, 0.753084, 0, 0, 0, 1),
            Qt.matrix4x4(-0.873316, 0.410201, 0.262783, -0.666965, -0.487155, -0.735363, -0.471086, 1.10007, 5.0664e-07, -0.539423, 0.842035, 0.753085, 0, 0, 0, 1),
            Qt.matrix4x4(-0.758365, 0.620086, -0.20094, -0.841492, -0.651831, -0.721431, 0.233782, 1.09979, 4.91738e-07, 0.308271, 0.951298, -0.497027, 0, 0, 0, 1),
            Qt.matrix4x4(-0.97833, -0.198381, -0.0592934, 0.345044, 0.207052, -0.937357, -0.280165, 1.35639, 2.55182e-07, -0.28637, 0.958119, 0.360782, 0, 0, 0, 1),
            Qt.matrix4x4(-0.97833, -0.198381, -0.0592934, 0.344866, 0.207052, -0.937356, -0.280165, 1.3319, 2.96161e-07, -0.28637, 0.958119, 0.360782, 0, 0, 0, 1),
            Qt.matrix4x4(-0.881908, -0.469668, -0.0406426, 0.635118, 0.471423, -0.878624, -0.0760325, 1.32773, 4.13507e-07, -0.0862136, 0.996277, 0.067105, 0, 0, 0, 1),
            Qt.matrix4x4(-0.794149, 0.477562, 0.375849, -0.751027, -0.607724, -0.624059, -0.491144, 0.897236, 2.23518e-07, -0.618454, 0.785821, 0.846868, 0, 0, 0, 1),
            Qt.matrix4x4(-0.794149, 0.477562, 0.375849, -0.75056, -0.607724, -0.624059, -0.491144, 0.870476, 2.83122e-07, -0.618454, 0.785821, 0.846868, 0, 0, 0, 1),
            Qt.matrix4x4(-0.999327, -0.0353718, -0.00986531, 0.141476, 0.0367218, -0.962587, -0.268479, 1.42998, 3.71132e-07, -0.26866, 0.963235, 0.434951, 0, 0, 0, 1),
            Qt.matrix4x4(-0.99935, 0.0347394, 0.00962639, 0.041794, -0.0360485, -0.963062, -0.266855, 1.37142, 4.22821e-07, -0.267029, 0.963688, 0.432634, 0, 0, 0, 1),
            Qt.matrix4x4(-0.99935, 0.0347394, 0.00962639, 0.041879, -0.0360485, -0.963062, -0.266855, 1.30529, 4.21889e-07, -0.267029, 0.963688, 0.432634, 0, 0, 0, 1),
            Qt.matrix4x4(-0.99589, -0.0905452, 0.00232404, 0.166901, 0.0905751, -0.995562, 0.0255478, 1.47886, 4.90225e-07, 0.0256533, 0.999671, 0.0898075, 0, 0, 0, 1),
            Qt.matrix4x4(-0.99587, -0.090772, 0.00219743, 0.167023, 0.0907986, -0.995578, 0.0240945, 1.42134, 6.06873e-07, 0.0241945, 0.999707, 0.0918953, 0, 0, 0, 1),
            Qt.matrix4x4(-0.99587, -0.090772, 0.00219743, 0.166837, 0.0907986, -0.995578, 0.0240945, 1.36399, 6.05476e-07, 0.0241945, 0.999707, 0.0918953, 0, 0, 0, 1),
            Qt.matrix4x4(-0.998613, -0.0525937, -0.00242336, 0.0310654, 0.0526495, -0.997555, -0.0459681, 1.47908, 2.00002e-07, -0.046032, 0.99894, 0.187857, 0, 0, 0, 1),
            Qt.matrix4x4(-0.998251, -0.059098, -0.00191901, 0.0403218, 0.0591291, -0.997725, -0.0324023, 1.42337, 2.69036e-07, -0.0324591, 0.999473, 0.16854, 0, 0, 0, 1),
            Qt.matrix4x4(-0.998251, -0.059098, -0.001919, 0.0401998, 0.0591291, -0.997725, -0.0324023, 1.36545, 2.71946e-07, -0.0324591, 0.999473, 0.16854, 0, 0, 0, 1),
            Qt.matrix4x4(-0.999307, 0.0362453, 0.00854644, -0.144734, -0.0372393, -0.972637, -0.229328, 1.44248, 5.26197e-07, -0.229487, 0.973312, 0.376786, 0, 0, 0, 1),
            Qt.matrix4x4(-0.999888, -0.0146086, -0.00337737, -0.072408, 0.014994, -0.974185, -0.225256, 1.38651, 5.10132e-07, -0.225282, 0.974294, 0.370807, 0, 0, 0, 1),
            Qt.matrix4x4(-0.999888, -0.0146086, -0.00337737, -0.0724419, 0.014994, -0.974185, -0.225256, 1.32315, 5.10132e-07, -0.225282, 0.974294, 0.370807, 0, 0, 0, 1),
            Qt.matrix4x4(0.990027, -0.140878, 3.88206e-09, 0.16484, 0.140878, 0.990027, 3.77144e-08, -1.31821, -9.15645e-09, -3.67914e-08, 1, 0.0257993, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.107344, 0, 1, 0, -1.31614, 0, 0, 1, 0.0257993, 0, 0, 0, 1),
            Qt.matrix4x4(0.999999, 2.70291e-08, 0.00169146, -0.329591, -2.71817e-08, 1, 9.02343e-08, -1.31614, -0.00169146, -9.02802e-08, 0.999999, 0.0263748, 0, 0, 0, 1),
            Qt.matrix4x4(0.0707804, -0.995133, 0.0685649, 1.26045, 0.958645, 0.048867, -0.280378, -0.485931, 0.275662, 0.0855747, 0.957438, -0.208315, 0, 0, 0, 1),
            Qt.matrix4x4(0.070781, -0.995133, 0.0685649, 1.18146, 0.958645, 0.0488677, -0.280378, -0.485735, 0.275662, 0.0855748, 0.957438, -0.208259, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.545423, 0, 1, 0, -1.31614, 0, 0, 1, 0.0254191, 0, 0, 0, 1),
            Qt.matrix4x4(0.999811, -1.77738e-09, -0.0194199, -0.610542, 2.64541e-09, 1, 4.4672e-08, -1.32311, 0.0194199, -4.4715e-08, 0.999811, -0.00610924, 0, 0, 0, 1),
            Qt.matrix4x4(0.998841, -0.0288736, -0.0385161, -0.604919, 0.0288734, 0.999583, -0.000560868, -1.34115, 0.0385163, -0.000551876, 0.999258, -0.0176686, 0, 0, 0, 1),
            Qt.matrix4x4(0.99884, -0.0347321, -0.0333433, -0.617503, 0.0347257, 0.999397, -0.000771367, -1.34482, 0.0333499, -0.000387397, 0.999444, -0.0144819, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.606187, 0, 1, 0, -1.32311, 0, 0, 1, 0.0546114, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.637458, 0, 1, 0, -1.32311, 0, 0, 1, 0.0546114, 0, 0, 0, 1),
            Qt.matrix4x4(0.999695, 0.0155363, 0.0192181, -0.674786, -0.0155363, 0.999879, -0.000149271, -1.31278, -0.0192181, -0.000149353, 0.999815, 0.0673955, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.611433, 0, 1, 0, -1.32311, 0, 0, 1, 0.023371, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.648286, 0, 1, 0, -1.32311, 0, 0, 1, 0.023371, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.671022, 0, 1, 0, -1.32311, 0, 0, 1, 0.023371, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.610681, 0, 1, 0, -1.32311, 0, 0, 1, 0.039015, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.644867, 0, 1, 0, -1.32311, 0, 0, 1, 0.039015, 0, 0, 0, 1),
            Qt.matrix4x4(0.999661, -0.012432, -0.0228667, -0.648809, 0.012432, 0.999922, -0.00014206, -1.33128, 0.0228667, -0.000142268, 0.999738, 0.0239918, 0, 0, 0, 1),
            Qt.matrix4x4(0.759128, -0.0442635, 0.649435, -0.352733, -0.6499, -0.107936, 0.752316, 0.504894, 0.0367976, -0.993172, -0.110704, 1.27652, 0, 0, 0, 1),
            Qt.matrix4x4(0.787202, -0.0338466, 0.615765, -0.428478, -0.615327, -0.109564, 0.78062, 0.486107, 0.0410442, -0.993403, -0.107076, 1.27439, 0, 0, 0, 1),
            Qt.matrix4x4(0.735822, -0.0584441, 0.674648, -0.396082, -0.676539, -0.106614, 0.728648, 0.521239, 0.0293419, -0.992581, -0.117989, 1.2809, 0, 0, 0, 1),
            Qt.matrix4x4(0.979067, -0.150702, -0.136807, -0.337845, 0.145611, 0.988246, -0.0465488, -1.36613, 0.142214, 0.0256538, 0.989503, -0.076949, 0, 0, 0, 1),
            Qt.matrix4x4(0.979067, -0.150702, -0.136807, -0.383194, 0.145611, 0.988246, -0.0465488, -1.36889, 0.142214, 0.0256538, 0.989503, -0.0809002, 0, 0, 0, 1),
            Qt.matrix4x4(0.990027, 0.140878, -3.88206e-09, -0.16484, -0.140878, 0.990027, 3.77144e-08, -1.31821, 9.15645e-09, -3.67914e-08, 1, 0.0257993, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.107344, 0, 1, 0, -1.31614, 0, 0, 1, 0.0257993, 0, 0, 0, 1),
            Qt.matrix4x4(0.999999, -2.70291e-08, -0.00169146, 0.329591, 2.71817e-08, 1, 9.02343e-08, -1.31614, 0.00169146, -9.02802e-08, 0.999999, 0.0263748, 0, 0, 0, 1),
            Qt.matrix4x4(0.0707804, 0.995133, -0.0685649, -1.26045, -0.958645, 0.048867, -0.280378, -0.485931, -0.275662, 0.0855747, 0.957438, -0.208315, 0, 0, 0, 1),
            Qt.matrix4x4(0.070781, 0.995133, -0.0685649, -1.18146, -0.958645, 0.0488677, -0.280378, -0.485735, -0.275662, 0.0855748, 0.957438, -0.208259, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.545423, 0, 1, 0, -1.31614, 0, 0, 1, 0.0254191, 0, 0, 0, 1),
            Qt.matrix4x4(0.999811, 1.77738e-09, 0.0194199, 0.610542, -2.64541e-09, 1, 4.4672e-08, -1.32311, -0.0194199, -4.4715e-08, 0.999811, -0.00610924, 0, 0, 0, 1),
            Qt.matrix4x4(0.998841, 0.0288736, 0.0385161, 0.604919, -0.0288734, 0.999583, -0.000560868, -1.34115, -0.0385163, -0.000551876, 0.999258, -0.0176686, 0, 0, 0, 1),
            Qt.matrix4x4(0.99884, 0.0347321, 0.0333433, 0.617503, -0.0347257, 0.999397, -0.000771367, -1.34482, -0.0333499, -0.000387397, 0.999444, -0.0144819, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.606187, 0, 1, 0, -1.32311, 0, 0, 1, 0.0546114, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.637458, 0, 1, 0, -1.32311, 0, 0, 1, 0.0546114, 0, 0, 0, 1),
            Qt.matrix4x4(0.999695, -0.0155363, -0.0192181, 0.674786, 0.0155363, 0.999879, -0.000149271, -1.31278, 0.0192181, -0.000149353, 0.999815, 0.0673955, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.611433, 0, 1, 0, -1.32311, 0, 0, 1, 0.023371, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.648286, 0, 1, 0, -1.32311, 0, 0, 1, 0.023371, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.671022, 0, 1, 0, -1.32311, 0, 0, 1, 0.023371, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.610681, 0, 1, 0, -1.32311, 0, 0, 1, 0.039015, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.644867, 0, 1, 0, -1.32311, 0, 0, 1, 0.039015, 0, 0, 0, 1),
            Qt.matrix4x4(0.999661, 0.012432, 0.0228667, 0.648809, -0.012432, 0.999922, -0.00014206, -1.33128, -0.0228667, -0.000142268, 0.999738, 0.0239918, 0, 0, 0, 1),
            Qt.matrix4x4(0.759128, 0.0442635, -0.649435, 0.352733, 0.6499, -0.107936, 0.752316, 0.504894, -0.0367976, -0.993172, -0.110704, 1.27652, 0, 0, 0, 1),
            Qt.matrix4x4(0.787202, 0.0338466, -0.615765, 0.428478, 0.615327, -0.109564, 0.78062, 0.486107, -0.0410442, -0.993403, -0.107076, 1.27439, 0, 0, 0, 1),
            Qt.matrix4x4(0.735822, 0.0584441, -0.674648, 0.396082, 0.676539, -0.106614, 0.728648, 0.521239, -0.0293419, -0.992581, -0.117989, 1.2809, 0, 0, 0, 1),
            Qt.matrix4x4(0.979067, 0.150702, 0.136807, 0.337845, -0.145611, 0.988246, -0.0465488, -1.36613, -0.142214, 0.0256538, 0.989503, -0.076949, 0, 0, 0, 1),
            Qt.matrix4x4(0.979067, 0.150702, 0.136807, 0.383194, -0.145611, 0.988246, -0.0465488, -1.36889, -0.142214, 0.0256538, 0.989503, -0.0809002, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0775518, 0, 0.999781, 0.0209207, -0.905186, 0, -0.0209207, 0.999781, 0.0190642, 0, 0, 0, 1),
            Qt.matrix4x4(-0.944987, -0.105431, -0.309654, 0.13233, -0.227874, 0.891326, 0.391933, -0.769215, 0.234681, 0.440933, -0.866316, -0.546666, 0, 0, 0, 1),
            Qt.matrix4x4(-0.944987, -0.105431, -0.309654, 0.13233, -0.227874, 0.891326, 0.391933, -0.769215, 0.234681, 0.440933, -0.866316, -0.546666, 0, 0, 0, 1),
            Qt.matrix4x4(-0.945495, -0.113147, -0.305349, 0.139453, -0.223875, 0.906802, 0.357198, -0.648573, 0.236475, 0.406089, -0.882707, -0.520743, 0, 0, 0, 1),
            Qt.matrix4x4(-0.945495, -0.113147, -0.305349, 0.139409, -0.223875, 0.906802, 0.357198, -0.509035, 0.236475, 0.406089, -0.882707, -0.520051, 0, 0, 0, 1),
            Qt.matrix4x4(0.895808, 0.0882061, -0.4356, -0.0827121, -0.171718, 0.972688, -0.156174, -0.849282, 0.409928, 0.214702, 0.886489, -0.354161, 0, 0, 0, 1),
            Qt.matrix4x4(0.895808, 0.0882061, -0.4356, -0.0827121, -0.171718, 0.972688, -0.156174, -0.849282, 0.409928, 0.214702, 0.886489, -0.354161, 0, 0, 0, 1),
            Qt.matrix4x4(0.89608, 0.0859134, -0.435499, -0.0809376, -0.170259, 0.972575, -0.158458, -0.718107, 0.409942, 0.216139, 0.886133, -0.354844, 0, 0, 0, 1),
            Qt.matrix4x4(-0.89608, -0.0859134, 0.435499, 0.080912, -0.170259, 0.972575, -0.158458, -0.558339, -0.409942, -0.216139, -0.886133, 0.354372, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0775518, 0, 0.997787, 0.0664965, -0.540239, 0, -0.0664965, 0.997787, 0.0440483, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0775518, 0, 0.999985, 0.00548092, -0.11721, 0, -0.00548092, 0.999985, 0.0339149, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0775518, 0, 0.999952, 0.00981418, -0.054431, 0, -0.00981418, 0.999952, -0.0767572, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.0775518, 0, 0.999781, 0.0209207, -0.905186, 0, -0.0209207, 0.999781, 0.0190642, 0, 0, 0, 1),
            Qt.matrix4x4(-0.944987, 0.105431, 0.309655, -0.13233, 0.227874, 0.891326, 0.391933, -0.769215, -0.234681, 0.440933, -0.866316, -0.546667, 0, 0, 0, 1),
            Qt.matrix4x4(-0.944987, 0.105431, 0.309655, -0.13233, 0.227874, 0.891326, 0.391933, -0.769215, -0.234681, 0.440933, -0.866316, -0.546667, 0, 0, 0, 1),
            Qt.matrix4x4(-0.945495, 0.113147, 0.305349, -0.139453, 0.223875, 0.906802, 0.357198, -0.648573, -0.236475, 0.406089, -0.882707, -0.520743, 0, 0, 0, 1),
            Qt.matrix4x4(-0.945495, 0.113147, 0.305349, -0.13941, 0.223875, 0.906802, 0.357198, -0.509035, -0.236475, 0.406089, -0.882707, -0.520052, 0, 0, 0, 1),
            Qt.matrix4x4(0.895808, -0.0882061, 0.4356, 0.082712, 0.171718, 0.972688, -0.156174, -0.849282, -0.409928, 0.214702, 0.886489, -0.354162, 0, 0, 0, 1),
            Qt.matrix4x4(0.895808, -0.0882061, 0.4356, 0.082712, 0.171718, 0.972688, -0.156174, -0.849282, -0.409928, 0.214702, 0.886489, -0.354162, 0, 0, 0, 1),
            Qt.matrix4x4(0.89608, -0.0859134, 0.435499, 0.0809376, 0.170259, 0.972575, -0.158458, -0.718107, -0.409942, 0.216139, 0.886133, -0.354844, 0, 0, 0, 1),
            Qt.matrix4x4(0.89608, -0.0859134, 0.435499, 0.0809115, 0.170259, 0.972575, -0.158458, -0.558339, -0.409942, 0.216139, 0.886133, -0.354372, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.0775518, 0, 0.997787, 0.0664965, -0.540239, 0, -0.0664965, 0.997787, 0.0440483, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.0775518, 0, 0.999985, 0.00548092, -0.11721, 0, -0.00548092, 0.999985, 0.0339149, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.0775518, 0, 0.999952, 0.00981418, -0.054431, 0, -0.00981418, 0.999952, -0.0767572, 0, 0, 0, 1)
        ]
    }
    PrincipledMaterial {
        id: n00_000_Hair_00_HAIR__Instance__material
        objectName: "N00_000_Hair_00_HAIR (Instance)"
        baseColorMap: _20_texture
        roughness: 0.8999999761581421
        normalMap: _21_texture
        emissiveMap: _22_texture
        emissiveFactor: Qt.vector3d(0.935897, 0.679257, 0.651928)
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Mask
        depthDrawMode: PrincipledMaterial.OpaquePrePassDepthDraw
        lighting: PrincipledMaterial.NoLighting
    }
    MorphTarget {
        id: fcl_BRW_Joy_morphtarget178
        objectName: "Fcl_BRW_Joy"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Sorrow_morphtarget179
        objectName: "Fcl_BRW_Sorrow"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_BRW_Surprised_morphtarget180
        objectName: "Fcl_BRW_Surprised"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Natural_morphtarget181
        objectName: "Fcl_EYE_Natural"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Angry_morphtarget182
        objectName: "Fcl_EYE_Angry"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    MorphTarget {
        id: fcl_EYE_Close_morphtarget183
        objectName: "Fcl_EYE_Close"
        attributes: MorphTarget.Position | MorphTarget.Normal
    }
    Skin {
        id: skin663
        joints: [
            root2,
            j_Bip_C_Hips,
            j_Sec_L_SkirtSide0_01,
            j_Sec_L_SkirtSide1_01,
            j_Sec_L_SkirtSide2_01,
            j_Sec_L_SkirtSide2_end_01,
            j_Sec_R_SkirtSide0_01,
            j_Sec_R_SkirtSide1_01,
            j_Sec_R_SkirtSide2_01,
            j_Sec_R_SkirtSide2_end_01,
            j_Bip_C_Spine,
            j_Bip_C_Chest,
            j_Bip_C_UpperChest,
            j_Sec_L_Bust1,
            j_Sec_L_Bust2,
            j_Sec_R_Bust1,
            j_Sec_R_Bust2,
            j_Bip_C_Neck,
            j_Bip_C_Head,
            j_Adj_L_FaceEye,
            j_Adj_R_FaceEye,
            j_Sec_Hair1_01,
            j_Sec_Hair2_01,
            j_Sec_Hair3_01,
            j_Sec_Hair1_02,
            j_Sec_Hair2_02,
            j_Sec_Hair3_02,
            j_Sec_Hair1_03,
            j_Sec_Hair2_03,
            j_Sec_Hair3_03,
            j_Sec_Hair1_04,
            j_Sec_Hair2_04,
            j_Sec_Hair3_04,
            j_Sec_Hair1_05,
            j_Sec_Hair2_05,
            j_Sec_Hair3_05,
            j_Sec_Hair1_06,
            j_Sec_Hair2_06,
            j_Sec_Hair3_06,
            j_Sec_Hair1_07,
            j_Sec_Hair2_07,
            j_Sec_Hair3_07,
            j_Sec_Hair1_08,
            j_Sec_Hair2_08,
            j_Sec_Hair3_08,
            j_Bip_L_Shoulder,
            j_Bip_L_UpperArm,
            j_Bip_L_LowerArm,
            j_Sec_L_LowerSleeve_01,
            j_Sec_L_LowerSleeve_end_01,
            j_Bip_L_Hand,
            j_Bip_L_Index1,
            j_Bip_L_Index2,
            j_Bip_L_Index3,
            j_Bip_L_Little1,
            j_Bip_L_Little2,
            j_Bip_L_Little3,
            j_Bip_L_Middle1,
            j_Bip_L_Middle2,
            j_Bip_L_Middle3,
            j_Bip_L_Ring1,
            j_Bip_L_Ring2,
            j_Bip_L_Ring3,
            j_Bip_L_Thumb1,
            j_Bip_L_Thumb2,
            j_Bip_L_Thumb3,
            j_Sec_L_TipSleeve_01,
            j_Sec_L_TipSleeve_end_01,
            j_Bip_R_Shoulder,
            j_Bip_R_UpperArm,
            j_Bip_R_LowerArm,
            j_Sec_R_LowerSleeve_01,
            j_Sec_R_LowerSleeve_end_01,
            j_Bip_R_Hand,
            j_Bip_R_Index1,
            j_Bip_R_Index2,
            j_Bip_R_Index3,
            j_Bip_R_Little1,
            j_Bip_R_Little2,
            j_Bip_R_Little3,
            j_Bip_R_Middle1,
            j_Bip_R_Middle2,
            j_Bip_R_Middle3,
            j_Bip_R_Ring1,
            j_Bip_R_Ring2,
            j_Bip_R_Ring3,
            j_Bip_R_Thumb1,
            j_Bip_R_Thumb2,
            j_Bip_R_Thumb3,
            j_Sec_R_TipSleeve_01,
            j_Sec_R_TipSleeve_end_01,
            j_Bip_L_UpperLeg,
            j_Sec_L_SkirtBack0_01,
            j_Sec_L_SkirtBack1_01,
            j_Sec_L_SkirtBack2_01,
            j_Sec_L_SkirtBack2_end_01,
            j_Sec_L_SkirtFront0_01,
            j_Sec_L_SkirtFront1_01,
            j_Sec_L_SkirtFront2_01,
            j_Sec_L_SkirtFront2_end_01,
            j_Bip_L_LowerLeg,
            j_Bip_L_Foot,
            j_Bip_L_ToeBase,
            j_Bip_R_UpperLeg,
            j_Sec_R_SkirtBack0_01,
            j_Sec_R_SkirtBack1_01,
            j_Sec_R_SkirtBack2_01,
            j_Sec_R_SkirtBack2_end_01,
            j_Sec_R_SkirtFront0_01,
            j_Sec_R_SkirtFront1_01,
            j_Sec_R_SkirtFront2_01,
            j_Sec_R_SkirtFront2_end_01,
            j_Bip_R_LowerLeg,
            j_Bip_R_Foot,
            j_Bip_R_ToeBase
        ]
        inverseBindPoses: [
            Qt.matrix4x4(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0, 0, 0.992088, 0.125548, -0.938575, 0, -0.125548, 0.992088, 0.115172, 0, 0, 0, 1),
            Qt.matrix4x4(-9.53675e-07, 0.0631874, -0.998002, -0.0467744, -0.388588, 0.91957, 0.0582219, -0.778062, 0.921412, 0.387812, 0.024553, -0.538367, 0, 0, 0, 1),
            Qt.matrix4x4(-9.53675e-07, 0.0631874, -0.998002, -0.0467744, -0.388588, 0.91957, 0.0582219, -0.778062, 0.921412, 0.387812, 0.024553, -0.538367, 0, 0, 0, 1),
            Qt.matrix4x4(-0.000345111, 0.0572343, -0.998361, -0.0421997, -0.312835, 0.948244, 0.0544693, -0.674806, 0.949808, 0.312341, 0.0175776, -0.481274, 0, 0, 0, 1),
            Qt.matrix4x4(0.000344098, -0.0572343, 0.998361, 0.0421997, -0.312835, 0.948244, 0.054469, -0.539394, -0.949807, -0.312341, -0.0175786, 0.481152, 0, 0, 0, 1),
            Qt.matrix4x4(-9.53675e-07, -0.0631874, 0.998002, 0.0467744, 0.388588, 0.91957, 0.0582219, -0.778062, -0.921412, 0.387812, 0.024553, -0.538367, 0, 0, 0, 1),
            Qt.matrix4x4(-9.53675e-07, -0.0631874, 0.998002, 0.0467744, 0.388588, 0.91957, 0.0582219, -0.778062, -0.921412, 0.387812, 0.024553, -0.538367, 0, 0, 0, 1),
            Qt.matrix4x4(-0.000345111, -0.0572343, 0.998361, 0.0421997, 0.312835, 0.948244, 0.0544693, -0.674807, -0.949808, 0.312341, 0.0175776, -0.481274, 0, 0, 0, 1),
            Qt.matrix4x4(-0.000345111, -0.0572342, 0.998361, 0.0421997, 0.312835, 0.948244, 0.0544693, -0.539394, -0.949808, 0.312341, 0.0175776, -0.481151, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 6.43536e-32, 0, 0.98855, 0.150896, -0.989285, 0, -0.150896, 0.98855, 0.134586, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -2.17976e-17, 0, 0.992589, -0.121518, -1.10196, 0, 0.121518, 0.992589, -0.15437, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 9.66503e-18, 0, 0.943357, -0.33178, -1.15073, 0, 0.33178, 0.943357, -0.409491, 0, 0, 0, 1),
            Qt.matrix4x4(0.890608, -0.047434, -0.45229, 0.0428981, -0.00726396, 0.992935, -0.118438, -1.1963, 0.454713, 0.108767, 0.883972, -0.222347, 0, 0, 0, 1),
            Qt.matrix4x4(0.890608, -0.047434, -0.45229, 0.0429639, -0.00726397, 0.992935, -0.118438, -1.1963, 0.454713, 0.108767, 0.883972, -0.275712, 0, 0, 0, 1),
            Qt.matrix4x4(0.890608, 0.047434, 0.45229, -0.0428981, 0.00726396, 0.992935, -0.118438, -1.1963, -0.454713, 0.108767, 0.883972, -0.222347, 0, 0, 0, 1),
            Qt.matrix4x4(0.890608, 0.047434, 0.45229, -0.0429639, 0.00726397, 0.992935, -0.118438, -1.1963, -0.454713, 0.108767, 0.883972, -0.275712, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.08406e-16, 0, 0.992864, 0.119252, -1.34143, 0, -0.119252, 0.992864, 0.195647, 0, 0, 0, 1),
            Qt.matrix4x4(1, 5.25951e-08, -4.37914e-07, -8.48482e-08, -4.78589e-08, 0.999942, 0.0108084, -1.42959, 4.38457e-07, -0.0108084, 0.999942, 0.0403668, 0, 0, 0, 1),
            Qt.matrix4x4(0.926238, -0.000104815, -0.376938, -0.0152009, 0.016399, 0.999064, 0.0400189, -1.48877, 0.376581, -0.0432485, 0.925373, 0.0637776, 0, 0, 0, 1),
            Qt.matrix4x4(0.926239, 0.000104929, 0.376937, 0.0152007, -0.0163991, 0.999064, 0.040019, -1.48877, -0.37658, -0.0432485, 0.925374, 0.0637777, 0, 0, 0, 1),
            Qt.matrix4x4(-0.983841, -0.178717, -0.0108568, 0.305734, 0.179046, -0.982031, -0.0596592, 1.51661, 4.03263e-07, -0.060639, 0.99816, 0.0182112, 0, 0, 0, 1),
            Qt.matrix4x4(-0.900025, -0.379103, -0.215028, 0.621468, 0.43584, -0.782861, -0.444042, 1.20439, 2.83122e-07, -0.493367, 0.869821, 0.683586, 0, 0, 0, 1),
            Qt.matrix4x4(-0.900025, -0.379103, -0.215028, 0.621054, 0.43584, -0.782861, -0.444042, 1.17498, 2.45869e-07, -0.493367, 0.869821, 0.683586, 0, 0, 0, 1),
            Qt.matrix4x4(-0.991273, 0.131317, 0.0116454, -0.231379, -0.131832, -0.987398, -0.0875603, 1.52608, 4.97792e-07, -0.0883314, 0.996091, 0.0600014, 0, 0, 0, 1),
            Qt.matrix4x4(-0.873316, 0.410201, 0.262783, -0.667429, -0.487155, -0.735363, -0.471086, 1.1304, 5.51343e-07, -0.539423, 0.842035, 0.753084, 0, 0, 0, 1),
            Qt.matrix4x4(-0.873316, 0.410201, 0.262783, -0.666965, -0.487155, -0.735363, -0.471086, 1.10007, 5.0664e-07, -0.539423, 0.842035, 0.753085, 0, 0, 0, 1),
            Qt.matrix4x4(-0.758365, 0.620086, -0.20094, -0.841492, -0.651831, -0.721431, 0.233782, 1.09979, 4.91738e-07, 0.308271, 0.951298, -0.497027, 0, 0, 0, 1),
            Qt.matrix4x4(-0.97833, -0.198381, -0.0592934, 0.345044, 0.207052, -0.937357, -0.280165, 1.35639, 2.55182e-07, -0.28637, 0.958119, 0.360782, 0, 0, 0, 1),
            Qt.matrix4x4(-0.97833, -0.198381, -0.0592934, 0.344866, 0.207052, -0.937356, -0.280165, 1.3319, 2.96161e-07, -0.28637, 0.958119, 0.360782, 0, 0, 0, 1),
            Qt.matrix4x4(-0.881908, -0.469668, -0.0406426, 0.635118, 0.471423, -0.878624, -0.0760325, 1.32773, 4.13507e-07, -0.0862136, 0.996277, 0.067105, 0, 0, 0, 1),
            Qt.matrix4x4(-0.794149, 0.477562, 0.375849, -0.751027, -0.607724, -0.624059, -0.491144, 0.897236, 2.23518e-07, -0.618454, 0.785821, 0.846868, 0, 0, 0, 1),
            Qt.matrix4x4(-0.794149, 0.477562, 0.375849, -0.75056, -0.607724, -0.624059, -0.491144, 0.870476, 2.83122e-07, -0.618454, 0.785821, 0.846868, 0, 0, 0, 1),
            Qt.matrix4x4(-0.999327, -0.0353718, -0.00986531, 0.141476, 0.0367218, -0.962587, -0.268479, 1.42998, 3.71132e-07, -0.26866, 0.963235, 0.434951, 0, 0, 0, 1),
            Qt.matrix4x4(-0.99935, 0.0347394, 0.00962639, 0.041794, -0.0360485, -0.963062, -0.266855, 1.37142, 4.22821e-07, -0.267029, 0.963688, 0.432634, 0, 0, 0, 1),
            Qt.matrix4x4(-0.99935, 0.0347394, 0.00962639, 0.041879, -0.0360485, -0.963062, -0.266855, 1.30529, 4.21889e-07, -0.267029, 0.963688, 0.432634, 0, 0, 0, 1),
            Qt.matrix4x4(-0.99589, -0.0905452, 0.00232404, 0.166901, 0.0905751, -0.995562, 0.0255478, 1.47886, 4.90225e-07, 0.0256533, 0.999671, 0.0898075, 0, 0, 0, 1),
            Qt.matrix4x4(-0.99587, -0.090772, 0.00219743, 0.167023, 0.0907986, -0.995578, 0.0240945, 1.42134, 6.06873e-07, 0.0241945, 0.999707, 0.0918953, 0, 0, 0, 1),
            Qt.matrix4x4(-0.99587, -0.090772, 0.00219743, 0.166837, 0.0907986, -0.995578, 0.0240945, 1.36399, 6.05476e-07, 0.0241945, 0.999707, 0.0918953, 0, 0, 0, 1),
            Qt.matrix4x4(-0.998613, -0.0525937, -0.00242336, 0.0310654, 0.0526495, -0.997555, -0.0459681, 1.47908, 2.00002e-07, -0.046032, 0.99894, 0.187857, 0, 0, 0, 1),
            Qt.matrix4x4(-0.998251, -0.059098, -0.00191901, 0.0403218, 0.0591291, -0.997725, -0.0324023, 1.42337, 2.69036e-07, -0.0324591, 0.999473, 0.16854, 0, 0, 0, 1),
            Qt.matrix4x4(-0.998251, -0.059098, -0.001919, 0.0401998, 0.0591291, -0.997725, -0.0324023, 1.36545, 2.71946e-07, -0.0324591, 0.999473, 0.16854, 0, 0, 0, 1),
            Qt.matrix4x4(-0.999307, 0.0362453, 0.00854644, -0.144734, -0.0372393, -0.972637, -0.229328, 1.44248, 5.26197e-07, -0.229487, 0.973312, 0.376786, 0, 0, 0, 1),
            Qt.matrix4x4(-0.999888, -0.0146086, -0.00337737, -0.072408, 0.014994, -0.974185, -0.225256, 1.38651, 5.10132e-07, -0.225282, 0.974294, 0.370807, 0, 0, 0, 1),
            Qt.matrix4x4(-0.999888, -0.0146086, -0.00337737, -0.0724419, 0.014994, -0.974185, -0.225256, 1.32315, 5.10132e-07, -0.225282, 0.974294, 0.370807, 0, 0, 0, 1),
            Qt.matrix4x4(0.990027, -0.140878, 3.88206e-09, 0.16484, 0.140878, 0.990027, 3.77144e-08, -1.31821, -9.15645e-09, -3.67914e-08, 1, 0.0257993, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.107344, 0, 1, 0, -1.31614, 0, 0, 1, 0.0257993, 0, 0, 0, 1),
            Qt.matrix4x4(0.999999, 2.70291e-08, 0.00169146, -0.329591, -2.71817e-08, 1, 9.02343e-08, -1.31614, -0.00169146, -9.02802e-08, 0.999999, 0.0263748, 0, 0, 0, 1),
            Qt.matrix4x4(0.0707804, -0.995133, 0.0685649, 1.26045, 0.958645, 0.048867, -0.280378, -0.485931, 0.275662, 0.0855747, 0.957438, -0.208315, 0, 0, 0, 1),
            Qt.matrix4x4(0.070781, -0.995133, 0.0685649, 1.18146, 0.958645, 0.0488677, -0.280378, -0.485735, 0.275662, 0.0855748, 0.957438, -0.208259, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.545423, 0, 1, 0, -1.31614, 0, 0, 1, 0.0254191, 0, 0, 0, 1),
            Qt.matrix4x4(0.999811, -1.77738e-09, -0.0194199, -0.610542, 2.64541e-09, 1, 4.4672e-08, -1.32311, 0.0194199, -4.4715e-08, 0.999811, -0.00610924, 0, 0, 0, 1),
            Qt.matrix4x4(0.998841, -0.0288736, -0.0385161, -0.604919, 0.0288734, 0.999583, -0.000560868, -1.34115, 0.0385163, -0.000551876, 0.999258, -0.0176686, 0, 0, 0, 1),
            Qt.matrix4x4(0.99884, -0.0347321, -0.0333433, -0.617503, 0.0347257, 0.999397, -0.000771367, -1.34482, 0.0333499, -0.000387397, 0.999444, -0.0144819, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.606187, 0, 1, 0, -1.32311, 0, 0, 1, 0.0546114, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.637458, 0, 1, 0, -1.32311, 0, 0, 1, 0.0546114, 0, 0, 0, 1),
            Qt.matrix4x4(0.999695, 0.0155363, 0.0192181, -0.674786, -0.0155363, 0.999879, -0.000149271, -1.31278, -0.0192181, -0.000149353, 0.999815, 0.0673955, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.611433, 0, 1, 0, -1.32311, 0, 0, 1, 0.023371, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.648286, 0, 1, 0, -1.32311, 0, 0, 1, 0.023371, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.671022, 0, 1, 0, -1.32311, 0, 0, 1, 0.023371, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.610681, 0, 1, 0, -1.32311, 0, 0, 1, 0.039015, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.644867, 0, 1, 0, -1.32311, 0, 0, 1, 0.039015, 0, 0, 0, 1),
            Qt.matrix4x4(0.999661, -0.012432, -0.0228667, -0.648809, 0.012432, 0.999922, -0.00014206, -1.33128, 0.0228667, -0.000142268, 0.999738, 0.0239918, 0, 0, 0, 1),
            Qt.matrix4x4(0.759128, -0.0442635, 0.649435, -0.352733, -0.6499, -0.107936, 0.752316, 0.504894, 0.0367976, -0.993172, -0.110704, 1.27652, 0, 0, 0, 1),
            Qt.matrix4x4(0.787202, -0.0338466, 0.615765, -0.428478, -0.615327, -0.109564, 0.78062, 0.486107, 0.0410442, -0.993403, -0.107076, 1.27439, 0, 0, 0, 1),
            Qt.matrix4x4(0.735822, -0.0584441, 0.674648, -0.396082, -0.676539, -0.106614, 0.728648, 0.521239, 0.0293419, -0.992581, -0.117989, 1.2809, 0, 0, 0, 1),
            Qt.matrix4x4(0.979067, -0.150702, -0.136807, -0.337845, 0.145611, 0.988246, -0.0465488, -1.36613, 0.142214, 0.0256538, 0.989503, -0.076949, 0, 0, 0, 1),
            Qt.matrix4x4(0.979067, -0.150702, -0.136807, -0.383194, 0.145611, 0.988246, -0.0465488, -1.36889, 0.142214, 0.0256538, 0.989503, -0.0809002, 0, 0, 0, 1),
            Qt.matrix4x4(0.990027, 0.140878, -3.88206e-09, -0.16484, -0.140878, 0.990027, 3.77144e-08, -1.31821, 9.15645e-09, -3.67914e-08, 1, 0.0257993, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.107344, 0, 1, 0, -1.31614, 0, 0, 1, 0.0257993, 0, 0, 0, 1),
            Qt.matrix4x4(0.999999, -2.70291e-08, -0.00169146, 0.329591, 2.71817e-08, 1, 9.02343e-08, -1.31614, 0.00169146, -9.02802e-08, 0.999999, 0.0263748, 0, 0, 0, 1),
            Qt.matrix4x4(0.0707804, 0.995133, -0.0685649, -1.26045, -0.958645, 0.048867, -0.280378, -0.485931, -0.275662, 0.0855747, 0.957438, -0.208315, 0, 0, 0, 1),
            Qt.matrix4x4(0.070781, 0.995133, -0.0685649, -1.18146, -0.958645, 0.0488677, -0.280378, -0.485735, -0.275662, 0.0855748, 0.957438, -0.208259, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.545423, 0, 1, 0, -1.31614, 0, 0, 1, 0.0254191, 0, 0, 0, 1),
            Qt.matrix4x4(0.999811, 1.77738e-09, 0.0194199, 0.610542, -2.64541e-09, 1, 4.4672e-08, -1.32311, -0.0194199, -4.4715e-08, 0.999811, -0.00610924, 0, 0, 0, 1),
            Qt.matrix4x4(0.998841, 0.0288736, 0.0385161, 0.604919, -0.0288734, 0.999583, -0.000560868, -1.34115, -0.0385163, -0.000551876, 0.999258, -0.0176686, 0, 0, 0, 1),
            Qt.matrix4x4(0.99884, 0.0347321, 0.0333433, 0.617503, -0.0347257, 0.999397, -0.000771367, -1.34482, -0.0333499, -0.000387397, 0.999444, -0.0144819, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.606187, 0, 1, 0, -1.32311, 0, 0, 1, 0.0546114, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.637458, 0, 1, 0, -1.32311, 0, 0, 1, 0.0546114, 0, 0, 0, 1),
            Qt.matrix4x4(0.999695, -0.0155363, -0.0192181, 0.674786, 0.0155363, 0.999879, -0.000149271, -1.31278, 0.0192181, -0.000149353, 0.999815, 0.0673955, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.611433, 0, 1, 0, -1.32311, 0, 0, 1, 0.023371, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.648286, 0, 1, 0, -1.32311, 0, 0, 1, 0.023371, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.671022, 0, 1, 0, -1.32311, 0, 0, 1, 0.023371, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.610681, 0, 1, 0, -1.32311, 0, 0, 1, 0.039015, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.644867, 0, 1, 0, -1.32311, 0, 0, 1, 0.039015, 0, 0, 0, 1),
            Qt.matrix4x4(0.999661, 0.012432, 0.0228667, 0.648809, -0.012432, 0.999922, -0.00014206, -1.33128, -0.0228667, -0.000142268, 0.999738, 0.0239918, 0, 0, 0, 1),
            Qt.matrix4x4(0.759128, 0.0442635, -0.649435, 0.352733, 0.6499, -0.107936, 0.752316, 0.504894, -0.0367976, -0.993172, -0.110704, 1.27652, 0, 0, 0, 1),
            Qt.matrix4x4(0.787202, 0.0338466, -0.615765, 0.428478, 0.615327, -0.109564, 0.78062, 0.486107, -0.0410442, -0.993403, -0.107076, 1.27439, 0, 0, 0, 1),
            Qt.matrix4x4(0.735822, 0.0584441, -0.674648, 0.396082, 0.676539, -0.106614, 0.728648, 0.521239, -0.0293419, -0.992581, -0.117989, 1.2809, 0, 0, 0, 1),
            Qt.matrix4x4(0.979067, 0.150702, 0.136807, 0.337845, -0.145611, 0.988246, -0.0465488, -1.36613, -0.142214, 0.0256538, 0.989503, -0.076949, 0, 0, 0, 1),
            Qt.matrix4x4(0.979067, 0.150702, 0.136807, 0.383194, -0.145611, 0.988246, -0.0465488, -1.36889, -0.142214, 0.0256538, 0.989503, -0.0809002, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0775518, 0, 0.999781, 0.0209207, -0.905186, 0, -0.0209207, 0.999781, 0.0190642, 0, 0, 0, 1),
            Qt.matrix4x4(-0.944987, -0.105431, -0.309654, 0.13233, -0.227874, 0.891326, 0.391933, -0.769215, 0.234681, 0.440933, -0.866316, -0.546666, 0, 0, 0, 1),
            Qt.matrix4x4(-0.944987, -0.105431, -0.309654, 0.13233, -0.227874, 0.891326, 0.391933, -0.769215, 0.234681, 0.440933, -0.866316, -0.546666, 0, 0, 0, 1),
            Qt.matrix4x4(-0.945495, -0.113147, -0.305349, 0.139453, -0.223875, 0.906802, 0.357198, -0.648573, 0.236475, 0.406089, -0.882707, -0.520743, 0, 0, 0, 1),
            Qt.matrix4x4(-0.945495, -0.113147, -0.305349, 0.139409, -0.223875, 0.906802, 0.357198, -0.509035, 0.236475, 0.406089, -0.882707, -0.520051, 0, 0, 0, 1),
            Qt.matrix4x4(0.895808, 0.0882061, -0.4356, -0.0827121, -0.171718, 0.972688, -0.156174, -0.849282, 0.409928, 0.214702, 0.886489, -0.354161, 0, 0, 0, 1),
            Qt.matrix4x4(0.895808, 0.0882061, -0.4356, -0.0827121, -0.171718, 0.972688, -0.156174, -0.849282, 0.409928, 0.214702, 0.886489, -0.354161, 0, 0, 0, 1),
            Qt.matrix4x4(0.89608, 0.0859134, -0.435499, -0.0809376, -0.170259, 0.972575, -0.158458, -0.718107, 0.409942, 0.216139, 0.886133, -0.354844, 0, 0, 0, 1),
            Qt.matrix4x4(-0.89608, -0.0859134, 0.435499, 0.080912, -0.170259, 0.972575, -0.158458, -0.558339, -0.409942, -0.216139, -0.886133, 0.354372, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0775518, 0, 0.997787, 0.0664965, -0.540239, 0, -0.0664965, 0.997787, 0.0440483, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0775518, 0, 0.999985, 0.00548092, -0.11721, 0, -0.00548092, 0.999985, 0.0339149, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0775518, 0, 0.999952, 0.00981418, -0.054431, 0, -0.00981418, 0.999952, -0.0767572, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.0775518, 0, 0.999781, 0.0209207, -0.905186, 0, -0.0209207, 0.999781, 0.0190642, 0, 0, 0, 1),
            Qt.matrix4x4(-0.944987, 0.105431, 0.309655, -0.13233, 0.227874, 0.891326, 0.391933, -0.769215, -0.234681, 0.440933, -0.866316, -0.546667, 0, 0, 0, 1),
            Qt.matrix4x4(-0.944987, 0.105431, 0.309655, -0.13233, 0.227874, 0.891326, 0.391933, -0.769215, -0.234681, 0.440933, -0.866316, -0.546667, 0, 0, 0, 1),
            Qt.matrix4x4(-0.945495, 0.113147, 0.305349, -0.139453, 0.223875, 0.906802, 0.357198, -0.648573, -0.236475, 0.406089, -0.882707, -0.520743, 0, 0, 0, 1),
            Qt.matrix4x4(-0.945495, 0.113147, 0.305349, -0.13941, 0.223875, 0.906802, 0.357198, -0.509035, -0.236475, 0.406089, -0.882707, -0.520052, 0, 0, 0, 1),
            Qt.matrix4x4(0.895808, -0.0882061, 0.4356, 0.082712, 0.171718, 0.972688, -0.156174, -0.849282, -0.409928, 0.214702, 0.886489, -0.354162, 0, 0, 0, 1),
            Qt.matrix4x4(0.895808, -0.0882061, 0.4356, 0.082712, 0.171718, 0.972688, -0.156174, -0.849282, -0.409928, 0.214702, 0.886489, -0.354162, 0, 0, 0, 1),
            Qt.matrix4x4(0.89608, -0.0859134, 0.435499, 0.0809376, 0.170259, 0.972575, -0.158458, -0.718107, -0.409942, 0.216139, 0.886133, -0.354844, 0, 0, 0, 1),
            Qt.matrix4x4(0.89608, -0.0859134, 0.435499, 0.0809115, 0.170259, 0.972575, -0.158458, -0.558339, -0.409942, 0.216139, 0.886133, -0.354372, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.0775518, 0, 0.997787, 0.0664965, -0.540239, 0, -0.0664965, 0.997787, 0.0440483, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.0775518, 0, 0.999985, 0.00548092, -0.11721, 0, -0.00548092, 0.999985, 0.0339149, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.0775518, 0, 0.999952, 0.00981418, -0.054431, 0, -0.00981418, 0.999952, -0.0767572, 0, 0, 0, 1)
        ]
    }

    // Nodes:
    Node {
        id: root1
        objectName: "ROOT"
        Node {
            id: root2
            objectName: "Root"
            Node {
                id: j_Bip_C_Hips
                objectName: "J_Bip_C_Hips"
                position: Qt.vector3d(0, 0.945608, 0.00357607)
                rotation: Qt.quaternion(0.99802, 0.0628984, 0, 0)
                Node {
                    id: j_Sec_L_SkirtSide0_01
                    objectName: "J_Sec_L_SkirtSide0_01"
                    position: Qt.vector3d(0.193712, -0.0172025, 0.0105048)
                    rotation: Qt.quaternion(0.688345, -0.161807, 0.697125, 0.118392)
                    scale: Qt.vector3d(1, 1, 1)
                    Node {
                        id: j_Sec_L_SkirtSide1_01
                        objectName: "J_Sec_L_SkirtSide1_01"
                        position: Qt.vector3d(1.49012e-08, -1.19209e-07, 0)
                        rotation: Qt.quaternion(1, 5.35802e-08, 3.1665e-08, 5.4948e-08)
                        scale: Qt.vector3d(1, 1, 1)
                        Node {
                            id: j_Sec_L_SkirtSide2_01
                            objectName: "J_Sec_L_SkirtSide2_01"
                            position: Qt.vector3d(0.000229612, -0.144607, -0.00423712)
                            rotation: Qt.quaternion(0.999177, 0.0404505, 0.0012077, -0.00273188)
                            scale: Qt.vector3d(1, 1, 1)
                            Node {
                                id: j_Sec_L_SkirtSide2_end_01
                                objectName: "J_Sec_L_SkirtSide2_end_01"
                                position: Qt.vector3d(3.35276e-08, -0.135412, -0.000122696)
                                rotation: Qt.quaternion(2.07219e-07, 3.07336e-08, 1, -1.3184e-08)
                                scale: Qt.vector3d(1, 1, 1)
                                Node {
                                    id: j_Sec_L_SkirtSide2_end_01_end
                                    objectName: "J_Sec_L_SkirtSide2_end_01_end"
                                    position: Qt.vector3d(1.73317e-08, -0.07, -6.34265e-05)
                                }
                            }
                        }
                    }
                }
                Node {
                    id: j_Sec_R_SkirtSide0_01
                    objectName: "J_Sec_R_SkirtSide0_01"
                    position: Qt.vector3d(-0.193712, -0.0172027, 0.0105048)
                    rotation: Qt.quaternion(0.688345, -0.161807, -0.697125, -0.118392)
                    scale: Qt.vector3d(1, 1, 1)
                    Node {
                        id: j_Sec_R_SkirtSide1_01
                        objectName: "J_Sec_R_SkirtSide1_01"
                        position: Qt.vector3d(-1.49012e-08, -5.96046e-08, -5.96046e-08)
                        rotation: Qt.quaternion(1, 5.35802e-08, -3.1665e-08, -5.4948e-08)
                        scale: Qt.vector3d(1, 1, 1)
                        Node {
                            id: j_Sec_R_SkirtSide2_01
                            objectName: "J_Sec_R_SkirtSide2_01"
                            position: Qt.vector3d(-0.000229675, -0.144606, -0.00423694)
                            rotation: Qt.quaternion(0.999177, 0.0404505, -0.0012077, 0.00273188)
                            scale: Qt.vector3d(1, 1, 1)
                            Node {
                                id: j_Sec_R_SkirtSide2_end_01
                                objectName: "J_Sec_R_SkirtSide2_end_01"
                                position: Qt.vector3d(2.23517e-08, -0.135413, -0.000122935)
                                rotation: Qt.quaternion(1, 1.30967e-10, 2.79397e-09, -1.11759e-08)
                                scale: Qt.vector3d(1, 1, 1)
                                Node {
                                    id: j_Sec_R_SkirtSide2_end_01_end
                                    objectName: "J_Sec_R_SkirtSide2_end_01_end"
                                    position: Qt.vector3d(1.15545e-08, -0.07, -6.35495e-05)
                                }
                            }
                        }
                    }
                }
                Node {
                    id: j_Bip_C_Spine
                    objectName: "J_Bip_C_Spine"
                    position: Qt.vector3d(-6.43536e-32, 0.0538297, 0.00594722)
                    rotation: Qt.quaternion(0.999918, 0.0127968, 0, 0)
                    scale: Qt.vector3d(1, 1, 1)
                    Node {
                        id: j_Bip_C_Chest
                        objectName: "J_Bip_C_Chest"
                        position: Qt.vector3d(2.17976e-17, 0.113442, -0.0141963)
                        rotation: Qt.quaternion(0.990678, -0.136221, 0, 0)
                        scale: Qt.vector3d(1, 1, 1)
                        Node {
                            id: j_Bip_C_UpperChest
                            objectName: "J_Bip_C_UpperChest"
                            position: Qt.vector3d(-3.14626e-17, 0.109849, -0.00147399)
                            rotation: Qt.quaternion(0.994154, -0.107976, 0, 0)
                            Node {
                                id: j_Sec_L_Bust1
                                objectName: "J_Sec_L_Bust1"
                                position: Qt.vector3d(0.0542086, -0.0300666, 0.0633706)
                                rotation: Qt.quaternion(0.966512, 0.105634, 0.232051, 0.0291196)
                                scale: Qt.vector3d(1, 1, 1)
                                Node {
                                    id: j_Sec_L_Bust2
                                    objectName: "J_Sec_L_Bust2"
                                    position: Qt.vector3d(-6.56508e-05, 8.34465e-07, 0.0533653)
                                    rotation: Qt.quaternion(1, -6.14673e-08, 2.30968e-07, -2.32831e-08)
                                    scale: Qt.vector3d(1, 1, 1)
                                    Node {
                                        id: j_Sec_L_Bust2_end
                                        objectName: "J_Sec_L_Bust2_end"
                                        position: Qt.vector3d(-8.61149e-05, 1.09458e-06, 0.0699999)
                                    }
                                }
                            }
                            Node {
                                id: j_Sec_R_Bust1
                                objectName: "J_Sec_R_Bust1"
                                position: Qt.vector3d(-0.0542086, -0.0300666, 0.0633706)
                                rotation: Qt.quaternion(0.966512, 0.105634, -0.232051, -0.0291196)
                                scale: Qt.vector3d(1, 1, 1)
                                Node {
                                    id: j_Sec_R_Bust2
                                    objectName: "J_Sec_R_Bust2"
                                    position: Qt.vector3d(6.56508e-05, 8.34465e-07, 0.0533653)
                                    rotation: Qt.quaternion(1, -6.14673e-08, -2.30968e-07, 2.32831e-08)
                                    scale: Qt.vector3d(1, 1, 1)
                                    Node {
                                        id: j_Sec_R_Bust2_end
                                        objectName: "J_Sec_R_Bust2_end"
                                        position: Qt.vector3d(8.61149e-05, 1.09458e-06, 0.0699999)
                                    }
                                }
                            }
                            Node {
                                id: j_Bip_C_Neck
                                objectName: "J_Bip_C_Neck"
                                position: Qt.vector3d(-9.87408e-17, 0.139069, 0.00779378)
                                rotation: Qt.quaternion(0.973925, 0.22687, 0, 0)
                                scale: Qt.vector3d(1, 1, 1)
                                Node {
                                    id: j_Bip_C_Head
                                    objectName: "J_Bip_C_Head"
                                    position: Qt.vector3d(-1.37122e-09, 0.0753409, 0.000405714)
                                    rotation: Qt.quaternion(0.998523, -0.054336, 2.20206e-07, 1.19822e-08)
                                    scale: Qt.vector3d(1, 1, 1)
                                    Node {
                                        id: j_Adj_L_FaceEye
                                        objectName: "J_Adj_L_FaceEye"
                                        position: Qt.vector3d(0.0144765, 0.0604008, 0.0190731)
                                        rotation: Qt.quaternion(0.981257, 0.0159138, 0.191972, -0.00524275)
                                        scale: Qt.vector3d(1, 1, 1)
                                    }
                                    Node {
                                        id: j_Adj_R_FaceEye
                                        objectName: "J_Adj_R_FaceEye"
                                        position: Qt.vector3d(-0.0144765, 0.0604008, 0.0190731)
                                        rotation: Qt.quaternion(0.981257, 0.0159138, -0.191971, 0.00524276)
                                        scale: Qt.vector3d(1, 1, 1)
                                    }
                                    Node {
                                        id: j_Sec_Hair1_01
                                        objectName: "J_Sec_Hair1_01"
                                        position: Qt.vector3d(0.0292501, 0.116241, 0.0992647)
                                        rotation: Qt.quaternion(-0.0898588, -0.00224101, -0.0248303, 0.995642)
                                        scale: Qt.vector3d(1, 1, 1)
                                        Node {
                                            id: j_Sec_Hair2_01
                                            objectName: "J_Sec_Hair2_01"
                                            position: Qt.vector3d(0.000187993, 0.0298729, 1.13621e-07)
                                            rotation: Qt.quaternion(0.965275, -0.21454, 0.070025, 0.131578)
                                            scale: Qt.vector3d(0.999999, 1, 1)
                                            Node {
                                                id: j_Sec_Hair3_01
                                                objectName: "J_Sec_Hair3_01"
                                                position: Qt.vector3d(0.00041467, 0.0294118, 0)
                                                rotation: Qt.quaternion(1, 1.49012e-08, -2.98023e-08, 2.42144e-08)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: j_Sec_Hair3_01_end
                                                    objectName: "J_Sec_Hair3_01_end"
                                                    position: Qt.vector3d(0.000986814, 0.069993, 0)
                                                }
                                            }
                                        }
                                    }
                                    Node {
                                        id: j_Sec_Hair1_02
                                        objectName: "J_Sec_Hair1_02"
                                        position: Qt.vector3d(-0.0281734, 0.113682, 0.100223)
                                        rotation: Qt.quaternion(0.0660106, 0.00256378, -0.0387245, 0.997064)
                                        scale: Qt.vector3d(1, 1, 1)
                                        Node {
                                            id: j_Sec_Hair2_02
                                            objectName: "J_Sec_Hair2_02"
                                            position: Qt.vector3d(-0.000147775, 0.0316501, 2.98023e-08)
                                            rotation: Qt.quaternion(0.954015, -0.226198, -0.0750908, -0.1818)
                                            scale: Qt.vector3d(1, 1, 1)
                                            Node {
                                                id: j_Sec_Hair3_02
                                                objectName: "J_Sec_Hair3_02"
                                                position: Qt.vector3d(-0.00046432, 0.0303254, -1.19209e-07)
                                                rotation: Qt.quaternion(1, -4.47035e-08, -1.49012e-08, 1.49012e-08)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: j_Sec_Hair3_02_end
                                                    objectName: "J_Sec_Hair3_02_end"
                                                    position: Qt.vector3d(-0.00107166, 0.0699918, -2.75138e-07)
                                                }
                                            }
                                        }
                                    }
                                    Node {
                                        id: j_Sec_Hair1_03
                                        objectName: "J_Sec_Hair1_03"
                                        position: Qt.vector3d(0.0787199, 0.0392703, 0.0710929)
                                        rotation: Qt.quaternion(0.343032, -0.056095, 0.151321, 0.925356)
                                        scale: Qt.vector3d(1, 1, 1)
                                        Node {
                                            id: j_Sec_Hair2_03
                                            objectName: "J_Sec_Hair2_03"
                                            position: Qt.vector3d(-0.000617504, 0.0344647, -8.9407e-08)
                                            rotation: Qt.quaternion(0.855831, -0.288044, -0.0737699, 0.423252)
                                            scale: Qt.vector3d(1, 1, 1)
                                            Node {
                                                id: j_Sec_Hair3_03
                                                objectName: "J_Sec_Hair3_03"
                                                position: Qt.vector3d(0.000177503, 0.0244938, 2.98023e-08)
                                                rotation: Qt.quaternion(1, 5.21541e-08, -4.19095e-08, -6.70552e-08)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: j_Sec_Hair3_03_end
                                                    objectName: "J_Sec_Hair3_03_end"
                                                    position: Qt.vector3d(0.000507265, 0.0699982, 8.51688e-08)
                                                }
                                            }
                                        }
                                    }
                                    Node {
                                        id: j_Sec_Hair1_04
                                        objectName: "J_Sec_Hair1_04"
                                        position: Qt.vector3d(-0.0658077, 0.0416318, 0.0843574)
                                        rotation: Qt.quaternion(-0.242821, -0.00917233, -0.0366157, 0.969336)
                                        scale: Qt.vector3d(1, 1, 1)
                                        Node {
                                            id: j_Sec_Hair2_04
                                            objectName: "J_Sec_Hair2_04"
                                            position: Qt.vector3d(0.000478506, 0.0319752, -2.23517e-08)
                                            rotation: Qt.quaternion(0.805632, -0.285228, -0.0231957, -0.518714)
                                            scale: Qt.vector3d(1, 0.999999, 1)
                                            Node {
                                                id: j_Sec_Hair3_04
                                                objectName: "J_Sec_Hair3_04"
                                                position: Qt.vector3d(-0.000467122, 0.0267601, -1.78814e-07)
                                                rotation: Qt.quaternion(1, -5.2154e-08, 2.08616e-07, 2.79397e-07)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: j_Sec_Hair3_04_end
                                                    objectName: "J_Sec_Hair3_04_end"
                                                    position: Qt.vector3d(-0.00122173, 0.0699893, -4.67676e-07)
                                                }
                                            }
                                        }
                                    }
                                    Node {
                                        id: j_Sec_Hair1_05
                                        objectName: "J_Sec_Hair1_05"
                                        position: Qt.vector3d(0.0888686, 0.0683001, -0.00948917)
                                        rotation: Qt.quaternion(-0.0182075, -0.0023915, -0.130204, 0.991317)
                                        scale: Qt.vector3d(1, 1, 1)
                                        Node {
                                            id: j_Sec_Hair2_05
                                            objectName: "J_Sec_Hair2_05"
                                            position: Qt.vector3d(8.64267e-05, 0.0659666, 8.9407e-08)
                                            rotation: Qt.quaternion(0.999337, 0.000846493, -3.12648e-07, -0.0363851)
                                            scale: Qt.vector3d(0.999999, 0.999999, 1)
                                            Node {
                                                id: j_Sec_Hair3_05
                                                objectName: "J_Sec_Hair3_05"
                                                position: Qt.vector3d(-8.50521e-05, 0.066135, 0)
                                                rotation: Qt.quaternion(1, -4.47035e-08, -2.32831e-09, -2.73576e-09)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: j_Sec_Hair3_05_end
                                                    objectName: "J_Sec_Hair3_05_end"
                                                    position: Qt.vector3d(-9.00225e-05, 0.0699999, 0)
                                                }
                                            }
                                        }
                                    }
                                    Node {
                                        id: j_Sec_Hair1_06
                                        objectName: "J_Sec_Hair1_06"
                                        position: Qt.vector3d(0.0322661, 0.0540527, -0.103644)
                                        rotation: Qt.quaternion(-0.0453264, 0.000826529, 0.0182126, 0.998806)
                                        scale: Qt.vector3d(1, 1, 1)
                                        Node {
                                            id: j_Sec_Hair2_06
                                            objectName: "J_Sec_Hair2_06"
                                            position: Qt.vector3d(0.000184655, 0.05735, -5.96046e-08)
                                            rotation: Qt.quaternion(1, -2.79397e-09, -9.31323e-10, -9.3014e-09)
                                            scale: Qt.vector3d(1, 1, 1)
                                            Node {
                                                id: j_Sec_Hair3_06
                                                objectName: "J_Sec_Hair3_06"
                                                position: Qt.vector3d(0.000185177, 0.057354, 7.45058e-09)
                                                rotation: Qt.quaternion(1, 0, 0, -1.85992e-09)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: j_Sec_Hair3_06_end
                                                    objectName: "J_Sec_Hair3_06_end"
                                                    position: Qt.vector3d(0.000226005, 0.0699996, 9.09332e-09)
                                                }
                                            }
                                        }
                                    }
                                    Node {
                                        id: j_Sec_Hair1_07
                                        objectName: "J_Sec_Hair1_07"
                                        position: Qt.vector3d(-0.0468503, 0.0547776, -0.0952961)
                                        rotation: Qt.quaternion(-0.0263297, -0.000464094, -0.0176128, 0.999498)
                                        scale: Qt.vector3d(1, 1, 1)
                                        Node {
                                            id: j_Sec_Hair2_07
                                            objectName: "J_Sec_Hair2_07"
                                            position: Qt.vector3d(0.000108644, 0.0578914, 0)
                                            rotation: Qt.quaternion(0.999972, 0.00678107, -0.000379617, 0.00324469)
                                            scale: Qt.vector3d(1, 1, 1)
                                            Node {
                                                id: j_Sec_Hair3_07
                                                objectName: "J_Sec_Hair3_07"
                                                position: Qt.vector3d(0.000122063, 0.0579246, 4.47035e-08)
                                                rotation: Qt.quaternion(1, -6.51926e-09, 3.20142e-10, 3.71074e-09)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: j_Sec_Hair3_07_end
                                                    objectName: "J_Sec_Hair3_07_end"
                                                    position: Qt.vector3d(0.000147509, 0.0699998, 5.40226e-08)
                                                }
                                            }
                                        }
                                    }
                                    Node {
                                        id: j_Sec_Hair1_08
                                        objectName: "J_Sec_Hair1_08"
                                        position: Qt.vector3d(-0.0909169, 0.0646733, -0.0104982)
                                        rotation: Qt.quaternion(0.0185097, 0.00205129, -0.110128, 0.993743)
                                        scale: Qt.vector3d(1, 1, 1)
                                        Node {
                                            id: j_Sec_Hair2_08
                                            objectName: "J_Sec_Hair2_08"
                                            position: Qt.vector3d(-8.40425e-05, 0.0632612, 2.98023e-08)
                                            rotation: Qt.quaternion(0.999657, 0.00215909, 2.40368e-05, 0.0261181)
                                            scale: Qt.vector3d(1, 0.999999, 1)
                                            Node {
                                                id: j_Sec_Hair3_08
                                                objectName: "J_Sec_Hair3_08"
                                                position: Qt.vector3d(3.39001e-05, 0.0633554, 2.98023e-08)
                                                rotation: Qt.quaternion(1, 1.11759e-08, -1.04774e-09, 6.40284e-09)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: j_Sec_Hair3_08_end
                                                    objectName: "J_Sec_Hair3_08_end"
                                                    position: Qt.vector3d(3.74555e-05, 0.07, 3.29279e-08)
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            Node {
                                id: j_Bip_L_Shoulder
                                objectName: "J_Bip_L_Shoulder"
                                position: Qt.vector3d(0.0225103, 0.110877, 0.00686976)
                                rotation: Qt.quaternion(0.983277, 0.16787, 0.0118837, -0.0696071)
                                scale: Qt.vector3d(1, 1, 1)
                                Node {
                                    id: j_Bip_L_UpperArm
                                    objectName: "J_Bip_L_UpperArm"
                                    position: Qt.vector3d(0.0856985, -7.28369e-05, -1.00583e-07)
                                    rotation: Qt.quaternion(0.997504, 2.23815e-08, 1.25862e-09, 0.0706143)
                                    scale: Qt.vector3d(1, 1, 1)
                                    Node {
                                        id: j_Bip_L_LowerArm
                                        objectName: "J_Bip_L_LowerArm"
                                        position: Qt.vector3d(0.222293, 0, 1.30385e-08)
                                        rotation: Qt.quaternion(1, 5.10232e-11, 5.3549e-10, 3.72529e-09)
                                        scale: Qt.vector3d(1, 1, 1)
                                        Node {
                                            id: j_Sec_L_LowerSleeve_01
                                            objectName: "J_Sec_L_LowerSleeve_01"
                                            position: Qt.vector3d(0.104412, -0.020247, 0.00240464)
                                            rotation: Qt.quaternion(0.720544, -0.127534, 0.0724578, -0.677718)
                                            scale: Qt.vector3d(1, 1, 1)
                                            Node {
                                                id: j_Sec_L_LowerSleeve_end_01
                                                objectName: "J_Sec_L_LowerSleeve_end_01"
                                                position: Qt.vector3d(0.0789914, -0.000195682, -5.66244e-05)
                                                rotation: Qt.quaternion(1, 5.21541e-08, 2.6077e-08, 3.52971e-07)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: j_Sec_L_LowerSleeve_end_01_end
                                                    objectName: "J_Sec_L_LowerSleeve_end_01_end"
                                                    position: Qt.vector3d(0.0699998, -0.000173407, -5.01788e-05)
                                                }
                                            }
                                        }
                                        Node {
                                            id: j_Bip_L_Hand
                                            objectName: "J_Bip_L_Hand"
                                            position: Qt.vector3d(0.215787, 2.38419e-06, 1.52271e-05)
                                            rotation: Qt.quaternion(1, 4.44089e-16, 0, -8.88178e-16)
                                            Node {
                                                id: j_Bip_L_Index1
                                                objectName: "J_Bip_L_Index1"
                                                position: Qt.vector3d(0.0651227, 0.00697017, 0.0196679)
                                                rotation: Qt.quaternion(0.999953, -1.4175e-08, 0.00970428, 2.52802e-08)
                                                Node {
                                                    id: j_Bip_L_Index2
                                                    objectName: "J_Bip_L_Index2"
                                                    position: Qt.vector3d(0.0330855, 0, -4.46523e-06)
                                                    rotation: Qt.quaternion(0.99985, 0.000137837, 0.0095633, -0.0144418)
                                                    scale: Qt.vector3d(1, 1, 1)
                                                    Node {
                                                        id: j_Bip_L_Index3
                                                        objectName: "J_Bip_L_Index3"
                                                        position: Qt.vector3d(0.0203694, 2.98023e-05, 2.78223e-05)
                                                        rotation: Qt.quaternion(0.999992, 5.59234e-08, -0.00258984, -0.00292625)
                                                        scale: Qt.vector3d(1, 1, 1)
                                                    }
                                                }
                                            }
                                            Node {
                                                id: j_Bip_L_Little1
                                                objectName: "J_Bip_L_Little1"
                                                position: Qt.vector3d(0.0607646, 0.00697017, -0.0291923)
                                                rotation: Qt.quaternion(1, 4.44089e-16, 0, 0)
                                                Node {
                                                    id: j_Bip_L_Little2
                                                    objectName: "J_Bip_L_Little2"
                                                    position: Qt.vector3d(0.0312701, 0, 1.86265e-08)
                                                    rotation: Qt.quaternion(1, 4.44089e-16, 0, 0)
                                                    Node {
                                                        id: j_Bip_L_Little3
                                                        objectName: "J_Bip_L_Little3"
                                                        position: Qt.vector3d(0.0180222, 1.19209e-07, 2.6077e-08)
                                                        rotation: Qt.quaternion(0.999924, -6.25416e-08, -0.00960976, 0.00776877)
                                                    }
                                                }
                                            }
                                            Node {
                                                id: j_Bip_L_Middle1
                                                objectName: "J_Bip_L_Middle1"
                                                position: Qt.vector3d(0.0660098, 0.00697029, 0.00204814)
                                                rotation: Qt.quaternion(1, 4.44089e-16, 0, 0)
                                                Node {
                                                    id: j_Bip_L_Middle2
                                                    objectName: "J_Bip_L_Middle2"
                                                    position: Qt.vector3d(0.0368533, -1.19209e-07, 1.11759e-08)
                                                    rotation: Qt.quaternion(1, 4.44089e-16, 0, 0)
                                                    Node {
                                                        id: j_Bip_L_Middle3
                                                        objectName: "J_Bip_L_Middle3"
                                                        position: Qt.vector3d(0.0227357, 0, 3.72529e-09)
                                                        rotation: Qt.quaternion(1, 4.44089e-16, 0, 0)
                                                    }
                                                }
                                            }
                                            Node {
                                                id: j_Bip_L_Ring1
                                                objectName: "J_Bip_L_Ring1"
                                                position: Qt.vector3d(0.0652579, 0.00697017, -0.0135958)
                                                rotation: Qt.quaternion(1, 4.44089e-16, 0, 0)
                                                Node {
                                                    id: j_Bip_L_Ring2
                                                    objectName: "J_Bip_L_Ring2"
                                                    position: Qt.vector3d(0.0341861, 0, 0)
                                                    rotation: Qt.quaternion(1, 4.44089e-16, 0, 0)
                                                    Node {
                                                        id: j_Bip_L_Ring3
                                                        objectName: "J_Bip_L_Ring3"
                                                        position: Qt.vector3d(0.0197288, 0, 0)
                                                        rotation: Qt.quaternion(0.999915, -3.68668e-08, 0.0114384, -0.00621871)
                                                        scale: Qt.vector3d(1, 1, 1)
                                                    }
                                                }
                                            }
                                            Node {
                                                id: j_Bip_L_Thumb1
                                                objectName: "J_Bip_L_Thumb1"
                                                position: Qt.vector3d(0.00350446, -0.00945234, 0.0159724)
                                                rotation: Qt.quaternion(0.620582, 0.703166, -0.246799, 0.24398)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: j_Bip_L_Thumb2
                                                    objectName: "J_Bip_L_Thumb2"
                                                    position: Qt.vector3d(0.0464567, 0.000126958, -0.000123024)
                                                    rotation: Qt.quaternion(0.999746, -5.98695e-05, 0.00279444, -0.0223553)
                                                    scale: Qt.vector3d(1, 1, 1)
                                                    Node {
                                                        id: j_Bip_L_Thumb3
                                                        objectName: "J_Bip_L_Thumb3"
                                                        position: Qt.vector3d(0.0285668, 0.000149161, -6.00815e-05)
                                                        rotation: Qt.quaternion(0.999161, 0.000382159, -0.00800169, 0.0401746)
                                                        scale: Qt.vector3d(1, 1, 1)
                                                    }
                                                }
                                            }
                                            Node {
                                                id: j_Sec_L_TipSleeve_01
                                                objectName: "J_Sec_L_TipSleeve_01"
                                                position: Qt.vector3d(-0.00478363, -0.0150099, -0.00825096)
                                                rotation: Qt.quaternion(0.994587, -0.0181489, 0.0701348, -0.0744813)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: j_Sec_L_TipSleeve_end_01
                                                    objectName: "J_Sec_L_TipSleeve_end_01"
                                                    position: Qt.vector3d(0.0453491, 0.00276423, 0.00395115)
                                                    rotation: Qt.quaternion(1, -9.31323e-10, 1.11759e-08, -4.42378e-09)
                                                    scale: Qt.vector3d(1, 1, 1)
                                                    Node {
                                                        id: j_Sec_L_TipSleeve_end_01_end
                                                        objectName: "J_Sec_L_TipSleeve_end_01_end"
                                                        position: Qt.vector3d(0.0696076, 0.00424288, 0.00606472)
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            Node {
                                id: j_Bip_R_Shoulder
                                objectName: "J_Bip_R_Shoulder"
                                position: Qt.vector3d(-0.0225103, 0.110877, 0.00686976)
                                rotation: Qt.quaternion(0.983277, 0.16787, -0.0118837, 0.0696071)
                                scale: Qt.vector3d(1, 1, 1)
                                Node {
                                    id: j_Bip_R_UpperArm
                                    objectName: "J_Bip_R_UpperArm"
                                    position: Qt.vector3d(-0.0856985, -7.28369e-05, -1.00583e-07)
                                    rotation: Qt.quaternion(0.997504, 2.23815e-08, -1.25862e-09, -0.0706143)
                                    scale: Qt.vector3d(1, 1, 1)
                                    Node {
                                        id: j_Bip_R_LowerArm
                                        objectName: "J_Bip_R_LowerArm"
                                        position: Qt.vector3d(-0.222293, 0, 1.30385e-08)
                                        rotation: Qt.quaternion(1, 5.10232e-11, -5.3549e-10, -3.72529e-09)
                                        scale: Qt.vector3d(1, 1, 1)
                                        Node {
                                            id: j_Sec_R_LowerSleeve_01
                                            objectName: "J_Sec_R_LowerSleeve_01"
                                            position: Qt.vector3d(-0.104412, -0.020247, 0.00240464)
                                            rotation: Qt.quaternion(0.720544, -0.127534, -0.0724578, 0.677718)
                                            scale: Qt.vector3d(1, 1, 1)
                                            Node {
                                                id: j_Sec_R_LowerSleeve_end_01
                                                objectName: "J_Sec_R_LowerSleeve_end_01"
                                                position: Qt.vector3d(-0.0789914, -0.000195682, -5.66244e-05)
                                                rotation: Qt.quaternion(1, 5.21541e-08, -2.6077e-08, -3.52971e-07)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: j_Sec_R_LowerSleeve_end_01_end
                                                    objectName: "J_Sec_R_LowerSleeve_end_01_end"
                                                    position: Qt.vector3d(-0.0699998, -0.000173407, -5.01788e-05)
                                                }
                                            }
                                        }
                                        Node {
                                            id: j_Bip_R_Hand
                                            objectName: "J_Bip_R_Hand"
                                            position: Qt.vector3d(-0.215787, 2.38419e-06, 1.52271e-05)
                                            rotation: Qt.quaternion(1, 4.44089e-16, 0, 8.88178e-16)
                                            Node {
                                                id: j_Bip_R_Index1
                                                objectName: "J_Bip_R_Index1"
                                                position: Qt.vector3d(-0.0651227, 0.00697017, 0.0196679)
                                                rotation: Qt.quaternion(0.999953, -1.4175e-08, -0.00970428, -2.52802e-08)
                                                Node {
                                                    id: j_Bip_R_Index2
                                                    objectName: "J_Bip_R_Index2"
                                                    position: Qt.vector3d(-0.0330855, 0, -4.46523e-06)
                                                    rotation: Qt.quaternion(0.99985, 0.000137837, -0.0095633, 0.0144418)
                                                    scale: Qt.vector3d(1, 1, 1)
                                                    Node {
                                                        id: j_Bip_R_Index3
                                                        objectName: "J_Bip_R_Index3"
                                                        position: Qt.vector3d(-0.0203694, 2.98023e-05, 2.78223e-05)
                                                        rotation: Qt.quaternion(0.999992, 5.59234e-08, 0.00258984, 0.00292625)
                                                        scale: Qt.vector3d(1, 1, 1)
                                                    }
                                                }
                                            }
                                            Node {
                                                id: j_Bip_R_Little1
                                                objectName: "J_Bip_R_Little1"
                                                position: Qt.vector3d(-0.0607646, 0.00697017, -0.0291923)
                                                rotation: Qt.quaternion(1, 4.44089e-16, 0, 0)
                                                Node {
                                                    id: j_Bip_R_Little2
                                                    objectName: "J_Bip_R_Little2"
                                                    position: Qt.vector3d(-0.0312701, 0, 1.86265e-08)
                                                    rotation: Qt.quaternion(1, 4.44089e-16, 0, 0)
                                                    Node {
                                                        id: j_Bip_R_Little3
                                                        objectName: "J_Bip_R_Little3"
                                                        position: Qt.vector3d(-0.0180222, 1.19209e-07, 2.6077e-08)
                                                        rotation: Qt.quaternion(0.999924, -6.25416e-08, 0.00960976, -0.00776877)
                                                    }
                                                }
                                            }
                                            Node {
                                                id: j_Bip_R_Middle1
                                                objectName: "J_Bip_R_Middle1"
                                                position: Qt.vector3d(-0.0660098, 0.00697029, 0.00204814)
                                                rotation: Qt.quaternion(1, 4.44089e-16, 0, 0)
                                                Node {
                                                    id: j_Bip_R_Middle2
                                                    objectName: "J_Bip_R_Middle2"
                                                    position: Qt.vector3d(-0.0368533, -1.19209e-07, 1.11759e-08)
                                                    rotation: Qt.quaternion(1, 4.44089e-16, 0, 0)
                                                    Node {
                                                        id: j_Bip_R_Middle3
                                                        objectName: "J_Bip_R_Middle3"
                                                        position: Qt.vector3d(-0.0227357, 0, 3.72529e-09)
                                                        rotation: Qt.quaternion(1, 4.44089e-16, 0, 0)
                                                    }
                                                }
                                            }
                                            Node {
                                                id: j_Bip_R_Ring1
                                                objectName: "J_Bip_R_Ring1"
                                                position: Qt.vector3d(-0.0652579, 0.00697017, -0.0135958)
                                                rotation: Qt.quaternion(1, 4.44089e-16, 0, 0)
                                                Node {
                                                    id: j_Bip_R_Ring2
                                                    objectName: "J_Bip_R_Ring2"
                                                    position: Qt.vector3d(-0.0341861, 0, 0)
                                                    rotation: Qt.quaternion(1, 4.44089e-16, 0, 0)
                                                    Node {
                                                        id: j_Bip_R_Ring3
                                                        objectName: "J_Bip_R_Ring3"
                                                        position: Qt.vector3d(-0.0197288, 0, 0)
                                                        rotation: Qt.quaternion(0.999915, -3.68668e-08, -0.0114384, 0.00621871)
                                                        scale: Qt.vector3d(1, 1, 1)
                                                    }
                                                }
                                            }
                                            Node {
                                                id: j_Bip_R_Thumb1
                                                objectName: "J_Bip_R_Thumb1"
                                                position: Qt.vector3d(-0.00350446, -0.00945234, 0.0159724)
                                                rotation: Qt.quaternion(0.620582, 0.703166, 0.246799, -0.24398)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: j_Bip_R_Thumb2
                                                    objectName: "J_Bip_R_Thumb2"
                                                    position: Qt.vector3d(-0.0464567, 0.000126958, -0.000123024)
                                                    rotation: Qt.quaternion(0.999746, -5.98695e-05, -0.00279444, 0.0223553)
                                                    scale: Qt.vector3d(1, 1, 1)
                                                    Node {
                                                        id: j_Bip_R_Thumb3
                                                        objectName: "J_Bip_R_Thumb3"
                                                        position: Qt.vector3d(-0.0285668, 0.000149161, -6.00815e-05)
                                                        rotation: Qt.quaternion(0.999161, 0.000382159, 0.00800169, -0.0401746)
                                                        scale: Qt.vector3d(1, 1, 1)
                                                    }
                                                }
                                            }
                                            Node {
                                                id: j_Sec_R_TipSleeve_01
                                                objectName: "J_Sec_R_TipSleeve_01"
                                                position: Qt.vector3d(0.00478363, -0.0150099, -0.00825096)
                                                rotation: Qt.quaternion(0.994587, -0.0181489, -0.0701348, 0.0744813)
                                                scale: Qt.vector3d(1, 1, 1)
                                                Node {
                                                    id: j_Sec_R_TipSleeve_end_01
                                                    objectName: "J_Sec_R_TipSleeve_end_01"
                                                    position: Qt.vector3d(-0.0453491, 0.00276423, 0.00395115)
                                                    rotation: Qt.quaternion(1, -9.31323e-10, -1.11759e-08, 4.42378e-09)
                                                    scale: Qt.vector3d(1, 1, 1)
                                                    Node {
                                                        id: j_Sec_R_TipSleeve_end_01_end
                                                        objectName: "J_Sec_R_TipSleeve_end_01_end"
                                                        position: Qt.vector3d(-0.0696076, 0.00424288, 0.00606472)
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                Node {
                    id: j_Bip_L_UpperLeg
                    objectName: "J_Bip_L_UpperLeg"
                    position: Qt.vector3d(0.0775518, -0.040368, 0.00138164)
                    rotation: Qt.quaternion(0.998623, -0.0524548, 0, 0)
                    scale: Qt.vector3d(1, 1, 1)
                    Node {
                        id: j_Sec_L_SkirtBack0_01
                        objectName: "J_Sec_L_SkirtBack0_01"
                        position: Qt.vector3d(0.00050658, 0.0324814, -0.131716)
                        rotation: Qt.quaternion(0.140529, -0.0880825, 0.964322, 0.20634)
                        scale: Qt.vector3d(1, 1, 1)
                        Node {
                            id: j_Sec_L_SkirtBack1_01
                            objectName: "J_Sec_L_SkirtBack1_01"
                            position: Qt.vector3d(7.45058e-08, -1.78814e-07, 0)
                            rotation: Qt.quaternion(1, -1.49012e-08, 7.45058e-09, -2.79397e-08)
                            scale: Qt.vector3d(1, 1, 1)
                            Node {
                                id: j_Sec_L_SkirtBack2_01
                                objectName: "J_Sec_L_SkirtBack2_01"
                                position: Qt.vector3d(2.25455e-05, -0.140139, -0.000748456)
                                rotation: Qt.quaternion(0.999811, 0.0189394, 0.00357706, -0.00260535)
                                scale: Qt.vector3d(1, 1, 1)
                                Node {
                                    id: j_Sec_L_SkirtBack2_end_01
                                    objectName: "J_Sec_L_SkirtBack2_end_01"
                                    position: Qt.vector3d(4.35263e-05, -0.139539, -0.000691712)
                                    rotation: Qt.quaternion(1, -7.45058e-09, -1.49012e-08, 3.72529e-09)
                                    scale: Qt.vector3d(1, 1, 1)
                                    Node {
                                        id: j_Sec_L_SkirtBack2_end_01_end
                                        objectName: "J_Sec_L_SkirtBack2_end_01_end"
                                        position: Qt.vector3d(2.18348e-05, -0.0699991, -0.000346995)
                                    }
                                }
                            }
                        }
                    }
                    Node {
                        id: j_Sec_L_SkirtFront0_01
                        objectName: "J_Sec_L_SkirtFront0_01"
                        position: Qt.vector3d(-0.00411415, 0.0070768, 0.1453)
                        rotation: Qt.quaternion(0.967835, -0.105826, 0.218859, 0.0647816)
                        scale: Qt.vector3d(1, 1, 1)
                        Node {
                            id: j_Sec_L_SkirtFront1_01
                            objectName: "J_Sec_L_SkirtFront1_01"
                            position: Qt.vector3d(0, -5.96046e-08, -2.98023e-08)
                            rotation: Qt.quaternion(1, 3.72529e-09, -1.49012e-08, -1.49012e-08)
                            scale: Qt.vector3d(1, 1, 1)
                            Node {
                                id: j_Sec_L_SkirtFront2_01
                                objectName: "J_Sec_L_SkirtFront2_01"
                                position: Qt.vector3d(-2.42665e-05, -0.130849, -0.000383437)
                                rotation: Qt.quaternion(1, 7.45058e-09, -1.49012e-08, -7.45058e-09)
                                scale: Qt.vector3d(1, 1, 1)
                                Node {
                                    id: j_Sec_L_SkirtFront2_end_01
                                    objectName: "J_Sec_L_SkirtFront2_end_01"
                                    position: Qt.vector3d(-2.56523e-05, -0.159767, -0.00047189)
                                    rotation: Qt.quaternion(1.41561e-07, 4.28408e-08, 1, 1.11759e-08)
                                    scale: Qt.vector3d(1, 1, 1)
                                    Node {
                                        id: j_Sec_L_SkirtFront2_end_01_end
                                        objectName: "J_Sec_L_SkirtFront2_end_01_end"
                                        position: Qt.vector3d(-1.12392e-05, -0.0699997, -0.000206751)
                                    }
                                }
                            }
                        }
                    }
                    Node {
                        id: j_Bip_L_LowerLeg
                        objectName: "J_Bip_L_LowerLeg"
                        position: Qt.vector3d(-1.49012e-08, -0.3635, -0.000299308)
                        rotation: Qt.quaternion(0.99974, 0.0228115, 0, 0)
                        scale: Qt.vector3d(1, 1, 1)
                        Node {
                            id: j_Bip_L_Foot
                            objectName: "J_Bip_L_Foot"
                            position: Qt.vector3d(0, -0.425317, 0.00304361)
                            rotation: Qt.quaternion(0.999534, -0.0305294, 0, 0)
                            scale: Qt.vector3d(1, 1, 1)
                            Node {
                                id: j_Bip_L_ToeBase
                                objectName: "J_Bip_L_ToeBase"
                                position: Qt.vector3d(0, -0.0631132, 0.110908)
                                rotation: Qt.quaternion(0.999998, 0.0021667, 0, 0)
                                scale: Qt.vector3d(1, 1, 1)
                            }
                        }
                    }
                }
                Node {
                    id: j_Bip_R_UpperLeg
                    objectName: "J_Bip_R_UpperLeg"
                    position: Qt.vector3d(-0.0775518, -0.040368, 0.00138164)
                    rotation: Qt.quaternion(0.998623, -0.0524548, 0, 0)
                    scale: Qt.vector3d(1, 1, 1)
                    Node {
                        id: j_Sec_R_SkirtBack0_01
                        objectName: "J_Sec_R_SkirtBack0_01"
                        position: Qt.vector3d(-0.000506595, 0.0324813, -0.131716)
                        rotation: Qt.quaternion(-0.140529, 0.0880825, 0.964322, 0.20634)
                        scale: Qt.vector3d(1, 1, 1)
                        Node {
                            id: j_Sec_R_SkirtBack1_01
                            objectName: "J_Sec_R_SkirtBack1_01"
                            position: Qt.vector3d(0, -1.19209e-07, 5.96046e-08)
                            rotation: Qt.quaternion(1, 7.45058e-09, -1.49012e-08, -9.31323e-09)
                            scale: Qt.vector3d(1, 1, 1)
                            Node {
                                id: j_Sec_R_SkirtBack2_01
                                objectName: "J_Sec_R_SkirtBack2_01"
                                position: Qt.vector3d(-2.24859e-05, -0.140139, -0.000748932)
                                rotation: Qt.quaternion(0.999811, 0.0189394, -0.00357679, 0.00260541)
                                scale: Qt.vector3d(1, 1, 1)
                                Node {
                                    id: j_Sec_R_SkirtBack2_end_01
                                    objectName: "J_Sec_R_SkirtBack2_end_01"
                                    position: Qt.vector3d(-4.30793e-05, -0.139538, -0.000691473)
                                    rotation: Qt.quaternion(1, 7.45058e-09, 7.45058e-09, 9.31323e-09)
                                    scale: Qt.vector3d(1, 1, 1)
                                    Node {
                                        id: j_Sec_R_SkirtBack2_end_01_end
                                        objectName: "J_Sec_R_SkirtBack2_end_01_end"
                                        position: Qt.vector3d(-2.16107e-05, -0.0699991, -0.000346877)
                                    }
                                }
                            }
                        }
                    }
                    Node {
                        id: j_Sec_R_SkirtFront0_01
                        objectName: "J_Sec_R_SkirtFront0_01"
                        position: Qt.vector3d(0.00411412, 0.00707656, 0.1453)
                        rotation: Qt.quaternion(0.967835, -0.105826, -0.218859, -0.0647816)
                        scale: Qt.vector3d(1, 1, 1)
                        Node {
                            id: j_Sec_R_SkirtFront1_01
                            objectName: "J_Sec_R_SkirtFront1_01"
                            position: Qt.vector3d(7.45058e-09, -5.96046e-08, 0)
                            rotation: Qt.quaternion(1, 3.72529e-09, 1.49012e-08, 1.49012e-08)
                            scale: Qt.vector3d(1, 1, 1)
                            Node {
                                id: j_Sec_R_SkirtFront2_01
                                objectName: "J_Sec_R_SkirtFront2_01"
                                position: Qt.vector3d(2.41548e-05, -0.130849, -0.000383466)
                                rotation: Qt.quaternion(1, 7.45058e-09, 1.49012e-08, 7.45058e-09)
                                scale: Qt.vector3d(1, 1, 1)
                                Node {
                                    id: j_Sec_R_SkirtFront2_end_01
                                    objectName: "J_Sec_R_SkirtFront2_end_01"
                                    position: Qt.vector3d(2.61441e-05, -0.159767, -0.000472009)
                                    rotation: Qt.quaternion(1, 0, -1.49012e-08, 1.86265e-09)
                                    scale: Qt.vector3d(1, 1, 1)
                                    Node {
                                        id: j_Sec_R_SkirtFront2_end_01_end
                                        objectName: "J_Sec_R_SkirtFront2_end_01_end"
                                        position: Qt.vector3d(1.14546e-05, -0.0699997, -0.000206804)
                                    }
                                }
                            }
                        }
                    }
                    Node {
                        id: j_Bip_R_LowerLeg
                        objectName: "J_Bip_R_LowerLeg"
                        position: Qt.vector3d(1.49012e-08, -0.3635, -0.000299308)
                        rotation: Qt.quaternion(0.99974, 0.0228115, 0, 0)
                        scale: Qt.vector3d(1, 1, 1)
                        Node {
                            id: j_Bip_R_Foot
                            objectName: "J_Bip_R_Foot"
                            position: Qt.vector3d(0, -0.425317, 0.00304361)
                            rotation: Qt.quaternion(0.999534, -0.0305294, 0, 0)
                            scale: Qt.vector3d(1, 1, 1)
                            Node {
                                id: j_Bip_R_ToeBase
                                objectName: "J_Bip_R_ToeBase"
                                position: Qt.vector3d(0, -0.0631132, 0.110908)
                                rotation: Qt.quaternion(0.999998, 0.0021667, 0, 0)
                                scale: Qt.vector3d(1, 1, 1)
                            }
                        }
                    }
                }
            }
        }
        Model {
            id: face
            objectName: "Face"
            source: "meshes/face_mesh.mesh"
            skin: skin
            materials: [
                n00_000_00_FaceMouth_00_FACE__Instance__material,
                n00_000_00_EyeIris_00_EYE__Instance__material,
                n00_000_00_EyeHighlight_00_EYE__Instance__material,
                n00_000_00_Face_00_SKIN__Instance__material,
                n00_000_00_EyeWhite_00_EYE__Instance__material,
                n00_000_00_FaceBrow_00_FACE__Instance__material,
                n00_000_00_FaceEyelash_00_FACE__Instance__material,
                n00_000_00_FaceEyeline_00_FACE__Instance__material
            ]
            morphTargets: [
                fcl_ALL_Neutral_morphtarget170,
                fcl_ALL_Angry_morphtarget171,
                fcl_ALL_Fun_morphtarget172,
                fcl_ALL_Joy_morphtarget173,
                fcl_ALL_Sorrow_morphtarget174,
                fcl_ALL_Surprised_morphtarget175,
                fcl_BRW_Angry_morphtarget176,
                fcl_BRW_Fun_morphtarget177,
                fcl_BRW_Joy_morphtarget178,
                fcl_BRW_Sorrow_morphtarget179,
                fcl_BRW_Surprised_morphtarget180,
                fcl_EYE_Natural_morphtarget181,
                fcl_EYE_Angry_morphtarget182,
                fcl_EYE_Close_morphtarget183,
                fcl_EYE_Close_R_morphtarget,
                fcl_EYE_Close_L_morphtarget,
                fcl_EYE_Fun_morphtarget,
                fcl_EYE_Joy_morphtarget,
                fcl_EYE_Joy_R_morphtarget,
                fcl_EYE_Joy_L_morphtarget,
                fcl_EYE_Sorrow_morphtarget,
                fcl_EYE_Surprised_morphtarget,
                fcl_EYE_Spread_morphtarget,
                fcl_EYE_Iris_Hide_morphtarget,
                fcl_EYE_Highlight_Hide_morphtarget,
                fcl_MTH_Close_morphtarget,
                fcl_MTH_Up_morphtarget,
                fcl_MTH_Down_morphtarget,
                fcl_MTH_Angry_morphtarget,
                fcl_MTH_Small_morphtarget,
                fcl_MTH_Large_morphtarget,
                fcl_MTH_Neutral_morphtarget,
                fcl_MTH_Fun_morphtarget,
                fcl_MTH_Joy_morphtarget,
                fcl_MTH_Sorrow_morphtarget,
                fcl_MTH_Surprised_morphtarget,
                fcl_MTH_SkinFung_morphtarget,
                fcl_MTH_SkinFung_R_morphtarget,
                fcl_MTH_SkinFung_L_morphtarget,
                fcl_MTH_A_morphtarget,
                fcl_MTH_I_morphtarget,
                fcl_MTH_U_morphtarget,
                fcl_MTH_E_morphtarget,
                fcl_MTH_O_morphtarget,
                fcl_HA_Hide_morphtarget,
                fcl_HA_Fung1_morphtarget,
                fcl_HA_Fung1_Low_morphtarget,
                fcl_HA_Fung1_Up_morphtarget,
                fcl_HA_Fung2_morphtarget,
                fcl_HA_Fung2_Low_morphtarget,
                fcl_HA_Fung2_Up_morphtarget,
                fcl_HA_Fung3_morphtarget,
                fcl_HA_Fung3_Up_morphtarget,
                fcl_HA_Fung3_Low_morphtarget,
                fcl_HA_Short_morphtarget,
                fcl_HA_Short_Up_morphtarget,
                fcl_HA_Short_Low_morphtarget,
                fcl_ALL_Neutral_morphtarget,
                fcl_ALL_Angry_morphtarget,
                fcl_ALL_Fun_morphtarget,
                fcl_ALL_Joy_morphtarget,
                fcl_ALL_Sorrow_morphtarget,
                fcl_ALL_Surprised_morphtarget,
                fcl_BRW_Angry_morphtarget,
                fcl_BRW_Fun_morphtarget,
                fcl_BRW_Joy_morphtarget,
                fcl_BRW_Sorrow_morphtarget,
                fcl_BRW_Surprised_morphtarget,
                fcl_EYE_Natural_morphtarget,
                fcl_EYE_Angry_morphtarget,
                fcl_EYE_Close_morphtarget,
                fcl_EYE_Close_R_morphtarget241,
                fcl_EYE_Close_L_morphtarget242,
                fcl_EYE_Fun_morphtarget243,
                fcl_EYE_Joy_morphtarget244,
                fcl_EYE_Joy_R_morphtarget245,
                fcl_EYE_Joy_L_morphtarget246,
                fcl_EYE_Sorrow_morphtarget247,
                fcl_EYE_Surprised_morphtarget248,
                fcl_EYE_Spread_morphtarget249,
                fcl_EYE_Iris_Hide_morphtarget250,
                fcl_EYE_Highlight_Hide_morphtarget251,
                fcl_MTH_Close_morphtarget252,
                fcl_MTH_Up_morphtarget253,
                fcl_MTH_Down_morphtarget254,
                fcl_MTH_Angry_morphtarget255,
                fcl_MTH_Small_morphtarget256,
                fcl_MTH_Large_morphtarget257,
                fcl_MTH_Neutral_morphtarget258,
                fcl_MTH_Fun_morphtarget259,
                fcl_MTH_Joy_morphtarget260,
                fcl_MTH_Sorrow_morphtarget261,
                fcl_MTH_Surprised_morphtarget262,
                fcl_MTH_SkinFung_morphtarget263,
                fcl_MTH_SkinFung_R_morphtarget264,
                fcl_MTH_SkinFung_L_morphtarget265,
                fcl_MTH_A_morphtarget266,
                fcl_MTH_I_morphtarget267,
                fcl_MTH_U_morphtarget268,
                fcl_MTH_E_morphtarget269,
                fcl_MTH_O_morphtarget270,
                fcl_HA_Hide_morphtarget271,
                fcl_HA_Fung1_morphtarget272,
                fcl_HA_Fung1_Low_morphtarget273,
                fcl_HA_Fung1_Up_morphtarget274,
                fcl_HA_Fung2_morphtarget275,
                fcl_HA_Fung2_Low_morphtarget276,
                fcl_HA_Fung2_Up_morphtarget277,
                fcl_HA_Fung3_morphtarget278,
                fcl_HA_Fung3_Up_morphtarget279,
                fcl_HA_Fung3_Low_morphtarget280,
                fcl_HA_Short_morphtarget281,
                fcl_HA_Short_Up_morphtarget282,
                fcl_HA_Short_Low_morphtarget283,
                fcl_ALL_Neutral_morphtarget284,
                fcl_ALL_Angry_morphtarget285,
                fcl_ALL_Fun_morphtarget286,
                fcl_ALL_Joy_morphtarget287,
                fcl_ALL_Sorrow_morphtarget288,
                fcl_ALL_Surprised_morphtarget289,
                fcl_BRW_Angry_morphtarget290,
                fcl_BRW_Fun_morphtarget291,
                fcl_BRW_Joy_morphtarget292,
                fcl_BRW_Sorrow_morphtarget293,
                fcl_BRW_Surprised_morphtarget294,
                fcl_EYE_Natural_morphtarget295,
                fcl_EYE_Angry_morphtarget296,
                fcl_EYE_Close_morphtarget297,
                fcl_EYE_Close_R_morphtarget298,
                fcl_EYE_Close_L_morphtarget299,
                fcl_EYE_Fun_morphtarget300,
                fcl_EYE_Joy_morphtarget301,
                fcl_EYE_Joy_R_morphtarget302,
                fcl_EYE_Joy_L_morphtarget303,
                fcl_EYE_Sorrow_morphtarget304,
                fcl_EYE_Surprised_morphtarget305,
                fcl_EYE_Spread_morphtarget306,
                fcl_EYE_Iris_Hide_morphtarget307,
                fcl_EYE_Highlight_Hide_morphtarget308,
                fcl_MTH_Close_morphtarget309,
                fcl_MTH_Up_morphtarget310,
                fcl_MTH_Down_morphtarget311,
                fcl_MTH_Angry_morphtarget312,
                fcl_MTH_Small_morphtarget313,
                fcl_MTH_Large_morphtarget314,
                fcl_MTH_Neutral_morphtarget315,
                fcl_MTH_Fun_morphtarget316,
                fcl_MTH_Joy_morphtarget317,
                fcl_MTH_Sorrow_morphtarget318,
                fcl_MTH_Surprised_morphtarget319,
                fcl_MTH_SkinFung_morphtarget320,
                fcl_MTH_SkinFung_R_morphtarget321,
                fcl_MTH_SkinFung_L_morphtarget322,
                fcl_MTH_A_morphtarget323,
                fcl_MTH_I_morphtarget324,
                fcl_MTH_U_morphtarget325,
                fcl_MTH_E_morphtarget326,
                fcl_MTH_O_morphtarget327,
                fcl_HA_Hide_morphtarget328,
                fcl_HA_Fung1_morphtarget329,
                fcl_HA_Fung1_Low_morphtarget330,
                fcl_HA_Fung1_Up_morphtarget331,
                fcl_HA_Fung2_morphtarget332,
                fcl_HA_Fung2_Low_morphtarget333,
                fcl_HA_Fung2_Up_morphtarget334,
                fcl_HA_Fung3_morphtarget335,
                fcl_HA_Fung3_Up_morphtarget336,
                fcl_HA_Fung3_Low_morphtarget337,
                fcl_HA_Short_morphtarget338,
                fcl_HA_Short_Up_morphtarget339,
                fcl_HA_Short_Low_morphtarget340,
                fcl_ALL_Neutral_morphtarget341,
                fcl_ALL_Angry_morphtarget342,
                fcl_ALL_Fun_morphtarget343,
                fcl_ALL_Joy_morphtarget344,
                fcl_ALL_Sorrow_morphtarget345,
                fcl_ALL_Surprised_morphtarget346,
                fcl_BRW_Angry_morphtarget347,
                fcl_BRW_Fun_morphtarget348,
                fcl_BRW_Joy_morphtarget349,
                fcl_BRW_Sorrow_morphtarget350,
                fcl_BRW_Surprised_morphtarget351,
                fcl_EYE_Natural_morphtarget352,
                fcl_EYE_Angry_morphtarget353,
                fcl_EYE_Close_morphtarget354,
                fcl_EYE_Close_R_morphtarget355,
                fcl_EYE_Close_L_morphtarget356,
                fcl_EYE_Fun_morphtarget357,
                fcl_EYE_Joy_morphtarget358,
                fcl_EYE_Joy_R_morphtarget359,
                fcl_EYE_Joy_L_morphtarget360,
                fcl_EYE_Sorrow_morphtarget361,
                fcl_EYE_Surprised_morphtarget362,
                fcl_EYE_Spread_morphtarget363,
                fcl_EYE_Iris_Hide_morphtarget364,
                fcl_EYE_Highlight_Hide_morphtarget365,
                fcl_MTH_Close_morphtarget366,
                fcl_MTH_Up_morphtarget367,
                fcl_MTH_Down_morphtarget368,
                fcl_MTH_Angry_morphtarget369,
                fcl_MTH_Small_morphtarget370,
                fcl_MTH_Large_morphtarget371,
                fcl_MTH_Neutral_morphtarget372,
                fcl_MTH_Fun_morphtarget373,
                fcl_MTH_Joy_morphtarget374,
                fcl_MTH_Sorrow_morphtarget375,
                fcl_MTH_Surprised_morphtarget376,
                fcl_MTH_SkinFung_morphtarget377,
                fcl_MTH_SkinFung_R_morphtarget378,
                fcl_MTH_SkinFung_L_morphtarget379,
                fcl_MTH_A_morphtarget380,
                fcl_MTH_I_morphtarget381,
                fcl_MTH_U_morphtarget382,
                fcl_MTH_E_morphtarget383,
                fcl_MTH_O_morphtarget384,
                fcl_HA_Hide_morphtarget385,
                fcl_HA_Fung1_morphtarget386,
                fcl_HA_Fung1_Low_morphtarget387,
                fcl_HA_Fung1_Up_morphtarget388,
                fcl_HA_Fung2_morphtarget389,
                fcl_HA_Fung2_Low_morphtarget390,
                fcl_HA_Fung2_Up_morphtarget391,
                fcl_HA_Fung3_morphtarget392,
                fcl_HA_Fung3_Up_morphtarget393,
                fcl_HA_Fung3_Low_morphtarget394,
                fcl_HA_Short_morphtarget395,
                fcl_HA_Short_Up_morphtarget396,
                fcl_HA_Short_Low_morphtarget397,
                fcl_ALL_Neutral_morphtarget398,
                fcl_ALL_Angry_morphtarget399,
                fcl_ALL_Fun_morphtarget400,
                fcl_ALL_Joy_morphtarget401,
                fcl_ALL_Sorrow_morphtarget402,
                fcl_ALL_Surprised_morphtarget403,
                fcl_BRW_Angry_morphtarget404,
                fcl_BRW_Fun_morphtarget405,
                fcl_BRW_Joy_morphtarget406,
                fcl_BRW_Sorrow_morphtarget407,
                fcl_BRW_Surprised_morphtarget408,
                fcl_EYE_Natural_morphtarget409,
                fcl_EYE_Angry_morphtarget410,
                fcl_EYE_Close_morphtarget411,
                fcl_EYE_Close_R_morphtarget412,
                fcl_EYE_Close_L_morphtarget413,
                fcl_EYE_Fun_morphtarget414,
                fcl_EYE_Joy_morphtarget415,
                fcl_EYE_Joy_R_morphtarget416,
                fcl_EYE_Joy_L_morphtarget417,
                fcl_EYE_Sorrow_morphtarget418,
                fcl_EYE_Surprised_morphtarget419,
                fcl_EYE_Spread_morphtarget420,
                fcl_EYE_Iris_Hide_morphtarget421,
                fcl_EYE_Highlight_Hide_morphtarget422,
                fcl_MTH_Close_morphtarget423,
                fcl_MTH_Up_morphtarget424,
                fcl_MTH_Down_morphtarget425,
                fcl_MTH_Angry_morphtarget426,
                fcl_MTH_Small_morphtarget427,
                fcl_MTH_Large_morphtarget428,
                fcl_MTH_Neutral_morphtarget429,
                fcl_MTH_Fun_morphtarget430,
                fcl_MTH_Joy_morphtarget431,
                fcl_MTH_Sorrow_morphtarget432,
                fcl_MTH_Surprised_morphtarget433,
                fcl_MTH_SkinFung_morphtarget434,
                fcl_MTH_SkinFung_R_morphtarget435,
                fcl_MTH_SkinFung_L_morphtarget436,
                fcl_MTH_A_morphtarget437,
                fcl_MTH_I_morphtarget438,
                fcl_MTH_U_morphtarget439,
                fcl_MTH_E_morphtarget440,
                fcl_MTH_O_morphtarget441,
                fcl_HA_Hide_morphtarget442,
                fcl_HA_Fung1_morphtarget443,
                fcl_HA_Fung1_Low_morphtarget444,
                fcl_HA_Fung1_Up_morphtarget445,
                fcl_HA_Fung2_morphtarget446,
                fcl_HA_Fung2_Low_morphtarget447,
                fcl_HA_Fung2_Up_morphtarget448,
                fcl_HA_Fung3_morphtarget449,
                fcl_HA_Fung3_Up_morphtarget450,
                fcl_HA_Fung3_Low_morphtarget451,
                fcl_HA_Short_morphtarget452,
                fcl_HA_Short_Up_morphtarget453,
                fcl_HA_Short_Low_morphtarget454,
                fcl_ALL_Neutral_morphtarget455,
                fcl_ALL_Angry_morphtarget456,
                fcl_ALL_Fun_morphtarget457,
                fcl_ALL_Joy_morphtarget458,
                fcl_ALL_Sorrow_morphtarget459,
                fcl_ALL_Surprised_morphtarget460,
                fcl_BRW_Angry_morphtarget461,
                fcl_BRW_Fun_morphtarget462,
                fcl_BRW_Joy_morphtarget463,
                fcl_BRW_Sorrow_morphtarget464,
                fcl_BRW_Surprised_morphtarget465,
                fcl_EYE_Natural_morphtarget466,
                fcl_EYE_Angry_morphtarget467,
                fcl_EYE_Close_morphtarget468,
                fcl_EYE_Close_R_morphtarget469,
                fcl_EYE_Close_L_morphtarget470,
                fcl_EYE_Fun_morphtarget471,
                fcl_EYE_Joy_morphtarget472,
                fcl_EYE_Joy_R_morphtarget473,
                fcl_EYE_Joy_L_morphtarget474,
                fcl_EYE_Sorrow_morphtarget475,
                fcl_EYE_Surprised_morphtarget476,
                fcl_EYE_Spread_morphtarget477,
                fcl_EYE_Iris_Hide_morphtarget478,
                fcl_EYE_Highlight_Hide_morphtarget479,
                fcl_MTH_Close_morphtarget480,
                fcl_MTH_Up_morphtarget481,
                fcl_MTH_Down_morphtarget482,
                fcl_MTH_Angry_morphtarget483,
                fcl_MTH_Small_morphtarget484,
                fcl_MTH_Large_morphtarget485,
                fcl_MTH_Neutral_morphtarget486,
                fcl_MTH_Fun_morphtarget487,
                fcl_MTH_Joy_morphtarget488,
                fcl_MTH_Sorrow_morphtarget489,
                fcl_MTH_Surprised_morphtarget490,
                fcl_MTH_SkinFung_morphtarget491,
                fcl_MTH_SkinFung_R_morphtarget492,
                fcl_MTH_SkinFung_L_morphtarget493,
                fcl_MTH_A_morphtarget494,
                fcl_MTH_I_morphtarget495,
                fcl_MTH_U_morphtarget496,
                fcl_MTH_E_morphtarget497,
                fcl_MTH_O_morphtarget498,
                fcl_HA_Hide_morphtarget499,
                fcl_HA_Fung1_morphtarget500,
                fcl_HA_Fung1_Low_morphtarget501,
                fcl_HA_Fung1_Up_morphtarget502,
                fcl_HA_Fung2_morphtarget503,
                fcl_HA_Fung2_Low_morphtarget504,
                fcl_HA_Fung2_Up_morphtarget505,
                fcl_HA_Fung3_morphtarget506,
                fcl_HA_Fung3_Up_morphtarget507,
                fcl_HA_Fung3_Low_morphtarget508,
                fcl_HA_Short_morphtarget509,
                fcl_HA_Short_Up_morphtarget510,
                fcl_HA_Short_Low_morphtarget511,
                fcl_ALL_Neutral_morphtarget512,
                fcl_ALL_Angry_morphtarget513,
                fcl_ALL_Fun_morphtarget514,
                fcl_ALL_Joy_morphtarget515,
                fcl_ALL_Sorrow_morphtarget516,
                fcl_ALL_Surprised_morphtarget517,
                fcl_BRW_Angry_morphtarget518,
                fcl_BRW_Fun_morphtarget519,
                fcl_BRW_Joy_morphtarget520,
                fcl_BRW_Sorrow_morphtarget521,
                fcl_BRW_Surprised_morphtarget522,
                fcl_EYE_Natural_morphtarget523,
                fcl_EYE_Angry_morphtarget524,
                fcl_EYE_Close_morphtarget525,
                fcl_EYE_Close_R_morphtarget526,
                fcl_EYE_Close_L_morphtarget527,
                fcl_EYE_Fun_morphtarget528,
                fcl_EYE_Joy_morphtarget529,
                fcl_EYE_Joy_R_morphtarget530,
                fcl_EYE_Joy_L_morphtarget531,
                fcl_EYE_Sorrow_morphtarget532,
                fcl_EYE_Surprised_morphtarget533,
                fcl_EYE_Spread_morphtarget534,
                fcl_EYE_Iris_Hide_morphtarget535,
                fcl_EYE_Highlight_Hide_morphtarget536,
                fcl_MTH_Close_morphtarget537,
                fcl_MTH_Up_morphtarget538,
                fcl_MTH_Down_morphtarget539,
                fcl_MTH_Angry_morphtarget540,
                fcl_MTH_Small_morphtarget541,
                fcl_MTH_Large_morphtarget542,
                fcl_MTH_Neutral_morphtarget543,
                fcl_MTH_Fun_morphtarget544,
                fcl_MTH_Joy_morphtarget545,
                fcl_MTH_Sorrow_morphtarget546,
                fcl_MTH_Surprised_morphtarget547,
                fcl_MTH_SkinFung_morphtarget548,
                fcl_MTH_SkinFung_R_morphtarget549,
                fcl_MTH_SkinFung_L_morphtarget550,
                fcl_MTH_A_morphtarget551,
                fcl_MTH_I_morphtarget552,
                fcl_MTH_U_morphtarget553,
                fcl_MTH_E_morphtarget554,
                fcl_MTH_O_morphtarget555,
                fcl_HA_Hide_morphtarget556,
                fcl_HA_Fung1_morphtarget557,
                fcl_HA_Fung1_Low_morphtarget558,
                fcl_HA_Fung1_Up_morphtarget559,
                fcl_HA_Fung2_morphtarget560,
                fcl_HA_Fung2_Low_morphtarget561,
                fcl_HA_Fung2_Up_morphtarget562,
                fcl_HA_Fung3_morphtarget563,
                fcl_HA_Fung3_Up_morphtarget564,
                fcl_HA_Fung3_Low_morphtarget565,
                fcl_HA_Short_morphtarget566,
                fcl_HA_Short_Up_morphtarget567,
                fcl_HA_Short_Low_morphtarget568,
                fcl_ALL_Neutral_morphtarget569,
                fcl_ALL_Angry_morphtarget570,
                fcl_ALL_Fun_morphtarget571,
                fcl_ALL_Joy_morphtarget572,
                fcl_ALL_Sorrow_morphtarget573,
                fcl_ALL_Surprised_morphtarget574,
                fcl_BRW_Angry_morphtarget575,
                fcl_BRW_Fun_morphtarget576,
                fcl_BRW_Joy_morphtarget577,
                fcl_BRW_Sorrow_morphtarget578,
                fcl_BRW_Surprised_morphtarget579,
                fcl_EYE_Natural_morphtarget580,
                fcl_EYE_Angry_morphtarget581,
                fcl_EYE_Close_morphtarget582,
                fcl_EYE_Close_R_morphtarget583,
                fcl_EYE_Close_L_morphtarget584,
                fcl_EYE_Fun_morphtarget585,
                fcl_EYE_Joy_morphtarget586,
                fcl_EYE_Joy_R_morphtarget587,
                fcl_EYE_Joy_L_morphtarget588,
                fcl_EYE_Sorrow_morphtarget589,
                fcl_EYE_Surprised_morphtarget590,
                fcl_EYE_Spread_morphtarget591,
                fcl_EYE_Iris_Hide_morphtarget592,
                fcl_EYE_Highlight_Hide_morphtarget593,
                fcl_MTH_Close_morphtarget594,
                fcl_MTH_Up_morphtarget595,
                fcl_MTH_Down_morphtarget596,
                fcl_MTH_Angry_morphtarget597,
                fcl_MTH_Small_morphtarget598,
                fcl_MTH_Large_morphtarget599,
                fcl_MTH_Neutral_morphtarget600,
                fcl_MTH_Fun_morphtarget601,
                fcl_MTH_Joy_morphtarget602,
                fcl_MTH_Sorrow_morphtarget603,
                fcl_MTH_Surprised_morphtarget604,
                fcl_MTH_SkinFung_morphtarget605,
                fcl_MTH_SkinFung_R_morphtarget606,
                fcl_MTH_SkinFung_L_morphtarget607,
                fcl_MTH_A_morphtarget608,
                fcl_MTH_I_morphtarget609,
                fcl_MTH_U_morphtarget610,
                fcl_MTH_E_morphtarget611,
                fcl_MTH_O_morphtarget612,
                fcl_HA_Hide_morphtarget613,
                fcl_HA_Fung1_morphtarget614,
                fcl_HA_Fung1_Low_morphtarget615,
                fcl_HA_Fung1_Up_morphtarget616,
                fcl_HA_Fung2_morphtarget617,
                fcl_HA_Fung2_Low_morphtarget618,
                fcl_HA_Fung2_Up_morphtarget619,
                fcl_HA_Fung3_morphtarget620,
                fcl_HA_Fung3_Up_morphtarget621,
                fcl_HA_Fung3_Low_morphtarget622,
                fcl_HA_Short_morphtarget623,
                fcl_HA_Short_Up_morphtarget624,
                fcl_HA_Short_Low_morphtarget625
            ]
        }
        Model {
            id: body
            objectName: "Body"
            source: "meshes/body_mesh.mesh"
            skin: skin653
            materials: [
                n00_000_00_Body_00_SKIN__Instance__material,
                n00_000_00_HairBack_00_HAIR__Instance__material,
                n00_001_02_Bottoms_01_CLOTH__Instance__material,
                n00_002_01_Tops_01_CLOTH__Instance__material,
                n00_008_01_Shoes_01_CLOTH_01__Instance__material,
                n00_008_01_Shoes_01_CLOTH_02__Instance__material,
                n00_010_01_Onepiece_00_CLOTH__Instance__material
            ]
        }
        Model {
            id: hair
            objectName: "Hair"
            source: "meshes/hair001__merged__mesh.mesh"
            skin: skin663
            materials: [
                n00_000_Hair_00_HAIR__Instance__material
            ]
        }
    }

    // Animations:
}
