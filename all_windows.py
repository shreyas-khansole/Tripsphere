"""
TripSphere — GLOBAL WINDOW SCAN (ALL PROCESSES)
================================================
Scans ALL top-level windows on the desktop, not filtered by PID.
Stores baseline, then reports any NEW window that appears.
This will catch Chromium child process windows.

Run: python all_windows.py
Navigate to Explore and interact with map.
The ghost window WILL be caught.
"""
from __future__ import annotations
import sys
import os
import ctypes
import ctypes.wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError as e:
    print(f"[ERROR] {e}")
    sys.exit(1)

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineNewWindowRequest
from PySide6.QtWidgets import QApplication, QWidget

_user32 = ctypes.windll.user32

def _get_all_toplevel() -> dict:
    """Get ALL top-level windows on the entire desktop."""
    result = {}
    def cb(hwnd, _):
        tbuf = ctypes.create_unicode_buffer(512)
        cbuf = ctypes.create_unicode_buffer(256)
        _user32.GetWindowTextW(hwnd, tbuf, 512)
        _user32.GetClassNameW(hwnd, cbuf, 256)
        rect = ctypes.wintypes.RECT()
        _user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        pid_c = ctypes.c_ulong()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_c))
        owner  = _user32.GetWindow(hwnd, 4)
        visible = bool(_user32.IsWindowVisible(hwnd))
        result[hwnd] = {
            'pid': pid_c.value,
            'title': tbuf.value, 'class': cbuf.value,
            'w': w, 'h': h, 'owner': owner, 'visible': visible,
        }
        return True
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    _user32.EnumWindows(WNDENUMPROC(cb), 0)
    return result

_BASELINE: dict = {}
_REPORTED: set = set()
_PID = os.getpid()

# Known system-level classes to skip (not from our app)
_SKIP_CLASSES = {
    'Shell_TrayWnd', 'Shell_SecondaryTrayWnd', 'Progman', 'WorkerW',
    'DV2ControlHost', 'MsgrIMEWindowClass', 'SysShadow', 'tooltips_class32',
    'IME', 'MSCTFIME UI', 'CabinetWClass', 'ExploreWClass',
    'Windows.UI.Core.CoreWindow', 'ApplicationFrameWindow',
    '#32769',  # desktop
    'ForegroundStaging', 'EdgeUiInputTopWndClass',
}

def _is_interesting(info: dict) -> bool:
    cls = info['class']
    if cls in _SKIP_CLASSES:
        return False
    if cls.startswith('Windows.') or cls.startswith('HwndWrapper'):
        return False
    return True

def _take_baseline():
    global _BASELINE
    _BASELINE = _get_all_toplevel()
    print(f"\n>>> GLOBAL BASELINE: {len(_BASELINE)} top-level windows")
    # Print only potentially relevant ones
    for hwnd, info in sorted(_BASELINE.items()):
        if info['pid'] == _PID or 'Chrome' in info['class'] or 'Qt6' in info['class'] or 'TripSphere' in info['title']:
            print(f"  HWND={hwnd:10d}  pid={info['pid']:7d}  vis={int(info['visible'])}  "
                  f"{info['w']:5d}x{info['h']:4d}  class={info['class']!r:40s}  title={info['title'][:30]!r}")
    print(">>> Interact with map NOW <<<\n")
    sys.stdout.flush()

def _scan():
    if not _BASELINE:
        return
    current = _get_all_toplevel()
    for hwnd, info in current.items():
        if hwnd in _BASELINE or hwnd in _REPORTED:
            continue
        _REPORTED.add(hwnd)
        if not _is_interesting(info):
            continue
        print()
        print("=" * 70)
        print(f"[*** NEW TOP-LEVEL WINDOW ***]  HWND={hwnd}  pid={info['pid']}")
        print(f"  class={info['class']!r}")
        print(f"  title={info['title']!r}")
        print(f"  size={info['w']}x{info['h']}  visible={info['visible']}")
        print(f"  owner_hwnd={info['owner']}")
        if info['pid'] == _PID:
            print(f"  *** SAME PROCESS as TripSphere ***")
        else:
            print(f"  *** DIFFERENT PROCESS (PID={info['pid']}, main={_PID}) ***")
        print("=" * 70)
        sys.stdout.flush()
    # Check visibility changes
    for hwnd, info in current.items():
        prev = _BASELINE.get(hwnd)
        if prev and prev['visible'] != info['visible'] and info['visible']:
            if not _is_interesting(info):
                continue
            print()
            print("=" * 70)
            print(f"[BECAME VISIBLE]  HWND={hwnd}  pid={info['pid']}")
            print(f"  class={info['class']!r}  title={info['title']!r}")
            print(f"  size={info['w']}x{info['h']}")
            if info['pid'] == _PID:
                print(f"  *** SAME PROCESS as TripSphere ***")
            else:
                print(f"  *** DIFFERENT PROCESS (PID={info['pid']}, main={_PID}) ***")
            print("=" * 70)
            sys.stdout.flush()
            _BASELINE[hwnd] = info

# ── Patch QWebEnginePage globally ─────────────────────────────────────────────
_orig_page_init = QWebEnginePage.__init__

def _patched_page_init(self, *args, **kwargs):
    _orig_page_init(self, *args, **kwargs)
    try:
        self.newWindowRequested.connect(_on_nwr)
        print(f"[PAGE PATCHED] {type(self).__name__}")
        sys.stdout.flush()
    except Exception:
        pass

QWebEnginePage.__init__ = _patched_page_init

@Slot(QWebEngineNewWindowRequest)
def _on_nwr(request):
    print()
    print("!" * 70)
    print(f"[newWindowRequested FIRED]  dest={request.destination()}  url={request.requestedUrl().toString()}")
    print("!" * 70)
    sys.stdout.flush()
    # Do NOT call openIn() — this blocks the window

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
    print(f"GLOBAL WINDOW SCAN  PID={_PID}")
    print()
    print("INSTRUCTIONS:")
    print("1. Skip the globe (click Skip or search anything)")
    print("2. Navigate to EXPLORE")
    print("3. Wait 3 seconds for map to load")
    print("4. Wait for 'Interact with map NOW' message (auto at 10 sec)")
    print("5. Click map, zoom, pan")
    print("6. Watch this console for the ghost window")
    print("=" * 70)
    sys.stdout.flush()

    # Take baseline at 10 seconds
    QTimer.singleShot(10000, _take_baseline)

    scan_timer = QTimer()
    scan_timer.timeout.connect(_scan)
    scan_timer.start(100)  # 100ms for faster detection

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
