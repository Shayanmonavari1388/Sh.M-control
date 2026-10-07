"""Local seal/open for sensitive strings. Defaults are empty in public source."""

from __future__ import annotations

import base64
import hashlib
from typing import Optional

_P = ("ShM", "Ctrl", "2026", "xK9")

# Public source ships NO built-in endpoints (configure via env / settings).
_SEALED_URL = ""
_SEALED_KEY = ""
_SEALED_PORTAL = ""


def _passphrase() -> str:
    return "".join(_P)


def _key() -> bytes:
    return hashlib.sha256(_passphrase().encode("utf-8")).digest()


def _xor(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def seal_text(plain: str) -> str:
    raw = plain.encode("utf-8")
    key = _key()
    salt = hashlib.sha256(key + b"shm").digest()[:8]
    return base64.urlsafe_b64encode(salt + _xor(raw, key)).decode("ascii")


def open_text(blob: str) -> Optional[str]:
    if not blob:
        return None
    try:
        data = base64.urlsafe_b64decode(blob.encode("ascii"))
        if len(data) < 9:
            return None
        plain = _xor(data[8:], _key())
        return plain.decode("utf-8")
    except Exception:
        return None


def get_default_api_url() -> str:
    return open_text(_SEALED_URL) or ""


def get_default_api_key() -> str:
    return open_text(_SEALED_KEY) or ""


def get_default_portal_url() -> str:
    return open_text(_SEALED_PORTAL) or ""
