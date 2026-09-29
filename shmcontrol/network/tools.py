"""
Sh.M Control - Network Tools
Ping, DNS lookup, public IP, adapters, flush DNS, etc.
All results are real; no fabricated data.
"""

from __future__ import annotations

import asyncio
import logging
import platform
import socket
import subprocess
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger("shmcontrol.network.tools")


@dataclass
class PingResult:
    host: str
    success: bool
    latency_ms: Optional[float] = None
    packet_loss: Optional[float] = None
    error: Optional[str] = None
    raw: str = ""


@dataclass
class DnsLookupResult:
    hostname: str
    addresses: list[str] = field(default_factory=list)
    success: bool = False
    error: Optional[str] = None


def is_windows() -> bool:
    return platform.system() == "Windows"


def get_local_ip() -> Optional[str]:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.3)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return None


def get_public_ip(timeout: float = 2.0) -> Optional[str]:
    """Best-effort; returns None offline without raising."""
    services = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
    ]
    for url in services:
        try:
            with httpx.Client(timeout=timeout) as client:
                r = client.get(url)
                if r.status_code == 200:
                    ip = r.text.strip()
                    if ip and len(ip) < 50 and " " not in ip:
                        return ip
        except Exception:
            continue
    return None


def dns_lookup(hostname: str) -> DnsLookupResult:
    result = DnsLookupResult(hostname=hostname)
    try:
        infos = socket.getaddrinfo(hostname, None)
        addrs = sorted({info[4][0] for info in infos})
        result.addresses = addrs
        result.success = len(addrs) > 0
    except socket.gaierror as e:
        result.error = str(e)
    except Exception as e:
        result.error = str(e)
    return result


def ping(host: str, count: int = 4, timeout_ms: int = 2000) -> PingResult:
    """Real ICMP ping via system ping command."""
    result = PingResult(host=host, success=False)
    try:
        if is_windows():
            cmd = ["ping", "-n", str(count), "-w", str(timeout_ms), host]
        else:
            cmd = ["ping", "-c", str(count), "-W", str(max(timeout_ms // 1000, 1)), host]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        result.raw = proc.stdout + proc.stderr
        if proc.returncode == 0:
            result.success = True
            # Simple latency extraction
            import re
            if is_windows():
                times = re.findall(r"time[=<](\d+)ms", result.raw, re.I)
            else:
                times = re.findall(r"time=([\d.]+)\s*ms", result.raw)
            if times:
                vals = [float(t) for t in times]
                result.latency_ms = sum(vals) / len(vals)
            # Packet loss
            loss_match = re.search(r"(\d+)%\s*(packet\s*)?loss", result.raw, re.I)
            if loss_match:
                result.packet_loss = float(loss_match.group(1))
        else:
            result.error = "Ping failed or host unreachable"
    except subprocess.TimeoutExpired:
        result.error = "Timeout"
    except Exception as e:
        result.error = str(e)
    return result


async def tcp_connect_test(host: str, port: int, timeout: float = 5.0) -> tuple[bool, Optional[float], Optional[str]]:
    """Async TCP connection test. Returns (success, latency_ms, error)."""
    start = asyncio.get_event_loop().time()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        latency = (asyncio.get_event_loop().time() - start) * 1000
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True, latency, None
    except asyncio.TimeoutError:
        return False, None, "Timeout"
    except Exception as e:
        return False, None, str(e)


async def http_test(url: str, timeout: float = 8.0) -> tuple[bool, Optional[float], Optional[int], Optional[str]]:
    """HTTP/HTTPS status + response time."""
    start = asyncio.get_event_loop().time()
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            r = await client.get(url)
            latency = (asyncio.get_event_loop().time() - start) * 1000
            return True, latency, r.status_code, None
    except Exception as e:
        return False, None, None, str(e)


def flush_dns() -> tuple[bool, str]:
    try:
        if is_windows():
            proc = subprocess.run(["ipconfig", "/flushdns"], capture_output=True, text=True)
            return proc.returncode == 0, proc.stdout or proc.stderr
        else:
            # Linux common
            for cmd in (["systemd-resolve", "--flush-caches"], ["resolvectl", "flush-caches"]):
                try:
                    proc = subprocess.run(cmd, capture_output=True, text=True)
                    if proc.returncode == 0:
                        return True, "DNS cache flushed"
                except Exception:
                    continue
            return False, "Flush DNS not available"
    except Exception as e:
        return False, str(e)


def list_network_adapters() -> list[dict[str, Any]]:
    """List network interfaces (name, addresses, status)."""
    import psutil
    adapters = []
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()
    for name, addr_list in addrs.items():
        info: dict[str, Any] = {"name": name, "addresses": [], "is_up": False}
        if name in stats:
            info["is_up"] = stats[name].isup
            info["speed_mbps"] = stats[name].speed
        for a in addr_list:
            if a.family.name in ("AF_INET", "AF_INET6"):
                info["addresses"].append({"family": a.family.name, "address": a.address})
        adapters.append(info)
    return adapters


def get_default_gateway() -> Optional[str]:
    try:
        if is_windows():
            proc = subprocess.run(["route", "print", "0.0.0.0"], capture_output=True, text=True)
            for line in proc.stdout.splitlines():
                if "0.0.0.0" in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        return parts[2]
        else:
            proc = subprocess.run(["ip", "route"], capture_output=True, text=True)
            for line in proc.stdout.splitlines():
                if line.startswith("default"):
                    parts = line.split()
                    if "via" in parts:
                        return parts[parts.index("via") + 1]
    except Exception:
        pass
    return None
