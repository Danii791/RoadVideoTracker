# -*- coding: utf-8 -*-
import os
import sys
import platform
import configparser
from qgis.PyQt.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, Qt, QTimer
from qgis.PyQt.QtGui import QIcon
try:
    from qgis.PyQt.QtGui import QAction
except ImportError:
    from qgis.PyQt.QtWidgets import QAction

from .tracker_dock import TrackerDock


def _read_plugin_version():
    meta = os.path.join(os.path.dirname(__file__), 'metadata.txt')
    try:
        cp = configparser.RawConfigParser()
        cp.read(meta)
        return cp.get('general', 'version')
    except Exception:  # nosec
        return ""


class VideoTracker:

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)

        locale = QSettings().value('locale/userLocale', 'en')[0:2]
        locale_path = os.path.join(
            self.plugin_dir, 'i18n', 'VideoTracker_{}.qm'.format(locale))
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        self.actions = []
        self.menu = self.tr(u'&Road Video Tracker')
        self.dock = None
        self.pluginIsActive = False

    def tr(self, message):
        return QCoreApplication.translate('RoadVideoTracker', message)

    def add_action(self, icon_path, text, callback, parent=None):
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        self.iface.addToolBarIcon(action)
        self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)
        return action

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, 'main_icon.svg')
        self.add_action(
            icon_path,
            text=self.tr(u'Road Video Tracker'),
            callback=self.run,
            parent=self.iface.mainWindow())

    def unload(self):
        from .tracking import send_tracking, reset_sent_open_processing, clear_last_error
        send_tracking("Quit")
        reset_sent_open_processing()
        clear_last_error()
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)

    def run(self):
        from .tracking import _processing_dialog, send_tracking
        if self.dock is None:
            self.dock = TrackerDock(self.iface)
            dlg = _processing_dialog()
            dlg.show()
            QCoreApplication.processEvents()
            self._loading_dlg = dlg
            QTimer.singleShot(3000, self._dismiss_loading)
            try:
                from qgis.core import Qgis
                from .mpv_control import find_mpv, detect_gpus
                qgis_ver = Qgis.version() if Qgis else ""
                mpv_avail = "true" if find_mpv() else "false"
                gpus = detect_gpus()
                gpu_info = ", ".join(gpus) if gpus else ""
                send_tracking("Open",
                    qgis_version=qgis_ver,
                    plugin_version=_read_plugin_version(),
                    python_version=sys.version.split()[0],
                    os_info=platform.platform(),
                    mpv_available=mpv_avail,
                    gpu_info=gpu_info,
                    mpv_fallback="",
                    error_msg="",
                    status="")
            except Exception:  # nosec
                pass
        self.iface.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock)
        self.dock.show()

    def _dismiss_loading(self):
        if self._loading_dlg:
            self._loading_dlg.close()
            self._loading_dlg = None
