"""
TripSphere — DEEP WINDOW DIAGNOSTIC
=====================================
Intercepts BOTH QWidget AND QWindow creation (Qt WebEngine compositor uses
QWindow directly, bypassing QWidget).  Also enumerates full Win32 HWND tree
including parent/owner HWNDs so we can see the exact native class.

Run:  python deep_diag.py
Navigate to Explore, then interact with the map (click, zoom, pan).
Watch the console for the mystery window report.
"""
from __future__ import annotations
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
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QApplication, QWidget

_user32 = ctypes.windll.user32
_PID = os.getpid()
_SEEN_HWNDS: set = set()

def _hwnd_info(hwnd) -> dict:
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
    owner    = _user32.GetWindow(hwnd, 4)
    visible  = bool(_user32.IsWindowVisible(hwnd))
    pid_c    = ctypes.c_ulong()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_c))
    return {
        'hwnd': hwnd, 'title': tbuf.value, 'class': cbuf.value,
        'w': w, 'h': h, 'style': hex(style), 'ex_style': hex(ex_style),
        'parent': parent, 'owner': owner, 'visible': visible,
        'pid': pid_c.value,
    }

def _enum_all_process_windows() -> list:
    wins = []
    def cb(hwnd, _):
        info = _hwnd_info(hwnd)
        if info['pid'] == _PID:
            wins.append(info)
        return True
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    _user32.EnumWindows(WNDENUMPROC(cb), 0)
    return wins

def _enum_child_windows(parent_hwnd) -> list:
    wins = []
    def cb(hwnd, _):
        wins.append(_hwnd_info(hwnd))
        return True
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    _user32.EnumChildWindows(parent_hwnd, WNDENUMPROC(cb), 0)
    return wins

def _print_win(info: dict, label: str = ""):
    print(f"  {label}HWND={info['hwnd']}  class={info['class']!r}  title={info['title']!r}")
    print(f"    size={info['w']}x{info['h']}  visible={info['visible']}")
    print(f"    style={info['style']}  ex_style={info['ex_style']}")
    print(f"    parent_hwnd={info['parent']}  owner_hwnd={info['owner']}")

def _win32_scan():
    for win in _enum_all_process_windows():
        hwnd = win['hwnd']
        if hwnd in _SEEN_HWNDS:
            continue
        _SEEN_HWNDS.add(hwnd)
        print()
        print("=" * 70)
        print(f"[WIN32 NEW HWND]")
        _print_win(win)
        children = _enum_child_windows(hwnd)
        if children:
            print(f"  Children ({len(children)}):")
            for c in children:
                _print_win(c, label="  child: ")
        print("=" * 70)
        sys.stdout.flush()

_SEEN_QWINDOWS: set = set()
_orig_qwindow_show = QWindow.show

def _patched_qwindow_show(self):
    _orig_qwindow_show(self)
    wid = id(self)
    if wid in _SEEN_QWINDOWS:
        return
    _SEEN_QWINDOWS.add(wid)
    try:
        cls = type(self).__name__
        qt_cls = self.metaObject().className()
        title = self.title()
        geom = self.geometry()
        parent = self.parent()
        flags = self.flags()
    except Exception as e:
        print(f"[QWindow inspect error] {e}")
        return
    print()
    print("=" * 70)
    print(f"[QWINDOW.show()] Python={cls}  Qt={qt_cls}")
    print(f"  title={title!r}  geom={geom.width()}x{geom.height()}@{geom.x()},{geom.y()}")
    print(f"  flags={hex(int(flags))}  parent={parent!r}")
    print("  STACK:")
    for line in _tb.format_stack()[:-2]:
        print("   ", line.rstrip())
    print("=" * 70)
    sys.stdout.flush()

QWindow.show = _patched_qwindow_show

_SEEN_QWIDGETS: set = set()
_IGNORE_QT_CLASSES = {'QMainWindow', 'QSplashScreen'}
_orig_widget_show = QWidget.show
_orig_widget_sv   = QWidget.setVisible

def _inspect_qwidget(w, trigger):
    wid = id(w)
    if wid in _SEEN_QWIDGETS:
        return
    try:
        if not w.isWindow():
            return
        py_cls = type(w).__name__
        qt_cls = w.metaObject().className()
        if py_cls in _IGNORE_QT_CLASSES or qt_cls in _IGNORE_QT_CLASSES:
            return
    except RuntimeError:
        return
    _SEEN_QWIDGETS.add(wid)
    try:
        geom   = w.geometry()
        flags  = w.windowFlags()
        parent = w.parentWidget()
        title  = w.windowTitle()
        obj    = w.objectName()
    except RuntimeError:
        return
    print()
    print("=" * 70)
    print(f"[QWIDGET TOP-LEVEL] trigger={trigger}")
    print(f"  Python={py_cls}  Qt={qt_cls}  objectName={obj!r}")
    print(f"  title={title!r}  geom={geom.width()}x{geom.height()}@{geom.x()},{geom.y()}")
    print(f"  flags={hex(int(flags))}  parent={parent!r}")
    print("  STACK:")
    for line in _tb.format_stack()[:-2]:
        print("   ", line.rstrip())
    print("=" * 70)
    sys.stdout.flush()

def _patched_widget_show(self):
    _orig_widget_show(self)
    _inspect_qwidget(self, "show()")

def _patched_widget_sv(self, visible):
    _orig_widget_sv(self, visible)
    if visible:
        _inspect_qwidget(self, "setVisible(True)")

QWidget.show = _patched_widget_show
QWidget.setVisible = _patched_widget_sv

def _periodic():
    app = QApplication.instance()
    if not app:
        return
    for w in app.topLevelWidgets():
        _inspect_qwidget(w, "periodic")
    for win in app.topLevelWindows():
        wid = id(win)
        if wid in _SEEN_QWINDOWS:
            continue
        _SEEN_QWINDOWS.add(wid)
        try:
            cls = type(win).__name__
            qt_cls = win.metaObject().className()
            title = win.title()
            geom = win.geometry()
            flags = win.flags()
        except Exception:
            continue
        print()
        print("=" * 70)
        print(f"[TOPLEVEL QWINDOW periodic]  Python={cls}  Qt={qt_cls}")
        print(f"  title={title!r}  geom={geom.width()}x{geom.height()}  flags={hex(int(flags))}")
        print("=" * 70)
        sys.stdout.flush()
    _win32_scan()

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
    print(f"DEEP DIAGNOSTIC ACTIVE  PID={_PID}")
    print("Watching QWidget.show + QWindow.show + Win32 HWNDs every 300ms")
    print()
    print("INITIAL HWND SNAPSHOT:")
    for win in _enum_all_process_windows():
        _SEEN_HWNDS.add(win['hwnd'])
        _print_win(win, label="INIT: ")
    for qwin in app.topLevelWindows():
        _SEEN_QWINDOWS.add(id(qwin))
    print()
    print("Navigate to EXPLORE then interact with MAP (click, zoom, pan)")
    print("=" * 70)
    sys.stdout.flush()

    t = QTimer()
    t.timeout.connect(_periodic)
    t.start(300)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
