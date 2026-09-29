"""
Sh.M Control - System Metrics Aggregator
CPU, RAM, Disk, Network, GPU (fans), Local/Public IP.
"""

from __future__ import annotations

import logging
import socket
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import psutil

from shmcontrol.system.gpu_monitor import GPUMetrics, get_gpu_monitor

logger = logging.getLogger("shmcontrol.system.metrics")


@dataclass
class SystemMetrics:
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    cpu_percent: float = 0.0
    cpu_per_core: list[float] = field(default_factory=list)
    cpu_temp_c: Optional[float] = None

    ram_percent: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0

    disk_percent: float = 0.0
    disk_read_mb_s: float = 0.0
    disk_write_mb_s: float = 0.0

    net_download_mb_s: float = 0.0
    net_upload_mb_s: float = 0.0
    public_ip: Optional[str] = None
    local_ip: Optional[str] = None

    gpus: list[GPUMetrics] = field(default_factory=list)
    uptime_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu_percent": self.cpu_percent,
            "cpu_per_core": self.cpu_per_core,
            "cpu_temp_c": self.cpu_temp_c,
            "ram_percent": self.ram_percent,
            "ram_used_gb": round(self.ram_used_gb, 2),
            "ram_total_gb": round(self.ram_total_gb, 2),
            "disk_percent": self.disk_percent,
            "disk_read_mb_s": round(self.disk_read_mb_s, 2),
            "disk_write_mb_s": round(self.disk_write_mb_s, 2),
            "net_download_mb_s": round(self.net_download_mb_s, 2),
            "net_upload_mb_s": round(self.net_upload_mb_s, 2),
            "public_ip": self.public_ip,
            "local_ip": self.local_ip,
            "gpus": [g.to_dict() for g in self.gpus],
            "uptime_seconds": self.uptime_seconds,
        }


