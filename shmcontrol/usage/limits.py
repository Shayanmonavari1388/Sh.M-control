"""
Sh.M Control - Usage Limits
Scopes: system | application | vpn | adapter
Actions: notify | notify_disconnect (disconnect requires explicit user setting + confirmation path)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from shmcontrol.database.models import db
from shmcontrol.notifications.notify import notify_windows, notify_telegram
from shmcontrol.usage.collector import usage_collector

logger = logging.getLogger("shmcontrol.usage.limits")


@dataclass
class UsageLimit:
    id: Optional[int]
    scope: str  # system | application | vpn | adapter
    target: str  # process name / adapter name / "system" / "vpn"
    limit_bytes: int
    action: str  # notify | notify_disconnect
    enabled: bool = True


def _ensure_limits_table() -> None:
    with db.connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL,
                target TEXT NOT NULL,
                limit_bytes INTEGER NOT NULL,
                action TEXT DEFAULT 'notify',
                enabled INTEGER DEFAULT 1,
                UNIQUE(scope, target)
            )
            """
        )


_ensure_limits_table()


class UsageLimitManager:
    def list_limits(self) -> list[UsageLimit]:
        rows = db.execute("SELECT * FROM usage_limits WHERE enabled = 1")
        return [
            UsageLimit(
                id=r["id"],
                scope=r["scope"],
                target=r["target"],
                limit_bytes=r["limit_bytes"],
                action=r["action"] or "notify",
                enabled=bool(r["enabled"]),
            )
            for r in rows
        ]

    def set_limit(self, scope: str, target: str, limit_mb: int, action: str = "notify") -> None:
        limit_bytes = max(0, int(limit_mb)) * 1024 * 1024
        with db.connection() as conn:
            conn.execute(
                """
                INSERT INTO usage_limits (scope, target, limit_bytes, action, enabled)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(scope, target) DO UPDATE SET
                    limit_bytes = excluded.limit_bytes,
                    action = excluded.action,
                    enabled = 1
                """,
                (scope, target, limit_bytes, action),
            )
        db.log("INFO", "usage", "set_limit", f"{scope}:{target}={limit_mb}MB action={action}")

    def remove_limit(self, scope: str, target: str) -> None:
        with db.connection() as conn:
            conn.execute("DELETE FROM usage_limits WHERE scope = ? AND target = ?", (scope, target))

    def _today_usage_for(self, process_name: str) -> int:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = db.execute_one(
            "SELECT download_bytes + upload_bytes as total FROM usage_daily WHERE date = ? AND process_name = ?",
            (today, process_name),
        )
        return int(row["total"] or 0) if row else 0

    def check_and_alert(self) -> list[dict]:
        """
        Compare real usage against limits. Returns breach list.
        Disconnect is NEVER automatic here — only flagged for UI confirmation.
        """
        breaches = []
        for lim in self.list_limits():
            used = 0
            if lim.scope == "system":
                used = self._today_usage_for("__SYSTEM__")
            elif lim.scope == "application":
                used = self._today_usage_for(lim.target)
                # also try partial name match from games
                if used == 0:
                    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    row = db.execute_one(
                        "SELECT SUM(download_bytes + upload_bytes) as total FROM usage_daily "
                        "WHERE date = ? AND process_name LIKE ?",
                        (today, f"%{lim.target}%"),
                    )
                    used = int(row["total"] or 0) if row else 0
            elif lim.scope == "vpn":
                # VPN adapter totals are tracked under adapter name if present; else not available
                used = self._today_usage_for("__VPN__")
            elif lim.scope == "adapter":
                used = self._today_usage_for(f"__ADAPTER__:{lim.target}")
            else:
                continue

            if used >= lim.limit_bytes:
                breach = {
                    "scope": lim.scope,
                    "target": lim.target,
                    "limit_bytes": lim.limit_bytes,
                    "used_bytes": used,
                    "action": lim.action,
                    "requires_disconnect_confirm": lim.action == "notify_disconnect",
                }
                breaches.append(breach)
                msg = (
                    f"Usage limit exceeded: {lim.scope}/{lim.target}\n"
                    f"Used: {used / (1024**3):.2f} GB / Limit: {lim.limit_bytes / (1024**3):.2f} GB"
                )
                notify_windows("Sh.M Control – Usage Limit", msg, key=f"limit_{lim.scope}_{lim.target}", cooldown=600)
                notify_telegram(f"⚠️ Sh.M Control\n{msg}", key=f"limit_{lim.scope}_{lim.target}", cooldown=600)
                db.log("WARN", "usage", "limit_exceeded", msg)

        # Also check game.internet_limit_mb
        for b in usage_collector.check_limits():
            breaches.append({**b, "action": "notify", "requires_disconnect_confirm": False})

        return breaches


usage_limit_manager = UsageLimitManager()
