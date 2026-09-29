"""
Sh.M Control - DNS Manager
Loads free DNS list from data file / DB. Never hardcodes paid services as free.
Supports testing, apply (Windows), restore automatic.
"""

from __future__ import annotations

import json
import logging
import platform
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from shmcontrol.database.models import db
from shmcontrol.network.tools import dns_lookup, ping

logger = logging.getLogger("shmcontrol.dns")


@dataclass
class DnsServer:
    id: Optional[int]
    name: str
    primary_ip: str
    secondary_ip: Optional[str] = None
    category: str = "General"
    country: str = ""
    doh_url: Optional[str] = None
    dot_host: Optional[str] = None
    dnssec: bool = False
    ipv6: Optional[str] = None
    is_free: bool = True
    enabled: bool = True
    source: str = "public"


class DnsManager:
    def __init__(self) -> None:
        self._loaded = False

    def seed_from_json(self, json_path: Optional[Path] = None, force: bool = False) -> int:
        """Import free DNS list into DB. force=True upserts missing names/IPs."""
        if json_path is None:
            root = Path(__file__).resolve().parents[2]
            json_path = root / "data" / "dns_servers.json"
        if not json_path.exists():
            logger.warning("DNS JSON not found: %s", json_path)
            return 0
        count_row = db.execute_one("SELECT COUNT(*) as c FROM dns_servers")
        existing_count = count_row["c"] if count_row else 0
        if existing_count > 0 and not force:
            # Still merge any new entries from JSON
            force = True
        data = json.loads(json_path.read_text(encoding="utf-8"))
        inserted = 0
        with db.connection() as conn:
            for item in data:
                if not item.get("is_free", 1):
                    continue
                name = item.get("name") or ""
                primary = item.get("ipv4_primary") or item.get("primary_ip")
                if not name or not primary:
                    continue
                secondary = item.get("ipv4_secondary") or item.get("secondary_ip")
                ipv6 = item.get("ipv6_primary") or item.get("ipv6")
                exists = conn.execute(
                    "SELECT id FROM dns_servers WHERE name = ? AND primary_ip = ?",
                    (name, primary),
                ).fetchone()
                if exists:
                    continue
                conn.execute(
                    """INSERT INTO dns_servers
                    (name, primary_ip, secondary_ip, category, country, doh_url, dot_host,
                     dnssec, ipv6, enabled, is_free, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?)""",
                    (
                        name,
                        primary,
                        secondary,
                        item.get("category") or "",
                        item.get("country") or "",
                        item.get("doh_url"),
                        item.get("dot_host"),
                        1 if item.get("dnssec") else 0,
                        ipv6,
                        item.get("source", "public"),
                    ),
                )
                inserted += 1
        logger.info("Seeded/merged %d free DNS servers (was %d)", inserted, existing_count)
        return inserted

    def list_servers(self, category: Optional[str] = None, free_only: bool = True) -> list[dict]:
        sql = "SELECT * FROM dns_servers WHERE enabled = 1"
        params: list[Any] = []
        if free_only:
            sql += " AND is_free = 1"
        if category:
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY category, name"
        rows = db.execute(sql, tuple(params))
        return [dict(r) for r in rows]

    def categories(self) -> list[str]:
        rows = db.execute("SELECT DISTINCT category FROM dns_servers WHERE enabled=1 ORDER BY category")
        return [r["category"] for r in rows]

    def test_dns(
        self,
        primary_ip: str,
        test_host: str = "example.com",
        timeout: float = 3.0,
        samples: int = 3,
    ) -> dict:
        """
        Test a DNS resolver by sending real DNS queries TO that server (UDP/53).
        Primary metric is DNS query success/time — NOT ICMP.
        samples: number of queries for min/avg/max (real only, no fabricated stats).
        """
        result = {
            "ip": primary_ip,
            "status": "offline",
            "resolution_ms": None,
            "resolution_min_ms": None,
            "resolution_avg_ms": None,
            "resolution_max_ms": None,
            "latency_ms": None,  # optional ICMP only
            "addresses": [],
            "error": None,
            "query_host": test_host,
            "last_tested": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        times: list[float] = []
        last_addrs: list[str] = []
        last_err: Optional[str] = None
        n = max(1, min(samples, 5))
        for _ in range(n):
            ok, ms, addrs, err = self._dns_query_udp(primary_ip, test_host, timeout=timeout)
            if ok and ms is not None:
                times.append(ms)
                if addrs:
                    last_addrs = addrs
            else:
                last_err = err
        if times:
            result["status"] = "online"
            result["resolution_min_ms"] = round(min(times), 1)
            result["resolution_max_ms"] = round(max(times), 1)
            result["resolution_avg_ms"] = round(sum(times) / len(times), 1)
            result["resolution_ms"] = result["resolution_avg_ms"]
            result["addresses"] = last_addrs
        else:
            result["status"] = "offline"
            result["error"] = last_err or "DNS query failed"

        try:
            pr = ping(primary_ip, count=1, timeout_ms=int(timeout * 1000))
            if pr.success and pr.latency_ms is not None:
                result["latency_ms"] = round(pr.latency_ms, 1)
        except Exception:
            pass

        return result

    @staticmethod
    def _dns_query_udp(
        resolver_ip: str,
        hostname: str,
        timeout: float = 3.0,
        qtype: int = 1,  # A
    ) -> tuple[bool, Optional[float], list[str], Optional[str]]:
        """
        Minimal DNS A-query over UDP to a specific resolver.
        Returns (success, time_ms, addresses, error).
        No third-party dependency required.
        """
        import random
        import socket
        import struct

        def encode_name(name: str) -> bytes:
            parts = name.strip(".").split(".")
            out = b""
            for p in parts:
                b = p.encode("idna")
                out += bytes([len(b)]) + b
            return out + b"\x00"

        try:
            tid = random.randint(0, 65535)
            header = struct.pack("!HHHHHH", tid, 0x0100, 1, 0, 0, 0)  # RD=1
            question = encode_name(hostname) + struct.pack("!HH", qtype, 1)  # IN
            packet = header + question

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            t0 = time.perf_counter()
            sock.sendto(packet, (resolver_ip, 53))
            data, _ = sock.recvfrom(4096)
            t1 = time.perf_counter()
            sock.close()

            if len(data) < 12:
                return False, None, [], "Truncated response"
            r_tid, flags, qd, an, ns, ar = struct.unpack("!HHHHHH", data[:12])
            if r_tid != tid:
                return False, None, [], "Transaction ID mismatch"
            rcode = flags & 0xF
            if rcode != 0:
                return False, (t1 - t0) * 1000, [], f"RCODE {rcode}"

            # Parse answers for A records (skip question)
            offset = 12
            # skip question name
            while offset < len(data) and data[offset] != 0:
                if data[offset] & 0xC0 == 0xC0:
                    offset += 2
                    break
                offset += 1 + data[offset]
            else:
                offset += 1
            offset += 4  # qtype qclass

            addresses: list[str] = []
            for _ in range(an):
                if offset >= len(data):
                    break
                # name (possibly pointer)
                if data[offset] & 0xC0 == 0xC0:
                    offset += 2
                else:
                    while offset < len(data) and data[offset] != 0:
                        offset += 1 + data[offset]
                    offset += 1
                if offset + 10 > len(data):
                    break
                rtype, rclass, _ttl, rdlen = struct.unpack("!HHIH", data[offset : offset + 10])
                offset += 10
                rdata = data[offset : offset + rdlen]
                offset += rdlen
                if rtype == 1 and rdlen == 4:  # A
                    addresses.append(".".join(str(b) for b in rdata))

            return True, (t1 - t0) * 1000, addresses, None
        except socket.timeout:
            return False, None, [], "Timeout"
        except OSError as e:
            return False, None, [], str(e)
        except Exception as e:
            return False, None, [], str(e)

    # ------------------------------------------------------------------
    # Windows DNS read / apply / restore (no shell injection)
    # ------------------------------------------------------------------

    VIRTUAL_ADAPTER_HINTS = (
        "vpn", "wintun", "tap", "tun", "wireguard", "openvpn", "nordlynx",
        "hyper-v", "vmware", "virtualbox", "vethernet", "docker", "wsl",
        "loopback", "isatap", "teredo", "6to4", "bluetooth",
    )

    def is_virtual_or_vpn_adapter(self, adapter_name: str) -> bool:
        n = (adapter_name or "").lower()
        return any(h in n for h in self.VIRTUAL_ADAPTER_HINTS)

    def list_dns_adapters(self) -> list[dict]:
        """
        List adapters for DNS UI.
        physical-first; virtual/vpn flagged so UI can warn.
        """
        from shmcontrol.network.tools import list_network_adapters
        out: list[dict] = []
        for a in list_network_adapters():
            name = a.get("name") or ""
            if not name:
                continue
            virtual = self.is_virtual_or_vpn_adapter(name)
            out.append({
                "name": name,
                "is_up": bool(a.get("is_up")),
                "is_virtual": virtual,
                "addresses": a.get("addresses") or [],
            })
        # Prefer non-virtual, up adapters first
        out.sort(key=lambda x: (x["is_virtual"], not x["is_up"], x["name"].lower()))
        return out

    @staticmethod
    def _is_valid_ipv4(ip: str) -> bool:
        if not ip or not isinstance(ip, str):
            return False
        parts = ip.strip().split(".")
        if len(parts) != 4:
            return False
        try:
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            return False

    def _netsh_run(self, args: list[str]) -> tuple[int, str, str]:
        """Run netsh with fixed argv list only (no shell)."""
        proc = subprocess.run(
            ["netsh", *args],
            capture_output=True,
            text=True,
            shell=False,
            timeout=30,
        )
        return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()

    def is_admin_windows(self) -> Optional[bool]:
        """True if elevated, False if not, None if not Windows / unknown."""
        if platform.system() != "Windows":
            return None
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return None

    def read_adapter_dns(self, adapter_name: str) -> dict:
        """
        Read current DNS configuration for a Windows adapter.
        Returns:
          mode: dhcp | static | unknown
          servers: list[str]
          raw: optional raw text
        """
        result = {
            "adapter": adapter_name,
            "mode": "unknown",
            "servers": [],
            "raw": "",
            "ok": False,
            "error": None,
        }
        if platform.system() != "Windows":
            result["error"] = "DNS read is only implemented for Windows"
            return result
        if not adapter_name or any(c in adapter_name for c in "\n\r;&|"):
            result["error"] = "Invalid adapter name"
            return result
        try:
            code, out, err = self._netsh_run([
                "interface", "ip", "show", "dns", f"name={adapter_name}",
            ])
            result["raw"] = out or err
            if code != 0 and not out:
                result["error"] = err or "Failed to read DNS"
                db.log("ERROR", "dns", "DNS_READ", adapter_name, err or "failed")
                return result

            text = (out or "").lower()
            servers: list[str] = []
            # Parse common netsh formats (EN/localized partially via digit patterns)
            for line in (out or "").splitlines():
                line_s = line.strip()
                # DHCP message
                low = line_s.lower()
                if "dhcp" in low and ("yes" in low or "true" in low or "enabled" in low):
                    result["mode"] = "dhcp"
                # Static servers often shown as "DNS servers configured through DHCP: None"
                # or "Statically Configured DNS Servers: 1.1.1.1"
                # Collect any IPv4 tokens on lines mentioning DNS / server
                for token in line_s.replace(",", " ").split():
                    if self._is_valid_ipv4(token):
                        if token not in servers:
                            servers.append(token)

            if servers:
                result["servers"] = servers
                if result["mode"] == "unknown":
                    # If we found explicit static-looking servers without dhcp yes
                    if "statically" in text or "static" in text:
                        result["mode"] = "static"
                    elif "dhcp" in text and ("none" in text or not servers):
                        result["mode"] = "dhcp"
                    else:
                        result["mode"] = "static" if servers else "dhcp"
            else:
                if "dhcp" in text:
                    result["mode"] = "dhcp"
                result["servers"] = []

            result["ok"] = True
            db.log(
                "INFO", "dns", "DNS_READ",
                f"{adapter_name} mode={result['mode']} servers={','.join(result['servers']) or 'none'}",
            )
            return result
        except Exception as e:
            result["error"] = str(e)
            db.log("ERROR", "dns", "DNS_READ", adapter_name, str(e))
            return result

    def _save_dns_backup(self, adapter_name: str, snapshot: dict) -> None:
        """Persist last known DNS config for restore."""
        try:
            with db.connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS dns_backups (
                        adapter TEXT PRIMARY KEY,
                        mode TEXT,
                        servers_json TEXT,
                        changed_at TEXT
                    )
                    """
                )
                import json as _json
                from datetime import datetime, timezone
                conn.execute(
                    """
                    INSERT OR REPLACE INTO dns_backups (adapter, mode, servers_json, changed_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        adapter_name,
                        snapshot.get("mode") or "unknown",
                        _json.dumps(snapshot.get("servers") or []),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
        except Exception as e:
            logger.warning("DNS backup save failed: %s", e)

    def _load_dns_backup(self, adapter_name: str) -> Optional[dict]:
        try:
            import json as _json
            with db.connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS dns_backups (
                        adapter TEXT PRIMARY KEY,
                        mode TEXT,
                        servers_json TEXT,
                        changed_at TEXT
                    )
                    """
                )
                row = conn.execute(
                    "SELECT mode, servers_json, changed_at FROM dns_backups WHERE adapter = ?",
                    (adapter_name,),
                ).fetchone()
            if not row:
                return None
            return {
                "mode": row["mode"],
                "servers": _json.loads(row["servers_json"] or "[]"),
                "changed_at": row["changed_at"],
            }
        except Exception:
            return None

    def apply_dns_windows(
        self,
        adapter_name: str,
        primary: str,
        secondary: Optional[str] = None,
        *,
        allow_virtual: bool = False,
        verify: bool = True,
    ) -> tuple[bool, str, dict]:
        """
        Apply static DNS to adapter. Requires admin on Windows.
        Returns (ok, message, details).
        Never reports success without post-read verification when verify=True.
        """
        details: dict = {
            "adapter": adapter_name,
            "requested_primary": primary,
            "requested_secondary": secondary,
            "previous": None,
            "after": None,
            "applied": False,
            "verified": False,
            "query": None,
        }

        if not adapter_name or any(c in adapter_name for c in "\n\r;&|"):
            return False, "Invalid adapter name", details
        if not self._is_valid_ipv4(primary):
            return False, f"Invalid primary DNS IP: {primary}", details
        if secondary and not self._is_valid_ipv4(secondary):
            return False, f"Invalid secondary DNS IP: {secondary}", details
        if self.is_virtual_or_vpn_adapter(adapter_name) and not allow_virtual:
            return (
                False,
                f"Adapter '{adapter_name}' looks like VPN/Virtual. "
                "Select a physical adapter, or confirm virtual apply explicitly.",
                details,
            )
        if platform.system() != "Windows":
            return False, "DNS apply is only implemented for Windows", details

        admin = self.is_admin_windows()
        if admin is False:
            msg = "Administrator permission is required to change DNS settings."
            db.log("ERROR", "dns", "DNS_APPLY_FAILED", adapter_name, msg)
            return False, msg, details

        # Backup current config
        before = self.read_adapter_dns(adapter_name)
        details["previous"] = before
        if before.get("ok"):
            self._save_dns_backup(adapter_name, before)

        db.log(
            "INFO", "dns", "DNS_APPLY_STARTED",
            f"{adapter_name} -> {primary}" + (f"/{secondary}" if secondary else ""),
        )

        try:
            code1, out1, err1 = self._netsh_run([
                "interface", "ip", "set", "dns",
                f"name={adapter_name}", "static", primary, "primary",
            ])
            if code1 != 0:
                err = err1 or out1 or "Failed to set primary DNS"
                # Access denied often
                if "access" in (err + out1).lower() or "denied" in (err + out1).lower():
                    err = "Administrator permission is required to change DNS settings. " + err
                db.log("ERROR", "dns", "DNS_APPLY_FAILED", adapter_name, err)
                return False, f"DNS Apply Failed: {err}", details

            if secondary:
                code2, out2, err2 = self._netsh_run([
                    "interface", "ip", "add", "dns",
                    f"name={adapter_name}", secondary, "index=2",
                ])
                if code2 != 0:
                    # Non-fatal if secondary already present; log only
                    logger.warning("Secondary DNS add: %s", err2 or out2 or code2)

            if not verify:
                details["applied"] = True
                db.log("INFO", "dns", "DNS_APPLY_SUCCESS", adapter_name, primary)
                return True, f"DNS set to {primary}" + (f" / {secondary}" if secondary else ""), details

            after = self.read_adapter_dns(adapter_name)
            details["after"] = after
            applied_ok = after.get("ok") and primary in (after.get("servers") or [])
            details["applied"] = bool(applied_ok)
            details["verified"] = bool(applied_ok)

            # Real DNS query verification against the resolver itself
            q = self.test_dns(primary, samples=1, timeout=3.0)
            details["query"] = {
                "status": q.get("status"),
                "resolution_ms": q.get("resolution_ms"),
                "error": q.get("error"),
            }
            db.log(
                "INFO", "dns", "DNS_VERIFY",
                f"{adapter_name} applied={applied_ok} query={q.get('status')} ms={q.get('resolution_ms')}",
            )

            if applied_ok:
                db.log("INFO", "dns", "DNS_APPLY_SUCCESS", adapter_name, primary)
                msg = (
                    f"DNS Applied Successfully\n"
                    f"Adapter: {adapter_name}\n"
                    f"Resolver: {primary}"
                    + (f" / {secondary}" if secondary else "")
                    + f"\nQuery: {q.get('status')}"
                    + (f"\nLatency: {q.get('resolution_ms')} ms" if q.get("resolution_ms") is not None else "")
                )
                return True, msg, details

            # netsh may have returned 0 but read didn't confirm
            err = "DNS Apply Failed: configuration not confirmed on adapter after change"
            if after.get("error"):
                err += f" ({after['error']})"
            db.log("ERROR", "dns", "DNS_APPLY_FAILED", adapter_name, err)
            return False, err, details
        except Exception as e:
            db.log("ERROR", "dns", "DNS_APPLY_FAILED", adapter_name, str(e))
            return False, f"DNS Apply Failed: {e}", details

    def restore_previous_dns(self, adapter_name: str, *, verify: bool = True) -> tuple[bool, str, dict]:
        """
        Restore DNS from backup snapshot:
          - mode dhcp → DHCP/automatic
          - mode static → previous static servers
        Falls back to DHCP if no backup.
        """
        details: dict = {"adapter": adapter_name, "backup": None, "after": None, "restored": False}
        if platform.system() != "Windows":
            return False, "Only Windows supported", details
        if not adapter_name or any(c in adapter_name for c in "\n\r;&|"):
            return False, "Invalid adapter name", details

        admin = self.is_admin_windows()
        if admin is False:
            msg = "Administrator permission is required to change DNS settings."
            db.log("ERROR", "dns", "DNS_RESTORE_FAILED", adapter_name, msg)
            return False, msg, details

        backup = self._load_dns_backup(adapter_name)
        details["backup"] = backup
        db.log("INFO", "dns", "DNS_RESTORE_STARTED", adapter_name, str(backup))

        try:
            if backup and backup.get("mode") == "static" and backup.get("servers"):
                servers = [s for s in backup["servers"] if self._is_valid_ipv4(s)]
                if not servers:
                    return False, "Backup static DNS invalid", details
                primary = servers[0]
                secondary = servers[1] if len(servers) > 1 else None
                ok, msg, det = self.apply_dns_windows(
                    adapter_name, primary, secondary, allow_virtual=True, verify=verify
                )
                details.update(det)
                details["restored"] = ok
                if ok:
                    db.log("INFO", "dns", "DNS_RESTORE_SUCCESS", adapter_name, "static")
                    return True, f"Restored previous static DNS: {primary}" + (f" / {secondary}" if secondary else ""), details
                db.log("ERROR", "dns", "DNS_RESTORE_FAILED", adapter_name, msg)
                return False, f"DNS Restore Failed: {msg}", details

            # DHCP / automatic (default if no backup or previous was dhcp)
            code, out, err = self._netsh_run([
                "interface", "ip", "set", "dns", f"name={adapter_name}", "dhcp",
            ])
            if code != 0:
                err_s = err or out or "Failed"
                if "access" in err_s.lower() or "denied" in err_s.lower():
                    err_s = "Administrator permission is required to change DNS settings. " + err_s
                db.log("ERROR", "dns", "DNS_RESTORE_FAILED", adapter_name, err_s)
                return False, f"DNS Restore Failed: {err_s}", details

            after = self.read_adapter_dns(adapter_name) if verify else {}
            details["after"] = after
            details["restored"] = True
            db.log("INFO", "dns", "DNS_RESTORE_SUCCESS", adapter_name, "dhcp")
            return True, "DNS restored to Automatic / DHCP", details
        except Exception as e:
            db.log("ERROR", "dns", "DNS_RESTORE_FAILED", adapter_name, str(e))
            return False, f"DNS Restore Failed: {e}", details

    def restore_automatic_dns(self, adapter_name: str) -> tuple[bool, str]:
        """Backward-compatible wrapper → DHCP restore."""
        ok, msg, _ = self.restore_previous_dns(adapter_name, verify=True)
        return ok, msg


dns_manager = DnsManager()
