"""
Sh.M Control - System Timer / Scheduled Actions
Only allow-listed actions. Persistence in SQLite.
Expired timers never auto-execute after restart.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from shmcontrol.database.models import db
from shmcontrol.system.control import SystemAction, execute_system_action
from shmcontrol.notifications.notify import notify_windows

logger = logging.getLogger("shmcontrol.system.timer")

ALLOWED_ACTIONS = {
    "shutdown": SystemAction.SHUTDOWN,
    "restart": SystemAction.RESTART,
    "sleep": SystemAction.SLEEP,
    "lock": SystemAction.LOCK,
    "hibernate": SystemAction.HIBERNATE,
}


def _ensure_table() -> None:
    with db.connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scheduled_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                target_time TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                source TEXT DEFAULT 'local',
                cancelled_at TEXT,
                executed_at TEXT,
                confirmed INTEGER DEFAULT 0,
                confirm_token TEXT,
                confirm_expires TEXT
            )
            """
        )


_ensure_table()


@dataclass
class ScheduledAction:
    id: int
    action: str
    target_time: datetime
    status: str
    source: str
    confirmed: bool


def parse_duration(text: str) -> Optional[timedelta]:
    """Parse 30m, 1h, 2h, 1h30m into timedelta. Rejects invalid input."""
    text = text.strip().lower().replace(" ", "")
    if not text:
        return None
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", text)
    if not m or not any(m.groups()):
        return None
    h = int(m.group(1) or 0)
    mi = int(m.group(2) or 0)
    s = int(m.group(3) or 0)
    if h == 0 and mi == 0 and s == 0:
        return None
    if h > 168 or mi > 10000:  # hard caps
        return None
    return timedelta(hours=h, minutes=mi, seconds=s)


