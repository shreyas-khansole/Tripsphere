"""
TripSphere — TARGETED MAP DIAGNOSTIC
======================================
Adds logging to MapView and also scans ALL processes' windows.
Specifically designed to catch the ghost window by scanning ALL PIDs,
not just the current process.

Run: python map_diag.py
Navigate to Explore and interact with map.
"""
from __future__ import annotations
import sys
import os
import ctypes
import ctypes.wintypes
import subprocess
import traceback as _tb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError as e:
    print(f"[ERROR] {e}")
    sys.exit(1)

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QWindow
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineNewWindowRequest
from PySide6.QtWidgets import QApplication, QWidget

_user32 = ctypes.windll.user32
_PID = os.getpid()

# ── Get all TripSphere-related PIDs ───────────────────────────────────────────
def _get_related_pids():
    """Get this process PID plus all child processes (Chromium renderer etc)."""
    pids = {_PID}
    try:
        result = subprocess.run(
            ['wmic', 'process', 'where', f'ParentProcessId={_PID}',
             'get', 'ProcessId'],
            capture_output=True, text=True, timeout=3
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.isdigit():
                pids.add(int(line))
    except Exception:
        pass
    return pids

# ── Win32 window enumeration for all PIDs ─────────────────────────────────────
def _get_all_windows(pids):
    result = {}
    def cb(hwnd, _):
        pid_c = ctypes.c_ulong()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_c))
        if pid_c.value in pids:
            tbuf = ctypes.create_unicode_buffer(512)
            cbuf = ctypes.create_unicode_buffer(256)
            _user32.GetWindowTextW(hwnd, tbuf, 512)
            _user32.GetClassNameW(hwnd, cbuf, 256)
            rect = ctypes.wintypes.RECT()
            _user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            parent  = _user32.GetParent(hwnd)
            owner   = _user32.GetWindow(hwnd, 4)
            visible = bool(_user32.IsWindowVisible(hwnd))
            result[hwnd] = {
                'pid': pid_c.value,
                'title': tbuf.value, 'class': cbuf.value,
                'w': w, 'h': h,
                'parent': parent, 'owner': owner, 'visible': visible,
            }
        return True
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    _user32.EnumWindows(WNDENUMPROC(cb), 0)
    return result

_BASELINE: dict = {}
_REPORTED: set = set()
_RELATED_PIDS: set = set()

def _take_baseline():
    global _BASELINE, _RELATED_PIDS
    _RELATED_PIDS = _get_related_pids()
    _BASELINE = _get_all_windows(_RELATED_PIDS)
    print(f"\n>>> BASELINE: {len(_BASELINE)} windows, PIDs={sorted(_RELATED_PIDS)}")
    for hwnd, info in sorted(_BASELINE.items()):
        is_top = (info['parent'] == 0 and info['owner'] == 0)
        mark = "TOP" if is_top else "CHD"
        print(f"  [{mark}] HWND={hwnd:10d}  pid={info['pid']:7d}  "
              f"vis={int(info['visible'])}  {info['w']:5d}x{info['h']:4d}  "
              f"class={info['class']!r:40s}  title={info['title'][:30]!r}")
    print(">>> Interact with map NOW <<<\n")
    sys.stdout.flush()

def _scan():
    if not _BASELINE:
        # Auto-scan after 5 seconds
        return
    _RELATED_PIDS.update(_get_related_pids())
    current = _get_all_windows(_RELATED_PIDS)
    for hwnd, info in current.items():
        if hwnd in _BASELINE or hwnd in _REPORTED:
            continue
        _REPORTED.add(hwnd)
        is_top = (info['parent'] == 0 and info['owner'] == 0)
        print()
        print("=" * 70)
        print(f"[*** NEW WINDOW ***]  HWND={hwnd}  pid={info['pid']}")
        print(f"  class={info['class']!r}")
        print(f"  title={info['title']!r}")
        print(f"  size={info['w']}x{info['h']}  visible={info['visible']}")
        print(f"  parent_hwnd={info['parent']}  owner_hwnd={info['owner']}")
        if is_top:
            print(f"  *** TOP-LEVEL WINDOW (parent=0, owner=0) ***")
        print("=" * 70)
        sys.stdout.flush()
    # Also check visibility changes
    for hwnd, info in current.items():
        prev = _BASELINE.get(hwnd)
        if prev and prev['visible'] != info['visible'] and info['visible']:
            is_top = (info['parent'] == 0 and info['owner'] == 0)
            print()
            print("=" * 70)
            print(f"[BECAME VISIBLE]  HWND={hwnd}  pid={info['pid']}")
            print(f"  class={info['class']!r}  title={info['title']!r}")
            print(f"  size={info['w']}x{info['h']}  top-level={is_top}")
            print("=" * 70)
            sys.stdout.flush()
            _BASELINE[hwnd] = info  # update to avoid re-reporting

