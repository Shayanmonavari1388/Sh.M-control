"""
Sh.M Control - Fan Monitoring / Control

Reality:
  Reading/controlling fans on Windows requires manufacturer SDK, LibreHardwareMonitor,
  or low-level EC access. Pure Python without those backends cannot invent RPM.

This module:
  - Attempts optional backends if present
  - Returns Not Supported when unavailable
  - NEVER fabricates RPM or fan percentages
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("shmcontrol.system.fan")


@dataclass
class FanInfo:
    name: str
    rpm: Optional[int] = None
    percent: Optional[int] = None
    supported: bool = False
    error: Optional[str] = None


@dataclass
class FanStatus:
    supported: bool = False
    backend: str = "none"
    fans: list[FanInfo] = field(default_factory=list)
    message: str = "Hardware Fan Control Not Supported"


class FanController:
    """Detect fans; control only if a real backend is available."""

    def __init__(self) -> None:
        self._backend = "none"
        self._previous_profile: Optional[dict] = None

    def status(self) -> FanStatus:
        # Try psutil sensors_fans (mostly Linux)
        try:
            import psutil
            if hasattr(psutil, "sensors_fans"):
                fans = psutil.sensors_fans() or {}
                out: list[FanInfo] = []
                for name, entries in fans.items():
                    for e in entries:
                        rpm = getattr(e, "current", None)
                        out.append(
                            FanInfo(
                                name=f"{name}:{getattr(e, 'label', '') or 'fan'}",
                                rpm=int(rpm) if rpm is not None else None,
                                supported=rpm is not None,
                            )
                        )
                if out:
                    return FanStatus(supported=True, backend="psutil", fans=out, message="OK")
        except Exception as e:
            logger.debug("psutil fans: %s", e)

        # NVIDIA GPU fan % already covered by gpu_monitor — surface as info only
        try:
            from shmcontrol.system.gpu_monitor import get_gpu_monitor
            gpus = get_gpu_monitor().get_all_gpus()
            out = []
            for g in gpus:
                if g.fans:
                    for f in g.fans:
                        if f.speed_percent is not None:
                            out.append(
                                FanInfo(
                                    name=f"{g.name} Fan{f.index}",
                                    percent=f.speed_percent,
                                    supported=True,
                                )
                            )
            if out:
                return FanStatus(
                    supported=True,
                    backend="nvml",
                    fans=out,
                    message="GPU fan % via NVML (read-only monitoring). System/CPU fan control not available.",
                )
        except Exception as e:
            logger.debug("nvml fans: %s", e)

        return FanStatus(
            supported=False,
            backend="none",
            fans=[],
            message=(
                "Hardware Fan Control Not Supported. "
                "Install vendor tools (e.g. manufacturer SDK / LibreHardwareMonitor) for chassis fans. "
                "NVIDIA GPU fan percentage may appear when NVML is available."
            ),
        )

    def set_mode(self, mode: str) -> tuple[bool, str]:
        """Modes: auto silent balanced performance custom — only if backend supports write."""
        st = self.status()
        if not st.supported or st.backend not in ("vendor",):  # no write backend yet
            return False, "Hardware Fan Control Not Supported on this system"
        return False, "Fan mode write not available without vendor SDK"

    def apply_curve(self, points: list[tuple[float, int]]) -> tuple[bool, str]:
        """points: list of (temp_c, fan_percent). Safety: reject 0% unless marked zero-rpm capable."""
        for temp, pct in points:
            if pct < 0 or pct > 100:
                return False, "Invalid fan percent"
            if pct == 0:
                return False, "0% fan not allowed (safety) unless hardware Zero-RPM is confirmed"
        return False, "Hardware Fan Control Not Supported — cannot apply curve without vendor API"

    def restore_previous(self) -> tuple[bool, str]:
        if self._previous_profile is None:
            return False, "No previous fan profile stored"
        return False, "Hardware Fan Control Not Supported"


fan_controller = FanController()
