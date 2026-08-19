import math
import os

from qgis.PyQt import QtWidgets, QtGui, QtCore
from qgis.PyQt.QtCore import Qt, QT_VERSION_STR
from qgis.core import QgsProject, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsPointXY
from qgis.gui import QgsMapCanvas, QgsMapToolPan
from .position_marker import PositionMarker

_QT6 = QT_VERSION_STR.startswith("6")
if _QT6:
    _WindowStateChange = QtCore.QEvent.Type.WindowStateChange
else:
    _WindowStateChange = QtCore.QEvent.WindowStateChange

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')


def _icon(name):
    for ext in ('.svg', '.png'):
        p = os.path.join(ICON_DIR, name + ext)
        if os.path.exists(p):
            return QtGui.QIcon(p)
    return QtGui.QIcon()


class DragStrip(QtWidgets.QWidget):

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setFixedHeight(11)
        self._drag_pos = None

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 2, 0)
        layout.setSpacing(0)

        self.label = QtWidgets.QLabel(title)
        self.label.setStyleSheet(
            "color: #bbb; font-size: 8px; background: transparent;")
        layout.addWidget(self.label)
        layout.addStretch()

        self.setStyleSheet("background-color: rgba(38, 38, 38, 128);")

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPos() - self.parent().pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == QtCore.Qt.MouseButton.LeftButton and self._drag_pos:
            self.parent().move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_pos = None
            event.accept()


class CornerGrip(QtWidgets.QWidget):

    def __init__(self, parent, corner):
        super().__init__(parent)
        self._corner = corner
        self._drag_start = None
        self._start_geo = None
        self.setFixedSize(5, 5)
        cursors = {
            'tl': QtCore.Qt.CursorShape.SizeFDiagCursor,
            'tr': QtCore.Qt.CursorShape.SizeBDiagCursor,
            'bl': QtCore.Qt.CursorShape.SizeBDiagCursor,
            'br': QtCore.Qt.CursorShape.SizeFDiagCursor,
        }
        self.setCursor(cursors.get(corner, QtCore.Qt.CursorShape.ArrowCursor))
        self.setStyleSheet("background: transparent;")

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_start = event.globalPos()
            self._start_geo = self.parent().geometry()
            event.accept()

    def mouseMoveEvent(self, event):
        if not self._drag_start or not event.buttons() == QtCore.Qt.MouseButton.LeftButton:
            return
        p = self.parent()
        dx = event.globalPos().x() - self._drag_start.x()
        dy = event.globalPos().y() - self._drag_start.y()
        x, y, w, h = self._start_geo.getRect()

        if 'l' in self._corner:
            x += dx; w -= dx
        if 'r' in self._corner:
            w += dx
        if 't' in self._corner:
            y += dy; h -= dy
        if 'b' in self._corner:
            h += dy

        p.setGeometry(x, y, w, h)
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_start = None
            self._start_geo = None
            event.accept()


class MiniMapCanvas(QgsMapCanvas):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._press_pos = None
        self._seek_callback = None

    def set_seek_callback(self, callback):
        self._seek_callback = callback

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._press_pos = event.pos()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self._press_pos is not None and event.button() == QtCore.Qt.MouseButton.LeftButton and self._seek_callback:
            dist = (event.pos() - self._press_pos).manhattanLength()
            self._press_pos = None
            if dist < 10:
                self._seek_callback(event.pos())


