"""Allow-listed remote commands from Telegram/Cloud — full PC control surface."""

from __future__ import annotations

import logging
from typing import Callable

from shmcontrol.system.control import SystemAction, execute_system_action

logger = logging.getLogger("shmcontrol.api.commands")


def _run(action: SystemAction, delay: int = 0) -> str:
    ok, msg = execute_system_action(action, delay_seconds=delay)
    return msg if ok else f"FAIL: {msg}"


def _status(_: str) -> str:
    try:
        from shmcontrol.system.metrics import MetricsCollector
        m = MetricsCollector().collect()
        gpu = "N/A"
        if m.gpus:
            g = m.gpus[0]
            bits = []
            if g.temperature_c is not None:
                bits.append(f"{g.temperature_c:.0f}C")
            if g.gpu_util_percent is not None:
                bits.append(f"{g.gpu_util_percent}%")
            gpu = " ".join(bits) or (g.name or "GPU")
        loc = m.local_ip or "N/A"
        pub = m.public_ip
        if not pub:
            try:
                from shmcontrol.network.tools import get_public_ip
                pub = get_public_ip(timeout=3.0)
            except Exception:
                pub = None
        pub = pub or "N/A"
        up = int(m.uptime_seconds)
        uh, urem = divmod(up, 3600)
        um, us = divmod(urem, 60)
        cpu_t = f"{m.cpu_temp_c:.0f}C" if m.cpu_temp_c is not None else "N/A"
        return (
            f"CPU {m.cpu_percent:.0f}% ({cpu_t}) | RAM {m.ram_percent:.0f}% "
            f"({m.ram_used_gb:.1f}/{m.ram_total_gb:.1f}GB) | "
            f"Disk {m.disk_percent:.0f}% | GPU {gpu}\n"
            f"NET ↓{m.net_download_mb_s:.2f} ↑{m.net_upload_mb_s:.2f} MB/s\n"
            f"Local {loc} | Public {pub}\n"
            f"Uptime {uh}h {um}m"
        )
    except Exception as e:
        return f"status error: {e}"


def _network(_: str) -> str:
    try:
        from shmcontrol.vpn.monitor import vpn_monitor
        from shmcontrol.system.metrics import MetricsCollector
        st = vpn_monitor.detect()
        vpn = "VPN ON" if st.connected else "VPN OFF"
        if st.processes:
            vpn += " (" + ", ".join(st.processes[:3]) + ")"
        m = MetricsCollector().collect()
        pub = m.public_ip
        if not pub:
            try:
                from shmcontrol.network.tools import get_public_ip
                pub = get_public_ip(timeout=3.0)
            except Exception:
                pub = None
        return f"{vpn}\nLocal {m.local_ip or 'N/A'} | Public {pub or 'N/A'}\n↓{m.net_download_mb_s:.2f} ↑{m.net_upload_mb_s:.2f} MB/s"
    except Exception as e:
        return str(e)


def _game(args: str) -> str:
    try:
        from shmcontrol.gaming.game_mode import game_mode_manager
        from shmcontrol.config.settings import settings_manager
        a = (args or "").strip().lower()
        if a in ("on", "1", "enable"):
            settings_manager.settings.game_mode_enabled = True
            settings_manager.save()
            game_mode_manager.enabled = True
            game_mode_manager.scan_and_apply()
            return "Game Mode enabled (scan active)"
        if a in ("off", "0", "disable"):
            if game_mode_manager.state.active:
                game_mode_manager.exit_game_mode()
            game_mode_manager.enabled = False
            settings_manager.settings.game_mode_enabled = False
            settings_manager.save()
            return "Game Mode disabled"
        s = game_mode_manager.state
        en = "ON" if game_mode_manager.enabled else "OFF"
        if s.active:
            return f"Game Mode {en} | Active: {s.game_name}"
        return f"Game Mode {en} | Idle"
    except Exception as e:
        return str(e)


def _dns(args: str) -> str:
    """dns | dns list | dns read | dns apply <name> | dns restore"""
    try:
        from shmcontrol.dns.manager import dns_manager
        a = (args or "").strip()
        low = a.lower()
        if not a or low in ("status", "read"):
            adapters = []
            if hasattr(dns_manager, "list_adapters"):
                try:
                    adapters = dns_manager.list_dns_adapters() or []
                except Exception:
                    pass
            lines = ["DNS status"]
            for ad in adapters[:5]:
                name = ad.get("name") or ad.get("description") or "?"
                try:
                    cur = dns_manager.read_adapter_dns(name) if hasattr(dns_manager, "read_dns") else None
                except Exception:
                    cur = None
                lines.append(f"- {name}: {cur or 'n/a'}")
            if len(lines) == 1:
                lines.append("(no adapter info)")
            return "\n".join(lines)
        if low.startswith("list"):
            servers = []
            if hasattr(dns_manager, "list_servers"):
                servers = dns_manager.list_servers() or []
            elif hasattr(dns_manager, "get_servers"):
                servers = dns_manager.get_servers() or []
            names = []
            for s in servers[:30]:
                if isinstance(s, dict):
                    names.append(s.get("name") or s.get("primary") or "?")
                else:
                    names.append(str(s))
            return "DNS list:\n" + "\n".join(f"• {n}" for n in names) if names else "No DNS list"
        if low.startswith("apply "):
            target = a[6:].strip()
            if not target:
                return "Usage: /dns apply Cloudflare"
            # Find server
            servers = []
            if hasattr(dns_manager, "list_servers"):
                servers = dns_manager.list_servers() or []
            match = None
            for s in servers:
                if not isinstance(s, dict):
                    continue
                if (s.get("name") or "").lower() == target.lower():
                    match = s
                    break
            if not match:
                return f"DNS profile not found: {target}"
            primary = match.get("primary") or match.get("primary_ipv4")
            secondary = match.get("secondary") or match.get("secondary_ipv4")
            adapters = dns_manager.list_dns_adapters() if hasattr(dns_manager, "list_adapters") else []
            physical = [x for x in adapters if not x.get("is_virtual")]
            if not physical and adapters:
                physical = adapters
            if not physical:
                return "No adapter to apply DNS"
            ad = physical[0].get("name") or physical[0].get("description")
            ok, msg, _ = dns_manager.apply_dns_windows(
                ad, primary, secondary, allow_virtual=False, verify=True
            )
            return msg if ok else f"FAIL: {msg}"
        if low.startswith("restore"):
            adapters = dns_manager.list_dns_adapters() if hasattr(dns_manager, "list_adapters") else []
            physical = [x for x in adapters if not x.get("is_virtual")] or adapters
            if not physical:
                return "No adapter"
            ad = physical[0].get("name") or physical[0].get("description")
            ok, msg, _ = dns_manager.restore_previous_dns(ad, verify=True)
            return msg if ok else f"FAIL: {msg}"
        return "Usage: /dns | /dns list | /dns apply Name | /dns restore"
    except Exception as e:
        return f"dns error: {e}"


