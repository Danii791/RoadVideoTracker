# -*- coding: utf-8 -*-
import os
import sys
import time
from defusedxml.minidom import parse

from qgis.PyQt import QtWidgets, QtCore
from qgis.PyQt.QtCore import Qt, QUrl, QTimer, QSize
from qgis.PyQt.QtGui import QIcon
try:
    from qgis.PyQt.QtMultimedia import QMediaPlayer, QMediaContent
    from qgis.PyQt.QtMultimediaWidgets import QVideoWidget
except ImportError:
    import importlib
    _qt_mm = importlib.import_module('PyQt5.QtMultimedia')
    _qt_mmw = importlib.import_module('PyQt5.QtMultimediaWidgets')
    QMediaPlayer = _qt_mm.QMediaPlayer
    QMediaContent = _qt_mm.QMediaContent
    QVideoWidget = _qt_mmw.QVideoWidget

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry,
    QgsPoint, QgsPointXY, QgsCoordinateReferenceSystem,
    QgsCoordinateTransform, QgsRectangle
)

from .map_tool import SkipTrackTool
from .position_marker import PositionMarker
from .mpv_control import (
    MpvController, find_mpv, mpv_cache_dir, download_mpv_async, MPV_URL)
from .minimap import MiniMapWindow, EmbeddedMap

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..'))
from geographiclib.geodesic import Geodesic

from . import resources

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
ICON_SIZE = QSize(20, 20)


def _icon(name):
    for ext in ('.svg', '.png'):
        p = os.path.join(ICON_DIR, name + ext)
        if os.path.exists(p):
            return QIcon(p)
    return QIcon()


class _MpvDownloadSignals(QtCore.QObject):
    progress = QtCore.pyqtSignal(str)
    done = QtCore.pyqtSignal(bool, str)