class MiniMapBase(QtWidgets.QWidget):

    def __init__(self, player, parent=None):
        super().__init__(parent)
        self.player = player
        self.iface = player.iface
        self.canvas = MiniMapCanvas(self)
        self.canvas.setCanvasColor(QtGui.QColor(255, 255, 255))
        self.canvas.set_seek_callback(self._on_canvas_clicked)
        self.marker = PositionMarker(self.canvas, alpha=200)
        self._ready = False
        self._gpx_coords = []
        self._polyline_crs = []
        self.follow_road = False
        self._rot_cur = 0.0
        self.overlay_btn = None

        QtCore.QTimer.singleShot(200, self._do_setup)

    def _do_setup(self):
        if self.canvas.width() < 10 or self.canvas.height() < 10:
            QtCore.QTimer.singleShot(100, self._do_setup)
            return

        main = self.iface.mapCanvas()
        self.canvas.setDestinationCrs(
            main.mapSettings().destinationCrs())
        self.canvas.setMapTool(QgsMapToolPan(self.canvas))

        main_layers = main.layers()
        if main_layers:
            self.canvas.setLayers(main_layers)
        else:
            layers = QgsProject.instance().layerTreeRoot().layerOrder()
            if layers:
                self.canvas.setLayers(layers)
        self.canvas.setExtent(main.extent())
        self.canvas.refresh()

        self._ready = True
        self._pre_transform()

        main.layersChanged.connect(self._sync_layers)
        main.destinationCrsChanged.connect(self._on_crs_changed)
        try:
            root = QgsProject.instance().layerTreeRoot()
            root.visibilityChanged.connect(lambda _: self._sync_layers())
        except Exception:  # nosec
            pass

    def _sync_layers(self):
        if not self._ready:
            return
        try:
            main = self.iface.mapCanvas()
            main_layers = main.layers()
            if main_layers:
                self.canvas.setLayers(main_layers)
            self.canvas.refresh()
        except Exception:  # nosec
            pass

    def _pre_transform(self):
        try:
            try:
                crs_src = QgsCoordinateReferenceSystem.fromEpsgId(4326)
            except AttributeError:
                crs_src = QgsCoordinateReferenceSystem(4326)
            crs_dst = self.canvas.mapSettings().destinationCrs()
            xform = QgsCoordinateTransform(crs_src, crs_dst, QgsProject.instance())
            self._polyline_crs = []
            for lat, lon in self._gpx_coords:
                pt = QgsPointXY(lon, lat)
                self._polyline_crs.append(xform.transform(pt))
        except Exception:
            self._polyline_crs = []

    def set_gpx_data(self, gpx_list):
        self._gpx_coords = [(pt[0], pt[1]) for pt in gpx_list]
        if self._ready:
            self._pre_transform()

    def set_extent(self, extent):
        if not self._ready or not extent:
            return
        self.canvas.setExtent(extent)
        self.canvas.refresh()

    def _on_canvas_clicked(self, pos):
        try:
            player = self.player
            if not hasattr(player, 'enable_map_tool') or not player.enable_map_tool:
                return
            point_xy = self.canvas.getCoordinateTransform().toMapCoordinates(pos)

            nearest_idx = -1
            nearest_dist = float('inf')
            for i, pt in enumerate(self._polyline_crs):
                dx = point_xy.x() - pt.x()
                dy = point_xy.y() - pt.y()
                dist = dx * dx + dy * dy
                if dist < nearest_dist:
                    nearest_dist = dist
                    nearest_idx = i

            if nearest_idx >= 0:
                if hasattr(self, 'drag_strip'):
                    self.drag_strip.label.setText("Seeking...")
                    QtCore.QTimer.singleShot(800, lambda: self.drag_strip.label.setText("Mini Map"))
                if hasattr(player, 'jump_to_gps'):
                    player.jump_to_gps(nearest_idx)
        except Exception:  # nosec
            pass

    def _on_crs_changed(self):
        if not self._ready:
            return
        self.canvas.setDestinationCrs(
            self.iface.mapCanvas().mapSettings().destinationCrs())
        self.canvas.refresh()
        self._pre_transform()

    def update_position(self, pt_t, heading):
        if not self._ready:
            return
        self.marker.setHasPosition(True)
        self.marker.newCoords(pt_t)
        if self.follow_road:
            self.marker.angle = 0
            self.marker.update()

            target = (360 - heading) % 360
            delta = (target - self._rot_cur + 540) % 360 - 180
            self._rot_cur = (self._rot_cur + delta * 0.3) % 360
            self.canvas.setRotation(self._rot_cur)

            rad = math.radians(heading)
            dist = 0.25 * self.canvas.height() * self.canvas.mapSettings().mapUnitsPerPixel()
            center = QgsPointXY(
                pt_t.x() + math.sin(rad) * dist,
                pt_t.y() + math.cos(rad) * dist)
            self.canvas.setCenter(center)
            self.canvas.refresh()
        else:
            self.marker.angle = heading
            self.marker.update()

    def _apply_follow_style(self):
        self.overlay_btn.setStyleSheet(
            "QToolButton { background: transparent; border: none; }")
        if self.follow_road:
            self.overlay_btn.setIcon(_icon('navigation'))
        else:
            self.overlay_btn.setIcon(_icon('north-arrow'))

    def _on_overlay_btn(self):
        self.follow_road = not self.follow_road
        self.overlay_btn.setChecked(self.follow_road)
        self._apply_follow_style()
        if not self.follow_road:
            self._rot_cur = 0.0
            self.canvas.setRotation(0)
            self.canvas.refresh()

    def _setup_follow_button(self):
        self.overlay_btn = QtWidgets.QToolButton(self)
        self.overlay_btn.setIcon(_icon('navigation'))
        self.overlay_btn.setIconSize(QtCore.QSize(22, 22))
        self.overlay_btn.setFixedSize(30, 30)
        self.overlay_btn.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.overlay_btn.setCheckable(True)
        self.overlay_btn.setToolTip("Follow road (auto-center)")
        self.overlay_btn.clicked.connect(self._on_overlay_btn)
        self._apply_follow_style()
        self._place_overlay_btn()

    def _place_overlay_btn(self):
        if not self.overlay_btn:
            return
        m = 4
        self.overlay_btn.move(
            self.width() - self.overlay_btn.width() - m,
            self.height() - self.overlay_btn.height() - m)

    def recenter_to(self, pt_t):
        if not self._ready or not pt_t:
            return
        self.canvas.setCenter(pt_t)
        self.canvas.refresh()

    def clear_marker(self):
        if not self._ready:
            return
        self.marker.setHasPosition(False)
        self.marker.update()


