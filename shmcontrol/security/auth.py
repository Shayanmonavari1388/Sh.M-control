"""Sh.M account session — required before Telegram remote features."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import httpx

from shmcontrol.config.settings import get_app_data_dir, settings_manager
from shmcontrol.security.crypto import get_default_api_url, get_default_portal_url, seal_text, open_text

logger = logging.getLogger("shmcontrol.security.auth")


def _portal_url() -> str:
    """Sh.M account portal (login/register). Separate from device-control API."""
    import os
    u = (
        os.getenv("SHM_PORTAL_URL")
        or os.getenv("SHM_API_URL")
        or get_default_portal_url()
        or ""
    )
    return str(u).rstrip("/")


@dataclass
class Session:
    token: str
    email: str
    user_id: str
    expires_at: float

    @property
    def valid(self) -> bool:
        return bool(self.token) and time.time() < self.expires_at - 30


class AuthManager:
    def __init__(self) -> None:
        self._session: Optional[Session] = None
        self._load()

    def _path(self) -> Path:
        return get_app_data_dir() / "session.sealed"

    def _load(self) -> None:
        p = self._path()
        if not p.exists():
            return
        try:
            raw = open_text(p.read_text(encoding="utf-8").strip())
            if not raw:
                return
            data = json.loads(raw)
            self._session = Session(
                token=str(data.get("token") or ""),
                email=str(data.get("email") or ""),
                user_id=str(data.get("user_id") or ""),
                expires_at=float(data.get("expires_at") or 0),
            )
            if self._session and not self._session.valid:
                self._session = None
        except Exception:
            self._session = None

    def _save(self) -> None:
        p = self._path()
        if not self._session:
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass
            return
        payload = json.dumps({
            "token": self._session.token,
            "email": self._session.email,
            "user_id": self._session.user_id,
            "expires_at": self._session.expires_at,
        })
        try:
            p.write_text(seal_text(payload), encoding="utf-8")
        except Exception as e:
            logger.debug("session save: %s", e)

    @property
    def is_logged_in(self) -> bool:
        return bool(self._session and self._session.valid)

    @property
    def email(self) -> str:
        return self._session.email if self._session else ""

    @property
    def token(self) -> str:
        return self._session.token if self._session and self._session.valid else ""

    def logout(self) -> None:
        self._session = None
        self._save()
        # Clear telegram bind when logging out (security)
        try:
            settings_manager.settings.telegram_user_id = None
            settings_manager.settings.cloud_sync_enabled = False
            settings_manager.save()
        except Exception:
            pass

    def register(self, email: str, password: str, display_name: str = "") -> tuple[bool, str]:
        base = _portal_url()
        if not base:
            return False, "Portal URL not available"
        try:
            r = httpx.post(
                f"{base}/auth/register",
                json={"email": email.strip().lower(), "password": password, "name": display_name},
                timeout=20.0,
            )
            try:
                data = r.json()
            except Exception:
                data = {}
            if data.get("need_verify"):
                return False, "کد تأیید به ایمیل ارسال شد. تأیید را در سایت انجام دهید: login.shayanmonavari.ir"
            if r.status_code >= 400:
                return False, str(data.get("error") or r.text or "Register failed")
            return self._apply_token_response(data, email)
        except Exception as e:
            return False, str(e)

    def login(self, email: str, password: str) -> tuple[bool, str]:
        base = _portal_url()
        if not base:
            return False, "Portal URL not available"
        try:
            r = httpx.post(
                f"{base}/auth/login",
                json={"email": email.strip().lower(), "password": password},
                timeout=20.0,
            )
            try:
                data = r.json()
            except Exception:
                data = {}
            if data.get("need_verify"):
                return False, "ایمیل نیاز به تأیید دارد. در سایت login.shayanmonavari.ir وارد شوید."
            if r.status_code >= 400:
                return False, str(data.get("error") or r.text or "Login failed")
            return self._apply_token_response(data, email)
        except Exception as e:
            return False, str(e)

    def _apply_token_response(self, data: dict[str, Any], email: str) -> tuple[bool, str]:
        token = str(data.get("token") or "")
        if not token:
            if data.get("need_verify"):
                return False, "نیاز به تأیید ایمیل در سایت"
            return False, str(data.get("error") or "No token returned")
        exp = data.get("expires_at")
        if isinstance(exp, (int, float)):
            expires_at = float(exp)
        else:
            expires_at = time.time() + float(data.get("expires_in") or 86400 * 7)
        self._session = Session(
            token=token,
            email=str(data.get("email") or email).strip().lower(),
            user_id=str(data.get("user_id") or data.get("id") or ""),
            expires_at=expires_at,
        )
        self._save()
        # Optional: server may return scoped API credentials
        if data.get("api_url"):
            settings_manager.settings.cloud_url = str(data["api_url"])
        if data.get("api_key"):
            settings_manager.settings.api_secret = str(data["api_key"])
        settings_manager.save()
        try:
            httpx.post(
                f"{_portal_url()}/usage/track",
                headers={"Authorization": f"Bearer {self._session.token}", "Content-Type": "application/json"},
                json={"app_id": "shm-control", "event": "app_login"},
                timeout=8.0,
            )
        except Exception:
            pass
        return True, "OK"

    def auth_headers(self) -> dict[str, str]:
        if not self.is_logged_in:
            return {}
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}


auth_manager = AuthManager()
