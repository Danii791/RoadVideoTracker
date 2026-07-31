# -*- coding: utf-8 -*-
from PyQt5 import QtGui, QtCore
from qgis.core import QgsPointXY
from qgis.gui import QgsMapCanvasItem


class PositionMarker(QgsMapCanvasItem):

    def __init__(self, canvas, alpha=255):
        super().__init__(canvas)
        self.pos = None
        self.has_position = False
        self.angle = 0
        self.d = 20
        self.alpha = alpha
        self.setZValue(100)

    def newCoords(self, pos):
        if self.pos != pos:
            self.pos = QgsPointXY(pos)
            self.updatePosition()

    def setHasPosition(self, has):
        if self.has_position != has:
            self.has_position = has
            self.update()

    def updatePosition(self):
        if self.pos:
            self.setPos(self.toCanvasCoordinates(self.pos))
            self.update()

    def paint(self, p, xxx, xxx2):
        if not self.pos:
            return

        path = QtGui.QPainterPath()
        path.moveTo(0, -15)
        path.lineTo(15, 15)
        path.lineTo(0, 7)
        path.lineTo(-15, 15)
        path.lineTo(0, -15)

        p.save()
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        if self.has_position:
            p.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0, self.alpha)))
        else:
            p.setBrush(QtGui.QBrush(QtGui.QColor(200, 200, 200, self.alpha)))
        p.setPen(QtGui.QColor(255, 255, 0, self.alpha))
        p.rotate(self.angle)
        p.drawPath(path)
        p.restore()

    def boundingRect(self):
        return QtCore.QRectF(-self.d, -self.d, self.d * 2, self.d * 2)
