# -*- coding: utf-8 -*-
from qgis.gui import QgsMapTool
from qgis.PyQt.QtGui import QCursor
from qgis.PyQt.QtCore import Qt


class SkipTrackTool(QgsMapTool):

    def __init__(self, canvas, layer, player):
        super().__init__(canvas)
        self.canvas = canvas
        self.layer = layer
        self.player = player
        self.cursor = QCursor(Qt.CursorShape.CrossCursor)

    def canvasPressEvent(self, event):
        point = self.toLayerCoordinates(self.layer, event.pos())
        self._find_nearest(point.x(), point.y())

    def _find_nearest(self, x, y):
        best_idx = 0
        best_dist = None
        for i, pt in enumerate(self.player.polyline):
            dx = pt.x() - x
            dy = pt.y() - y
            d = dx * dx + dy * dy
            if best_dist is None or d < best_dist:
                best_dist = d
                best_idx = i
        self.player.jump_to_gps(best_idx)

    def activate(self):
        self.canvas.setCursor(self.cursor)

    def deactivate(self):
        pass
