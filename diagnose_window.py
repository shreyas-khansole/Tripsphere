"""
TripSphere — Top-Level Window Catcher
======================================
Run with:  python diagnose_window.py   (from the travel_app directory)
"""
import sys
import os
import traceback as _traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
except ImportError as e:
    print(f"[ERROR] PySide6-WebEngine not found: {e}")
    sys.exit(1)

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget

_SEEN_WINDOWS: set[int] = set()
_IGNORE_CLASSES = {"QMainWindow"}


def _inspect_widget(widget: QWidget, trigger: str) -> None:
    wid = id(widget)
    if wid in _SEEN_WINDOWS:
        return
    try:
        is_win = widget.isWindow()
        parent = widget.parentWidget()
        flags = widget.windowFlags()
    except RuntimeError:
        return

    if not is_win:
        return

    py_class = type(widget).__name__
    qt_class = widget.metaObject().className()

    if py_class in _IGNORE_CLASSES or qt_class in _IGNORE_CLASSES:
        return

    _SEEN_WINDOWS.add(wid)

    try:
        title = widget.windowTitle()
        obj_name = widget.objectName()
        geom = widget.geometry()
        parent_info = repr(parent) if parent else "None"
        window_info = repr(widget.window())
    except RuntimeError:
        return

    stack = _traceback.format_stack()
    relevant = stack[:-2]

    print()
    print("=" * 70)
    print(f"NEW TOP-LEVEL WINDOW  [trigger: {trigger}]")
    print(f"  Python class  : {py_class}")
    print(f"  Qt class      : {qt_class}")
    print(f"  objectName    : {repr(obj_name)}")
    print(f"  windowTitle   : {repr(title)}")
    print(f"  geometry      : x={geom.x()} y={geom.y()} w={geom.width()} h={geom.height()}")
    print(f"  isWindow()    : {is_win}")
    print(f"  windowFlags() : {hex(int(flags))}")
    print(f"  parentWidget(): {parent_info}")
    print(f"  window()      : {window_info}")
    print()
    print("  TRACEBACK:")
    for line in relevant:
        print("  ", line.rstrip())
    print("=" * 70)
    sys.stdout.flush()


_orig_show = QWidget.show
_orig_set_visible = QWidget.setVisible


def _patched_show(self: QWidget) -> None:
    _orig_show(self)
    _inspect_widget(self, "show()")


def _patched_set_visible(self: QWidget, visible: bool) -> None:
    _orig_set_visible(self, visible)
    if visible:
        _inspect_widget(self, f"setVisible(True)")


QWidget.show = _patched_show
QWidget.setVisible = _patched_set_visible


def _periodic_scan() -> None:
    app = QApplication.instance()
    if not app:
        return
    for w in app.topLevelWidgets():
        if w.isVisible():
            _inspect_widget(w, "periodic-scan")


def main() -> None:
    from app.config import APP_NAME, APP_VERSION, get_app_stylesheet, logger
    logger.info("DIAGNOSTIC MODE: Starting %s v%s", APP_NAME, APP_VERSION)

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-logging --no-sandbox")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("TripSphere")
    app.setStyleSheet(get_app_stylesheet())

    try:
        from app.database.models import initialize_database
        from app.database.seed_data import run_seed
        initialize_database()
        run_seed()
    except Exception as exc:
        print(f"[FATAL] DB init failed: {exc}")
        sys.exit(1)

    from app.ui.main_window import MainWindow
    mw = MainWindow()

    import socket
    try:
        socket.setdefaulttimeout(2)
        socket.create_connection(("8.8.8.8", 53))
        online = True
    except OSError:
        online = False
    mw.show_offline_indicator(not online)
    mw.showMaximized()
    mw.raise_()
    mw.activateWindow()

    timer = QTimer()
    timer.timeout.connect(_periodic_scan)
    timer.start(500)

    print()
    print("=" * 70)
    print("DIAGNOSTIC MODE ACTIVE")
    print("Interact with the app. Every new top-level window will be logged.")
    print("Actions: Search, Locate (map pin), Save (heart), Plan (+), Route, Nearby")
    print("=" * 70)
    sys.stdout.flush()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