class MetricsCollector:
    """Call collect() periodically. CPU% needs a prior sample (psutil)."""

    def __init__(self) -> None:
        self._last_net = psutil.net_io_counters()
        self._last_disk = psutil.disk_io_counters()
        self._last_time = time.monotonic()
        self._boot_time = psutil.boot_time()
        self._gpu = get_gpu_monitor()
        self._public_ip_cache: Optional[str] = None
        self._public_ip_at: float = 0.0
        self._public_ip_lock = threading.Lock()
        self._public_ip_fetching = False
        # Prime CPU percent so first real sample is non-zero
        psutil.cpu_percent(interval=None)

    def collect(self) -> SystemMetrics:
        try:
            return self._collect_inner()
        except Exception as exc:
            logger.exception("Metrics collect failed: %s", exc)
            return SystemMetrics()

    def _collect_inner(self) -> SystemMetrics:
        m = SystemMetrics()

        # CPU
        m.cpu_percent = float(psutil.cpu_percent(interval=None) or 0.0)
        try:
            m.cpu_per_core = list(psutil.cpu_percent(interval=None, percpu=True) or [])
        except Exception:
            m.cpu_per_core = []
        m.cpu_temp_c = self._get_cpu_temperature()

        # RAM
        mem = psutil.virtual_memory()
        m.ram_percent = float(mem.percent)
        m.ram_used_gb = float(mem.used) / (1024 ** 3)
        m.ram_total_gb = float(mem.total) / (1024 ** 3)

        # Disk (Windows: C:\)
        for path in ("C:\\", "/"):
            try:
                disk = psutil.disk_usage(path)
                m.disk_percent = float(disk.percent)
                break
            except Exception:
                continue

        now = time.monotonic()
        dt = max(now - self._last_time, 0.001)

        try:
            disk_io = psutil.disk_io_counters()
            if disk_io and self._last_disk:
                m.disk_read_mb_s = max(
                    0.0, (disk_io.read_bytes - self._last_disk.read_bytes) / dt / (1024 ** 2)
                )
                m.disk_write_mb_s = max(
                    0.0, (disk_io.write_bytes - self._last_disk.write_bytes) / dt / (1024 ** 2)
                )
            self._last_disk = disk_io
        except Exception:
            pass

        try:
            net = psutil.net_io_counters()
            if net and self._last_net:
                m.net_download_mb_s = max(
                    0.0, (net.bytes_recv - self._last_net.bytes_recv) / dt / (1024 ** 2)
                )
                m.net_upload_mb_s = max(
                    0.0, (net.bytes_sent - self._last_net.bytes_sent) / dt / (1024 ** 2)
                )
            self._last_net = net
        except Exception:
            pass

        self._last_time = now

        m.local_ip = self._get_local_ip()
        m.public_ip = self._get_public_ip_cached()

        try:
            m.gpus = self._gpu.get_all_gpus()
        except Exception as exc:
            logger.debug("GPU collection failed: %s", exc)
            m.gpus = []

        m.uptime_seconds = max(0.0, time.time() - self._boot_time)
        return m

    def _get_cpu_temperature(self) -> Optional[float]:
        """Best-effort CPU temperature (Linux sensors + Windows WMI/LHM)."""
        # 1) psutil (works on many Linux systems; rarely on Windows)
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name in ("coretemp", "k10temp", "cpu_thermal", "acpitz", "zenpower"):
                    if name in temps and temps[name]:
                        return float(temps[name][0].current)
                for entries in temps.values():
                    if entries:
                        return float(entries[0].current)
        except Exception:
            pass

        # 2) Windows: LibreHardwareMonitor / OpenHardwareMonitor WMI
        try:
            t = self._wmi_ohm_cpu_temp()
            if t is not None:
                return t
        except Exception:
            pass

        # 3) Windows: MSAcpi thermal zone (often kelvin; may need admin)
        try:
            t = self._wmi_acpi_temp()
            if t is not None:
                return t
        except Exception:
            pass

        # 4) Windows: PowerShell CIM (Win32_PerfFormattedData not reliable;
        #    try Root/WMI MSAcpi via powershell one-liner)
        try:
            t = self._powershell_cpu_temp()
            if t is not None:
                return t
        except Exception:
            pass
        return None

    def _wmi_ohm_cpu_temp(self) -> Optional[float]:
        """LibreHardwareMonitor / OpenHardwareMonitor expose WMI sensors."""
        import platform
        if platform.system() != "Windows":
            return None
        try:
            import subprocess
            # Query LHM / OHM sensor classes
            ps = (
                "$ErrorActionPreference='SilentlyContinue';"
                "$ns=@('root\\LibreHardwareMonitor','root\\OpenHardwareMonitor');"
                "foreach($n in $ns){"
                "  $s=Get-CimInstance -Namespace $n -ClassName Sensor -ErrorAction SilentlyContinue;"
                "  if($s){"
                "    $cpu=$s | Where-Object { $_.SensorType -eq 'Temperature' -and ("
                "      $_.Name -match 'CPU' -or $_.Name -match 'Package' -or $_.Name -match 'Tctl'"
                "    ) };"
                "    if($cpu){ ($cpu | Select-Object -First 1).Value; break }"
                "    $any=$s | Where-Object { $_.SensorType -eq 'Temperature' };"
                "    if($any){ ($any | Select-Object -First 1).Value; break }"
                "  }"
                "}"
            )
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True, timeout=4,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            out = (r.stdout or "").strip().splitlines()
            for line in out:
                line = line.strip().replace(",", ".")
                try:
                    val = float(line)
                    if 0 < val < 150:
                        return val
                except ValueError:
                    continue
        except Exception:
            pass
        return None

    def _wmi_acpi_temp(self) -> Optional[float]:
        import platform
        if platform.system() != "Windows":
            return None
        try:
            import subprocess
            ps = (
                "$ErrorActionPreference='SilentlyContinue';"
                "$t=Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature "
                "-ErrorAction SilentlyContinue | Select-Object -First 1;"
                "if($t){ [math]::Round(($t.CurrentTemperature/10.0)-273.15,1) }"
            )
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True, timeout=4,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            out = (r.stdout or "").strip().replace(",", ".")
            if out:
                val = float(out)
                if 0 < val < 150:
                    return val
        except Exception:
            pass
        return None

    def _powershell_cpu_temp(self) -> Optional[float]:
        """Last resort: thermal zone via Get-WmiObject style."""
        import platform
        if platform.system() != "Windows":
            return None
        try:
            import subprocess
            ps = (
                "$ErrorActionPreference='SilentlyContinue';"
                "Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace root/wmi | "
                "ForEach-Object { [math]::Round(($_.CurrentTemperature/10)-273.15,1) } | "
                "Select-Object -First 1"
            )
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True, timeout=4,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            out = (r.stdout or "").strip().replace(",", ".")
            if out:
                val = float(out)
                if 0 < val < 150:
                    return val
        except Exception:
            pass
        return None

    def _get_local_ip(self) -> Optional[str]:
        # Prefer real outbound interface
        for dest in (("8.8.8.8", 80), ("1.1.1.1", 80)):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(0.5)
                s.connect(dest)
                ip = s.getsockname()[0]
                s.close()
                if ip and not ip.startswith("127."):
                    return ip
            except Exception:
                continue
        try:
            for _name, addrs in psutil.net_if_addrs().items():
                for a in addrs:
                    if getattr(a, "family", None) == socket.AF_INET:
                        ip = a.address
                        if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
                            return ip
        except Exception:
            pass
        try:
            host = socket.gethostbyname(socket.gethostname())
            if host and not host.startswith("127."):
                return host
        except Exception:
            pass
        return None

    def _get_public_ip_cached(self) -> Optional[str]:
        """Non-blocking: return cache; refresh in background every 5 min."""
        now = time.monotonic()
        with self._public_ip_lock:
            cached = self._public_ip_cache
            age = now - self._public_ip_at
            need = cached is None or age > 300
            if need and not self._public_ip_fetching:
                self._public_ip_fetching = True
                threading.Thread(target=self._fetch_public_ip_bg, daemon=True).start()
            return cached

    def _fetch_public_ip_bg(self) -> None:
        urls = (
            "https://api.ipify.org",
            "https://ifconfig.me/ip",
            "https://icanhazip.com",
            "https://checkip.amazonaws.com",
        )
        found: Optional[str] = None
        for u in urls:
            try:
                req = urllib.request.Request(u, headers={"User-Agent": "ShMControl/1.1"})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    ip = (resp.read() or b"").decode("utf-8", errors="ignore").strip()
                if ip and 6 <= len(ip) <= 45 and " " not in ip:
                    found = ip
                    break
            except Exception:
                continue
        with self._public_ip_lock:
            if found:
                self._public_ip_cache = found
                self._public_ip_at = time.monotonic()
            self._public_ip_fetching = False
