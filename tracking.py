import os
import sys
import json
import socket
import platform
import threading
import traceback
from datetime import datetime
from urllib.request import Request, urlopen
from qgis.PyQt.QtWidgets import QDialog, QLabel, QVBoxLayout, QProgressBar, QApplication
from qgis.PyQt.QtCore import Qt, QTimer, QT_VERSION_STR
from qgis.PyQt.QtGui import QPainterPath, QRegion

_QT6 = QT_VERSION_STR.startswith("6")

_FramelessWindowHint = Qt.WindowType.FramelessWindowHint
_WindowStaysOnTopHint = Qt.WindowType.WindowStaysOnTopHint
_AlignCenter = Qt.AlignmentFlag.AlignCenter

TRACKING_URL = "https://script.google.com/macros/s/AKfycby8cWstU91dTsgULm1X4XqWGojt3Pg0KKuQtAMBEnbZ2bKir_M0BFE48wgBt3GJn0fv8g/exec"
_last_error = ""
_SENT_OPEN_PROCESSING = False


def _install_excepthook():
    _prev = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):
        global _last_error
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        if "road_video_tracker" in tb:
            _last_error = repr(exc_value)
        if _prev is not None:
            _prev(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook


_install_excepthook()


def get_last_error():
    return _last_error


def clear_last_error():
    global _last_error
    _last_error = ""


def sent_open_processing():
    return _SENT_OPEN_PROCESSING


def mark_open_processing_sent():
    global _SENT_OPEN_PROCESSING
    _SENT_OPEN_PROCESSING = True


def reset_sent_open_processing():
    global _SENT_OPEN_PROCESSING
    _SENT_OPEN_PROCESSING = False


def _processing_dialog(parent=None):
    dlg = QDialog(parent, _FramelessWindowHint | _WindowStaysOnTopHint)
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
    lbl.setAlignment(_AlignCenter)
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
    sub.setAlignment(_AlignCenter)
    layout.addWidget(sub)

    _dot_count = 0
    def _animate():
        nonlocal _dot_count
        _dot_count = (_dot_count + 1) % 4
        lbl.setText("Preparing" + "." * _dot_count)

    timer = QTimer(dlg)
    timer.timeout.connect(_animate)
    timer.start(500)

    try:
        screen = dlg.screen()
    except AttributeError:
        screen = QApplication.primaryScreen()
    if screen:
        center = screen.geometry().center()
        dlg.move(center.x() - 160, center.y() - 60)
    return dlg


def send_tracking(action="Open", **extra):
    def _do_send():
        try:
            err = extra.pop("error_msg", None)
            if err is None:
                err = get_last_error()
            data = {
                "timestamp": datetime.now().isoformat(),
                "username": os.environ.get('USERNAME', 'Unknown'),
                "computer": os.environ.get('COMPUTERNAME', socket.gethostname()),
                "time": datetime.now().strftime("%H:%M:%S"),
                "action": action,
                "error_msg": err
            }
            data.update(extra)

            def _send():
                try:
                    req = Request(
                        TRACKING_URL,
                        json.dumps(data).encode(),
                        {"Content-Type": "application/json"})
                    urlopen(req, timeout=5)  # nosec B310
                except Exception:  # nosec
                    pass

            threading.Thread(target=_send, daemon=True).start()
            clear_last_error()
        except Exception:  # nosec
            pass

    _do_send()
