"""
Sh.M Control - GPU Monitoring Module
Supports NVIDIA (via pynvml / NVML) and graceful fallbacks.
Reads: utilization, memory, temperature, fan speed(s), power, clocks.
Never fabricates data. Returns None / empty when unsupported.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("shmcontrol.system.gpu")

# ---------------------------------------------------------------------------
# Optional NVIDIA support
# ---------------------------------------------------------------------------
_NVML_AVAILABLE = False
try:
    import pynvml
    from pynvml import (
        NVML_TEMPERATURE_GPU,
        nvmlDeviceGetCount,
        nvmlDeviceGetFanSpeed,
        nvmlDeviceGetFanSpeed_v2,
        nvmlDeviceGetHandleByIndex,
        nvmlDeviceGetMemoryInfo,
        nvmlDeviceGetName,
        nvmlDeviceGetNumFans,
        nvmlDeviceGetPowerUsage,
        nvmlDeviceGetTemperature,
        nvmlDeviceGetUtilizationRates,
        nvmlInit,
        nvmlShutdown,
        nvmlSystemGetDriverVersion,
        NVMLError,
    )
    _NVML_AVAILABLE = True
except ImportError:
    pynvml = None  # type: ignore
    logger.info("pynvml not installed – NVIDIA GPU metrics unavailable")


@dataclass
class FanInfo:
    index: int
    speed_percent: Optional[int] = None  # 0-100
    rpm: Optional[int] = None            # if available


@dataclass
class GPUMetrics:
    index: int
    name: str
    vendor: str = "Unknown"              # NVIDIA / AMD / Intel / Unknown

    # Utilization
    gpu_util_percent: Optional[int] = None
    mem_util_percent: Optional[int] = None

    # Memory (MB)
    mem_used_mb: Optional[float] = None
    mem_total_mb: Optional[float] = None

    # Temperature (°C)
    temperature_c: Optional[float] = None

    # Fans
    fans: list[FanInfo] = field(default_factory=list)
    fan_speed_avg_percent: Optional[float] = None

    # Power (W)
    power_draw_w: Optional[float] = None

    # Extra
    driver_version: Optional[str] = None
    supported: bool = True
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "name": self.name,
            "vendor": self.vendor,
            "gpu_util_percent": self.gpu_util_percent,
            "mem_util_percent": self.mem_util_percent,
            "mem_used_mb": self.mem_used_mb,
            "mem_total_mb": self.mem_total_mb,
            "temperature_c": self.temperature_c,
            "fans": [
                {"index": f.index, "speed_percent": f.speed_percent, "rpm": f.rpm}
                for f in self.fans
            ],
            "fan_speed_avg_percent": self.fan_speed_avg_percent,
            "power_draw_w": self.power_draw_w,
            "driver_version": self.driver_version,
            "supported": self.supported,
            "error": self.error,
        }


class GPUMonitor:
    """
    Central GPU monitoring service.
    Designed to be called from a background QThread / asyncio task.
    """

    def __init__(self) -> None:
        self._nvml_initialized = False
        self._driver_version: Optional[str] = None

    def initialize(self) -> bool:
        """Initialize NVML if available. Safe to call multiple times."""
        if not _NVML_AVAILABLE:
            return False
        if self._nvml_initialized:
            return True
        try:
            nvmlInit()
            self._driver_version = nvmlSystemGetDriverVersion()
            if isinstance(self._driver_version, bytes):
                self._driver_version = self._driver_version.decode("utf-8", errors="ignore")
            self._nvml_initialized = True
            logger.info("NVML initialized – driver %s", self._driver_version)
            return True
        except Exception as exc:
            logger.warning("NVML init failed: %s", exc)
            self._nvml_initialized = False
            return False

    def shutdown(self) -> None:
        if self._nvml_initialized and _NVML_AVAILABLE:
            try:
                nvmlShutdown()
            except Exception:
                pass
            self._nvml_initialized = False

    def get_all_gpus(self) -> list[GPUMetrics]:
        """Return metrics for every detectable GPU."""
        results: list[GPUMetrics] = []

        # 1. NVIDIA path (preferred – accurate fan %)
        if self.initialize():
            try:
                count = nvmlDeviceGetCount()
                for i in range(count):
                    metrics = self._read_nvidia_gpu(i)
                    results.append(metrics)
            except Exception as exc:
                logger.error("Error enumerating NVIDIA GPUs: %s", exc)

        # 2. Future: AMD / Intel Arc via LibreHardwareMonitor or ADLX
        #    Currently left as extension point so we never invent numbers.

        if not results:
            # No GPU detected or libraries missing
            results.append(
                GPUMetrics(
                    index=0,
                    name="No supported GPU detected",
                    vendor="Unknown",
                    supported=False,
                    error="Install nvidia-ml-py for NVIDIA support, or enable LibreHardwareMonitor for AMD/Intel",
                )
            )

        return results

    def get_primary_gpu(self) -> GPUMetrics:
        gpus = self.get_all_gpus()
        return gpus[0] if gpus else GPUMetrics(0, "Unknown", supported=False)

    def _read_nvidia_gpu(self, index: int) -> GPUMetrics:
        """Read a single NVIDIA GPU via NVML."""
        metrics = GPUMetrics(index=index, name="NVIDIA GPU", vendor="NVIDIA")
        metrics.driver_version = self._driver_version

        try:
            handle = nvmlDeviceGetHandleByIndex(index)

            # Name
            try:
                name = nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8", errors="ignore")
                metrics.name = name
            except Exception:
                pass

            # Utilization
            try:
                util = nvmlDeviceGetUtilizationRates(handle)
                metrics.gpu_util_percent = int(util.gpu)
                metrics.mem_util_percent = int(util.memory)
            except Exception:
                pass

            # Memory
            try:
                mem = nvmlDeviceGetMemoryInfo(handle)
                metrics.mem_used_mb = mem.used / (1024 * 1024)
                metrics.mem_total_mb = mem.total / (1024 * 1024)
            except Exception:
                pass

            # Temperature
            try:
                temp = nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)
                metrics.temperature_c = float(temp)
            except Exception:
                pass

            # Power
            try:
                power_mw = nvmlDeviceGetPowerUsage(handle)  # milliwatts
                metrics.power_draw_w = power_mw / 1000.0
            except Exception:
                pass

            # Fans – core feature requested by user
            fans = self._read_nvidia_fans(handle)
            metrics.fans = fans
            if fans:
                speeds = [f.speed_percent for f in fans if f.speed_percent is not None]
                if speeds:
                    metrics.fan_speed_avg_percent = sum(speeds) / len(speeds)

        except NVMLError as exc:
            metrics.supported = False
            metrics.error = str(exc)
            logger.debug("NVML error on GPU %d: %s", index, exc)
        except Exception as exc:
            metrics.supported = False
            metrics.error = str(exc)
            logger.exception("Unexpected error reading NVIDIA GPU %d", index)

        return metrics

    def _read_nvidia_fans(self, handle) -> list[FanInfo]:
        """
        Read fan speed(s) for an NVIDIA GPU.
        Prefer nvmlDeviceGetFanSpeed_v2 (per-fan) when available.
        Falls back to the older single-value API.
        """
        fans: list[FanInfo] = []

        # Try multi-fan API first
        try:
            num_fans = nvmlDeviceGetNumFans(handle)
            if num_fans and num_fans > 0:
                for i in range(num_fans):
                    try:
                        speed = nvmlDeviceGetFanSpeed_v2(handle, i)
                        fans.append(FanInfo(index=i, speed_percent=int(speed)))
                    except Exception:
                        # Some drivers return error for individual fans
                        fans.append(FanInfo(index=i, speed_percent=None))
                return fans
        except Exception:
            # Older driver or no multi-fan support
            pass

        # Fallback: single fan value (many cards report one average %)
        try:
            speed = nvmlDeviceGetFanSpeed(handle)
            fans.append(FanInfo(index=0, speed_percent=int(speed)))
        except Exception:
            # Fan reading not supported (e.g. some laptop GPUs, or driver limitation)
            pass

        return fans


# Singleton helper for the rest of the application
_gpu_monitor: Optional[GPUMonitor] = None


def get_gpu_monitor() -> GPUMonitor:
    global _gpu_monitor
    if _gpu_monitor is None:
        _gpu_monitor = GPUMonitor()
    return _gpu_monitor
