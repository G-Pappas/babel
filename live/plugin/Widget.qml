import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Bar icon for the Babel live theme. Shown only while Babel is the active
// theme; the popup changes the same settings as `babel-theme` and the
// Style > Babel menu, by running that command.
Panel {
  id: root
  moduleName: "babel.live"
  ipcTarget: "babel.live"

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property string icon: ""
  readonly property string cli: Quickshell.env("HOME") + "/.config/omarchy/themes/babel/live/babel-theme"

  property bool themeActive: false
  property var st: ({ cycle: "", sky: "", skyLoop: "", background: "live", weather: "live", weatherNow: "",
                      wonders: [], disasters: [], monitors: [] })

  readonly property string statusLine: {
    var m = root.st.monitors || []
    if (!m.length) return root.st.running ? "Starting…" : "Not running"
    var parts = []
    for (var i = 0; i < m.length; i++) {
      var x = m[i]
      var what = x.phase === "build" ? Math.round(100 * x.placed / Math.max(1, x.total)) + "%"
        : x.phase === "admire" ? "finished"
        : x.phase === "disaster" ? "under attack!"
        : x.phase === "recover" ? "clearing rubble" : x.phase
      parts.push(x.label + " · " + what)
    }
    return parts.join("   ")
  }

  function run(args) {
    Quickshell.execDetached([root.cli].concat(args))
    refreshSoon.restart()
  }

  function refresh() {
    if (!statusProc.running) statusProc.running = true
  }

  visible: themeActive
  implicitWidth: themeActive ? button.implicitWidth : 0
  implicitHeight: button.implicitHeight
  onOpenedChanged: if (opened) { refresh(); Qt.callLater(function() { keys.forceActiveFocus() }) }

  FileView {
    path: Quickshell.env("HOME") + "/.local/state/omarchy/current/theme.name"
    watchChanges: true
    onFileChanged: reload()
    onLoaded: root.themeActive = text().trim() === "babel"
  }

  Process {
    id: statusProc
    command: [root.cli, "status", "--json"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try { root.st = JSON.parse(text) } catch (e) {}
      }
    }
  }

  Timer {
    id: refreshSoon
    interval: 350
    onTriggered: root.refresh()
  }

  Timer {
    interval: 2500
    repeat: true
    running: root.opened
    onTriggered: root.refresh()
  }

  // keep the tooltip's "current wonder" line fresh without opening the popup
  Timer {
    interval: 30000
    repeat: true
    running: root.themeActive && !root.opened
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.icon
    slotSize: Style.bar.statusSlot
    tooltipText: "Babel — " + root.statusLine
    onTooltipHoveredChanged: if (tooltipHovered) root.refresh()
    onPressed: function(code) { if (code === Qt.LeftButton) root.toggle() }
  }

  component Section: PanelSectionHeader {
    width: parent ? parent.width : 0
    foreground: root.foreground
    fontFamily: root.fontFamily
  }

  component Chip: Button {
    bordered: true
    foreground: root.foreground
    fontFamily: root.fontFamily
    fontSize: Style.font.caption
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keys
    contentWidth: panel.fittedContentWidth(Style.space(460))
    contentHeight: panel.fittedContentHeight(content.implicitHeight, Style.space(700))

    PanelKeyCatcher {
      id: keys
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Flickable {
        anchors.fill: parent
        contentWidth: width
        contentHeight: content.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Column {
          id: content
          width: parent.width
          spacing: Style.space(8)

          PanelHero {
            iconComponent: Component {
              Text {
                text: root.icon
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.display
              }
            }
            title: "Babel"
            meta: root.statusLine
            foreground: root.foreground
            fontFamily: root.fontFamily
          }

          PanelSeparator { foreground: root.foreground }

          Section { text: "Loop length" }
          ButtonGroup {
            options: ["1m", "10m", "1h", "6h", "1d", "1w"]
            value: root.st.cycle
            foreground: root.foreground
            fontFamily: root.fontFamily
            fontSize: Style.font.caption
            onChanged: function(v) { root.run(["cycle", v]) }
          }

          Section { text: "Sky" }
          ButtonGroup {
            options: [
              { value: "clock", label: "Clock" }, { value: "loop", label: "Loop" },
              { value: "dawn", label: "Dawn" }, { value: "day", label: "Day" },
              { value: "sunset", label: "Sunset" }, { value: "night", label: "Night" }
            ]
            value: root.st.sky
            foreground: root.foreground
            fontFamily: root.fontFamily
            fontSize: Style.font.caption
            onChanged: function(v) { root.run(["sky", v]) }
          }
          Row {
            visible: root.st.sky === "loop"
            spacing: Style.space(8)
            Text {
              anchors.verticalCenter: parent.verticalCenter
              text: "A whole day every"
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
            }
            ButtonGroup {
              options: ["2m", "10m", "1h", "6h"]
              value: root.st.skyLoop
              foreground: root.foreground
              fontFamily: root.fontFamily
              fontSize: Style.font.caption
              onChanged: function(v) { root.run(["sky-loop", v]) }
            }
          }

          Section { text: "Weather" + (root.st.weather === "live" && root.st.weatherNow ? " · " + root.st.weatherNow : "") }
          ButtonGroup {
            options: [
              { value: "live", label: "Live" }, { value: "off", label: "Off" }, { value: "rain", label: "Rain" },
              { value: "snow", label: "Snow" }, { value: "storm", label: "Storm" }, { value: "fog", label: "Fog" }
            ]
            value: root.st.weather
            foreground: root.foreground
            fontFamily: root.fontFamily
            fontSize: Style.font.caption
            onChanged: function(v) { root.run(["weather", v]) }
          }

          Section { text: "Background" }
          Row {
            spacing: Style.space(6)
            Chip {
              text: "Live landscape"
              selected: root.st.background === "live"
              onClicked: root.run(["background", "live"])
            }
            Chip {
              text: root.st.background === "live" ? "Picture…"
                : "Picture: " + String(root.st.background).replace(/^.*\//, "")
              selected: root.st.background !== "live"
              onClicked: { root.close(); root.run(["background", "pick"]) }
            }
          }

          Section { text: "Wonders" }
          Flow {
            width: parent.width
            spacing: Style.space(6)
            Repeater {
              model: root.st.wonders
              delegate: Chip {
                required property var modelData
                text: modelData.label
                selected: modelData.on
                onClicked: root.run(["toggle", "wonder", modelData.id])
              }
            }
          }

          Section { text: "Disasters" }
          Flow {
            width: parent.width
            spacing: Style.space(6)
            Repeater {
              model: root.st.disasters
              delegate: Chip {
                required property var modelData
                text: modelData.label
                selected: modelData.on
                onClicked: root.run(["toggle", "disaster", modelData.id])
              }
            }
          }

          PanelSeparator { foreground: root.foreground }

          Row {
            spacing: Style.space(6)
            Chip {
              iconText: ""
              text: "Disaster now"
              onClicked: root.run(["disaster-now"])
            }
            Chip {
              iconText: ""
              text: "Reset"
              tooltipText: "Switch every wonder and disaster back on"
              onClicked: root.run(["reset"])
            }
            Chip {
              iconText: ""
              text: "Edit settings file"
              onClicked: { root.close(); root.run(["edit"]) }
            }
          }
        }
      }
    }
  }
}
