"""Track play sessions for known game executables (SQLite)."""

from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import psutil

from shmcontrol.database.models import db


def _ensure_table() -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS play_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_name TEXT NOT NULL,
            executable TEXT,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            duration_sec INTEGER DEFAULT 0
        )
        """
    )


class PlaytimeTracker:
    def __init__(self) -> None:
        _ensure_table()
        self._active: dict[str, dict] = {}  # exe -> {name, started, pid}

    def tick(self) -> None:
        """Call periodically: open sessions for running games, close ended ones."""
        rows = db.execute(
            "SELECT name, executable FROM games WHERE enabled = 1 AND executable IS NOT NULL AND executable != ''"
        )
        wanted = {(r["executable"] or "").lower(): r["name"] for r in rows}
        running_exe: dict[str, int] = {}
        try:
            for p in psutil.process_iter(["name", "pid"]):
                n = (p.info.get("name") or "").lower()
                if n in wanted:
                    running_exe[n] = p.info["pid"]
        except Exception:
            return

        now = datetime.now(timezone.utc).isoformat()
        # start new
        for exe, name in wanted.items():
            if exe in running_exe and exe not in self._active:
                self._active[exe] = {"name": name, "started": now, "pid": running_exe[exe]}
                db.execute(
                    "INSERT INTO play_sessions (game_name, executable, started_at) VALUES (?,?,?)",
                    (name, exe, now),
                )
        # end closed
        for exe in list(self._active.keys()):
            if exe not in running_exe:
                info = self._active.pop(exe)
                ended = now
                # duration
                try:
                    t0 = datetime.fromisoformat(info["started"])
                    dur = int((datetime.now(timezone.utc) - t0).total_seconds())
                except Exception:
                    dur = 0
                db.execute(
                    """
                    UPDATE play_sessions SET ended_at = ?, duration_sec = ?
                    WHERE executable = ? AND ended_at IS NULL
                    """,
                    (ended, dur, exe),
                )

    def summary(self, days: int = 1) -> dict:
        start = (datetime.now(timezone.utc) - timedelta(days=days - 1)).strftime("%Y-%m-%d")
        rows = db.execute(
            """
            SELECT game_name, SUM(duration_sec) as total, COUNT(*) as sessions
            FROM play_sessions
            WHERE started_at >= ?
            GROUP BY game_name
            ORDER BY total DESC
            """,
            (start,),
        )
        total = sum(int(r["total"] or 0) for r in rows)
        return {
            "total_sec": total,
            "games": [
                {"name": r["game_name"], "seconds": int(r["total"] or 0), "sessions": r["sessions"]}
                for r in rows
            ],
        }


playtime_tracker = PlaytimeTracker()