class SystemTimer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._on_tick: Optional[Callable[[], None]] = None

    def set_tick_callback(self, cb: Callable[[], None]) -> None:
        self._on_tick = cb

    def start_watcher(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="SystemTimer", daemon=True)
        self._thread.start()

    def stop_watcher(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._check_due()
                if self._on_tick:
                    self._on_tick()
            except Exception:
                logger.exception("timer tick failed")
            self._stop.wait(1.0)

    def get_active(self) -> Optional[ScheduledAction]:
        row = db.execute_one(
            "SELECT * FROM scheduled_actions WHERE status = 'active' AND confirmed = 1 ORDER BY id DESC LIMIT 1"
        )
        if not row:
            return None
        try:
            tt = datetime.fromisoformat(row["target_time"])
            if tt.tzinfo is None:
                tt = tt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
        return ScheduledAction(
            id=row["id"],
            action=row["action"],
            target_time=tt,
            status=row["status"],
            source=row["source"] or "local",
            confirmed=bool(row["confirmed"]),
        )

    def remaining_seconds(self) -> Optional[int]:
        a = self.get_active()
        if not a:
            return None
        now = datetime.now(timezone.utc)
        sec = int((a.target_time - now).total_seconds())
        return max(0, sec)

    def schedule(
        self,
        action: str,
        target: datetime,
        source: str = "local",
        require_confirm: bool = True,
    ) -> tuple[bool, str, Optional[int]]:
        action = action.lower().strip()
        if action not in ALLOWED_ACTIONS:
            return False, f"Action not allowed: {action}", None
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if target <= now:
            return False, "Target time must be in the future", None
        if (target - now).total_seconds() > 7 * 24 * 3600:
            return False, "Maximum schedule window is 7 days", None

        with self._lock:
            existing = self.get_active()
            if existing:
                return False, "A scheduled action already exists. Cancel or replace it first.", existing.id

            created = now.isoformat()
            confirmed = 0 if require_confirm else 1
            status = "pending_confirm" if require_confirm else "active"
            import secrets
            token = secrets.token_urlsafe(16) if require_confirm else None
            expires = (now + timedelta(minutes=5)).isoformat() if require_confirm else None

            with db.connection() as conn:
                cur = conn.execute(
                    """INSERT INTO scheduled_actions
                    (action, target_time, created_at, status, source, confirmed, confirm_token, confirm_expires)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (action, target.isoformat(), created, status, source, confirmed, token, expires),
                )
                sid = cur.lastrowid

            db.log("INFO", "timer", "created", f"{action} @ {target.isoformat()} source={source}")
            if require_confirm:
                return True, f"Confirm required for {action}. Token expires in 5 minutes.", sid
            notify_windows(
                "Sh.M Control – Timer",
                f"{action.upper()} scheduled for {target.strftime('%Y-%m-%d %H:%M:%S UTC')}",
                key=f"timer_{sid}",
                cooldown=30,
            )
            return True, f"{action} scheduled", sid

    def confirm(self, action_id: int, token: Optional[str] = None) -> tuple[bool, str]:
        row = db.execute_one("SELECT * FROM scheduled_actions WHERE id = ?", (action_id,))
        if not row:
            return False, "Not found"
        if row["status"] not in ("pending_confirm", "active"):
            return False, f"Cannot confirm status={row['status']}"
        if row["confirmed"]:
            return True, "Already confirmed"
        if row["confirm_token"] and token and token != row["confirm_token"]:
            return False, "Invalid confirmation token"
        if row["confirm_expires"]:
            try:
                exp = datetime.fromisoformat(row["confirm_expires"])
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > exp:
                    with db.connection() as conn:
                        conn.execute(
                            "UPDATE scheduled_actions SET status='expired' WHERE id=?",
                            (action_id,),
                        )
                    return False, "Confirmation expired"
            except Exception:
                pass
        with db.connection() as conn:
            conn.execute(
                "UPDATE scheduled_actions SET confirmed=1, status='active', confirm_token=NULL WHERE id=?",
                (action_id,),
            )
        db.log("INFO", "timer", "confirmed", str(action_id))
        return True, "Confirmed and active"

    def cancel(self, action_id: Optional[int] = None) -> tuple[bool, str]:
        with self._lock:
            if action_id is None:
                active = self.get_active()
                pending = db.execute_one(
                    "SELECT id FROM scheduled_actions WHERE status IN ('active','pending_confirm') ORDER BY id DESC LIMIT 1"
                )
                if not active and not pending:
                    return False, "No scheduled action"
                action_id = active.id if active else pending["id"]
            now = datetime.now(timezone.utc).isoformat()
            with db.connection() as conn:
                conn.execute(
                    "UPDATE scheduled_actions SET status='cancelled', cancelled_at=? WHERE id=? AND status IN ('active','pending_confirm')",
                    (now, action_id),
                )
            db.log("INFO", "timer", "cancelled", str(action_id))
            return True, "Cancelled"

    def replace(self, action: str, target: datetime, source: str = "local") -> tuple[bool, str, Optional[int]]:
        self.cancel()
        return self.schedule(action, target, source=source, require_confirm=False)

    def on_startup_recover(self) -> None:
        """Never execute timers that were due while the machine was off/asleep."""
        now = datetime.now(timezone.utc)
        # Expire any active timer whose target is in the past OR within 90s of boot
        # (avoids immediate hibernate/sleep loop after resume)
        rows = db.execute(
            "SELECT id, action, target_time FROM scheduled_actions "
            "WHERE status='active' AND confirmed=1"
        )
        for r in rows:
            try:
                tt = datetime.fromisoformat(r["target_time"])
                if tt.tzinfo is None:
                    tt = tt.replace(tzinfo=timezone.utc)
                # Past due, or would fire in the next 90 seconds after startup
                if tt <= now + timedelta(seconds=90):
                    with db.connection() as conn:
                        conn.execute(
                            "UPDATE scheduled_actions SET status='expired' WHERE id=?",
                            (r["id"],),
                        )
                    db.log("WARN", "timer", "expired_on_startup", f"{r['id']}:{r['action']}")
            except Exception:
                continue

    def _check_due(self) -> None:
        active = self.get_active()
        if not active:
            return
        now = datetime.now(timezone.utc)
        if active.target_time > now:
            return
        # Execute once
        with self._lock:
            active2 = self.get_active()
            if not active2 or active2.id != active.id:
                return
            action = active.action
            with db.connection() as conn:
                conn.execute(
                    "UPDATE scheduled_actions SET status='executed', executed_at=? WHERE id=?",
                    (now.isoformat(), active.id),
                )
            db.log("INFO", "timer", "executed", action)
            self._execute(action)

    def _execute(self, action: str) -> None:
        sa = ALLOWED_ACTIONS.get(action)
        if sa is None:
            logger.warning("Timer blocked unknown action: %s", action)
            return
        delay = 5 if action in ("shutdown", "restart") else 0
        ok, msg = execute_system_action(sa, delay_seconds=delay)
        logger.info("Timer execute %s: %s %s", action, ok, msg)
        notify_windows("Sh.M Control – Timer", f"{action}: {msg}", key=f"timer_exec_{action}", cooldown=10)


system_timer = SystemTimer()
