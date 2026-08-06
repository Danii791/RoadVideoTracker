# -*- coding: utf-8 -*-
import threading

from qgis.PyQt import QtWidgets, QtCore
from qgis.PyQt.QtCore import Qt, QMetaObject, Q_ARG

from qgis.core import QgsSettings

from .mpv_control import hwdec_status

PREFIX = 'road_video_tracker/'

_PRESETS = {
    'performance': {'gpu_decode': True, 'audio_only': False,
                    'audio_buffer': 0.0, 'sync_mode': 'audio',
                    'framedrop': 'vo', 'cache_mb': 50,
                    'readahead_sec': 0, 'poll_ms': 50},
    'low_spec': {'gpu_decode': True, 'audio_only': True,
                 'audio_buffer': 0.5, 'sync_mode': 'display',
                 'framedrop': 'vo', 'cache_mb': 200,
                 'readahead_sec': 30, 'poll_ms': 100},
}

_MIGRATE_OPTIMIZE = {'auto': 'performance', 'low': 'low_spec',
                     'max': 'low_spec', 'balanced': 'low_spec'}


def load_opts():
    s = QgsSettings()
    optimize = s.value(PREFIX + 'optimize', 'performance', type=str)
    optimize = _MIGRATE_OPTIMIZE.get(optimize, optimize)
    if optimize not in _PRESETS:
        optimize = 'performance'
    opts = dict(_PRESETS[optimize])
    opts['optimize'] = optimize
    opts['gpu_decode'] = s.value(PREFIX + 'gpu_decode', True, type=bool)
    opts['audio_only'] = s.value(
        PREFIX + 'audio_only', _PRESETS[optimize]['audio_only'], type=bool)
    return opts


def save_opts(opts):
    s = QgsSettings()
    s.setValue(PREFIX + 'gpu_decode', opts['gpu_decode'])
    s.setValue(PREFIX + 'audio_only', opts['audio_only'])
    s.setValue(PREFIX + 'audio_buffer', opts['audio_buffer'])
    s.setValue(PREFIX + 'optimize', opts['optimize'])
    s.setValue(PREFIX + 'sync_mode', opts['sync_mode'])
    s.setValue(PREFIX + 'framedrop', opts['framedrop'])
    s.setValue(PREFIX + 'cache_mb', opts['cache_mb'])
    s.setValue(PREFIX + 'readahead_sec', opts['readahead_sec'])
    s.setValue(PREFIX + 'poll_ms', opts['poll_ms'])


class SettingsDialog(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Performance Settings")
        self.setModal(True)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumWidth(340)
        self._setup_ui()
        self._load()

    @staticmethod
    def _set_combo(combo, data):
        idx = combo.findData(data)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(6)

        self.chk_gpu = QtWidgets.QCheckBox("GPU decode (hardware accel)")
        self.chk_gpu.setToolTip(
            "Hardware acceleration for mpv (hwdec=auto). "
            "Falls back to software if unsupported.")
        layout.addWidget(self.chk_gpu)

        self.chk_noaudio = QtWidgets.QCheckBox("Video Only (without audio)")
        self.chk_noaudio.setToolTip(
            "Play without audio (--no-audio). Lighter and smoother on "
            "slow disks (HDD/USB); GPS stays synchronized.")
        layout.addWidget(self.chk_noaudio)

        grp = QtWidgets.QGroupBox("Performance Optimization")
        g = QtWidgets.QVBoxLayout(grp)
        g.setSpacing(4)

        opt_row = QtWidgets.QHBoxLayout()
        opt_row.addWidget(QtWidgets.QLabel("Optimization"))
        self.combo_opt = QtWidgets.QComboBox()
        self.combo_opt.addItem("Performance (Default)", "performance")
        self.combo_opt.setItemData(
            0, "Ringan, hemat RAM. Cocok untuk mesin normal.",
            Qt.ItemDataRole.ToolTipRole)
        self.combo_opt.addItem("Low-Spec Systems", "low_spec")
        self.combo_opt.setItemData(
            1,
            "Anti-patah untuk komputer spek rendah / HDD / USB lambat. "
            "RAM ekstra +-200 MB.",
            Qt.ItemDataRole.ToolTipRole)
        opt_row.addWidget(self.combo_opt, 1)
        g.addLayout(opt_row)

        self.combo_opt.currentIndexChanged.connect(self._on_opt_changed)

        layout.addWidget(grp)

        self.lbl_gpu = QtWidgets.QLabel()
        self.lbl_gpu.setStyleSheet("color: gray;")
        layout.addWidget(self.lbl_gpu)

        self.chk_gpu.toggled.connect(self.lbl_gpu.setVisible)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        self.btn_ok = QtWidgets.QPushButton("OK")
        self.btn_ok.clicked.connect(self._on_ok)
        self.btn_cancel = QtWidgets.QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_ok)
        btn_row.addWidget(self.btn_cancel)
        layout.addLayout(btn_row)

    def _load(self):
        opts = load_opts()
        self.combo_opt.blockSignals(True)
        self._set_combo(self.combo_opt, opts['optimize'])
        self.combo_opt.blockSignals(False)
        self.chk_gpu.setChecked(opts['gpu_decode'])
        self.chk_noaudio.setChecked(opts['audio_only'])
        self.lbl_gpu.setText("GPU: detecting...")
        self._detect_gpu()
        self.lbl_gpu.setVisible(opts['gpu_decode'])

    def _detect_gpu(self):
        def work():
            try:
                status = hwdec_status()
                QMetaObject.invokeMethod(
                    self, '_set_gpu_status', Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, status))
            except Exception:  # nosec B110
                pass
        threading.Thread(target=work, daemon=True).start()

    @QtCore.pyqtSlot(str)
    def _set_gpu_status(self, status):
        self.lbl_gpu.setText(status)

    def _on_opt_changed(self):
        if self.combo_opt.currentData() == 'low_spec':
            self.chk_noaudio.setChecked(True)

    def _on_ok(self):
        preset = self.combo_opt.currentData()
        opts = dict(_PRESETS[preset])
        opts['optimize'] = preset
        opts['gpu_decode'] = self.chk_gpu.isChecked()
        opts['audio_only'] = self.chk_noaudio.isChecked()
        save_opts(opts)
        self.accept()
