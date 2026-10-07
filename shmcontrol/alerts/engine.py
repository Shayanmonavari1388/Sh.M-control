"""
Sh.M Control - Alerts Engine
Uses real metrics only. Cooldown prevents spam.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from shmcontrol.config.settings import settings_manager
from shmcontrol.notifications.notify import notify_windows, notify_telegram, alert_temperature
from shmcontrol.system.metrics import MetricsCollector
from shmcontrol.database.models import db

logger = logging.getLogger("shmcontrol.alerts")

_last: dict[str, float] = {}


def _cd(key: str, sec: int) -> bool:
    now = time.time()
    if now - _last.get(key, 0) < sec:
        return False
    _last[key] = now
    return True


class AlertsEngine:
    def __init__(self) -> None:
        self._collector = MetricsCollector()
        self._prev_internet: Optional[bool] = None

    def tick(self) -> None:
        try:
            m = self._collector.collect()
            t = settings_manager.settings.temperature
            device = "PC"

            if m.cpu_temp_c is not None:
                if m.cpu_temp_c >= t.cpu_critical and _cd("cpu_crit", 180):
                    alert_temperature("cpu", m.cpu_temp_c, device)
                elif m.cpu_temp_c >= t.cpu_warning and _cd("cpu_warn", 300):
                    alert_temperature("cpu", m.cpu_temp_c, device)

            if m.gpus:
                g = m.gpus[0]
                if g.temperature_c is not None:
                    if g.temperature_c >= t.gpu_critical and _cd("gpu_crit", 180):
                        alert_temperature("gpu", g.temperature_c, device)
                    elif g.temperature_c >= t.gpu_warning and _cd("gpu_warn", 300):
                        alert_temperature("gpu", g.temperature_c, device)

            if m.cpu_percent >= 95 and _cd("cpu_high", 300):
                notify_windows("Sh.M Control", f"CPU usage high: {m.cpu_percent:.0f}%", key="cpu_high")
            if m.ram_percent >= 95 and _cd("ram_high", 300):
                notify_windows("Sh.M Control", f"RAM usage high: {m.ram_percent:.0f}%", key="ram_high")
            if m.disk_percent >= 95 and _cd("disk_full", 600):
                notify_windows("Sh.M Control", f"Disk almost full: {m.disk_percent:.0f}%", key="disk_full")

            # Internet rough check via public IP attempt is expensive; skip silent fail
        except Exception:
            logger.exception("alerts tick failed")


alerts_engine = AlertsEngine()
