# Road Video Tracker

A QGIS plugin for viewing road survey videos synchronized with GPS tracks on the map in real-time.

| | |
|---|---|
| **Name** | Road Video Tracker |
| **Author** | C.R Rhamdani |
| **Version** | 1.5 |
| **Release** | July 2026 |
| **License** | MIT |
| **QGIS** | 3.0+ |

## Features

- **Video + GPS Sync** — Play video while the vehicle position is shown on the QGIS map in real-time
- **mpv Player** — High-performance video playback via mpv with JSON IPC control (auto-downloads `mpv.exe` on first use on Windows, or auto-detects `mpv` in the system PATH)
- **Qt Multimedia Fallback** — Automatic fallback to Qt Multimedia if mpv is not available
- **Real-time GPS Info** — Displays coordinates, heading, speed, and elevation in the dock panel
- **Free Mode** — Toggle to disable auto-panning of the map (position marker still updates)
- **Navigate Mode** — Click anywhere on the map to seek the video to the nearest GPS point
- **Autoplay Option** — Checkbox to auto-start playback after selecting video and GPX files
- **Keyboard Shortcuts** — Full keyboard control for playback, frame stepping, and navigation
- **Mini Map Window** — Independent floating mini map (frameless, semi-transparent, always on top, resizable from all 4 corners)
- **Embedded Map Panel** — Mini map embedded on the right side of the player window, not active by default (activated via the `map` icon toggle), width adjustable by dragging the divider
- **Custom Icons** — All player controls use custom SVG/PNG icons
- **Silent Tracking** — Anonymous usage statistics sent to Google Sheets on plugin open/close (fails silently if offline)

## Installation

### Requirements

- QGIS 3.0 or higher
- Windows (for the mpv auto-download path; on other platforms mpv must be installed separately or the Qt Multimedia fallback is used)
- No manual installation needed — on first playback the plugin downloads the mpv player automatically (Windows, ~30 MB) and caches it in the QGIS profile folder. If mpv is already installed and available in PATH, it is used directly. If the download fails, playback falls back to the built-in Qt Multimedia engine.

### Install from QGIS

1. Open QGIS
2. Go to `Plugins` > `Manage and Install Plugins...`
3. Search for "Road Video Tracker"
4. Click `Install Plugin`

### Manual Install

1. Copy the `road_video_tracker` folder to:
   ```
   %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\
   ```
2. Restart QGIS
3. Enable the plugin in `Plugins` > `Manage and Install Plugins...`

## Usage

### Getting Started

1. Click the **Road Video Tracker** icon in the toolbar (or `Plugins` menu)
2. The dock panel appears on the left side of QGIS

### Select Video & GPX

1. Click **"Select Video & GPX"** button
2. Choose a video file (`.mp4`, `.avi`, `.ogv`, `.mkv`)
3. Choose a GPX file (`.gpx`)
4. If **Autoplay** is checked (default), the player starts automatically
5. If Autoplay is unchecked, click **Start** to begin

### Player Controls

| Button | Action | Keyboard |
|--------|--------|----------|
| ▶/⏸ | Play / Pause | `Space` |
| 🔇/🔊 | Mute / Unmute | `M` |
| ⏪ | Skip backward 1s | `←` |
| ⏩ | Skip forward 1s | `→` |
| ◀ Frame | Previous frame (15 frames) | `↓` |
| ▶ Frame | Next frame (15 frames) | `↑` |
| 📍 Free Mode | Toggle map auto-pan | `F` |
| 🧭 Navigate | Click map to seek video | `N` |

### Free Mode

- **OFF (default):** Map auto-pans to follow the GPS position marker
- **ON:** Map stays still; the position marker still moves but you can pan/zoom freely

### Navigate Mode

1. Click the Navigate button (or press `N`)
2. Click anywhere on the map
3. The video seeks to the nearest GPS point on the track

### Bottom Bar

- **Mute button** — Toggle audio
- **Time display** — Current time / total GPS duration
- **Mini Map** — Toggle the floating mini map window (`find-location` icon; button hidden by default, press `Ctrl+Shift+H` to reveal)
- **Embedded Map** — Toggle the map panel inside the player window (`map` icon, not active by default)
- **Free Mode** — Toggle auto-pan
- **Navigate** — Toggle map click-to-seek
- **Close** — Close the player

### Mini Map & Embedded Map

- The **Mini Map** is a separate frameless window: semi-transparent (75%), always on top of the player, draggable via its top strip, resizable from all 4 corner grips, with independent pan/zoom.
- The **Embedded Map** is a panel docked to the right side of the player window, **not shown by default** — click the `map` icon toggle to activate it; drag the divider to adjust its width (min 150px). Its toggle button is always visible in the bottom bar.
- The **Mini Map** button is hidden by default — press `Ctrl+Shift+H` (hidden dev shortcut) to reveal/hide the Mini Map button.
- Both share the same map engine (`MiniMapBase`) and sync GPS position, layer visibility, and extent with the main canvas.
- **Only one map can be visible at a time** — turning one on automatically hides the other (to keep performance light).
- Click-to-seek works on both maps while **Navigate mode** is active.

## Project Structure

