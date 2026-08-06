# Road Video Tracker

A QGIS 3 plugin for playing road survey videos synchronized with GPS (GPX) tracks on the map in real-time.

![QGIS](https://img.shields.io/badge/QGIS-3.2%2B-green) ![License](https://img.shields.io/badge/license-MIT-blue)

## Features

- **Video + GPS Sync** — play a video while the vehicle position is shown live on the QGIS map
- **mpv player** — high-performance playback via mpv (JSON IPC); auto-downloaded on first use on Windows, or detected from PATH
- **Qt Multimedia fallback** — automatic fallback if mpv is unavailable
- **Real-time GPS info** — coordinates, heading, speed, and elevation in the dock panel
- **Geodesic interpolation** — sub-second positioning via geographiclib (WGS84)
- **Free Mode** — toggle to disable map auto-pan
- **Navigate Mode** — click the map to seek the video to the nearest GPS point
- **Mini Map** — floating, frameless, always-on-top mini map window
- **Embedded Map** — mini map panel inside the player window (hidden by default)
- **Keyboard shortcuts** — full playback and frame-step control
- **Custom icons** — SVG/PNG icons for all controls

## Requirements

- QGIS 3.2 or higher
- Windows (recommended) — mpv is downloaded automatically on first playback (~30 MB) and cached in the QGIS profile folder
- On other platforms mpv must be installed separately, otherwise the Qt Multimedia fallback is used

## Installation

1. In QGIS open `Plugins` > `Manage and Install Plugins...`
2. Search for **Road Video Tracker**
3. Click **Install Plugin**

### Manual install

1. Copy the `road_video_tracker` folder to:
   ```
   %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\
   ```
2. Restart QGIS and enable the plugin in the Plugin Manager.

## Usage

1. Click the **Road Video Tracker** toolbar icon (or the `Plugins` menu).
2. Click **Select Video & GPX**, choose a video (`.mp4`, `.avi`, `.ogv`, `.mkv`) and a GPX track (`.gpx`).
3. If **Autoplay** is checked the player starts automatically; otherwise click **Start**.

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Space` | Play / Pause |
| `M` | Mute / Unmute |
| `←` / `→` | Skip ±1 second |
| `↓` / `↑` | Step ±15 frames |
| `F` | Toggle Free Mode (map auto-pan) |
| `N` | Toggle Navigate mode (click map to seek) |

## Documentation

See [Documentation.md](Documentation.md) for full details, architecture, and development notes.

## License

[MIT](LICENSE)

## Credits

- **C.R Rhamdani** — Plugin author
- **A. Yusrizah S** — Designer
- **Okta** — Support
- **Syaeful** — Technical Advisor
- **geographiclib** — Geodesic calculations (MIT)
- **mpv** — Video player (external dependency, downloaded on demand)
