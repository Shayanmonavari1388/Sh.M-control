"""
Sh.M Control - Telegram Bot (secure remote control)
Token from ENV only. Only authorized user_id can issue commands.
No arbitrary shell execution. Destructive actions need one-time confirm.
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from typing import Optional

logger = logging.getLogger("shmcontrol.telegram")

ALLOWED_COMMANDS = {
    "start", "status", "system", "network", "usage", "vpn", "dns",
    "game", "connectivity", "logs", "restart", "shutdown", "sleep", "lock",
    "timer", "cancel_timer", "confirm", "cancel",
}

# One-time confirmations: token -> {action, expires, user_id}
_pending: dict[str, dict] = {}
_rate: dict[int, list[float]] = {}


def get_token() -> Optional[str]:
    env = os.getenv("GUARDIAN_TELEGRAM_BOT_TOKEN")
    if env:
        return env.strip()
    try:
        from shmcontrol.config.settings import settings_manager
        tok = getattr(settings_manager.settings, "telegram_bot_token", None)
        if tok:
            return str(tok).strip()
    except Exception:
        pass
    return None


def get_authorized_user_id() -> Optional[int]:
    raw = os.getenv("GUARDIAN_TELEGRAM_USER_ID")
    if not raw:
        from shmcontrol.config.settings import settings_manager
        return settings_manager.settings.telegram_user_id
    try:
        return int(raw)
    except ValueError:
        return None


def _rate_ok(user_id: int, limit: int = 20, window: float = 60.0) -> bool:
    now = time.time()
    bucket = _rate.setdefault(user_id, [])
    _rate[user_id] = [t for t in bucket if now - t < window]
    if len(_rate[user_id]) >= limit:
        return False
    _rate[user_id].append(now)
    return True


def _request_confirm(user_id: int, action: str, detail: str = "") -> str:
    token = secrets.token_hex(4)
    _pending[token] = {
        "user_id": user_id,
        "action": action,
        "detail": detail,
        "expires": time.time() + 120,
    }
    return (
        f"⚠️ Confirm required for *{action}*\n"
        f"{detail}\n\n"
        f"Reply within 2 minutes:\n"
        f"/confirm {token}\n"
        f"or /cancel {token}"
    )


def _consume_confirm(user_id: int, token: str) -> Optional[dict]:
    item = _pending.pop(token, None)
    if not item:
        return None
    if item["user_id"] != user_id:
        return None
    if time.time() > item["expires"]:
        return None
    return item


async def handle_command(user_id: int, command: str, args: str = "") -> str:
    auth = get_authorized_user_id()
    if auth is None or user_id != auth:
        return "⛔ Unauthorized. This device is bound to another Telegram user."
    if not _rate_ok(user_id):
        return "⛔ Rate limit. Try again later."

    cmd = command.lower().lstrip("/")
    if cmd not in ALLOWED_COMMANDS:
        return f"Unknown command. Allowed: {', '.join(sorted(ALLOWED_COMMANDS))}"

    if cmd == "start":
        return (
            "🛡 *Sh.M Control*\n"
            "Commands: /status /system /network /usage /vpn /dns /logs /game /connectivity\n"
            "Power: /lock /sleep /restart /shutdown (confirm required)\n"
            "Timer: /timer shutdown 2h | /cancel_timer"
        )

    if cmd == "confirm":
        token = args.strip().split()[0] if args.strip() else ""
        item = _consume_confirm(user_id, token)
        if not item:
            return "❌ Invalid or expired confirmation."
        return await _execute_confirmed(item["action"], item.get("detail", ""))

    if cmd == "cancel":
        token = args.strip().split()[0] if args.strip() else ""
        if token in _pending and _pending[token]["user_id"] == user_id:
            _pending.pop(token, None)
            return "✅ Cancelled."
        return "Nothing to cancel."

    if cmd == "status":
        from shmcontrol.system.metrics import MetricsCollector
        from shmcontrol.system.timer import system_timer
        m = MetricsCollector().collect()
        gpu = m.gpus[0] if m.gpus else None
        lines = [
            "📊 *Status*",
            f"CPU: {m.cpu_percent:.0f}%",
            f"RAM: {m.ram_percent:.0f}%",
            f"Local IP: {m.local_ip or 'N/A'}",
        ]
        if gpu and gpu.temperature_c is not None:
            lines.append(f"GPU Temp: {gpu.temperature_c:.0f}°C")
        if gpu and gpu.fan_speed_avg_percent is not None:
            lines.append(f"GPU Fan: {gpu.fan_speed_avg_percent:.0f}%")
        a = system_timer.get_active()
        if a:
            rem = system_timer.remaining_seconds() or 0
            lines.append(f"Timer: {a.action} in {rem}s")
        return "\n".join(lines)

    if cmd == "lock":
        from shmcontrol.system.control import SystemAction, execute_system_action
        ok, msg = execute_system_action(SystemAction.LOCK)
        return f"{'✅' if ok else '❌'} {msg}"

    if cmd in ("sleep", "shutdown", "restart"):
        return _request_confirm(user_id, cmd, f"Device will {cmd}.")

    if cmd == "timer":
        # /timer shutdown 2h
        parts = args.split()
        if len(parts) < 2:
            return "Usage: /timer <shutdown|restart|sleep|lock> <30m|1h|2h|1h30m>"
        action, dur = parts[0].lower(), parts[1]
        if action not in ("shutdown", "restart", "sleep", "lock", "hibernate"):
            return "Invalid action"
        from shmcontrol.system.timer import parse_duration
        from datetime import datetime, timezone
        delta = parse_duration(dur)
        if not delta:
            return "Invalid duration. Examples: 30m, 1h, 2h, 1h30m"
        detail = f"{action}|{dur}|{(datetime.now(timezone.utc) + delta).isoformat()}"
        return _request_confirm(user_id, "timer", detail)

    if cmd == "cancel_timer":
        from shmcontrol.system.timer import system_timer
        ok, msg = system_timer.cancel()
        return f"{'✅' if ok else '❌'} {msg}"

    if cmd == "usage":
        from shmcontrol.database.models import db
        rows = db.execute(
            "SELECT process_name, SUM(download_bytes+upload_bytes) as total "
            "FROM usage_daily GROUP BY process_name ORDER BY total DESC LIMIT 10"
        )
        if not rows:
            return "📈 No usage data yet."
        lines = ["📈 *Usage (top)*"]
        for r in rows:
            total = r["total"] or 0
            lines.append(f"{r['process_name']}: {total/(1024**2):.1f} MB")
        return "\n".join(lines)

    if cmd == "logs":
        from shmcontrol.database.models import db
        rows = db.execute(
            "SELECT timestamp, feature, result, error FROM logs ORDER BY id DESC LIMIT 8"
        )
        lines = ["📜 *Recent logs*"]
        for r in rows:
            lines.append(f"{(r['timestamp'] or '')[:16]} {r['feature']}: {r['result'] or r['error'] or ''}")
        return "\n".join(lines) if rows else "No logs"

    if cmd == "vpn":
        from shmcontrol.vpn.monitor import vpn_monitor
        s = vpn_monitor.detect()
        if s.connected:
            return f"🟢 VPN adapters: {', '.join(s.adapters)}\nProvider: {s.provider_hint}"
        return "⚪ No VPN adapter detected"

    return f"Command /{cmd} received. See desktop app for full details."


async def _execute_confirmed(action: str, detail: str = "") -> str:
    if action in ("shutdown", "restart", "sleep"):
        from shmcontrol.system.control import SystemAction, execute_system_action
        mapping = {
            "shutdown": SystemAction.SHUTDOWN,
            "restart": SystemAction.RESTART,
            "sleep": SystemAction.SLEEP,
        }
        ok, msg = execute_system_action(mapping[action], delay_seconds=30 if action != "sleep" else 0)
        return f"{'✅' if ok else '❌'} {msg}"

    if action == "timer":
        # detail: action|dur|iso
        parts = detail.split("|")
        if len(parts) < 2:
            return "❌ Bad timer detail"
        act, dur = parts[0], parts[1]
        from shmcontrol.system.timer import system_timer, parse_duration
        from datetime import datetime, timezone
        delta = parse_duration(dur)
        if not delta:
            return "❌ Bad duration"
        target = datetime.now(timezone.utc) + delta
        ok, msg, _ = system_timer.schedule(act, target, source="telegram", require_confirm=False)
        return f"{'✅' if ok else '❌'} {msg}"

    return "Unknown confirmed action"


def start_bot_polling() -> None:
    token = get_token()
    if not token:
        logger.info("Telegram bot token not set – remote control disabled")
        return
    try:
        from telegram import Update
        from telegram.ext import Application, CommandHandler, ContextTypes

        async def cmd_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            if not update.effective_user or not update.message:
                return
            text = update.message.text or ""
            parts = text.split(maxsplit=1)
            command = parts[0]
            args = parts[1] if len(parts) > 1 else ""
            reply = await handle_command(update.effective_user.id, command, args)
            await update.message.reply_text(reply)

        app = Application.builder().token(token).build()
        for c in ALLOWED_COMMANDS:
            app.add_handler(CommandHandler(c, cmd_handler))
        logger.info("Telegram bot starting (polling)")
        app.run_polling(drop_pending_updates=True)
    except ImportError:
        logger.warning("python-telegram-bot not installed")
    except Exception as e:
        logger.exception("Telegram bot failed: %s", e)
