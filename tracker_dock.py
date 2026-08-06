# -*- coding: utf-8 -*-
import os
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QSize, Qt, QCoreApplication
from qgis.PyQt.QtWidgets import QFileDialog

from . import resources

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
ICON_SIZE = QSize(20, 20)


def _icon(name):
    return QIcon(os.path.join(ICON_DIR, name + '.svg'))


class TrackerDock(QtWidgets.QDockWidget):

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle("Road Video Tracker")
        self.setMinimumWidth(220)
        self.setMaximumWidth(350)
        self.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable |
            QtWidgets.QDockWidget.DockWidgetFloatable |
            QtWidgets.QDockWidget.DockWidgetClosable)

        self.videofile = None
        self.gpxfile = None
        self.player_window = None

        self._setup_ui()

    def _setup_ui(self):
        widget = QtWidgets.QWidget()
        widget.setMaximumWidth(340)
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        grp = QtWidgets.QGroupBox("Input Files")
        grp_layout = QtWidgets.QVBoxLayout()
        grp_layout.setSpacing(3)

        self.btn_select_folder = QtWidgets.QPushButton("Auto Find (Folder)")
        self.btn_select_folder.setMinimumHeight(28)
        self.btn_select_folder.clicked.connect(self._select_folder)
        grp_layout.addWidget(self.btn_select_folder)

        self.btn_select = QtWidgets.QPushButton("Select Video && GPX")
        self.btn_select.setMinimumHeight(28)
        self.btn_select.clicked.connect(self._select_files)
        grp_layout.addWidget(self.btn_select)

        self.lbl_video = QtWidgets.QLabel("No video selected")
        self.lbl_video.setStyleSheet("color: gray;")
        self.lbl_video.setWordWrap(True)
        grp_layout.addWidget(self.lbl_video)

        self.lbl_gpx = QtWidgets.QLabel("No GPX selected")
        self.lbl_gpx.setStyleSheet("color: gray;")
        self.lbl_gpx.setWordWrap(True)
        grp_layout.addWidget(self.lbl_gpx)

        self.chk_autoplay = QtWidgets.QCheckBox("Autoplay")
        self.chk_autoplay.setChecked(True)
        grp_layout.addWidget(self.chk_autoplay)

        grp.setLayout(grp_layout)
        layout.addWidget(grp)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(4)
        self.btn_settings = QtWidgets.QToolButton()
        self.btn_settings.setIcon(_icon('settings'))
        self.btn_settings.setIconSize(ICON_SIZE)
        self.btn_settings.setFixedHeight(28)
        self.btn_settings.setToolTip("Performance Settings")
        self.btn_settings.clicked.connect(self._open_settings)
        btn_layout.addWidget(self.btn_settings)
        self.btn_start = QtWidgets.QPushButton(" Start")
        self.btn_start.setIcon(_icon('start'))
        self.btn_start.setIconSize(ICON_SIZE)
        self.btn_start.setMinimumHeight(28)
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self._start)
        btn_layout.addWidget(self.btn_start)

        self.btn_quit = QtWidgets.QPushButton(" Quit")
        self.btn_quit.setIcon(_icon('quit'))
        self.btn_quit.setIconSize(ICON_SIZE)
        self.btn_quit.setMinimumHeight(28)
        self.btn_quit.clicked.connect(self.close)
        btn_layout.addWidget(self.btn_quit)
        layout.addLayout(btn_layout)

        layout.addStretch()
        self.setWidget(widget)

        self.loading_label = QtWidgets.QLabel("Please wait...", widget)
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet(
            "background-color: rgba(0,0,0,180); color: white; font-size: 14px;")
        self.loading_label.hide()

    def _show_loading(self):
        self.loading_label.setGeometry(self.widget().rect())
        self.loading_label.raise_()
        self.loading_label.show()
        self.loading_label.repaint()
        self.btn_start.setEnabled(False)
        self.btn_select.setEnabled(False)
        self.btn_select_folder.setEnabled(False)
        self.btn_quit.setEnabled(False)
        self.btn_settings.setEnabled(False)
        QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QCoreApplication.processEvents()

    def _hide_loading(self):
        self.loading_label.hide()
        self.btn_select.setEnabled(True)
        self.btn_select_folder.setEnabled(True)
        self.btn_quit.setEnabled(True)
        self.btn_settings.setEnabled(True)
        QtWidgets.QApplication.restoreOverrideCursor()
        self._check_ready()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.loading_label.isVisible():
            self.loading_label.setGeometry(self.widget().rect())

    def _select_files(self):
        videopath, _ = QFileDialog.getOpenFileName(
            self, "Select Video", "",
            "Video Files (*.mp4 *.avi *.ogv *.mkv);;All Files (*)")
        if not videopath:
            return
        self.videofile = videopath
        self.lbl_video.setText(os.path.basename(videopath))
        self.lbl_video.setStyleSheet("color: black;")

        gpxpath, _ = QFileDialog.getOpenFileName(
            self, "Select GPX", "",
            "GPX Files (*.gpx);;All Files (*)")
        if not gpxpath:
            return
        self.gpxfile = gpxpath
        self.lbl_gpx.setText(os.path.basename(gpxpath))
        self.lbl_gpx.setStyleSheet("color: black;")
        self._check_ready()
        if self.chk_autoplay.isChecked():
            self._start()

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not folder:
            return

        videos = []
        gpxs = []
        for f in os.listdir(folder):
            if f.lower().endswith('.mp4'):
                videos.append(os.path.join(folder, f))
            elif f.lower().endswith('.gpx'):
                gpxs.append(os.path.join(folder, f))

        if not videos:
            QtWidgets.QMessageBox.warning(
                self, "Error",
                "No MP4 video file found in the selected folder.")
            return
        if not gpxs:
            QtWidgets.QMessageBox.warning(
                self, "Error",
                "No GPX file found in the selected folder.")
            return

        self.videofile = videos[0]
        self.gpxfile = gpxs[0]
        self.lbl_video.setText(os.path.basename(self.videofile))
        self.lbl_video.setStyleSheet("color: black;")
        self.lbl_gpx.setText(os.path.basename(self.gpxfile))
        self.lbl_gpx.setStyleSheet("color: black;")
        self._check_ready()
        if self.chk_autoplay.isChecked():
            self._start()

    def _check_ready(self):
        self.btn_start.setEnabled(
            self.videofile is not None and self.gpxfile is not None)

    def _open_settings(self):
        from .settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        dlg.raise_()
        dlg.activateWindow()
        dlg.exec()

    def _start(self):
        if not self.videofile or not self.gpxfile:
            return
        if self.player_window:
            self._show_loading()
            try:
                pw = self.player_window
                if pw.use_mpv and pw.mpv:
                    pw.mpv.stop()
                else:
                    pw.qplayer.stop()
                pw.close()
                pw.deleteLater()
            except Exception:  # nosec
                pass
            self.player_window = None
            self._hide_loading()
        from .player_window import PlayerWindow
        self.player_window = PlayerWindow(
            self.videofile, self.gpxfile, self.iface, self)
        self.player_window.show()

    def closeEvent(self, event):
        self._show_loading()
        try:
            if self.player_window:
                self.player_window.close()
            from .tracking import send_tracking
            send_tracking("Quit")
        finally:
            self._hide_loading()
            event.accept()