class MiniMapWindow(MiniMapBase):

    closed = QtCore.pyqtSignal()

    def __init__(self, player, parent=None):
        super().__init__(player, parent)
        self.resize(235, 200)
        self.setMinimumSize(150, 100)
        self.setWindowFlags(
            QtCore.Qt.WindowType.Window | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowOpacity(0.75)
        self._was_minimized = False
        self._keep_top = QtCore.QTimer(self)
        self._keep_top.setInterval(300)
        self._keep_top.timeout.connect(self._keep_on_top)
        self.player.installEventFilter(self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.drag_strip = DragStrip("Mini Map", self)
        layout.addWidget(self.drag_strip)

        layout.addWidget(self.canvas, 1)

        self.grip_tl = CornerGrip(self, 'tl')
        self.grip_tr = CornerGrip(self, 'tr')
        self.grip_bl = CornerGrip(self, 'bl')
        self.grip_br = CornerGrip(self, 'br')

        self._setup_follow_button()

    def _keep_on_top(self):
        self.raise_()

    def showEvent(self, event):
        super().showEvent(event)
        self.raise_()
        self._keep_top.start()

    def hideEvent(self, event):
        self._keep_top.stop()
        super().hideEvent(event)

    def eventFilter(self, obj, event):
        if obj is self.player and event.type() == _WindowStateChange:
            if self.player.isMinimized():
                if self.isVisible():
                    self._was_minimized = True
                    self.hide()
            elif self._was_minimized:
                self.show()
                self._was_minimized = False
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        self.grip_tl.move(0, 0)
        self.grip_tr.move(w - 5, 0)
        self.grip_bl.move(0, h - 5)
        self.grip_br.move(w - 5, h - 5)
        self._place_overlay_btn()

    def closeEvent(self, event):
        self._keep_top.stop()
        self.clear_marker()
        self.closed.emit()
        event.accept()


class EmbeddedMap(MiniMapBase):

    def __init__(self, player, parent=None):
        super().__init__(player, parent)
        self.setMinimumWidth(150)
        self.resize(160, 300)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.canvas)

        self._setup_follow_button()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_overlay_btn()
