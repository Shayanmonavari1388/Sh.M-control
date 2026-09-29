"""
Windows session monitor: lock / unlock / resume.
Sends Telegram + optional Windows tray alerts when user enables them.
"""

from __future__ import annotations

import logging
import platform
import threading
import time
from typing import Optional

logger = logging.getLogger("shmcontrol.system.session")


def _is_windows() -> bool:
    return platform.system() == "Windows"


def is_workstation_locked() -> Optional[bool]:
    """True if locked, False if unlocked, None if unknown."""
    if not _is_windows():
        return None
    try:
        import ctypes
        user32 = ctypes.windll.user32
        # OpenInputDesktop fails when session is locked for this process in many setups
        # DESKTOP_SWITCHDESKTOP = 0x0100
        h = user32.OpenInputDesktop(0, False, 0x0100)
        if not h:
            h = user32.OpenInputDesktop(0, False, 0x0001 | 0x0020)
        if h:
            user32.CloseDesktop(h)
            return False
        # fallback: SwitchDesktop
        return True
    except Exception as e:
        logger.debug("lock probe: %s", e)
        return None


class SessionMonitor:
    def __init__(self, interval: float = 2.0) -> None:
        self.interval = interval
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_locked: Optional[bool] = None
        self._stable_count: int = 0
        self._pending_locked: Optional[bool] = None
        self._started = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="session-monitor", daemon=True)
        self._thread.start()
        logger.info("Session monitor started")

    def stop(self) -> None:
        self._stop.set()

    def notify_startup(self) -> None:
        """Call once after app ready — 'system/app online'."""
        from shmcontrol.config.settings import settings_manager
        s = settings_manager.settings
        if not getattr(s, "notify_on_startup", True):
            return
        self._emit(
            "startup",
            "🟢 سیستم / برنامه آنلاین شد",
            "Sh.M Control is running on your PC.",
            cooldown=10,
        )

    def _loop(self) -> None:
        # initial sample
        self._last_locked = is_workstation_locked()
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.debug("session tick: %s", e)
            self._stop.wait(self.interval)

    def _tick(self) -> None:
        from shmcontrol.config.settings import settings_manager
        s = settings_manager.settings
        locked = is_workstation_locked()
        if locked is None:
            return
        # Require 2 identical readings to avoid flapping false alerts
        if self._pending_locked is None or locked != self._pending_locked:
            self._pending_locked = locked
            self._stable_count = 1
            return
        self._stable_count += 1
        if self._stable_count < 2:
            return
        prev = self._last_locked
        self._last_locked = locked
        if prev is None:
            return
        if prev and not locked:
            if getattr(s, "notify_on_unlock", True):
                self._emit(
                    "unlock",
                    "🔓 قفل سیستم باز شد",
                    "Workstation unlocked.",
                    cooldown=60,
                )
        elif not prev and locked:
            if getattr(s, "notify_on_lock", False):
                self._emit(
                    "lock",
                    "🔒 سیستم قفل شد",
                    "Workstation locked.",
                    cooldown=60,
                )

    def _emit(self, key: str, title_fa: str, title_en: str, cooldown: int = 30) -> None:
        from shmcontrol.config.settings import settings_manager
        from shmcontrol.notifications.notify import notify_windows, notify_telegram_real
        fa = (settings_manager.settings.language or "fa") == "fa"
        title = title_fa if fa else title_en
        name = getattr(settings_manager.settings, "device_name", None) or "PC"
        msg = f"{title}\nDevice: {name}"
        notify_windows("Sh.M Control", msg, key=f"session_{key}", cooldown=cooldown)
        notify_telegram_real(msg, key=f"session_{key}", cooldown=cooldown)


session_monitor = SessionMonitor()