def _usage(_: str) -> str:
    try:
        import psutil
        n = psutil.net_io_counters()
        return f"Total ↓{n.bytes_recv/1024**3:.2f}GB ↑{n.bytes_sent/1024**3:.2f}GB"
    except Exception as e:
        return str(e)


def _temp(_: str) -> str:
    try:
        from shmcontrol.system.metrics import MetricsCollector
        m = MetricsCollector().collect()
        cpu = f"{m.cpu_temp_c:.0f}C" if m.cpu_temp_c is not None else "N/A"
        gpu = "N/A"
        if m.gpus and m.gpus[0].temperature_c is not None:
            gpu = f"{m.gpus[0].temperature_c:.0f}C"
        note = ""
        if m.cpu_temp_c is None:
            note = (
                "\nCPU sensor: N/A on this PC (Windows often hides it). "
                "Install LibreHardwareMonitor for live CPU temp."
            )
        return f"CPU temp {cpu} | GPU temp {gpu}{note}"
    except Exception as e:
        return str(e)


def _timer(args: str) -> str:
    try:
        from shmcontrol.system.timer import system_timer
        a = (args or "").strip().lower()
        if a in ("cancel", "stop", "off"):
            system_timer.cancel()
            return "Timer cancelled"
        if a.startswith("shutdown") or a.startswith("restart") or a.startswith("sleep") or a.startswith("lock"):
            from datetime import datetime, timedelta, timezone
            parts = a.split()
            action = parts[0]
            mins = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 30
            target = datetime.now(timezone.utc) + timedelta(minutes=mins)
            ok, msg, _id = system_timer.schedule(action, target, source="telegram", require_confirm=False)
            return msg if ok else f"FAIL: {msg}"
        active = system_timer.get_active() if hasattr(system_timer, "get_active") else None
        if active:
            rem = system_timer.remaining_seconds() if hasattr(system_timer, "remaining_seconds") else None
            return f"Active timer: {getattr(active, 'action', active)} remaining={rem}s"
        return "No active timer. Usage: /timer shutdown 30 | /timer cancel"
    except Exception as e:
        return str(e)


def _processes(_: str) -> str:
    try:
        import psutil
        rows = []
        for p in psutil.process_iter(["name", "cpu_percent", "memory_percent"]):
            try:
                info = p.info
                cpu = info.get("cpu_percent") or 0
                if cpu and cpu > 1:
                    rows.append((cpu, info.get("name") or "?", info.get("memory_percent") or 0))
            except Exception:
                continue
        rows.sort(reverse=True)
        lines = [f"{n} CPU {c:.0f}% RAM {m:.0f}%" for c, n, m in rows[:12]]
        return "Top processes:\n" + "\n".join(lines) if lines else "No heavy processes"
    except Exception as e:
        return str(e)


def _update(_: str) -> str:
    try:
        from shmcontrol.updater import check_for_update
        info = check_for_update()
        if info.error:
            return f"Update check error: {info.error}"
        if info.available:
            return f"Update available: {info.current} → {info.latest}\n{info.html_url or ''}"
        return f"Up to date: v{info.current}"
    except Exception as e:
        return str(e)


def _hibernate(_: str) -> str:
    return _run(SystemAction.HIBERNATE, 0)


HANDLERS: dict[str, Callable[[str], str]] = {
    "status": _status,
    "system": _status,
    "network": _network,
    "dns": _dns,
    "game": _game,
    "usage": _usage,
    "vpn": _network,
    "temp": _temp,
    "temperature": _temp,
    "timer": _timer,
    "processes": _processes,
    "apps": _processes,
    "update": _update,
    "logs": lambda _a: "see app Logs page",
    "lock": lambda _a: _run(SystemAction.LOCK, 0),
    "sleep": lambda _a: _run(SystemAction.SLEEP, 0),
    "hibernate": _hibernate,
    "shutdown": lambda _a: _run(SystemAction.SHUTDOWN, 5),
    "restart": lambda _a: _run(SystemAction.RESTART, 5),
    "cancel_shutdown": lambda _a: _run(SystemAction.CANCEL_SHUTDOWN, 0),
}


def run_command(command: str, args: str = "") -> str:
    cmd = (command or "").strip().lower()
    handler = HANDLERS.get(cmd)
    if not handler:
        return f"blocked: {cmd}"
    try:
        return handler(args or "")
    except Exception as e:
        logger.exception("command failed: %s", cmd)
        return f"error: {e}"
