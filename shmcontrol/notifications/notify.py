"""
Windows + optional Telegram notifications.
Cooldown to prevent spam.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger("shmcontrol.notifications")

_last_sent: dict[str, float] = {}


def _cooldown_ok(key: str, seconds: int = 300) -> bool:
    now = time.time()
    last = _last_sent.get(key, 0)
    if now - last < seconds:
        return False
    _last_sent[key] = now
    return True


def notify_windows(title: str, message: str, key: str = "general", cooldown: int = 300) -> None:
    if not _cooldown_ok(key, cooldown):
        return
    try:
        from PySide6.QtWidgets import QSystemTrayIcon, QApplication
        app = QApplication.instance()
        if app is None:
            return
        # Use tray if available via main window
        for w in app.topLevelWidgets():
            tray = getattr(w, "_tray", None)
            if tray and isinstance(tray, QSystemTrayIcon):
                tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Warning, 5000)
                return
    except Exception as e:
        logger.debug("Windows notify failed: %s", e)


def notify_telegram(message: str, key: str = "general", cooldown: int = 300) -> None:
    notify_telegram_real(message, key=key, cooldown=cooldown)


def notify_telegram_real(message: str, key: str = "general", cooldown: int = 300) -> None:
    """Send to Telegram via remote API (preferred) or direct Bot API if token present."""
    if not _cooldown_ok(f"tg:{key}", cooldown):
        return
    logger.info("Telegram alert: %s", message[:200])
    try:
        from shmcontrol.api.cloud import push_telegram_message
        if push_telegram_message(message):
            return
    except Exception as e:
        logger.debug("cloud tg push: %s", e)
    # Direct bot API fallback
    try:
        import os
        import httpx
        from shmcontrol.config.settings import settings_manager
        token = (
            os.getenv("GUARDIAN_TELEGRAM_BOT_TOKEN")
            or getattr(settings_manager.settings, "telegram_bot_token", None)
        )
        uid = (
            os.getenv("GUARDIAN_TELEGRAM_USER_ID")
            or getattr(settings_manager.settings, "telegram_user_id", None)
        )
        if not token or not uid:
            return
        httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": int(uid), "text": message},
            timeout=15.0,
        )
    except Exception as e:
        logger.debug("direct tg: %s", e)


def alert_temperature(kind: str, value: float, device: str = "PC") -> None:
    """kind = cpu | gpu"""
    title = f"⚠️ High {kind.upper()} Temperature"
    msg = f"{kind.upper()} Temperature:\n{value:.0f}°C\n\nDevice:\n{device}"
    notify_windows(title, msg, key=f"temp_{kind}", cooldown=180)
    tg = (
        f"⚠️ Sh.M Control Alert\n\n"
        f"{kind.upper()} temperature reached {value:.0f}°C.\n\n"
        f"Device:\n{device}"
    )
    notify_telegram(tg, key=f"temp_{kind}", cooldown=180)
