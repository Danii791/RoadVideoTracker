# -*- coding: utf-8 -*-
import os
import re
import json
import hashlib
import secrets
import shutil
import subprocess  # nosec
import threading
import time
import ctypes
import urllib.request
from qgis.PyQt.QtCore import QProcess, QTimer

MPV_API_URL = (
    'https://api.github.com/repos/shinchiro/mpv-winbuild-cmake/'
    'releases/latest')
MPV_PINNED_URL = (
    'https://github.com/shinchiro/mpv-winbuild-cmake/releases/download/'
    '20261111/mpv-x86_64-20261111-git-bcde6b93cc.7z')
MPV_PINNED_SHA256 = (
    'f259b5fd4b5c395617c948a4fadcdf55bba1c5282fb7c13e88626b3f71072baf')  # pragma: allowlist secret
MPV_URL = MPV_PINNED_URL

_SETTINGS_PREFIX = 'road_video_tracker/'
_URL_CACHE_TTL = 7 * 24 * 3600
_ASSET_RE = re.compile(r'^mpv-x86_64-\d{8}-git-[0-9a-f]+\.7z$')
_MPV_CHECK_CACHE = {}
_GPU_CACHE = None


def _settings():
    from qgis.core import QgsSettings
    return QgsSettings()


def mpv_cache_dir():
    from qgis.core import QgsApplication
    return os.path.join(QgsApplication.qgisSettingsDirPath(), 'mpv')


def resolve_mpv_asset(force=False):
    s = _settings()
    now = int(time.time())
    url = s.value(_SETTINGS_PREFIX + 'mpv_url', '', type=str)
    sha = s.value(_SETTINGS_PREFIX + 'mpv_sha256', '', type=str)
    ts = s.value(_SETTINGS_PREFIX + 'mpv_url_ts', 0, type=int)
    if not force and url and sha and ts and now - ts < _URL_CACHE_TTL:
        return url, sha
    try:
        req = urllib.request.Request(
            MPV_API_URL,
            headers={'User-Agent': 'RoadVideoTracker',
                     'Accept': 'application/vnd.github+json'})
        with urllib.request.urlopen(req, timeout=20) as r:  # nosec
            payload = json.loads(r.read().decode('utf-8'))
        for asset in payload.get('assets', []):
            name = asset.get('name', '')
            if not _ASSET_RE.match(name):
                continue
            download_url = asset.get('browser_download_url', '')
            digest = asset.get('digest', '')
            if not download_url or not digest.startswith('sha256:'):
                continue
            sha = digest.split(':', 1)[1].strip().lower()
            s.setValue(_SETTINGS_PREFIX + 'mpv_url', download_url)
            s.setValue(_SETTINGS_PREFIX + 'mpv_sha256', sha)
            s.setValue(_SETTINGS_PREFIX + 'mpv_url_ts', now)
            return download_url, sha
    except Exception:  # nosec
        pass
    return MPV_PINNED_URL, MPV_PINNED_SHA256


def _mpv_usable(path):
    try:
        st = os.stat(path)
    except OSError:
        return False
    key = (path, st.st_size, st.st_mtime)
    if key in _MPV_CHECK_CACHE:
        return _MPV_CHECK_CACHE[key]
    ok = False
    try:
        p = subprocess.run([path, '--version'],  # nosec
                           stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT,
                           timeout=10)
        ok = p.returncode == 0 and b'mpv' in p.stdout[:4096].lower()
    except Exception:  # nosec
        ok = False
    _MPV_CHECK_CACHE[key] = ok
    return ok


def find_mpv():
    d = os.path.dirname(os.path.abspath(__file__))
    for p in [os.path.join(d, 'mpv.exe'),
              os.path.join(d, 'mpv', 'mpv.exe'),
              os.path.join(mpv_cache_dir(), 'mpv.exe')]:
        if os.path.exists(p) and _mpv_usable(p):
            return p
    found = shutil.which('mpv')
    if found and _mpv_usable(found):
        return found
    return None


def mpv_version(path=None):
    exe = path or find_mpv()
    if not exe:
        return ''
    try:
        out = subprocess.run([exe, '--version'],  # nosec
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             timeout=10).stdout
        return out.decode('utf-8', 'replace').splitlines()[0].strip()
    except Exception:  # nosec
        return ''


def remove_cached_mpv():
    d = mpv_cache_dir()
    removed = []
    for name in ('mpv.exe', 'mpv.7z'):
        p = os.path.join(d, name)
        try:
            if os.path.exists(p):
                os.remove(p)
                removed.append(name)
        except Exception:  # nosec
            pass
    return removed


def detect_gpus():
    global _GPU_CACHE
    if _GPU_CACHE is not None:
        return _GPU_CACHE
    names = []
    try:
        import winreg
        base = (r'SYSTEM\CurrentControlSet\Control\Class'
                r'\{4d36e968-e325-11ce-bfc1-08002be10318}')
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as key:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(key, i)
                except OSError:
                    break
                try:
                    with winreg.OpenKey(
                            winreg.HKEY_LOCAL_MACHINE,
                            base + '\\' + sub) as sk:
                        desc, _ = winreg.QueryValueEx(sk, 'DriverDesc')
                    if desc and desc not in names:
                        names.append(desc)
                except OSError:
                    pass
                i += 1
    except Exception:
        names = []
    _GPU_CACHE = names
    return names


