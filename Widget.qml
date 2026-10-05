import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Bar icon for the Babel live theme. Shown while Babel is the active theme
// (and, right after installing from the plugin marketplace, until it has been
// turned on). The popup changes the same settings as `babel-theme` and the
// Style > Babel menu, by running that command from this checkout.
Panel {
  id: root
  moduleName: "gpappas.babel"
  ipcTarget: "gpappas.babel"

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property string icon: ""
  readonly property string cli: decodeURIComponent(Qt.resolvedUrl("live/babel-theme").toString().replace(/^file:\/\//, ""))

  property bool themeActive: false
  property var st: ({ setUp: true, cycle: "", sky: "", skyLoop: "", background: "live", weather: "live", weatherNow: "",
                      wonders: [], disasters: [], monitors: [], screens: [], monitorMode: "span", wonderMonitor: "" })

  // With several monitors: the one the wonder goes up on (the others are the
  // crew's yard), the biggest, or a wonder on each.
  readonly property var wonderOptions: {
    var o = [{ value: "auto", label: "Biggest", tooltip: "The biggest monitor" }]
    var s = root.st.screens || []
    for (var i = 0; i < s.length; i++)
      o.push({ value: s[i].name, label: s[i].name, tooltip: s[i].size })
    o.push({ value: "separate", label: "Each monitor", tooltip: "A wonder of its own on every monitor" })
    return o
  }

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
    Quickshell.execDetached(["python3", root.cli].concat(args))
    refreshSoon.restart()
  }

  function refresh() {
    if (!statusProc.running) statusProc.running = true
  }

  // fresh from the marketplace, Babel isn't set up yet: show the icon so it can be turned on
  readonly property bool shown: themeActive || !root.st.setUp
  visible: shown
  implicitWidth: shown ? button.implicitWidth : 0
  Component.onCompleted: refresh()
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
    // bounded in time and size, so a stuck or runaway status can't hold the shell
    command: ["sh", "-c", "timeout 5 python3 \"$1\" status --json | head -c 65536", "babel-status", root.cli]
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

          Column {
            visible: !root.themeActive
            width: parent.width
            spacing: Style.space(8)
            Text {
              width: parent.width
              wrapMode: Text.Wrap
              text: "Babel is a live wallpaper theme. Turning it on adds the bar icon and a Style > Babel menu, starts the wallpaper whenever Babel is your theme, and switches to it now."
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
            }
            Chip {
              text: "Turn on Babel"
              onClicked: { root.close(); root.run(["install"]) }
            }
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

          Section {
            visible: (root.st.screens || []).length > 1
            text: "Wonder on"
          }
          ButtonGroup {
            visible: (root.st.screens || []).length > 1
            options: root.wonderOptions
            // a chosen monitor that isn't plugged in: the wallpaper falls back to the biggest
            value: root.st.monitorMode === "separate" ? "separate"
              : (root.st.screens || []).some(function(m) { return m.name === root.st.wonderMonitor })
                ? root.st.wonderMonitor : "auto"
            foreground: root.foreground
            fontFamily: root.fontFamily
            fontSize: Style.font.caption
            onChanged: function(v) { root.run(v === "separate" ? ["monitors", "separate"] : ["wonder-monitor", v]) }
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
