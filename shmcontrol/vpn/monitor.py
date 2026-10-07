"""
Sh.M Control - VPN Detection & Traffic Monitoring
Detection only – does not provide VPN service.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import psutil

logger = logging.getLogger("shmcontrol.vpn")

# Interface name keywords (Windows / Linux)
VPN_IF_KEYWORDS = (
    "wintun", "tap-windows", "tap0901", "tap", "tun", "wireguard", "wg-",
    "openvpn", "nordlynx", "nordvpn", "proton", "mullvad", "expressvpn",
    "surfshark", "anyconnect", "vpn", "outline", "v2ray", "xray", "sing",
    "singbox", "sing-box", "clash", "meta", "mihomo", "hysteria", "aethon",
    "utun", "tun0", "wg0", "cloudflare", "warp", "tailscale", "zerotier",
    "hamachi", "softether", "sstp", "pptp", "l2tp",
)

# Process names that indicate a tunnel client is running
VPN_PROCESS_KEYWORDS = (
    "openvpn", "wireguard", "wireguard.exe", "wg.exe", "nordvpn", "expressvpn",
    "surfshark", "protonvpn", "mullvad", "v2ray", "xray", "sing-box", "singbox",
    "clash", "clash-meta", "mihomo", "hysteria", "hysteria2", "naive", "trojan",
    "outline", "shadowsocks", "ss-local", "wintun", "tun2socks", "warp-svc",
    "cloudflared", "tailscale", "zerotier", "softether",
)

# Physical/default adapters we should NOT treat as VPN by default
PHYSICAL_HINTS = (
    "wi-fi", "wifi", "ethernet", "local area connection", "wlan",
    "bluetooth", "vethernet", "hyper-v", "docker", "br-", "lo",
)


@dataclass
class VpnStatus:
    connected: bool = False
    adapters: list[str] = field(default_factory=list)
    processes: list[str] = field(default_factory=list)
    provider_hint: str = "Unknown"
    download_bytes: int = 0
    upload_bytes: int = 0
    per_app_attribution: str = "unavailable"
    detection_method: str = ""  # adapter | process | both


class VpnMonitor:
    def __init__(self) -> None:
        self._last_io: dict[str, tuple[int, int]] = {}

    def _find_processes(self) -> list[str]:
        found: list[str] = []
        try:
            for p in psutil.process_iter(["name"]):
                name = p.info.get("name") or ""
                low = name.lower()
                if any(k in low for k in VPN_PROCESS_KEYWORDS):
                    if name not in found:
                        found.append(name)
        except (psutil.Error, PermissionError):
            pass
        return found

    def _find_adapters(self) -> list[str]:
        adapters: list[str] = []
        try:
            stats = psutil.net_if_stats()
        except Exception:
            return adapters
        for name, st in stats.items():
            if not st.isup:
                continue
            lower = name.lower()
            # skip obvious physical if no vpn keyword
            if any(k in lower for k in VPN_IF_KEYWORDS):
                adapters.append(name)
                continue
            # Windows sometimes names TUN as "VPN - xxx" or random with "tun"
            if "vpn" in lower or "tun" in lower:
                if not any(p in lower for p in PHYSICAL_HINTS):
                    adapters.append(name)
        return adapters

    def detect(self) -> VpnStatus:
        status = VpnStatus()
        status.processes = self._find_processes()
        status.adapters = self._find_adapters()

        if status.adapters and status.processes:
            status.connected = True
            status.detection_method = "both"
        elif status.adapters:
            status.connected = True
            status.detection_method = "adapter"
        elif status.processes:
            # Client running – treat as connected even if interface name is generic
            status.connected = True
            status.detection_method = "process"
        else:
            status.connected = False
            status.detection_method = ""

        # Provider hint
        joined = " ".join(status.adapters + status.processes).lower()
        for hint, keys in (
            ("sing-box / xray", ("sing", "xray", "v2ray")),
            ("WireGuard", ("wireguard", "wintun", "wg")),
            ("OpenVPN", ("openvpn", "tap")),
            ("Clash / Meta", ("clash", "mihomo", "meta")),
            ("Cloudflare WARP", ("warp", "cloudflare")),
            ("Tailscale", ("tailscale",)),
            ("NordVPN", ("nord",)),
            ("Proton", ("proton",)),
            ("Mullvad", ("mullvad",)),
        ):
            if any(k in joined for k in keys):
                status.provider_hint = hint
                break
        else:
            if status.connected:
                status.provider_hint = "VPN/Proxy client"

        # Traffic from matched adapters
        try:
            io = psutil.net_io_counters(pernic=True)
            for name in status.adapters:
                if name in io:
                    c = io[name]
                    status.download_bytes += c.bytes_recv
                    status.upload_bytes += c.bytes_sent
        except Exception:
            pass

        return status


vpn_monitor = VpnMonitor()
