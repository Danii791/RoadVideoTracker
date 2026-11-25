# Road Video Tracker

A QGIS plugin for viewing road survey videos synchronized with GPS tracks on the map in real-time.

| | |
|---|---|
| **Name** | Road Video Tracker |
| **Author** | C.R Rhamdani |
| **Version** | 1.4.2 |
| **Release** | November 2026 |
| **License** | MIT |
| **QGIS** | 3.14+ |

## Features

- **Video + GPS Sync** — Play video while the vehicle position is shown on the QGIS map in real-time
- **mpv Player** — High-performance video playback via mpv with JSON IPC control (auto-downloads the latest `mpv.exe` on first use on Windows, or auto-detects `mpv` in the system PATH). The download URL is resolved dynamically from the mpv-winbuild-cmake releases API, verified with SHA-256, and retried once on a 404
- **Renderer Indicator & Repair** — The player title shows `[mpv]` or `[Qt]`; download/startup errors are reported with the original message and manual download link, and the Performance Settings dialog has a **Repair mpv** button to re-download a broken cache
- **Qt Multimedia Fallback** — Automatic fallback to Qt Multimedia if mpv is not available (the fallback is now visible in the UI and tracking)
- **Real-time GPS Info** — Displays coordinates, heading, speed, and elevation in the dock panel
- **Follow Road Mode** — On the mini map, auto-rotate and auto-center to the road heading (toggle button at the bottom-right of the mini map)
- **Navigate Mode** — Click anywhere on the map to seek the video to the nearest GPS point
- **Autoplay Option** — Checkbox to auto-start playback after selecting video and GPX files
- **Keyboard Shortcuts** — Full keyboard control for playback, frame stepping, navigation, and embedded map position
- **Mini Map Window** — Independent floating mini map (frameless, semi-transparent, always on top, resizable from all 4 corners); stays on top and follows the player window minimize/restore
- **Embedded Map Panel** — Mini map panel inside the player window, not active by default (activated via the `map` icon toggle); move it left/right with `Ctrl+←` / `Ctrl+→`, width adjustable by dragging the divider
- **Performance Settings** — GPU decode, video-only mode, and performance/low-spec presets (gear icon)
- **Custom Icons** — All player controls use custom SVG/PNG icons
- **Silent Tracking** — Anonymous usage statistics sent to Google Sheets on plugin open/close (fails silently if offline)

## Installation

### Requirements

- QGIS 3.14 or higher
- Windows (for the mpv auto-download path; on other platforms mpv must be installed separately or the Qt Multimedia fallback is used)
- No manual installation needed — on first playback the plugin resolves the latest mpv build from the GitHub releases API, verifies its SHA-256 digest, and caches it in the QGIS profile folder (Windows, ~30 MB). If mpv is already installed and available in PATH, it is used directly. If the download fails, the original error is shown with a manual download link and playback falls back to the built-in Qt Multimedia engine (use **Repair mpv** in Performance Settings to retry).

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
| 🧭 Navigate | Click map to seek video | `A` |
| 📍 Recenter | Recenter map on the GPS position | `F` |
| ↔ Move map | Move embedded map left/right | `Ctrl+←` / `Ctrl+→` |

### Map Auto-Pan

- During playback the map auto-pans to keep the GPS position marker centered (re-centering at most every 2.5 s, only when the marker nears the map edge).
- Press `F` (or the 📍 button) to recenter immediately.
- While **Navigate mode** is active, auto-pan is disabled so you can pan/zoom freely.

### Navigate Mode

1. Click the Navigate button (or press `A`)
2. Click anywhere on the map
3. The video seeks to the nearest GPS point on the track

### Bottom Bar

- **Mute button** — Toggle audio
- **Time display** — Current time / total GPS duration
- **Mini Map** — Toggle the floating mini map window (`find-location` icon)
- **Embedded Map** — Toggle the map panel inside the player window (`map` icon, not active by default)
- **Navigate** — Toggle map click-to-seek
- **Close** — Close the player

### Mini Map & Embedded Map

- The **Mini Map** is a separate frameless window: semi-transparent (75%), always on top of the player, draggable via its top strip, resizable from all 4 corner grips, with independent pan/zoom. It stays on top and follows the player window minimize/restore.
- **Follow Road** — the button at the bottom-right of the mini map toggles auto-rotate and auto-center to the road heading (navigation icon when ON, north-arrow icon when OFF).
- The **Embedded Map** is a panel inside the player window, **not shown by default** — click the `map` icon toggle to activate it; drag the divider to adjust its width (min 150px); move it left/right with `Ctrl+←` / `Ctrl+→`. Its toggle button is always visible in the bottom bar.
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
│   ├── north-arrow.svg
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
  Update marker + auto-pan map (unless Navigate mode is active)
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
| `EmbeddedMap` | `minimap.py` | Map panel embedded in the player window (default 160px) |
| `SkipTrackTool` | `map_tool.py` | Map click-to-seek |
| `PositionMarker` | `position_marker.py` | GPS arrow marker on canvas |
| `send_tracking` / `_processing_dialog` | `tracking.py` | Usage tracking + "Preparing..." popup |

### GPS Interpolation

The plugin uses **geographiclib** (WGS84 geodesic) for sub-second GPS interpolation between GPX track points. This provides accurate positioning even when GPX timestamps don't align perfectly with video frames.

### mpv Integration

mpv is launched as a child process with the video embedded in the QGIS window via `--wid` (Windows handle). Communication uses mpv's JSON IPC protocol for seeking, play/pause, mute, and property queries.

On Windows, when mpv is not found in the plugin folder or in the system PATH, the plugin queries the mpv-winbuild-cmake `releases/latest` API, downloads the newest `mpv-x86_64-*.7z` asset, verifies its SHA-256 digest (with a pinned URL as offline fallback and one retry on 404), and caches the extracted `mpv.exe` in the QGIS settings folder (`mpv/`). The cached executable is validated with `mpv.exe --version` before use. No mpv binary is bundled in the plugin package. Failures are surfaced in the player and tracking data instead of silently falling back; **Repair mpv** in Performance Settings clears the cache and downloads again.

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

- Python 3, PyQt (Qt5 & Qt6, via `qgis.PyQt`)
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
