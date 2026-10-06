"""
TripSphere — HWND SNAPSHOT DIAGNOSTIC
=======================================
Takes a Win32 HWND snapshot at startup, then prints ONLY new HWNDs
that appear after that point. Uses parent HWND to distinguish true
top-level windows from child/helper windows.

Also hooks QWebEngineView's page to log newWindowRequested events.

Run: python hwnd_snap.py
1. App opens — startup globe shows
2. ENTER key pressed in console = take baseline snapshot
3. Navigate to Explore
4. Interact with map (click, zoom, pan)
5. New windows are printed automatically every 200ms
"""
from __future__ import annotations
import sys
import os
import ctypes
import ctypes.wintypes
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError as e:
    print(f"[ERROR] PySide6-WebEngine not found: {e}")
    sys.exit(1)

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineNewWindowRequest
from PySide6.QtWidgets import QApplication, QWidget

_user32 = ctypes.windll.user32
_PID = os.getpid()

def _get_all_hwnds_for_pid(pid: int) -> dict:
    """Returns dict of hwnd -> info for ALL windows (top+child) of this PID."""
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
            style    = _user32.GetWindowLongW(hwnd, -16)
            ex_style = _user32.GetWindowLongW(hwnd, -20)
            parent   = _user32.GetParent(hwnd)
            owner    = _user32.GetWindow(hwnd, 4)  # GW_OWNER
            visible  = bool(_user32.IsWindowVisible(hwnd))
            result[hwnd] = {
                'hwnd': hwnd, 'title': tbuf.value, 'class': cbuf.value,
                'w': w, 'h': h, 'style': hex(style & 0xFFFFFFFF),
                'ex_style': hex(ex_style & 0xFFFFFFFF),
                'parent': parent, 'owner': owner, 'visible': visible,
            }
        return True
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    _user32.EnumWindows(WNDENUMPROC(cb), 0)
    return result

_BASELINE: dict = {}
_BASELINE_TAKEN = False
_SCAN_LOCK = threading.Lock()

def _take_baseline():
    global _BASELINE, _BASELINE_TAKEN
    _BASELINE = _get_all_hwnds_for_pid(_PID)
    _BASELINE_TAKEN = True
    print(f"\n>>> BASELINE TAKEN: {len(_BASELINE)} HWNDs")
    for hwnd, info in sorted(_BASELINE.items()):
        is_toplevel = (info['parent'] == 0)
        mark = "[TOP]" if is_toplevel else "[CHD]"
        print(f"  {mark} HWND={hwnd}  class={info['class']!r}  "
              f"size={info['w']}x{info['h']}  vis={info['visible']}  "
              f"title={info['title'][:40]!r}")
    print(">>> Navigate to Explore and interact with map now!\n")
    sys.stdout.flush()

_REPORTED: set = set()

def _scan_for_new():
    if not _BASELINE_TAKEN:
        return
    current = _get_all_hwnds_for_pid(_PID)
    for hwnd, info in current.items():
        if hwnd in _BASELINE or hwnd in _REPORTED:
            continue
        _REPORTED.add(hwnd)
        is_toplevel = (info['parent'] == 0)
        is_visible  = info['visible']
        print()
        print("=" * 70)
        print(f"[NEW HWND AFTER BASELINE]  HWND={hwnd}")
        print(f"  class={info['class']!r}  title={info['title']!r}")
        print(f"  size={info['w']}x{info['h']}  visible={is_visible}")
        print(f"  style={info['style']}  ex_style={info['ex_style']}")
        print(f"  parent_hwnd={info['parent']}  owner_hwnd={info['owner']}")
        if is_toplevel:
            print(f"  *** THIS IS A TOP-LEVEL WINDOW (parent=0) ***")
        else:
            parent_info = _BASELINE.get(info['parent']) or current.get(info['parent'])
            if parent_info:
                print(f"  parent class={parent_info['class']!r}  "
                      f"parent title={parent_info['title'][:40]!r}")
        print("=" * 70)
        sys.stdout.flush()

# ── Patch QWebEngineView to log page events ───────────────────────────────────
_orig_qwev_setpage = QWebEngineView.setPage

def _patched_setpage(self, page):
    _orig_qwev_setpage(self, page)
    try:
        page.newWindowRequested.connect(_on_new_window_req_global)
        print(f"[PATCHED] newWindowRequested connected on page {type(page).__name__}")
    except Exception as e:
        print(f"[PATCH ERROR] {e}")

QWebEngineView.setPage = _patched_setpage

@Slot(QWebEngineNewWindowRequest)
def _on_new_window_req_global(request):
    print()
    print("!" * 70)
    print(f"[newWindowRequested FIRED]")
    print(f"  destination={request.destination()}")
    print(f"  url={request.requestedUrl().toString()}")
    print(f"  userInitiated={request.isUserInitiated()}")
    print("!" * 70)
    sys.stdout.flush()

# ── Main ──────────────────────────────────────────────────────────────────────
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
    print(f"HWND SNAPSHOT DIAGNOSTIC  PID={_PID}")
    print("App is starting...")
    print()
    print("STEP 1: Let the startup screen load fully")
    print("STEP 2: Navigate to Explore")
    print("STEP 3: Let the map load fully")
    print("STEP 4: Press ENTER in this console to take the baseline snapshot")
    print("STEP 5: Interact with map (click, zoom, pan)")
    print("STEP 6: Watch this console for new windows")
    print("=" * 70)
    sys.stdout.flush()

    def _read_enter():
        while True:
            try:
                input()
                QTimer.singleShot(0, _take_baseline)
            except EOFError:
                break

    t = threading.Thread(target=_read_enter, daemon=True)
    t.start()

    scan_timer = QTimer()
    scan_timer.timeout.connect(_scan_for_new)
    scan_timer.start(200)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