def hwdec_status():
    names = detect_gpus()
    if names:
        return "GPU: " + ", ".join(names) + " (hwdec=auto)"
    exe = find_mpv()
    if not exe:
        return "mpv not found"
    return "hwdec=auto (GPU not detected)"


def _extract(archive, target):
    exe7z = shutil.which('7z') or shutil.which('7za')
    if exe7z:
        subprocess.run([exe7z, 'x', archive,  # nosec
                        '-o' + target, '-y'],
                       check=True, capture_output=True, timeout=180)
        return
    tar = shutil.which('tar')
    if not tar:
        raise RuntimeError(
            'No 7z or tar executable found to extract mpv. '
            'Install 7-Zip or use Windows 10/11.')
    subprocess.run([tar, '-xf', archive, '-C', target],  # nosec
                   check=True, capture_output=True, timeout=180)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def download_mpv(url, target_dir, status_cb=None, sha256=None):
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
        if sha256:
            if status_cb:
                status_cb('Verifying mpv...')
            if _sha256(archive).lower() != sha256.lower():
                raise RuntimeError('mpv checksum mismatch')
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
    if not _mpv_usable(exe):
        raise RuntimeError('mpv.exe failed validation after extraction')
    return exe


def download_mpv_async(url, sha256, target_dir, on_progress, on_done):
    def worker():
        ok, err = False, ''
        try:
            download_mpv(url, target_dir, on_progress, sha256)
            ok, err = True, None
        except Exception as e:
            err = str(e)
            if '404' in err:
                try:
                    new_url, new_sha = resolve_mpv_asset(force=True)
                    on_progress('Retrying mpv download...')
                    download_mpv(new_url, target_dir, on_progress, new_sha)
                    ok, err = True, None
                except Exception as e2:
                    err = str(e2)
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
        self.last_error = ''
        self._stderr = b''

    @staticmethod
    def build_args(hwnd, filepath, opts=None, pipe_name=''):
        opts = opts or {}
        audio_only = bool(opts.get('audio_only'))
        sync = 'display-resample' if audio_only or \
            opts.get('sync_mode') == 'display' else 'audio'
        drop = opts.get('framedrop', 'vo')
        if drop not in ('vo', 'decoder', 'no'):
            drop = 'vo'
        cache_mb = int(opts.get('cache_mb', 50))
        read = int(opts.get('readahead_sec', 0) or 0)
        audio_buffer = float(opts.get('audio_buffer', 0.0) or 0.0)
        args = [
            '--no-terminal', '--no-config', '--no-osc', '--no-osd-bar',
            '--osd-level=0', '--no-input-default-bindings',
            '--hr-seek=absolute', '--hr-seek-framedrop=yes',
            '--vo=gpu', f'--wid={hwnd}', '--pause', '--keep-open=yes',
            '--profile=low-latency',
            '--vd-lavc-threads=0',
            '--cache=yes',
            '--demuxer-max-bytes=%dMiB' % cache_mb,
            '--framedrop=' + drop,
            '--video-sync=' + sync,
        ]
        if read > 0:
            args.append('--demuxer-readahead-secs=%d' % read)
        if audio_buffer > 0:
            args.append('--audio-buffer=%s' % audio_buffer)
        if audio_only:
            args.append('--no-audio')
        if pipe_name:
            args.append(f'--input-ipc-server={pipe_name}')
        if opts.get('gpu_decode'):
            args.append('--hwdec=auto-safe')
        args.append(filepath)
        return args

    def launch(self, hwnd, filepath, opts=None):
        self.last_error = ''
        exe = find_mpv()
        if not exe:
            cached = os.path.join(mpv_cache_dir(), 'mpv.exe')
            self.last_error = (
                'mpv.exe found but not usable'
                if os.path.exists(cached) else 'mpv not found')
            return False

        pipe_name = (
            r'\\.\pipe\mpv-'
            + str(os.getpid())
            + '-'
            + str(secrets.randbelow(90000) + 10000))

        self.proc = QProcess()
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.proc.setReadChannel(QProcess.ProcessChannel.StandardOutput)

        args = self.build_args(hwnd, filepath, opts, pipe_name)
        self.proc.start(exe, args)
        if not self.proc.waitForStarted(10000):
            self.last_error = 'mpv failed to start: ' + \
                str(self.proc.errorString())
            return False
        self.proc.readyReadStandardError.connect(self._read_stderr)

        if not self._connect_pipe(pipe_name):
            self.last_error = 'mpv IPC not connected'
            return False

        self._read_timer = QTimer()
        self._read_timer.timeout.connect(self._read_pipe)
        self._read_timer.start(50)
        return True

    def _read_stderr(self):
        try:
            data = bytes(self.proc.readAllStandardError())
            self._stderr = (self._stderr + data)[-4000:]
        except Exception:  # nosec
            pass

    def stderr_tail(self):
        return self._stderr.decode('utf-8', 'replace')

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
