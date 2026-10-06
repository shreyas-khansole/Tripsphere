"""
TripSphere — Application Entry Point
=====================================
Run with:  python main.py
"""
import sys
import os
import logging

# ── Ensure project root is on the path ───────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── PySide6 WebEngine must be imported before QApplication ───────────────────
# This is a known requirement on some platforms.
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
except ImportError as e:
    print(f"[ERROR] PySide6-WebEngine not found: {e}")
    print("Install with:  pip install PySide6-WebEngine")
    sys.exit(1)

from PySide6.QtCore    import Qt, QTimer
from PySide6.QtGui     import QColor
from PySide6.QtWidgets import QApplication, QSplashScreen, QLabel

from app.config import APP_NAME, APP_VERSION, get_app_stylesheet, logger


def _init_database() -> None:
    """Initialize schema and seed data."""
    from app.database.models   import initialize_database
    from app.database.seed_data import run_seed
    initialize_database()
    run_seed()


def _check_internet() -> bool:
    """Quick connectivity check."""
    import socket
    try:
        socket.setdefaulttimeout(2)
        socket.create_connection(("8.8.8.8", 53))
        return True
    except OSError:
        return False


def main() -> None:
    logger.info("Starting %s v%s", APP_NAME, APP_VERSION)

    # ── High-DPI settings ─────────────────────────────────────────────────────
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS",
                          "--disable-logging --no-sandbox")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("TripSphere")

    # Apply global stylesheet
    app.setStyleSheet(get_app_stylesheet())

    # ── Database initialization ───────────────────────────────────────────────
    try:
        _init_database()
        logger.info("Database ready.")
    except Exception as exc:
        logger.critical("Database initialization failed: %s", exc)
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(None, "Fatal Error",
                             f"Failed to initialize database:\n{exc}\n\nThe application will exit.")
        sys.exit(1)

    # ── Check connectivity ────────────────────────────────────────────────────
    online = _check_internet()
    logger.info("Network: %s", "online" if online else "offline")

    # ── Main Window ───────────────────────────────────────────────────────────
    from app.ui.main_window import MainWindow
    main_window = MainWindow()
    main_window.show_offline_indicator(not online)
    main_window.showMaximized()
    main_window.raise_()
    main_window.activateWindow()

    # ── Start event loop ──────────────────────────────────────────────────────
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
