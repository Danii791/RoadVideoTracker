# -*- coding: utf-8 -*-
import os
import json
import secrets
import shutil
import subprocess  # nosec
import threading
import time
import ctypes
import urllib.request
from qgis.PyQt.QtCore import QProcess, QTimer

MPV_URL = (
    'https://github.com/shinchiro/mpv-winbuild-cmake/releases/download/'
    '20260610/mpv-x86_64-20260610-git-304426c.7z')


def mpv_cache_dir():
    from qgis.core import QgsApplication
    return os.path.join(QgsApplication.qgisSettingsDirPath(), 'mpv')


def find_mpv():
    d = os.path.dirname(os.path.abspath(__file__))
    for p in [os.path.join(d, 'mpv.exe'),
              os.path.join(d, 'mpv', 'mpv.exe')]:
        if os.path.exists(p):
            return p
    cached = os.path.join(mpv_cache_dir(), 'mpv.exe')
    if os.path.exists(cached):
        return cached
    found = shutil.which('mpv')
    if found:
        return found
    return None


def _extract(archive, target):
    exe7z = shutil.which('7z') or shutil.which('7za')
    if exe7z:
        subprocess.run([exe7z, 'x', archive,  # nosec
                        '-o' + target, '-y'],
                       check=True, capture_output=True, timeout=180)
        return
    tar = shutil.which('tar')
    if not tar:
        raise RuntimeError('tar executable not found')
    subprocess.run([tar, '-xf', archive, '-C', target],  # nosec
                   check=True, capture_output=True, timeout=180)


def download_mpv(url, target_dir, status_cb=None):
    if status_cb:
        status_cb('Downloading mpv... 0%')
    os.makedirs(target_dir, exist_ok=True)
    archive = os.path.join(target_dir, 'mpv.7z')
    try:
        req = urllib.request.Request(
            url, headers={'User-Agent': 'RoadVideoTracker'})
        with urllib.request.urlopen(req, timeout=120) as r:  # nosec
            total = int(r.headers.get('Content-Length') or 0)
            done = 0
            last_pct = -1
            with open(archive, 'wb') as f:
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total and status_cb:
                        pct = int(done * 100 / total)
                        if pct != last_pct:
                            last_pct = pct
                            status_cb(
                                'Downloading mpv... %d%%' % pct)
        if status_cb:
            status_cb('Extracting mpv...')
        _extract(archive, target_dir)
    except Exception:
        raise
    finally:
        try:
            if os.path.exists(archive):
                os.remove(archive)
        except Exception:  # nosec
            pass
    exe = os.path.join(target_dir, 'mpv.exe')
    if not os.path.exists(exe):
        raise RuntimeError('mpv.exe not found after extraction')
    return exe


def download_mpv_async(url, target_dir, on_progress, on_done):
    def worker():
        try:
            download_mpv(url, target_dir, on_progress)
            ok, err = True, None
        except Exception as e:
            ok, err = False, str(e)
        on_done(ok, err)
    threading.Thread(target=worker, daemon=True).start()


class MpvController:

    def __init__(self):
        self.proc = None
        self._buf = b''
        self._rid = 0
        self._callbacks = {}
        self._pipe_handle = None
        self._read_timer = None

    def launch(self, hwnd, filepath):
        exe = find_mpv()
        if not exe:
            return False

        pipe_name = (
            r'\\.\pipe\mpv-'
            + str(os.getpid())
            + '-'
            + str(secrets.randbelow(90000) + 10000))

        self.proc = QProcess()
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.proc.setReadChannel(QProcess.ProcessChannel.StandardOutput)

        args = [
            '--no-terminal', '--no-config', '--no-osc', '--no-osd-bar',
            '--osd-level=0', '--no-input-default-bindings',
            '--hr-seek=absolute', '--hr-seek-framedrop=no',
            '--vo=gpu', f'--wid={hwnd}', '--pause', '--keep-open=yes',
            '--profile=low-latency',
            '--cache=yes', '--demuxer-max-bytes=50MiB',
            '--framedrop=vo', '--video-sync=audio',
            f'--input-ipc-server={pipe_name}',
            filepath
        ]
        self.proc.start(exe, args)
        if not self.proc.waitForStarted(10000):
            return False

        if not self._connect_pipe(pipe_name):
            return False

        self._read_timer = QTimer()
        self._read_timer.timeout.connect(self._read_pipe)
        self._read_timer.start(50)
        return True

    def _connect_pipe(self, pipe_name):
        for i in range(100):
            handle = ctypes.windll.kernel32.CreateFileW(
                pipe_name,
                0xC0000000,
                0,
                None,
                3,
                0,
                None)
            if handle != -1:
                self._pipe_handle = handle
                return True
            time.sleep(0.05)
        return False

    def _read_pipe(self):
        if not self._pipe_handle:
            return

        available = ctypes.c_ulong(0)
        ok = ctypes.windll.kernel32.PeekNamedPipe(
            self._pipe_handle, None, 0, None, ctypes.byref(available), None)
        if not ok or available.value == 0:
            return

        buf = ctypes.create_string_buffer(available.value)
        read = ctypes.c_ulong(0)
        ok = ctypes.windll.kernel32.ReadFile(
            self._pipe_handle, buf, available.value, ctypes.byref(read), None)
        if not ok or read.value == 0:
            return

        self._buf += buf.raw[:read.value]
        while b'\n' in self._buf:
            line, self._buf = self._buf.split(b'\n', 1)
            try:
                data = json.loads(line)
                rid = data.get('request_id')
                if rid is not None:
                    cb = self._callbacks.pop(rid, None)
                    if cb:
                        cb(data.get('data'))
            except Exception:  # nosec
                pass

    def send(self, *args):
        if not self._pipe_handle:
            return
        try:
            cmd = json.dumps({'command': list(args)}) + '\n'
            written = ctypes.c_ulong(0)
            ctypes.windll.kernel32.WriteFile(
                self._pipe_handle,
                cmd.encode(),
                len(cmd.encode()),
                ctypes.byref(written),
                None)
        except Exception:  # nosec
            pass

    def req(self, *args, cb=None):
        if not self._pipe_handle:
            return -1
        self._rid += 1
        rid = self._rid
        try:
            msg = json.dumps(
                {'command': list(args), 'request_id': rid}) + '\n'
            written = ctypes.c_ulong(0)
            ctypes.windll.kernel32.WriteFile(
                self._pipe_handle,
                msg.encode(),
                len(msg.encode()),
                ctypes.byref(written),
                None)
            if cb:
                self._callbacks[rid] = cb
        except Exception:
            return -1
        return rid

    def play(self):
        self.send('set_property', 'pause', False)

    def pause(self):
        self.send('set_property', 'pause', True)

    def toggle(self):
        self.send('cycle', 'pause')

    def seek(self, seconds):
        self.send('seek', seconds, 'absolute')

    def seek_rel(self, seconds):
        self.send('seek', seconds, 'relative')

    def frame_step(self):
        self.send('frame-step')

    def frame_back(self):
        self.send('frame-back-step')

    def mute(self, muted):
        self.send('set_property', 'mute', muted)

    def stop(self):
        if self._read_timer:
            self._read_timer.stop()
            self._read_timer = None
        if self._pipe_handle:
            ctypes.windll.kernel32.CloseHandle(self._pipe_handle)
            self._pipe_handle = None
        if self.proc and self.proc.state() == QProcess.ProcessState.Running:
            self.send('quit')
            self.proc.kill()
            self.proc.waitForFinished()
            self.proc = None
