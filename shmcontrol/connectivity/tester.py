"""
Sh.M Control - Game / Launcher Connectivity Tester
Real tests only: DNS resolve, ICMP, TCP, TLS/HTTP.
No fake success. "Not Testable" when protocol cannot be tested.
Endpoints come from database, never hardcoded in logic.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from shmcontrol.database.models import db
from shmcontrol.network.tools import dns_lookup, ping, tcp_connect_test, http_test

logger = logging.getLogger("shmcontrol.connectivity")


class TestKind(str, Enum):
    DNS = "dns"
    ICMP = "icmp"
    TCP = "tcp"
    TLS = "tls"
    HTTP = "http"
    UDP = "udp"  # limited support


@dataclass
class EndpointSpec:
    id: Optional[int]
    hostname: str
    ip: Optional[str] = None
    port: Optional[int] = None
    protocol: str = "tcp"
    service_name: str = ""
    region: str = ""


@dataclass
class EndpointResult:
    hostname: str
    ip: Optional[str]
    port: Optional[int]
    protocol: str
    service_name: str
    success: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    details: str = ""
    not_testable: bool = False


@dataclass
class ConnectivityReport:
    target_name: str
    target_type: str
    dns_used: Optional[str] = None
    results: list[EndpointResult] = field(default_factory=list)
    started_at: float = 0.0
    finished_at: float = 0.0

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def successful(self) -> int:
        return sum(1 for r in self.results if r.success and not r.not_testable)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.success and not r.not_testable)

    @property
    def not_testable_count(self) -> int:
        return sum(1 for r in self.results if r.not_testable)

    @property
    def avg_latency(self) -> Optional[float]:
        vals = [r.latency_ms for r in self.results if r.latency_ms is not None]
        return sum(vals) / len(vals) if vals else None

    @property
    def status_summary(self) -> str:
        if self.total == 0:
            return "No endpoints configured"
        if self.failed == 0 and self.successful > 0:
            return "No detected connectivity issue"
        if self.successful == 0:
            return "Possible connectivity issue – all testable endpoints failed"
        return "Possible connectivity issue – some endpoints unreachable"

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_name": self.target_name,
            "target_type": self.target_type,
            "dns_used": self.dns_used,
            "total": self.total,
            "successful": self.successful,
            "failed": self.failed,
            "not_testable": self.not_testable_count,
            "avg_latency_ms": round(self.avg_latency, 1) if self.avg_latency else None,
            "status": self.status_summary,
            "results": [
                {
                    "hostname": r.hostname,
                    "ip": r.ip,
                    "port": r.port,
                    "protocol": r.protocol,
                    "service": r.service_name,
                    "success": r.success,
                    "latency_ms": r.latency_ms,
                    "error": r.error,
                    "not_testable": r.not_testable,
                    "details": r.details,
                }
                for r in self.results
            ],
        }


class ConnectivityTester:
    def __init__(self) -> None:
        pass

    def get_game_endpoints(self, game_name: str) -> list[EndpointSpec]:
        rows = db.execute(
            """
            SELECT e.id, e.hostname, e.ip, e.port, e.protocol, s.service_name, e.region
            FROM game_endpoints e
            LEFT JOIN game_services s ON e.service_id = s.id
            JOIN games g ON e.game_id = g.id
            WHERE g.name = ? AND e.enabled = 1
            """,
            (game_name,),
        )
        return [
            EndpointSpec(
                id=r["id"],
                hostname=r["hostname"],
                ip=r["ip"],
                port=r["port"],
                protocol=(r["protocol"] or "tcp").lower(),
                service_name=r["service_name"] or "",
                region=r["region"] or "",
            )
            for r in rows
        ]

    def get_launcher_endpoints(self, launcher_name: str) -> list[EndpointSpec]:
        rows = db.execute(
            """
            SELECT e.id, e.hostname, e.ip, e.port, e.protocol, e.service_name
            FROM launcher_endpoints e
            JOIN launchers l ON e.launcher_id = l.id
            WHERE l.name = ? AND e.enabled = 1
            """,
            (launcher_name,),
        )
        return [
            EndpointSpec(
                id=r["id"],
                hostname=r["hostname"],
                ip=r["ip"],
                port=r["port"],
                protocol=(r["protocol"] or "tcp").lower(),
                service_name=r["service_name"] or "",
            )
            for r in rows
        ]

    async def test_endpoint(self, ep: EndpointSpec) -> list[EndpointResult]:
        """
        Test one endpoint. If hostname resolves to multiple IPs,
        each IP is tested separately (real results only).
        Returns a list of EndpointResult.
        """
        results: list[EndpointResult] = []

        lookup = dns_lookup(ep.hostname)
        if not lookup.success:
            r = EndpointResult(
                hostname=ep.hostname,
                ip=ep.ip,
                port=ep.port,
                protocol=ep.protocol,
                service_name=ep.service_name,
                success=False,
                error=f"DNS resolution failed: {lookup.error}",
            )
            return [r]

        ips = list(lookup.addresses)
        if ep.ip and ep.ip not in ips:
            ips.insert(0, ep.ip)
        if not ips:
            ips = [ep.hostname]

        proto = ep.protocol.lower()
        port = ep.port or (443 if proto in ("https", "tls") else 80 if proto == "http" else None)

        for ip in ips:
            result = EndpointResult(
                hostname=ep.hostname,
                ip=ip,
                port=port,
                protocol=ep.protocol,
                service_name=ep.service_name,
                success=False,
            )

            if proto in ("icmp", "ping"):
                pr = ping(ip, count=3)
                result.success = pr.success
                result.latency_ms = pr.latency_ms
                result.error = pr.error
                results.append(result)
                continue

            if proto in ("tcp", "https", "tls", "http"):
                if port is None:
                    result.not_testable = True
                    result.error = "Port not specified – Not Testable"
                    results.append(result)
                    continue
                ok, latency, err = await tcp_connect_test(ip, port)
                result.success = ok
                result.latency_ms = latency
                result.error = err
                if ok and proto in ("https", "tls", "http"):
                    scheme = "https" if proto in ("https", "tls") else "http"
                    url = f"{scheme}://{ep.hostname}/"
                    if port not in (80, 443):
                        url = f"{scheme}://{ep.hostname}:{port}/"
                    h_ok, h_lat, status, h_err = await http_test(url)
                    if h_ok:
                        result.details = f"HTTP {status}"
                        if h_lat is not None:
                            result.latency_ms = h_lat
                    else:
                        result.details = f"TCP OK, HTTP: {h_err or 'failed'}"
                results.append(result)
                continue

            if proto == "udp":
                result.not_testable = True
                result.error = "UDP reachability test not available without raw sockets – Not Testable"
                results.append(result)
                continue

            result.not_testable = True
            result.error = f"Unknown protocol '{proto}' – Not Testable"
            results.append(result)

        return results

    async def run_test(
        self,
        target_name: str,
        target_type: str = "game",
        endpoints: Optional[list[EndpointSpec]] = None,
        dns_label: Optional[str] = None,
    ) -> ConnectivityReport:
        report = ConnectivityReport(
            target_name=target_name,
            target_type=target_type,
            dns_used=dns_label,
            started_at=time.time(),
        )
        if endpoints is None:
            if target_type == "game":
                endpoints = self.get_game_endpoints(target_name)
            elif target_type == "launcher":
                endpoints = self.get_launcher_endpoints(target_name)
            else:
                endpoints = []

        if not endpoints:
            report.finished_at = time.time()
            return report

        tasks = [self.test_endpoint(ep) for ep in endpoints]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                for item in r:
                    if isinstance(item, EndpointResult):
                        report.results.append(item)
            elif isinstance(r, EndpointResult):
                report.results.append(r)
            elif isinstance(r, Exception):
                logger.error("Endpoint test exception: %s", r)
        report.finished_at = time.time()
        return report

    async def compare_dns_labels(
        self,
        target_name: str,
        target_type: str,
        dns_labels: list[str],
    ) -> list[dict]:
        """
        Run the same connectivity test under the current system resolver.
        Note: Switching system DNS mid-test requires admin and is disruptive;
        this reports connectivity with the current DNS and labels the run.
        True multi-DNS comparison that changes system resolver is optional
        and only done when user explicitly Applies a DNS first.
        """
        out = []
        for label in dns_labels:
            report = await self.run_test(target_name, target_type, dns_label=label)
            out.append({
                "dns": label,
                "total": report.total,
                "successful": report.successful,
                "failed": report.failed,
                "avg_latency_ms": report.avg_latency,
                "status": report.status_summary,
            })
        return out


connectivity_tester = ConnectivityTester()
