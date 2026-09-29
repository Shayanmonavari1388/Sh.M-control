"""
Remote API client for optional device linking.
Endpoint and credentials come only from environment / local settings.
Nothing is hard-coded for public distribution.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from shmcontrol.config.settings import settings_manager

logger = logging.getLogger("shmcontrol.api.cloud")


def cloud_url() -> str:
    u = (
        os.getenv("SHM_API_URL")
        or os.getenv("GUARDIAN_CLOUD_URL")
        or getattr(settings_manager.settings, "cloud_url", None)
        or ""
    )
    return str(u).rstrip("/")


def api_secret() -> str:
    s = (
        os.getenv("SHM_API_KEY")
        or os.getenv("GUARDIAN_API_SECRET")
        or getattr(settings_manager.settings, "api_secret", None)
        or ""
    )
    return str(s)


def device_id() -> str:
    did = getattr(settings_manager.settings, "device_id", None)
    return str(did) if did else "unknown-device"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_secret()}",
        "Content-Type": "application/json",
    }


def is_configured() -> bool:
    return bool(cloud_url() and api_secret())


def health() -> dict[str, Any]:
    if not cloud_url():
        return {"ok": False, "error": "API URL not set"}
    try:
        r = httpx.get(f"{cloud_url()}/health", timeout=10.0)
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


def register_device(name: str = "PC", refresh_link: bool = False) -> dict[str, Any]:
    if not is_configured():
        return {"ok": False, "error": "Remote API not configured"}
    try:
        r = httpx.post(
            f"{cloud_url()}/device/register",
            headers=_headers(),
            json={"device_id": device_id(), "name": name},
            timeout=15.0,
        )
        if r.status_code == 401:
            return {"ok": False, "error": "Unauthorized"}
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


def bind_telegram(telegram_user_id: int, name: str = "PC") -> dict[str, Any]:
    if not is_configured():
        return {"ok": False, "error": "Remote API not configured"}
    try:
        r = httpx.post(
            f"{cloud_url()}/device/bind",
            headers=_headers(),
            json={
                "device_id": device_id(),
                "telegram_user_id": int(telegram_user_id),
                "name": name,
            },
            timeout=15.0,
        )
        if r.status_code == 401:
            return {"ok": False, "error": "Unauthorized"}
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


def poll_commands() -> list[dict]:
    if not is_configured():
        return []
    try:
        r = httpx.get(
            f"{cloud_url()}/commands",
            headers=_headers(),
            params={"device_id": device_id()},
            timeout=15.0,
        )
        if r.status_code != 200:
            return []
        return list((r.json() or {}).get("commands") or [])
    except Exception as e:
        logger.debug("poll_commands: %s", e)
        return []


def ack_command(
    command_id: int,
    status: str = "done",
    result: str = "",
    telegram_user_id: int | None = None,
) -> None:
    if not is_configured():
        return
    try:
        payload: dict[str, Any] = {
            "command_id": command_id,
            "status": status,
            "result": result,
        }
        if telegram_user_id:
            payload["telegram_user_id"] = int(telegram_user_id)
        httpx.post(
            f"{cloud_url()}/commands/ack",
            headers=_headers(),
            json=payload,
            timeout=15.0,
        )
    except Exception as e:
        logger.debug("ack_command: %s", e)


def push_telegram_message(message: str) -> bool:
    if not is_configured():
        return False
    try:
        r = httpx.post(
            f"{cloud_url()}/device/notify",
            headers=_headers(),
            json={"device_id": device_id(), "message": message},
            timeout=15.0,
        )
        if r.status_code == 200:
            return bool((r.json() or {}).get("ok"))
        return False
    except Exception as e:
        logger.debug("push_telegram_message: %s", e)
        return False
