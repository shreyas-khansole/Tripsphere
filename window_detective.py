"""
TripSphere - Complete Window Detective
Combines Qt-level monkey-patching with Win32 native window enumeration.

Run: python window_detective.py
Then interact with the app (Search, Locate, Save, Plan, Route, Nearby, navigate pages).

Every new top-level window - whether Qt-managed or purely native - will be logged.
"""
import sys
import os
import ctypes
import ctypes.wintypes
import traceback as _tb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError as e:
    print(f"[ERROR] PySide6-WebEngine not found: {e}")
    sys.exit(1)

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget

# ── Win32 window scanner ──────────────────────────────────────────────────────
_user32 = ctypes.windll.user32
_SEEN_HWNDS: set = set()

def _get_process_windows(pid):
    wins = []
    def cb(hwnd, _):
        p = ctypes.c_ulong()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid:
            tbuf = ctypes.create_unicode_buffer(256)
            cbuf = ctypes.create_unicode_buffer(256)
            _user32.GetWindowTextW(hwnd, tbuf, 256)
            _user32.GetClassNameW(hwnd, cbuf, 256)
            rect = ctypes.wintypes.RECT()
            _user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            vis = bool(_user32.IsWindowVisible(hwnd))
            wins.append({'hwnd': hwnd, 'title': tbuf.value, 'class': cbuf.value,
                         'w': w, 'h': h, 'visible': vis})
        return True
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    _user32.EnumWindows(WNDENUMPROC(cb), 0)
    return wins

# ── Qt widget interceptor ─────────────────────────────────────────────────────
_SEEN_QWIDGETS: set = set()
_IGNORE = {'QMainWindow'}

def _check_widget(w: QWidget, trigger: str):
    wid = id(w)
    if wid in _SEEN_QWIDGETS:
        return
    try:
        if not w.isWindow():
            return
        py_cls = type(w).__name__
        qt_cls = w.metaObject().className()
        if py_cls in _IGNORE or qt_cls in _IGNORE:
            return
    except RuntimeError:
        return

    _SEEN_QWIDGETS.add(wid)
    try:
        geom = w.geometry()
        flags = w.windowFlags()
        parent = w.parentWidget()
        title = w.windowTitle()
    except RuntimeError:
        return

    stack = _tb.format_stack()
    print()
    print("=" * 70)
    print(f"[QT TOP-LEVEL WINDOW] trigger={trigger}")
    print(f"  Python: {py_cls}  Qt: {qt_cls}")
    print(f"  title={title!r}  geom={geom.width()}x{geom.height()}@{geom.x()},{geom.y()}")
    print(f"  flags={hex(int(flags))}  parent={parent!r}")
    print("  TRACEBACK:")
    for line in stack[:-2]:
        print("   ", line.rstrip())
    print("=" * 70)
    sys.stdout.flush()

_orig_show = QWidget.show
_orig_sv   = QWidget.setVisible

def _patch_show(self):
    _orig_show(self)
    _check_widget(self, "show()")

def _patch_sv(self, visible):
    _orig_sv(self, visible)
    if visible:
        _check_widget(self, "setVisible(True)")

QWidget.show = _patch_show
QWidget.setVisible = _patch_sv

# ── Win32 periodic scan ───────────────────────────────────────────────────────
_PID = os.getpid()

def _win32_scan():
    for win in _get_process_windows(_PID):
        hwnd = win['hwnd']
        if hwnd in _SEEN_HWNDS:
            continue
        _SEEN_HWNDS.add(hwnd)
        # Skip the main TripSphere window and WebEngine helper windows
        cls = win['class']
        if cls in ('Qt5152QWindowIcon', 'Qt6152QWindowIcon'):
            continue  # Qt's own hidden helper
        w = win['w']
        h = win['h']
        vis = win['visible']
        title = win['title']
        if vis or (80 <= w <= 300 and 30 <= h <= 150):
            print()
            print("=" * 70)
            print(f"[WIN32 WINDOW DETECTED]  HWND={hwnd}")
            print(f"  class={cls!r}  title={title!r}")
            print(f"  size={w}x{h}  visible={vis}")
            print("=" * 70)
            sys.stdout.flush()

def _periodic():
    app = QApplication.instance()
    if not app:
        return
    for w in app.topLevelWidgets():
        if w.isVisible():
            _check_widget(w, "periodic")
    _win32_scan()

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    from app.config import APP_NAME, APP_VERSION, get_app_stylesheet
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
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

    t = QTimer()
    t.timeout.connect(_periodic)
    t.start(200)

    print()
    print("=" * 70)
    print("WINDOW DETECTIVE ACTIVE")
    print(f"Process PID: {_PID}")
    print("Interact with TripSphere: Search, Save, Plan, Route, Nearby, Navigate")
    print("=" * 70)
    sys.stdout.flush()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