# ── Patch QWebEnginePage to log ALL new-window events ────────────────────────
_orig_page_init = QWebEnginePage.__init__

def _patched_page_init(self, *args, **kwargs):
    _orig_page_init(self, *args, **kwargs)
    try:
        self.newWindowRequested.connect(_on_nwr)
        print(f"[PAGE CREATED & PATCHED] {type(self).__name__}")
        sys.stdout.flush()
    except Exception:
        pass

QWebEnginePage.__init__ = _patched_page_init

@Slot(QWebEngineNewWindowRequest)
def _on_nwr(request):
    print()
    print("!" * 70)
    print(f"[newWindowRequested FIRED!]")
    print(f"  class={type(request).__name__}")
    print(f"  destination={request.destination()}")
    print(f"  url={request.requestedUrl().toString()}")
    print(f"  userInitiated={request.isUserInitiated()}")
    print("!" * 70)
    sys.stdout.flush()
    # Do NOT call openIn()

# ── Also patch QWidget.show to catch any new widget being shown ───────────────
_orig_widget_show = QWidget.show
_SEEN_WIDGETS: set = set()

def _patched_widget_show(self):
    _orig_widget_show(self)
    wid = id(self)
    if wid in _SEEN_WIDGETS:
        return
    try:
        if not self.isWindow():
            return
        cls = type(self).__name__
        qt_cls = self.metaObject().className()
        if cls in ('MainWindow', 'QSplashScreen'):
            return
    except RuntimeError:
        return
    _SEEN_WIDGETS.add(wid)
    try:
        title = self.windowTitle()
        geom = self.geometry()
        parent = self.parentWidget()
        flags = self.windowFlags()
    except RuntimeError:
        return
    print()
    print("=" * 70)
    print(f"[QWIDGET TOP-LEVEL SHOWN]  {cls}  Qt:{qt_cls}")
    print(f"  title={title!r}  geom={geom.width()}x{geom.height()}")
    print(f"  flags={hex(int(flags))}  parent={parent!r}")
    print("  STACK:")
    for line in _tb.format_stack()[:-2]:
        print("   ", line.rstrip())
    print("=" * 70)
    sys.stdout.flush()

QWidget.show = _patched_widget_show

# Auto-baseline after 8 seconds
_AUTO_BASELINE_DONE = False
def _auto_baseline():
    global _AUTO_BASELINE_DONE
    if not _AUTO_BASELINE_DONE and not _BASELINE:
        _AUTO_BASELINE_DONE = True
        _take_baseline()

def main():
    from app.config import APP_NAME, APP_VERSION, get_app_stylesheet
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-logging --no-sandbox")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("TripSphere")
    app.setStyleSheet(get_app_stylesheet())

    from app.database.models import initialize_database
    from app.database.seed_data import run_seed
    initialize_database()
    run_seed()

    from app.ui.main_window import MainWindow
    mw = MainWindow()

    import socket
    try:
        socket.setdefaulttimeout(2)
        socket.create_connection(("8.8.8.8", 53))
    except OSError:
        mw.show_offline_indicator(True)

    mw.showMaximized()
    mw.raise_()
    mw.activateWindow()

    print()
    print("=" * 70)
    print(f"TARGETED MAP DIAGNOSTIC  PID={_PID}")
    print("Pages will be auto-patched for newWindowRequested")
    print()
    print("INSTRUCTIONS:")
    print("1. Let startup globe load")
    print("2. Skip to Explore screen")  
    print("3. Let the MAP fully load (tiles appear)")
    print("4. Wait for the baseline to auto-capture (8 seconds after start)")
    print("5. THEN interact with map: click, zoom, pan")
    print("6. Watch this console")
    print("=" * 70)
    sys.stdout.flush()

    # Auto-take baseline after 8 seconds
    QTimer.singleShot(8000, _auto_baseline)

    # Scan every 200ms
    scan_timer = QTimer()
    scan_timer.timeout.connect(_scan)
    scan_timer.start(200)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
