# -*- coding: utf-8 -*-
import os
from qgis.PyQt.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, Qt
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon

from .tracker_dock import TrackerDock


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
        from .tracking import send_tracking
        send_tracking("Close")
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)

    def run(self):
        from .tracking import send_tracking, _processing_dialog
        if self.dock is None:
            self.dock = TrackerDock(self.iface)
        dlg = _processing_dialog()
        dlg.show()
        QCoreApplication.processEvents()
        send_tracking("Open")
        dlg.close()
        self.iface.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock)
        self.dock.show()
