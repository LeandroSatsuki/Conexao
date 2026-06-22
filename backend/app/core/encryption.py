from __future__ import annotations

import base64
import json
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet

from app.core.config import get_settings


def _serialize_secret(secret: Any) -> str:
    if secret is None:
        return ""
    if isinstance(secret, bytes):
        return secret.decode("utf-8")
    if isinstance(secret, str):
        return secret
    return json.dumps(secret, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = get_settings().fernet_key.strip()
    if not key:
        raise ValueError("FERNET_KEY must be configured")
    return Fernet(key.encode("utf-8"))


def encrypt_secret(secret: Any) -> str:
    payload = _serialize_secret(secret).encode("utf-8")
    return _fernet().encrypt(payload).decode("utf-8")


def decrypt_secret(token: str) -> str:
    if not token:
        return ""
    return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")


def mask_secret(secret: Any, visible: int = 2) -> str:
    value = _serialize_secret(secret)
    if not value:
        return ""
    if len(value) <= visible * 2:
        return "*" * max(4, len(value))
    return f"{value[:visible]}***{value[-visible:]}"


def build_fernet_key_from_bytes(seed: bytes) -> str:
    return base64.urlsafe_b64encode(seed[:32].ljust(32, b"0")).decode("utf-8")