class PlayerWindow(QtWidgets.QWidget):

    def __init__(self, videofile, gpxfile, iface, dock):
        super().__init__()
        self.iface = iface
        self.dock = dock
        self.videofile = videofile
        self.gpxfile = gpxfile
        self.enable_map_tool = False
        self.GPXList = []
        self.polyline = []
        self.gps_layer = None
        self.position_marker = None
        self.skip_tool = None
        self.use_mpv = False
        self.mpv = None
        self.fps = 30.0
        self._frame_busy = False
        self._paused = True
        self._last_recenter = 0.0
        self._last_pt_t = None
        self._eof = False

        self.setWindowTitle("Road Video Tracker - Player")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.resize(600, 410)
        self._video_initialized = False
        self._gps_jumped = False

        self._setup_ui()
        self._parse_gpx()
        self._load_gps_track()

        self.mini_map_win = MiniMapWindow(self)
        self.mini_map_win.closed.connect(self._on_minimap_closed)
        self.mini_map_win.set_gpx_data(self.GPXList)

        self.embed_map.set_gpx_data(self.GPXList)

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 0)
        layout.setSpacing(0)

        self.splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(4)

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(320, 240)
        self.video_widget.setStyleSheet("background-color: black;")
        self.splitter.addWidget(self.video_widget)

        self.embed_map = EmbeddedMap(self)
        self.embed_map.hide()
        self.splitter.addWidget(self.embed_map)

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([352, 240])

        layout.addWidget(self.splitter, 1)

        self.loading_label = QtWidgets.QLabel("Processing...", self)
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet(
            "background-color: rgba(0,0,0,180); color: white; font-size: 16px;")
        self.loading_label.hide()

        self.slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.slider.setFixedHeight(14)
        self.slider.sliderMoved.connect(self._on_slider)
        layout.addWidget(self.slider)

        bar = QtWidgets.QHBoxLayout()
        bar.setContentsMargins(8, 0, 8, 2)
        bar.setSpacing(4)

        self.btn_mute = self._make_btn('unmute', self._toggle_mute)
        bar.addWidget(self.btn_mute)
        self.lbl_time = QtWidgets.QLabel("0:00:00 / 0:00:00")
        self.lbl_time.setFixedHeight(24)
        bar.addWidget(self.lbl_time)

        bar.addStretch()

        self.btn_toggle_minimap = QtWidgets.QToolButton()
        self.btn_toggle_minimap.setIcon(_icon('find-location'))
        self.btn_toggle_minimap.setIconSize(ICON_SIZE)
        self.btn_toggle_minimap.setFixedHeight(24)
        self.btn_toggle_minimap.setCheckable(True)
        self.btn_toggle_minimap.setChecked(False)
        self.btn_toggle_minimap.setToolTip("Mini Map (toggle)")
        self.btn_toggle_minimap.clicked.connect(self._toggle_minimap)
        bar.addWidget(self.btn_toggle_minimap)
        self.btn_toggle_minimap.hide()

        self.btn_toggle_embed = QtWidgets.QToolButton()
        self.btn_toggle_embed.setIcon(_icon('map'))
        self.btn_toggle_embed.setIconSize(ICON_SIZE)
        self.btn_toggle_embed.setFixedHeight(24)
        self.btn_toggle_embed.setCheckable(True)
        self.btn_toggle_embed.setChecked(False)
        self.btn_toggle_embed.setToolTip("Embedded Map (toggle)")
        self.btn_toggle_embed.clicked.connect(self._toggle_embedmap)
        bar.addWidget(self.btn_toggle_embed)

        self.btn_recenter = QtWidgets.QToolButton()
        self.btn_recenter.setIcon(_icon('gps'))
        self.btn_recenter.setIconSize(ICON_SIZE)
        self.btn_recenter.setFixedHeight(24)
        self.btn_recenter.setToolTip("Recenter (F)")
        self.btn_recenter.clicked.connect(self._recenter_once)
        bar.addWidget(self.btn_recenter)

        self.btn_map_tool = QtWidgets.QToolButton()
        self.btn_map_tool.setIcon(_icon('cursor'))
        self.btn_map_tool.setIconSize(ICON_SIZE)
        self.btn_map_tool.setCheckable(True)
        self.btn_map_tool.setFixedHeight(24)
        self.btn_map_tool.setToolTip("Go to Location (A)")
        self.btn_map_tool.clicked.connect(self._toggle_map_tool)
        bar.addWidget(self.btn_map_tool)

        self.btn_close = QtWidgets.QToolButton()
        self.btn_close.setText("Close")
        self.btn_close.setFixedHeight(24)
        self.btn_close.clicked.connect(self.close)
        bar.addWidget(self.btn_close)

        layout.addLayout(bar)

        nav = QtWidgets.QHBoxLayout()
        nav.setContentsMargins(8, 2, 8, 2)
        nav.setSpacing(4)
        nav.addStretch()
        nav.addWidget(self._make_btn('backward', lambda: self._skip(-1)))
        nav.addWidget(self._make_btn('prev_frame', lambda: self._skip_frame(-1)))
        self.btn_play = self._make_btn('pause', self._play_pause)
        self.btn_play.setFixedSize(30, 24)
        nav.addWidget(self.btn_play)
        nav.addWidget(self._make_btn('next_frame', lambda: self._skip_frame(1)))
        nav.addWidget(self._make_btn('forward', lambda: self._skip(1)))
        nav.addStretch()
        layout.addLayout(nav)

        self.qplayer = QMediaPlayer()
        self.qplayer.setVideoOutput(self.video_widget)
        self.qplayer.durationChanged.connect(self._on_duration)
        self.qplayer.positionChanged.connect(self._on_position)
        self.qplayer.setNotifyInterval(100)

    def _make_btn(self, icon_name, callback):
        btn = QtWidgets.QToolButton()
        btn.setIcon(_icon(icon_name))
        btn.setIconSize(ICON_SIZE)
        btn.setFixedHeight(24)
        btn.clicked.connect(callback)
        return btn

    def _loading_geometry(self):
        pos = self.video_widget.mapTo(self, QtCore.QPoint(0, 0))
        return QtCore.QRect(pos, self.video_widget.size())

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus()
        if not self._video_initialized:
            self._video_initialized = True
            QtCore.QCoreApplication.processEvents()
            self.loading_label.setGeometry(self._loading_geometry())
            self.loading_label.raise_()
            self.loading_label.show()
            self.loading_label.repaint()
            QTimer.singleShot(500, self._init_video)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.loading_label.isVisible():
            self.loading_label.setGeometry(self._loading_geometry())

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Space:
            self._play_pause()
        elif key == Qt.Key.Key_M:
            self._toggle_mute()
        elif key == Qt.Key.Key_Left:
            self._skip(-1)
        elif key == Qt.Key.Key_Right:
            self._skip(1)
        elif key == Qt.Key.Key_Down:
            self._skip_frame(-1)
        elif key == Qt.Key.Key_Up:
            self._skip_frame(1)
        elif key == Qt.Key.Key_A:
            self.btn_map_tool.toggle()
            self._toggle_map_tool()
        elif (key == Qt.Key.Key_H
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier
                and event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self._reveal_map_buttons()
        elif key == Qt.Key.Key_F:
            self._recenter_once()
        else:
            super().keyPressEvent(event)

    def _parse_gpx(self):
        gpx = parse(self.gpxfile)
        track = gpx.getElementsByTagName("trkpt")
        prev_time = None

        for node in track:
            attrs = {}
            for token in node.toprettyxml(indent='').split():
                if token.startswith('lat='):
                    attrs['lat'] = float(token.split('"')[1])
                elif token.startswith('lon='):
                    attrs['lon'] = float(token.split('"')[1])
                elif token.startswith('<ele>'):
                    try:
                        attrs['ele'] = float(token[5:-6])
                    except ValueError:
                        attrs['ele'] = 0
                elif token.startswith('<time>'):
                    attrs['time'] = token[6:-7]

            if 'time' in attrs and attrs['time'] != prev_time:
                self.GPXList.append([
                    attrs['lat'], attrs['lon'],
                    attrs.get('ele', 0), attrs['time']
                ])
                prev_time = attrs['time']

        self.total_gps_seconds = len(self.GPXList)

    def _load_gps_track(self):
        self.polyline = [QgsPoint(pt[1], pt[0]) for pt in self.GPXList]

        self.gps_layer = QgsVectorLayer(
            "LineString?crs=epsg:4326",
            os.path.splitext(os.path.basename(self.videofile))[0] + "_GPS",
            "memory")
        pr = self.gps_layer.dataProvider()
        feat = QgsFeature()
        feat.setGeometry(QgsGeometry.fromPolyline(self.polyline))
        pr.addFeatures([feat])
        self.gps_layer.updateExtents()
        QgsProject.instance().addMapLayers([self.gps_layer])

        self.position_marker = PositionMarker(self.iface.mapCanvas())
        self.skip_tool = SkipTrackTool(
            self.iface.mapCanvas(), self.gps_layer, self)

    def _init_video(self):
        if self.video_widget.width() < 10:
            QTimer.singleShot(100, self._init_video)
            return
        self.loading_label.setGeometry(self._loading_geometry())
        self.loading_label.raise_()
        self.loading_label.show()
        self.loading_label.repaint()

        if self.gps_layer:
            canvas = self.iface.mapCanvas()
            pt0 = QgsPointXY(self.polyline[0].x(), self.polyline[0].y())
            canvas.setCenter(pt0)
            canvas.zoomScale(2500)
            canvas.refresh()
            self.mini_map_win.set_extent(canvas.extent())
            self.embed_map.set_extent(canvas.extent())

        exe = find_mpv()
        if not exe and sys.platform == 'win32':
            self._start_mpv_download()
            return
        self._init_playback(exe)

    def _start_mpv_download(self):
        self._dl_signals = _MpvDownloadSignals()
        self._dl_signals.progress.connect(self._mpv_progress)
        self._dl_signals.done.connect(self._mpv_download_done)
        self.loading_label.setText("Downloading mpv...")
        self.loading_label.setGeometry(self._loading_geometry())
        self.loading_label.raise_()
        self.loading_label.repaint()

        def on_progress(msg):
            try:
                self._dl_signals.progress.emit(msg)
            except Exception:  # nosec
                pass

        def on_done(ok, err):
            try:
                self._dl_signals.done.emit(ok, err)
            except Exception:  # nosec
                pass

        download_mpv_async(
            MPV_URL, mpv_cache_dir(), on_progress, on_done)

    def _mpv_progress(self, msg):
        self.loading_label.setText(msg)
        self.loading_label.setGeometry(self._loading_geometry())
        self.loading_label.raise_()
        self.loading_label.repaint()

    def _mpv_download_done(self, ok, err):
        if ok:
            self.loading_label.setText("Starting mpv...")
            self.loading_label.setGeometry(self._loading_geometry())
            self.loading_label.raise_()
            self.loading_label.repaint()
            self._init_playback(find_mpv())
        else:
            self.loading_label.hide()
            self._init_playback(None)

    def _init_playback(self, exe):
        self.mpv = MpvController()
        hwnd = int(self.video_widget.winId())
        if exe and self.mpv.launch(hwnd, self.videofile):
            self.use_mpv = True
            self.mpv.mute(True)
            self._poll_pos_rid = -1
            self._poll_dur_rid = -1
            QTimer.singleShot(800, self._delayed_play)
        else:
            self.use_mpv = False
            self.mpv = None
            url = QUrl.fromLocalFile(self.videofile)
            self.qplayer.setMedia(QMediaContent(url))
            self.qplayer.setMuted(True)
            self.qplayer.play()
            self.loading_label.hide()
            self.btn_play.setIcon(_icon('pause'))
            self.btn_mute.setIcon(_icon('mute'))

    def _delayed_play(self):
        if self.use_mpv and self.mpv:
            self.mpv.play()
            self._paused = False
        self.loading_label.hide()
        self.btn_play.setIcon(_icon('pause'))
        self.btn_mute.setIcon(_icon('mute'))
        self._poll_pos()
        self._poll_dur()

    def _poll_pos(self):
        if not self.mpv:
            return
        self._poll_pos_rid = self.mpv.req(
            'get_property', 'time-pos', cb=self._cb_pos)

    def _cb_pos(self, pos):
        if pos is not None:
            self._update_position(pos)
        QTimer.singleShot(100, self._poll_pos)

    def _poll_dur(self):
        if not self.mpv:
            return
        self._poll_dur_rid = self.mpv.req(
            'get_property', 'duration', cb=self._cb_dur)

    def _cb_dur(self, dur):
        if dur is not None:
            self.slider.setMaximum(int(dur))
        QTimer.singleShot(2000, self._poll_dur)

    def _update_position(self, pos_sec):
        total = self.total_gps_seconds

        if not self.slider.isSliderDown():
            self.slider.setValue(int(pos_sec))

        self.lbl_time.setText(
            f"{self._fmt(pos_sec)} / {self._fmt(total)}")

        gps_sec = int(pos_sec)
        dur = self.slider.maximum()
        if dur > 0 and pos_sec >= dur:
            if self.use_mpv:
                self.mpv.pause()
            else:
                self.qplayer.pause()
            self._paused = True
            self._eof = True
            self.btn_play.setIcon(_icon('play'))
            return

        x, y, z, heading, speed = self._interpolate(gps_sec)
        self._display(gps_sec, x, y, z, heading, speed)

    def _interpolate(self, t):
        i = int(t)
        if i + 1 >= len(self.GPXList):
            i = max(0, len(self.GPXList) - 2)

        lat1, lon1 = self.GPXList[i][0], self.GPXList[i][1]
        lat2, lon2 = self.GPXList[i + 1][0], self.GPXList[i + 1][1]
        ele1, ele2 = self.GPXList[i][2], self.GPXList[i + 1][2]

        calc = Geodesic.WGS84.Inverse(lat1, lon1, lat2, lon2)
        dist = calc['s12']
        azimuth = calc['azi2']
        if azimuth < 0:
            azimuth += 360

        frac = t - i
        direct = Geodesic.WGS84.Direct(lat1, lon1, azimuth, frac * dist)
        x, y = direct['lon2'], direct['lat2']
        z = ele1 + frac * (ele2 - ele1)

        return x, y, z, azimuth, dist

    def _display(self, idx, lon, lat, ele, heading, speed):
        if idx >= len(self.GPXList):
            idx = len(self.GPXList) - 1
        gps_time = self.GPXList[idx][3]

        canvas = self.iface.mapCanvas()
        crs_src = QgsCoordinateReferenceSystem(4326)
        crs_dst = canvas.mapSettings().destinationCrs()
        xform = QgsCoordinateTransform(
            crs_src, crs_dst, QgsProject.instance())

        pt = QgsPointXY(lon, lat)
        pt_t = xform.transform(pt)
        self._last_pt_t = pt_t

        self.position_marker.setHasPosition(True)
        self.position_marker.newCoords(pt_t)
        self.position_marker.angle = heading
        self.position_marker.update()

        if self.mini_map_win.isVisible():
            self.mini_map_win.update_position(pt_t, heading)

        if self.embed_map.isVisible():
            self.embed_map.update_position(pt_t, heading)

        self.dock.lbl_gpx.setText(
            f"GPS: {gps_time} | Lat: {lat:.6f} | Lon: {lon:.6f} | "
            f"Heading: {heading:.1f}\u00b0 | "
            f"Speed: {speed:.1f} m/s | Ele: {ele:.1f}m")

        if not self.enable_map_tool and not self._paused:
            now = time.time()
            if now - self._last_recenter >= 2.5:
                self._last_recenter = now
                extent = canvas.extent()
                bounds = QgsRectangle(extent)
                bounds.scale(0.7)
                if not bounds.contains(QgsRectangle(pt_t, pt_t)):
                    canvas.setExtent(QgsRectangle(
                        pt_t.x() - extent.width() / 2,
                        pt_t.y() - extent.height() / 2,
                        pt_t.x() + extent.width() / 2,
                        pt_t.y() + extent.height() / 2))
                    canvas.refresh()
                    self.mini_map_win.recenter_to(pt_t)
                    self.embed_map.recenter_to(pt_t)

        if self._gps_jumped:
            self._gps_jumped = False
            self.mini_map_win.recenter_to(pt_t)
            self.embed_map.recenter_to(pt_t)

    def _play_pause(self):
        if self.use_mpv:
            if self._eof:
                self._eof = False
                self.mpv.seek(0)
            self.mpv.toggle()
        else:
            if self.qplayer.state() == QMediaPlayer.PlayingState:
                self.qplayer.pause()
            else:
                if self._eof:
                    self._eof = False
                    self.qplayer.setPosition(0)
                self.qplayer.play()
        self._paused = not self._paused
        self.btn_play.setIcon(_icon('play' if self._paused else 'pause'))

    def _toggle_mute(self):
        if self.use_mpv:
            self.mpv.req('get_property', 'mute', cb=self._cb_mute_toggle)
        else:
            self.qplayer.setMuted(not self.qplayer.isMuted())
            self.btn_mute.setIcon(
                _icon('mute' if self.qplayer.isMuted() else 'unmute'))

    def _cb_mute_toggle(self, muted):
        if muted is not None:
            self.mpv.mute(not muted)
            self.btn_mute.setIcon(_icon('mute' if not muted else 'unmute'))

    def _skip(self, seconds):
        self._eof = False
        if self.use_mpv:
            self.mpv.seek_rel(seconds)
        else:
            self.qplayer.setPosition(
                self.qplayer.position() + seconds * 1000)

    def _skip_frame(self, direction):
        if self._frame_busy:
            return
        self._frame_busy = True
        QTimer.singleShot(80, lambda: self._do_frame(direction))

    def _do_frame(self, direction):
        step = 15 / self.fps
        self._eof = False
        if self.use_mpv:
            self.mpv.seek_rel(direction * step)
        else:
            ms = round(step * 1000)
            self.qplayer.setPosition(
                self.qplayer.position() + direction * ms)
        QTimer.singleShot(80, self._clear_frame_busy)

    def _clear_frame_busy(self):
        self._frame_busy = False

    def _on_slider(self, pos):
        self._eof = False
        if self.use_mpv:
            self.mpv.seek(pos)
        else:
            self.qplayer.setPosition(int(pos * 1000))
        self._last_recenter = 0

    def _on_duration(self, dur):
        self.slider.setMaximum(int(dur / 1000))

    def _on_position(self, pos_ms):
        self._update_position(pos_ms / 1000)

    def _toggle_map_tool(self):
        canvas = self.iface.mapCanvas()
        if not self.enable_map_tool:
            self.prev_tool = canvas.mapTool()
            canvas.setMapTool(self.skip_tool)
            self.enable_map_tool = True
        else:
            canvas.unsetMapTool(self.skip_tool)
            if hasattr(self, 'prev_tool'):
                canvas.setMapTool(self.prev_tool)
            self.enable_map_tool = False
            self.raise_()

    def _recenter_once(self):
        if self._last_pt_t:
            canvas = self.iface.mapCanvas()
            extent = canvas.extent()
            canvas.setExtent(QgsRectangle(
                self._last_pt_t.x() - extent.width() / 2,
                self._last_pt_t.y() - extent.height() / 2,
                self._last_pt_t.x() + extent.width() / 2,
                self._last_pt_t.y() + extent.height() / 2))
            canvas.refresh()
            self.mini_map_win.recenter_to(self._last_pt_t)
            self.embed_map.recenter_to(self._last_pt_t)

    def _reveal_map_buttons(self):
        if self.btn_toggle_minimap.isVisible():
            self.btn_toggle_minimap.hide()
        else:
            self.btn_toggle_minimap.show()

    def _toggle_minimap(self):
        if self.mini_map_win.isVisible():
            self.mini_map_win.hide()
            self.btn_toggle_minimap.setChecked(False)
        else:
            self.mini_map_win.show()
            self.mini_map_win.raise_()
            self.btn_toggle_minimap.setChecked(True)
            self.embed_map.hide()
            self.btn_toggle_embed.setChecked(False)

    def _toggle_embedmap(self):
        if self.embed_map.isVisible():
            self.embed_map.hide()
            self.btn_toggle_embed.setChecked(False)
        else:
            self.embed_map.show()
            self.btn_toggle_embed.setChecked(True)
            self.mini_map_win.hide()
            self.btn_toggle_minimap.setChecked(False)
            self.splitter.setSizes(
                [self.splitter.width() - 240, 240])

    def _on_minimap_closed(self):
        self.btn_toggle_minimap.setChecked(False)

    def jump_to_gps(self, idx):
        self._eof = False
        if self.use_mpv:
            self.mpv.seek(idx)
        else:
            self.qplayer.setPosition(idx * 1000)
        self._last_recenter = 0
        self._gps_jumped = True
        self.raise_()
        self.activateWindow()

    def _fmt(self, s):
        s = int(s)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}"

    def closeEvent(self, event):
        try:
            self.loading_label.setText("Please wait...")
            self.loading_label.setGeometry(self._loading_geometry())
            self.loading_label.raise_()
            self.loading_label.show()
            self.loading_label.repaint()
            QtCore.QCoreApplication.processEvents()
            if self.use_mpv and self.mpv:
                self.mpv.stop()
            else:
                self.qplayer.stop()
            self.mini_map_win.clear_marker()
            self.mini_map_win.hide()
            self.mini_map_win.close()
            self.embed_map.clear_marker()
            canvas = self.iface.mapCanvas()
            canvas.scene().removeItem(self.position_marker)
            if self.gps_layer:
                QgsProject.instance().removeMapLayer(
                    self.gps_layer.id())
            canvas.unsetMapTool(self.skip_tool)
        except Exception:  # nosec
            pass
        event.accept()
