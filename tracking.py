import os
import json
import socket
from datetime import datetime
from urllib.request import Request, urlopen
from qgis.PyQt.QtWidgets import QDialog, QLabel, QVBoxLayout, QProgressBar
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QPainterPath, QRegion

TRACKING_URL = "https://script.google.com/macros/s/AKfycby8cWstU91dTsgULm1X4XqWGojt3Pg0KKuQtAMBEnbZ2bKir_M0BFE48wgBt3GJn0fv8g/exec"
_SENT_OPEN = False


def _processing_dialog(parent=None):
    dlg = QDialog(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
    dlg.setFixedSize(320, 120)
    path = QPainterPath()
    path.addRoundedRect(0, 0, 320, 120, 8, 8)
    dlg.setMask(QRegion(path.toFillPolygon().toPolygon()))
    dlg.setStyleSheet("""
        QDialog {
            background-color: #2c3e50;
            border: 1px solid #34495e;
        }
    """)
    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(20, 15, 20, 15)
    layout.setSpacing(8)

    lbl = QLabel("Preparing")
    lbl.setStyleSheet("color: #ecf0f1; font-size: 14px; font-weight: bold;")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(lbl)

    bar = QProgressBar()
    bar.setRange(0, 0)
    bar.setFixedHeight(12)
    bar.setTextVisible(False)
    bar.setStyleSheet("""
        QProgressBar {
            border: none;
            border-radius: 6px;
            background-color: #34495e;
        }
        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #3498db, stop:1 #2ecc71);
            border-radius: 6px;
        }
    """)
    layout.addWidget(bar)

    sub = QLabel("Please wait a moment...")
    sub.setStyleSheet("color: #95a5a6; font-size: 10px;")
    sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(sub)

    _dot_count = 0
    def _animate():
        nonlocal _dot_count
        _dot_count = (_dot_count + 1) % 4
        lbl.setText("Preparing" + "." * _dot_count)

    timer = QTimer(dlg)
    timer.timeout.connect(_animate)
    timer.start(500)

    screen = dlg.screen()
    if screen:
        center = screen.geometry().center()
        dlg.move(center.x() - 160, center.y() - 60)
    return dlg


def send_tracking(action="Open"):
    if action == "Open":
        global _SENT_OPEN
        if _SENT_OPEN:
            return
        _SENT_OPEN = True
    try:
        data = {
            "timestamp": datetime.now().isoformat(),
            "username": os.environ.get('USERNAME', 'Unknown'),
            "computer": os.environ.get('COMPUTERNAME', socket.gethostname()),
            "time": datetime.now().strftime("%H:%M:%S"),
            "action": action
        }
        req = Request(
            TRACKING_URL,
            json.dumps(data).encode(),
            {"Content-Type": "application/json"})
        urlopen(req, timeout=5)  # nosec
    except Exception:  # nosec
        pass
