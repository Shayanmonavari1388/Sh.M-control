"""
Live network applications monitor with best-effort per-app bytes.

Windows: TCP GetPerTcpConnectionEStats aggregated by PID (real counters).
Other OS: process.net_io_counters when available.
Never invent numbers.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Optional

import psutil


@dataclass
class NetAppInfo:
    name: str
    pid: int
    path: str = ""
    connections: int = 0
    remote_sample: list[str] = field(default_factory=list)
    download_bytes: Optional[int] = None
    upload_bytes: Optional[int] = None
    download_rate: Optional[float] = None  # B/s
    upload_rate: Optional[float] = None
    bytes_supported: bool = False
    bytes_source: str = ""  # "estats" | "psutil" | ""


class NetworkAppsMonitor:
    def __init__(self) -> None:
        self._prev_psutil: dict[int, tuple[int, int, float]] = {}
        self._win = None
        if sys.platform == "win32":
            try:
                from shmcontrol.network.win_per_app import win_per_app_tracker
                self._win = win_per_app_tracker
            except Exception:
                self._win = None

    def snapshot(self) -> list[NetAppInfo]:
        by_pid: dict[int, NetAppInfo] = {}
        now = time.monotonic()

        try:
            conns = psutil.net_connections(kind="inet")
        except (psutil.Error, PermissionError):
            conns = []

        for c in conns:
            if not c.pid:
                continue
            info = by_pid.get(c.pid)
            if info is None:
                name, path = "?", ""
                try:
                    proc = psutil.Process(c.pid)
                    name = proc.name()
                    try:
                        path = proc.exe() or ""
                    except (psutil.Error, ProcessLookupError):
                        path = ""
                except (psutil.Error, ProcessLookupError):
                    continue
                info = NetAppInfo(name=name, pid=c.pid, path=path)
                by_pid[c.pid] = info
            info.connections += 1
            if c.raddr and len(info.remote_sample) < 3:
                try:
                    sample = f"{c.raddr.ip}:{c.raddr.port}"
                    if sample not in info.remote_sample:
                        info.remote_sample.append(sample)
                except Exception:
                    pass

        # --- bytes: Windows EStats first ---
        win_data = {}
        if self._win is not None:
            try:
                win_data = self._win.snapshot() or {}
            except Exception:
                win_data = {}

        if win_data:
            for pid, info in by_pid.items():
                d = win_data.get(pid)
                if not d:
                    continue
                info.download_bytes = int(d.get("download_bytes") or 0)
                info.upload_bytes = int(d.get("upload_bytes") or 0)
                info.download_rate = d.get("download_rate")
                info.upload_rate = d.get("upload_rate")
                info.bytes_supported = True
                info.bytes_source = "estats"
        else:
            # --- psutil per-process (Linux / rare Windows builds) ---
            for pid, info in list(by_pid.items()):
                try:
                    proc = psutil.Process(pid)
                    if not hasattr(proc, "net_io_counters"):
                        continue
                    counters = proc.net_io_counters()
                    if counters is None:
                        continue
                    recv = int(getattr(counters, "bytes_recv", 0) or 0)
                    sent = int(getattr(counters, "bytes_sent", 0) or 0)
                    info.download_bytes = recv
                    info.upload_bytes = sent
                    info.bytes_supported = True
                    info.bytes_source = "psutil"
                    prev = self._prev_psutil.get(pid)
                    if prev:
                        pr, ps_, pt = prev
                        dt = max(now - pt, 0.05)
                        info.download_rate = max(0.0, (recv - pr) / dt)
                        info.upload_rate = max(0.0, (sent - ps_) / dt)
                    self._prev_psutil[pid] = (recv, sent, now)
                except (psutil.Error, ProcessLookupError, AttributeError, NotImplementedError):
                    continue

        apps = list(by_pid.values())
        apps.sort(key=lambda a: (-(a.download_rate or 0), -a.connections, a.name.lower()))
        return apps

    def bytes_method(self) -> str:
        if self._win is not None:
            return "windows-estats"
        return "psutil-or-none"


network_apps_monitor = NetworkAppsMonitor()
