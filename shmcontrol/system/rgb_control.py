"""
Sh.M Control - RGB Control

Honest policy:
  Without OpenRGB server, manufacturer SDK, or verified HID device support,
  RGB cannot be controlled. Never fake color changes in UI only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("shmcontrol.system.rgb")


@dataclass
class RgbDevice:
    name: str
    type: str  # keyboard | motherboard | gpu | other
    supported: bool = False


@dataclass
class RgbStatus:
    supported: bool = False
    backend: str = "none"
    devices: list[RgbDevice] = field(default_factory=list)
    current_profile: Optional[str] = None
    message: str = "RGB Control Not Supported"


class RgbController:
    def __init__(self) -> None:
        self._previous_profile: Optional[dict] = None
        self._profile_name: Optional[str] = None

    def status(self) -> RgbStatus:
        # Optional: OpenRGB TCP (localhost:6742) if user runs OpenRGB
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            s.connect(("127.0.0.1", 6742))
            s.close()
            return RgbStatus(
                supported=True,
                backend="openrgb",
                devices=[RgbDevice(name="OpenRGB Server", type="other", supported=True)],
                current_profile=self._profile_name,
                message="OpenRGB server detected on localhost:6742. Full control requires openrgb Python client.",
            )
        except Exception:
            pass

        return RgbStatus(
            supported=False,
            backend="none",
            devices=[],
            message=(
                "RGB Control Not Supported. "
                "Start OpenRGB with SDK server, or use vendor SDK (Lenovo/ASUS/etc.) for hardware RGB."
            ),
        )

    def set_static(self, r: int, g: int, b: int, brightness: int = 100) -> tuple[bool, str]:
        st = self.status()
        if not st.supported:
            return False, "RGB Control Not Supported"
        return False, "OpenRGB client binding not installed — detection only in this build"

    def apply_profile(self, name: str) -> tuple[bool, str]:
        st = self.status()
        if not st.supported:
            return False, "RGB Control Not Supported"
        self._previous_profile = {"name": self._profile_name}
        self._profile_name = name
        return False, "RGB profile apply requires OpenRGB SDK client"

    def restore_previous(self) -> tuple[bool, str]:
        if self._previous_profile is None:
            return False, "No previous RGB profile"
        return False, "RGB Control Not Supported"


rgb_controller = RgbController()
