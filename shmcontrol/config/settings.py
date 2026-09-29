"""
Sh.M Control - Configuration Management
Uses environment variables + local JSON for user settings.
Secrets never hardcoded.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


APP_NAME = "Sh.M Control"
APP_VERSION = "1.1.0"
ORG_NAME = "Sh.M"


def get_app_data_dir() -> Path:
    """Cross-platform app data directory."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path.home() / ".local" / "share"
    path = base / "ShMControl"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_path() -> Path:
    return get_app_data_dir() / "config.json"


def get_db_path() -> Path:
    return get_app_data_dir() / "shmcontrol.db"


class AlertChannelConfig(BaseModel):
    windows: bool = True
    telegram: bool = False
    both: bool = False
    disabled: bool = False


class TemperatureThresholds(BaseModel):
    cpu_warning: float = 80.0
    cpu_critical: float = 90.0
    gpu_warning: float = 80.0
    gpu_critical: float = 90.0


class AppSettings(BaseModel):
    language: str = "fa"  # fa | en
    theme: str = "dark_gaming"
    start_with_windows: bool = False
    minimize_to_tray: bool = True
    close_to_tray: bool = True  # False = full exit on window close
    monitoring_interval_ms: int = 2000
    last_update_check: Optional[str] = None
    update_channel: str = "stable"
    temperature: TemperatureThresholds = Field(default_factory=TemperatureThresholds)
    alert_channels: dict[str, AlertChannelConfig] = Field(default_factory=dict)
    telegram_user_id: Optional[int] = None
    telegram_bot_token: Optional[str] = None  # local only; prefer ENV
    device_id: Optional[str] = None
    cloud_sync_enabled: bool = False
    cloud_url: Optional[str] = None
    api_secret: Optional[str] = None
    device_name: str = "PC"
    selected_network_adapter: Optional[str] = None
    game_mode_enabled: bool = False
    current_dns_profile: Optional[str] = None
    # Session / power Telegram alerts (user selectable)
    notify_on_unlock: bool = True
    notify_on_lock: bool = False
    notify_on_startup: bool = True
    notify_on_resume: bool = True

    def ensure_alert_defaults(self) -> None:
        defaults = [
            "cpu_temp", "gpu_temp", "internet_down", "internet_restored",
            "vpn_connected", "vpn_disconnected", "usage_limit",
            "game_started", "game_closed", "dns_changed", "agent_offline", "critical_error"
        ]
        for key in defaults:
            if key not in self.alert_channels:
                self.alert_channels[key] = AlertChannelConfig(windows=True, telegram=False)


class SettingsManager:
    def __init__(self) -> None:
        self._settings = AppSettings()
        self.load()

    @property
    def settings(self) -> AppSettings:
        return self._settings

    def load(self) -> None:
        path = get_config_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self._settings = AppSettings.model_validate(data)
            except Exception:
                self._settings = AppSettings()
        self._settings.ensure_alert_defaults()
        # Environment overrides for secrets
        if os.getenv("GUARDIAN_TELEGRAM_USER_ID"):
            try:
                self._settings.telegram_user_id = int(os.getenv("GUARDIAN_TELEGRAM_USER_ID", "0"))
            except ValueError:
                pass

    def save(self) -> None:
        path = get_config_path()
        path.write_text(
            self._settings.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self._settings, key, default)

    def set(self, key: str, value: Any) -> None:
        if hasattr(self._settings, key):
            setattr(self._settings, key, value)
            self.save()


# Global instance
settings_manager = SettingsManager()
