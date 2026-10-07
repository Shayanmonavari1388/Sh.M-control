"""
Sh.M Control - Local SQLite Schema & Helpers
Cloud D1 schema is mirrored for optional sync.
"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Optional

from shmcontrol.config.settings import get_db_path


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_seen TEXT
);

CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    executable TEXT,
    profile_name TEXT,
    dns_profile TEXT,
    network_test_profile TEXT,
    internet_limit_mb INTEGER,
    enabled INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS game_services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    service_name TEXT NOT NULL,
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS game_endpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER,
    service_id INTEGER,
    hostname TEXT NOT NULL,
    ip TEXT,
    port INTEGER,
    protocol TEXT DEFAULT 'tcp',
    region TEXT,
    provider TEXT,
    enabled INTEGER DEFAULT 1,
    last_checked TEXT,
    source TEXT,
    last_updated TEXT,
    version INTEGER DEFAULT 1,
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
    FOREIGN KEY (service_id) REFERENCES game_services(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS launchers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    executable TEXT,
    enabled INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS launcher_endpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    launcher_id INTEGER NOT NULL,
    service_name TEXT,
    hostname TEXT NOT NULL,
    ip TEXT,
    port INTEGER,
    protocol TEXT DEFAULT 'tcp',
    enabled INTEGER DEFAULT 1,
    last_updated TEXT,
    source TEXT,
    FOREIGN KEY (launcher_id) REFERENCES launchers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS dns_servers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    primary_ip TEXT NOT NULL,
    secondary_ip TEXT,
    category TEXT,
    country TEXT,
    doh_url TEXT,
    dot_host TEXT,
    dnssec INTEGER DEFAULT 0,
    ipv6 TEXT,
    enabled INTEGER DEFAULT 1,
    is_free INTEGER DEFAULT 1,
    source TEXT,
    last_tested TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS dns_test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dns_id INTEGER,
    resolution_ms REAL,
    latency_ms REAL,
    status TEXT,
    tested_at TEXT,
    FOREIGN KEY (dns_id) REFERENCES dns_servers(id)
);

CREATE TABLE IF NOT EXISTS connectivity_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT, -- game | launcher | custom
    target_name TEXT,
    dns_used TEXT,
    started_at TEXT,
    finished_at TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS connectivity_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id INTEGER,
    endpoint_id INTEGER,
    hostname TEXT,
    ip TEXT,
    protocol TEXT,
    success INTEGER,
    latency_ms REAL,
    error TEXT,
    details TEXT,
    FOREIGN KEY (test_id) REFERENCES connectivity_tests(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS usage_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    process_name TEXT NOT NULL,
    download_bytes INTEGER DEFAULT 0,
    upload_bytes INTEGER DEFAULT 0,
    UNIQUE(date, process_name)
);

CREATE TABLE IF NOT EXISTS usage_hourly (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hour_start TEXT NOT NULL,
    process_name TEXT NOT NULL,
    download_bytes INTEGER DEFAULT 0,
    upload_bytes INTEGER DEFAULT 0,
    UNIQUE(hour_start, process_name)
);

CREATE TABLE IF NOT EXISTS vpn_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    adapter_name TEXT,
    provider TEXT,
    started_at TEXT,
    ended_at TEXT,
    download_bytes INTEGER DEFAULT 0,
    upload_bytes INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    message TEXT,
    severity TEXT,
    created_at TEXT,
    acknowledged INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS alert_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT UNIQUE,
    windows_notif INTEGER DEFAULT 1,
    telegram INTEGER DEFAULT 0,
    cooldown_seconds INTEGER DEFAULT 300
);

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    level TEXT,
    feature TEXT,
    command TEXT,
    result TEXT,
    error TEXT,
    user_id TEXT,
    device_id TEXT
);

CREATE TABLE IF NOT EXISTS commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT, -- telegram | local
    command TEXT,
    status TEXT,
    created_at TEXT,
    executed_at TEXT,
    result TEXT
);

CREATE TABLE IF NOT EXISTS endpoint_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint_id INTEGER,
    old_ip TEXT,
    new_ip TEXT,
    changed_at TEXT,
    source TEXT
);

CREATE INDEX IF NOT EXISTS idx_usage_daily_date ON usage_daily(date);
CREATE INDEX IF NOT EXISTS idx_logs_ts ON logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_endpoints_game ON game_endpoints(game_id);
CREATE INDEX IF NOT EXISTS idx_dns_category ON dns_servers(category);
"""


class Database:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or get_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with self.connection() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.path), timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def ensure_device(self, name: str = "SHAYAN-PC") -> str:
        with self.connection() as conn:
            row = conn.execute("SELECT id FROM devices LIMIT 1").fetchone()
            if row:
                return row["id"]
            device_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO devices (id, name, created_at, last_seen) VALUES (?, ?, ?, ?)",
                (device_id, name, now, now),
            )
            return device_id

    def log(self, level: str, feature: str, command: str = "", result: str = "", error: str = "", device_id: str = "") -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO logs (timestamp, level, feature, command, result, error, device_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (now, level, feature, command, result, error, device_id),
            )

    def execute(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self.connection() as conn:
            cur = conn.execute(sql, params)
            return cur.fetchall()

    def execute_one(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        rows = self.execute(sql, params)
        return rows[0] if rows else None


# Global
db = Database()
