"""
Sh.M Control - Internet Usage Collector (background)

Reality on Windows:
  psutil does NOT expose per-process network byte counters on Windows.
  We collect:
    1) System-wide download/upload (accurate)
    2) Which processes currently hold network connections (accurate)
    3) Aggregate system totals into usage_daily / usage_hourly under "__SYSTEM__"

  Per-app byte attribution is marked unavailable unless a platform API provides it.
  We never invent per-process download/upload numbers.
"""

from __future__ import annotations

import logging
import platform
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import psutil

from shmcontrol.database.models import db

logger = logging.getLogger("shmcontrol.usage")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _date_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _hour_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:00:00")


class UsageCollector:
    def __init__(self, interval_sec: float = 5.0) -> None:
        self.interval = interval_sec
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_net = psutil.net_io_counters()
        self._last_ts = time.monotonic()
        self._active_processes: set[str] = set()
        self._active_paths: dict[str, str] = {}  # name -> exe path
        self.per_app_bytes_supported = self._detect_per_app_support()

    def _detect_per_app_support(self) -> bool:
        """True only if OS exposes real per-process network bytes."""
        # Linux / some Unix: process.net_io_counters exists in newer psutil
        try:
            p = psutil.Process()
            if hasattr(p, "net_io_counters"):
                try:
                    p.net_io_counters()
                    return True
                except (AttributeError, NotImplementedError, psutil.Error):
                    pass
        except Exception:
            pass
        return False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="UsageCollector", daemon=True)
        self._thread.start()
        logger.info(
            "UsageCollector started (per-app bytes: %s)",
            "supported" if self.per_app_bytes_supported else "NOT available on this platform",
        )

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._sample()
            except Exception:
                logger.exception("Usage sample failed")
            self._stop.wait(self.interval)

    def _sample(self) -> None:
        now = time.monotonic()
        dt = max(now - self._last_ts, 0.001)
        net = psutil.net_io_counters()
        if not net or not self._last_net:
            self._last_net = net
            self._last_ts = now
            return

        dl = max(0, net.bytes_recv - self._last_net.bytes_recv)
        ul = max(0, net.bytes_sent - self._last_net.bytes_sent)
        self._last_net = net
        self._last_ts = now

        # Always record accurate system totals
        if dl > 0 or ul > 0:
            self._add_bytes("__SYSTEM__", dl, ul)

        # Track processes with active network connections (no fake bytes)
        active: set[str] = set()
        paths: dict[str, str] = {}
        try:
            for c in psutil.net_connections(kind="inet"):
                if c.pid:
                    try:
                        proc = psutil.Process(c.pid)
                        name = proc.name()
                        active.add(name)
                        if name not in paths:
                            try:
                                exe = proc.exe()
                                if exe:
                                    paths[name] = exe
                            except (psutil.Error, ProcessLookupError):
                                pass
                    except (psutil.Error, ProcessLookupError):
                        continue
        except (psutil.Error, PermissionError) as e:
            logger.debug("net_connections limited: %s", e)

        self._active_processes = active
        self._active_paths = paths

        # If platform supports real per-process net IO, record it
        if self.per_app_bytes_supported:
            self._sample_per_process()

    def _sample_per_process(self) -> None:
        """Only called when Process.net_io_counters is real."""
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                p = proc
                counters = p.net_io_counters()  # type: ignore[attr-defined]
                if not counters:
                    continue
                # Without previous snapshot we can't compute delta reliably first run;
                # store cumulative snapshot keys in memory
                key = f"_proc_{p.pid}"
                prev = getattr(self, key, None)
                setattr(self, key, counters)
                if prev is None:
                    continue
                dl = max(0, counters.bytes_recv - prev.bytes_recv)
                ul = max(0, counters.bytes_sent - prev.bytes_sent)
                if dl or ul:
                    self._add_bytes(p.name() or f"pid:{p.pid}", dl, ul)
            except (psutil.Error, AttributeError, NotImplementedError):
                continue

    def _add_bytes(self, process_name: str, download: int, upload: int) -> None:
        now = _utc_now()
        day = _date_str(now)
        hour = _hour_str(now)
        with db.connection() as conn:
            conn.execute(
                """
                INSERT INTO usage_daily (date, process_name, download_bytes, upload_bytes)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(date, process_name) DO UPDATE SET
                    download_bytes = download_bytes + excluded.download_bytes,
                    upload_bytes = upload_bytes + excluded.upload_bytes
                """,
                (day, process_name, download, upload),
            )
            conn.execute(
                """
                INSERT INTO usage_hourly (hour_start, process_name, download_bytes, upload_bytes)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(hour_start, process_name) DO UPDATE SET
                    download_bytes = download_bytes + excluded.download_bytes,
                    upload_bytes = upload_bytes + excluded.upload_bytes
                """,
                (hour, process_name, download, upload),
            )

    def get_active_network_processes(self) -> list[str]:
        return sorted(self._active_processes)

    def get_active_network_process_details(self) -> list[dict]:
        """name + exe path for real Windows icons."""
        # Refresh once if empty
        if not self._active_processes:
            try:
                self._sample()
            except Exception:
                pass
        out = []
        for name in sorted(self._active_processes):
            out.append({
                "name": name,
                "path": self._active_paths.get(name) or "",
            })
        return out

    def get_period_totals(self, days: int = 1) -> list[dict]:
        """Aggregate from usage_daily for the last N days."""
        end = _utc_now().date()
        start = end - timedelta(days=days - 1)
        rows = db.execute(
            """
            SELECT process_name,
                   SUM(download_bytes) as dl,
                   SUM(upload_bytes) as ul
            FROM usage_daily
            WHERE date >= ? AND date <= ?
            GROUP BY process_name
            ORDER BY (dl + ul) DESC
            """,
            (start.isoformat(), end.isoformat()),
        )
        return [
            {
                "process_name": r["process_name"],
                "download_bytes": r["dl"] or 0,
                "upload_bytes": r["ul"] or 0,
                "total_bytes": (r["dl"] or 0) + (r["ul"] or 0),
            }
            for r in rows
        ]

    def check_limits(self) -> list[dict]:
        """Return list of limit breaches from settings / DB. Real counts only."""
        breaches = []
        # Game-level limits from games table
        rows = db.execute(
            "SELECT name, internet_limit_mb FROM games WHERE internet_limit_mb IS NOT NULL AND internet_limit_mb > 0"
        )
        today = _date_str(_utc_now())
        for r in rows:
            limit_b = int(r["internet_limit_mb"]) * 1024 * 1024
            # Match process name loosely
            usage = db.execute_one(
                "SELECT download_bytes + upload_bytes as total FROM usage_daily WHERE date = ? AND process_name LIKE ?",
                (today, f"%{r['name']}%"),
            )
            total = (usage["total"] if usage else 0) or 0
            if total >= limit_b:
                breaches.append({
                    "scope": "application",
                    "name": r["name"],
                    "limit_bytes": limit_b,
                    "used_bytes": total,
                })
        return breaches


# Singleton
usage_collector = UsageCollector()
