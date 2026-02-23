"""
Encrypted at-rest storage for user context. Optional: used only when user chooses "Save securely".
Data is encrypted with Fernet (symmetric) using CONTEXT_ENCRYPTION_KEY. In-memory store keyed by restore_token.
"""
import os
import time
import uuid
import json
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from server.models.user_context import UserContext

# Default TTL 30 days (seconds). Entries are removed when restored or when expired.
TTL_SECONDS = 30 * 24 * 3600

_store: dict[str, tuple[bytes, float]] = {}
_fernet: Optional[Fernet] = None


def _get_fernet() -> Optional[Fernet]:
    global _fernet
    if _fernet is not None:
        return _fernet
    key = os.environ.get("CONTEXT_ENCRYPTION_KEY", "").strip()
    if not key:
        return None
    try:
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
        return _fernet
    except Exception:
        return None


def save_context(ctx: UserContext) -> Optional[str]:
    """Encrypt and store context; return restore_token. Returns None if encryption is not configured."""
    f = _get_fernet()
    if not f:
        return None
    payload = ctx.model_dump_json()
    encrypted = f.encrypt(payload.encode("utf-8"))
    token = str(uuid.uuid4()).replace("-", "")[:16]
    expiry = time.time() + TTL_SECONDS
    _store[token] = (encrypted, expiry)
    return token


def get_context(restore_token: str) -> Optional[UserContext]:
    """Decrypt and return context for restore_token; remove from store (one-time restore). Returns None if invalid or missing."""
    f = _get_fernet()
    if not f:
        return None
    restore_token = (restore_token or "").strip()
    if not restore_token or restore_token not in _store:
        return None
    encrypted, expiry = _store.pop(restore_token)
    if time.time() > expiry:
        return None
    try:
        payload = f.decrypt(encrypted).decode("utf-8")
        data = json.loads(payload)
        return UserContext.model_validate(data)
    except (InvalidToken, json.JSONDecodeError, Exception):
        return None


def is_encryption_available() -> bool:
    return _get_fernet() is not None
