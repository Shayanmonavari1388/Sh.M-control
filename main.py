#!/usr/bin/env python3
"""
Sh.M Control – Entry Point
Professional Windows Utility / Gaming Optimizer / Network Monitor
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Request Administrator on Windows before UI starts
from shmcontrol.core.admin import ensure_admin, is_admin
ensure_admin()

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from shmcontrol import __app_name__, __version__
from shmcontrol.config.settings import settings_manager, get_app_data_dir
from shmcontrol.ui.i18n import set_language
from shmcontrol.database.models import db
from shmcontrol.dns.manager import dns_manager
from shmcontrol.ui.main_window import MainWindow


def setup_logging() -> None:
    log_dir = get_app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "shmcontrol.log", encoding="utf-8"),
        ],
    )


def bootstrap() -> None:
    """Initialize DB, seed free DNS, ensure device id, start background services."""
    # Ensure optional tables exist (idempotent)
    try:
        from shmcontrol.usage.limits import _ensure_limits_table
        _ensure_limits_table()
    except Exception:
        pass
    try:
        from shmcontrol.system.timer import _ensure_table as _ensure_timer_table
        _ensure_timer_table()
    except Exception:
        pass
    try:
        from shmcontrol.gaming.playtime import _ensure_table as _ensure_play_table
        _ensure_play_table()
    except Exception:
        pass

    device_id = db.ensure_device()
    settings_manager.settings.device_id = device_id
    settings_manager.save()
    dns_manager.seed_from_json()

    try:
        from scripts.seed_trusted_endpoints import main as seed_eps
        seed_eps()
    except Exception as e:
        logging.getLogger("shmcontrol").debug("Endpoint seed skipped: %s", e)

    try:
        from shmcontrol.usage.collector import usage_collector
        usage_collector.start()
    except Exception as e:
        logging.getLogger("shmcontrol").warning("Usage collector not started: %s", e)

    try:
        from shmcontrol.system.timer import system_timer
        system_timer.on_startup_recover()
        system_timer.start_watcher()
    except Exception as e:
        logging.getLogger("shmcontrol").warning("System timer not started: %s", e)

    try:
        from shmcontrol.api.poller import cloud_poller
        if getattr(settings_manager.settings, "cloud_sync_enabled", False) or getattr(settings_manager.settings, "telegram_user_id", None):
            cloud_poller.start()
    except Exception as e:
        logging.getLogger("shmcontrol").warning("Cloud poller not started: %s", e)

    try:
        from shmcontrol.system.session_monitor import session_monitor
        session_monitor.start()
        # Delay startup notify slightly so UI is up
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2500, session_monitor.notify_startup)
    except Exception as e:
        logging.getLogger("shmcontrol").warning("Session monitor not started: %s", e)

    db.log("INFO", "app", "startup", f"Sh.M Control {__version__} started", device_id=device_id)


def main() -> int:
    setup_logging()
    logger = logging.getLogger("shmcontrol")
    logger.info("Starting %s v%s", __app_name__, __version__)
    logger.info("Admin elevated: %s", is_admin())
    try:
        from shmcontrol.updater import check_for_update
        info = check_for_update(timeout=3.0)
        if info.available:
            logger.info("Update available: %s -> %s", info.current, info.latest)
        elif info.error:
            logger.debug("Update check: %s", info.error)
    except Exception:
        pass

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)

    # App icon (window + taskbar)
    try:
        from PySide6.QtGui import QIcon
        ico = ROOT / "resources" / "icons" / "app_icon.ico"
        if not ico.exists():
            ico = ROOT / "resources" / "icons" / "app_icon_256.png"
        if ico.exists():
            app.setWindowIcon(QIcon(str(ico)))
    except Exception:
        pass
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("Sh.M")
    app.setFont(QFont("Segoe UI", 10))

    # Apply language before building UI
    set_language(getattr(settings_manager.settings, "language", "fa") or "fa")
    bootstrap()

    window = MainWindow()
    try:
        from shmcontrol.ui.main_window import _install_resume_watcher
        _install_resume_watcher(window)
    except Exception:
        pass
    window.show()

    from shmcontrol.gaming.game_mode import game_mode_manager

    def _scan_games() -> None:
        try:
            game_mode_manager.enabled = bool(settings_manager.settings.game_mode_enabled)
            if game_mode_manager.enabled:
                game_mode_manager.scan_and_apply()
        except Exception:
            pass

    gm_timer = QTimer()
    gm_timer.timeout.connect(_scan_games)
    gm_timer.start(4000)

    code = app.exec()

    try:
        from shmcontrol.usage.collector import usage_collector
        usage_collector.stop()
    except Exception:
        pass
    try:
        from shmcontrol.system.timer import system_timer
        system_timer.stop_watcher()
    except Exception:
        pass
    try:
        from shmcontrol.api.poller import cloud_poller
        cloud_poller.stop()
    except Exception:
        pass
    try:
        from shmcontrol.system.session_monitor import session_monitor
        session_monitor.stop()
    except Exception:
        pass

    return code


if __name__ == "__main__":
    sys.exit(main())