```
road_video_tracker/
├── __init__.py              # Plugin entry point (classFactory)
├── video_tracker.py         # Plugin class, toolbar/menu registration
├── tracker_dock.py          # Dock panel (file selection, Start/Quit)
├── player_window.py         # Main player window (video + controls)
├── minimap.py               # MiniMapBase (shared logic), MiniMapWindow (floating), EmbeddedMap (in-player panel)
├── mpv_control.py           # mpv process control via JSON IPC
├── map_tool.py              # Click-to-seek map tool (SkipTrackTool)
├── position_marker.py       # GPS position marker on map canvas
├── tracking.py              # Silent usage tracking + processing dialogs
├── resources.py             # Qt resource file
├── main_icon.svg            # Plugin icon (SVG)
├── icon.png                 # Plugin icon (PNG fallback)
├── icons/                   # Player control icons (SVG + PNG)
│   ├── play.svg / .png
│   ├── pause.svg / .png
│   ├── forward.svg / .png
│   ├── backward.svg / .png
│   ├── next_frame.svg / .png
│   ├── prev_frame.svg / .png
│   ├── mute.svg / .png
│   ├── unmute.svg / .png
│   ├── navigate.png
│   ├── navigation.png
│   ├── location.png
│   ├── find-location.png
│   ├── map.png
│   ├── compass.png
│   ├── start.svg / .png
│   └── quit.svg / .png
├── geographiclib/           # Geodesic calculations (WGS84)
├── metadata.txt             # QGIS plugin metadata
└── Documentation.md          # This file
```

## Architecture

### Data Flow

```
Select Video + GPX
       │
       ▼
  Parse GPX (lat/lon/ele/time)
       │
       ▼
  Create GPS layer (LineString on map)
       │
       ▼
  Create PositionMarker on canvas
       │
       ▼
  Launch mpv (embed in QVideoWidget via --wid)
       │
       ▼
  Poll position every 100ms
       │
       ▼
  Interpolate GPS (Geodesic WGS84)
       │
       ▼
  Update marker + recenter map (if Free Mode OFF)
```

### Key Classes

| Class | File | Responsibility |
|-------|------|----------------|
| `VideoTracker` | `video_tracker.py` | QGIS plugin entry, toolbar/menu |
| `TrackerDock` | `tracker_dock.py` | Dock panel UI, file selection, start/quit |
| `PlayerWindow` | `player_window.py` | Player UI, video playback, GPS sync |
| `MpvController` | `mpv_control.py` | mpv process management, JSON IPC |
| `MiniMapBase` | `minimap.py` | Shared mini map engine (canvas, GPS transform, layer sync, seek) |
| `MiniMapWindow` | `minimap.py` | Floating mini map window (frameless, always on top, resizable) |
| `EmbeddedMap` | `minimap.py` | Map panel embedded in the player window (fixed 240px) |
| `SkipTrackTool` | `map_tool.py` | Map click-to-seek |
| `PositionMarker` | `position_marker.py` | GPS arrow marker on canvas |
| `send_tracking` / `_processing_dialog` | `tracking.py` | Usage tracking + "Preparing..." popup |

### GPS Interpolation

The plugin uses **geographiclib** (WGS84 geodesic) for sub-second GPS interpolation between GPX track points. This provides accurate positioning even when GPX timestamps don't align perfectly with video frames.

### mpv Integration

mpv is launched as a child process with the video embedded in the QGIS window via `--wid` (Windows handle). Communication uses mpv's JSON IPC protocol for seeking, play/pause, mute, and property queries.

On Windows, when mpv is not found in the plugin folder or in the system PATH, it is downloaded automatically on first playback (from the mpv-winbuild-cmake project releases) and cached in the QGIS settings folder (`mpv/`). No mpv binary is bundled in the plugin package.

## Development

### Adding a New Feature

1. **UI changes:** Edit `tracker_dock.py` (dock panel) or `player_window.py` (player)
2. **Icons:** Add SVG/PNG to `icons/` folder, use `_icon('name')` helper
3. **Keyboard shortcuts:** Add to `keyPressEvent` in `player_window.py`
4. **Map features:** Edit `map_tool.py`, `position_marker.py`, or `minimap.py` (mini map / embedded map)

### Testing

1. Place plugin in QGIS plugins folder
2. Restart QGIS
3. Enable plugin in Plugin Manager
4. Test with a video + GPX pair

### Code Conventions

- Python 3, PyQt5
- No comments unless requested
- Icons loaded via `_icon()` helper (tries `.svg` first, falls back to `.png`)
- Player controls use `QToolButton` with 20x20 icon size
- mpv communication via `MpvController.req()` with callbacks
- GPS interpolation via `Geodesic.WGS84.Inverse()` / `Direct()`
- Mini maps share logic via `MiniMapBase`; `MiniMapWindow` and `EmbeddedMap` are mutually exclusive (toggle buttons)
- Tracking via `send_tracking(action)` — silent POST to Google Apps Script (fails silently)

## License

MIT License

## Credits

- **C.R Rhamdani** — Plugin author
- **A. Yusrizah S** — Designer
- **Okta** — Support
- **Syaeful** — Technical Advisor
- **geographiclib** — Geodesic calculations (bundled, MIT License)
- **mpv** — Video player (external dependency)
