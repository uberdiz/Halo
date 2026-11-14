// SAINT Visualizer widget settings. Size and position: drag the widget's edges like any desktop widget.
import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    property string cfg_Source
    property string cfg_BarStyle
    property alias cfg_ShowLogo: logoBox.checked
    property alias cfg_Glow: glowSlider.value
    property alias cfg_Accent: accentField.text
    property alias cfg_UseThemeColor: themeBox.checked
    property alias cfg_Sensitivity: sensSlider.value
    property alias cfg_Fps: fpsBox.value

    readonly property var sources: [["saint", i18n("SAINT's voice")], ["desktop", i18n("Music and sound playing")],
                                    ["mic", i18n("Microphone")], ["breathing", i18n("A slow breath")]]
    readonly property var styles: [["bars", i18n("Bars under the logo")], ["ring", i18n("A ring around the logo")]]

    Kirigami.FormLayout {
        QQC2.ComboBox {
            Kirigami.FormData.label: i18n("Moves with:")
            model: sources.map(function (s) { return s[1]; })
            currentIndex: Math.max(0, sources.findIndex(function (s) { return s[0] === cfg_Source; }))
            onActivated: function (i) { cfg_Source = sources[i][0]; }
        }
        QQC2.ComboBox {
            Kirigami.FormData.label: i18n("Style:")
            model: styles.map(function (s) { return s[1]; })
            currentIndex: Math.max(0, styles.findIndex(function (s) { return s[0] === cfg_BarStyle; }))
            onActivated: function (i) { cfg_BarStyle = styles[i][0]; }
        }
        QQC2.CheckBox {
            id: logoBox
            text: i18n("Show the SAINT logo")
        }
        QQC2.Slider {
            id: glowSlider
            Kirigami.FormData.label: i18n("Glow:")
            from: 0; to: 1; stepSize: 0.05
        }
        QQC2.TextField {
            id: accentField
            Kirigami.FormData.label: i18n("Colour:")
            placeholderText: "#feaa34"
            validator: RegularExpressionValidator { regularExpression: /#[0-9a-fA-F]{6}/ }
        }
        QQC2.CheckBox {
            id: themeBox
            text: i18n("Use the desktop accent colour instead")
        }
        QQC2.Slider {
            id: sensSlider
            Kirigami.FormData.label: i18n("Sensitivity:")
            from: 0.2; to: 3; stepSize: 0.1
        }
        QQC2.SpinBox {
            id: fpsBox
            Kirigami.FormData.label: i18n("Frames a second:")
            from: 5; to: 60
        }
    }
}
