"""
TripSphere — VISIBILITY CHANGE MONITOR
========================================
Monitors ALL existing HWNDs for the process AND new ones.
Reports when any window changes visibility (hidden -> visible).
This catches the case where Chrome_WidgetWin_0 becomes visible.

Run: python vis_monitor.py
Navigate to Explore and interact with map.
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
_PID = os.getpid()

def _get_process_hwnds(pid):
    result = {}
    def cb(hwnd, _):
        pid_c = ctypes.c_ulong()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_c))
        if pid_c.value == pid:
            tbuf = ctypes.create_unicode_buffer(512)
            cbuf = ctypes.create_unicode_buffer(256)
            _user32.GetWindowTextW(hwnd, tbuf, 512)
            _user32.GetClassNameW(hwnd, cbuf, 256)
            rect = ctypes.wintypes.RECT()
            _user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            parent = _user32.GetParent(hwnd)
            owner = _user32.GetWindow(hwnd, 4)
            visible = bool(_user32.IsWindowVisible(hwnd))
            result[hwnd] = {
                'title': tbuf.value, 'class': cbuf.value,
                'w': w, 'h': h, 'parent': parent, 'owner': owner,
                'visible': visible,
            }
        return True
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    _user32.EnumWindows(WNDENUMPROC(cb), 0)
    return result

_PREV_STATE: dict = {}
_REPORTED_NEW: set = set()

def _monitor():
    global _PREV_STATE
    current = _get_process_hwnds(_PID)

    for hwnd, info in current.items():
        prev = _PREV_STATE.get(hwnd)

        # New window
        if prev is None and hwnd not in _REPORTED_NEW:
            _REPORTED_NEW.add(hwnd)
            is_top = (info['parent'] == 0 and info['owner'] == 0)
            print()
            print("=" * 70)
            print(f"[NEW HWND={hwnd}]  top-level={is_top}")
            print(f"  class={info['class']!r}  title={info['title'][:60]!r}")
            print(f"  size={info['w']}x{info['h']}  visible={info['visible']}")
            print(f"  parent={info['parent']}  owner={info['owner']}")
            if is_top and info['visible']:
                print(f"  *** NEW VISIBLE TOP-LEVEL WINDOW ***")
            print("=" * 70)
            sys.stdout.flush()
            continue

        # Visibility change
        if prev and prev['visible'] != info['visible']:
            is_top = (info['parent'] == 0 and info['owner'] == 0)
            change = "hidden->VISIBLE" if info['visible'] else "visible->HIDDEN"
            print()
            print("=" * 70)
            print(f"[VISIBILITY CHANGE]  HWND={hwnd}  {change}")
            print(f"  class={info['class']!r}  title={info['title'][:60]!r}")
            print(f"  size={info['w']}x{info['h']}  top-level={is_top}")
            print(f"  parent={info['parent']}  owner={info['owner']}")
            if is_top and info['visible']:
                print(f"  *** THIS IS THE GHOST WINDOW — TOP-LEVEL BECAME VISIBLE ***")
            print("=" * 70)
            sys.stdout.flush()

        # Size change (window being shown/moved)
        if prev and (prev['w'] != info['w'] or prev['h'] != info['h']):
            if info['w'] > 0 and info['h'] > 0:
                is_top = (info['parent'] == 0)
                skip_classes = {
                    'Qt6112QWindowIcon', 'Qt6112ThemeChangeObserverWindow',
                    'Qt6112ScreenChangeObserverWindow', 'Base_PowerMessageWindow',
                    'UAC_InputIndicatorOverlayWnd', 'UAC Input Indicator',
                }
                if info['class'] not in skip_classes:
                    print()
                    print("-" * 50)
                    print(f"[SIZE CHANGE]  HWND={hwnd}  {prev['w']}x{prev['h']} -> {info['w']}x{info['h']}")
                    print(f"  class={info['class']!r}  title={info['title'][:40]!r}")
                    print(f"  visible={info['visible']}  top-level={is_top}")
                    print("-" * 50)
                    sys.stdout.flush()

    _PREV_STATE = current

# ── Also monitor newWindowRequested from ALL WebEngine pages ──────────────────
_orig_init_page = QWebEnginePage.__init__

def _patched_page_init(self, *args, **kwargs):
    _orig_init_page(self, *args, **kwargs)
    try:
        self.newWindowRequested.connect(_on_nwr)
        print(f"[PAGE] newWindowRequested connected: {type(self).__name__}")
        sys.stdout.flush()
    except Exception as e:
        pass

QWebEnginePage.__init__ = _patched_page_init

@Slot(QWebEngineNewWindowRequest)
def _on_nwr(request):
    print()
    print("!" * 70)
    print(f"[newWindowRequested FIRED]")
    print(f"  destination={request.destination()}")
    print(f"  url={request.requestedUrl().toString()}")
    print(f"  userInitiated={request.isUserInitiated()}")
    print("!" * 70)
    sys.stdout.flush()
    # DO NOT call openIn() — this blocks the new window

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

    # Take initial snapshot
    _PREV_STATE.update(_get_process_hwnds(_PID))
    for hwnd, info in sorted(_PREV_STATE.items()):
        is_top = (info['parent'] == 0 and info['owner'] == 0)
        mark = "TOP" if is_top else "CHD"
        print(f"[{mark}] HWND={hwnd:10d}  vis={int(info['visible'])}  "
              f"{info['w']:5d}x{info['h']:4d}  class={info['class']!r:40s}  "
              f"title={info['title'][:30]!r}")
    sys.stdout.flush()

    print()
    print("=" * 70)
    print(f"VISIBILITY MONITOR ACTIVE  PID={_PID}")
    print("Navigate to Explore then interact with map.")
    print("Any window visibility change will be reported.")
    print("=" * 70)
    sys.stdout.flush()

    t = QTimer()
    t.timeout.connect(_monitor)
    t.start(150)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
