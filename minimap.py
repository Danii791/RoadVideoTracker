from PyQt5 import QtWidgets, QtGui, QtCore
from qgis.core import QgsProject, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsPointXY
from qgis.gui import QgsMapCanvas, QgsMapToolPan
from .position_marker import PositionMarker


class DragStrip(QtWidgets.QWidget):

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setFixedHeight(12)
        self._drag_pos = None

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 2, 0)
        layout.setSpacing(0)

        self.label = QtWidgets.QLabel(title)
        self.label.setStyleSheet(
            "color: #bbb; font-size: 10px; background: transparent;")
        layout.addWidget(self.label)
        layout.addStretch()

        self.setStyleSheet("background-color: rgba(38, 38, 38, 128);")

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.parent().pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == QtCore.Qt.LeftButton and self._drag_pos:
            self.parent().move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
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
            'tl': QtCore.Qt.SizeFDiagCursor,
            'tr': QtCore.Qt.SizeBDiagCursor,
            'bl': QtCore.Qt.SizeBDiagCursor,
            'br': QtCore.Qt.SizeFDiagCursor,
        }
        self.setCursor(cursors.get(corner, QtCore.Qt.ArrowCursor))
        self.setStyleSheet("background: transparent;")

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_start = event.globalPos()
            self._start_geo = self.parent().geometry()
            event.accept()

    def mouseMoveEvent(self, event):
        if not self._drag_start or not event.buttons() == QtCore.Qt.LeftButton:
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
        if event.button() == QtCore.Qt.LeftButton:
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
        if event.button() == QtCore.Qt.LeftButton:
            self._press_pos = event.pos()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self._press_pos is not None and event.button() == QtCore.Qt.LeftButton and self._seek_callback:
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
        except Exception:
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
        except Exception:
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
        except Exception:
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
        self.marker.angle = heading
        self.marker.update()

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
        self.resize(400, 300)
        self.setMinimumSize(150, 100)
        self.setWindowFlags(
            QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint)
        self.setWindowOpacity(0.75)

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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        self.grip_tl.move(0, 0)
        self.grip_tr.move(w - 5, 0)
        self.grip_bl.move(0, h - 5)
        self.grip_br.move(w - 5, h - 5)

    def closeEvent(self, event):
        self.clear_marker()
        self.closed.emit()
        event.accept()


class EmbeddedMap(MiniMapBase):

    def __init__(self, player, parent=None):
        super().__init__(player, parent)
        self.setMinimumWidth(150)
        self.resize(240, 300)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.canvas)
