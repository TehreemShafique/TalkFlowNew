"""Symmetric secret encryption (Fernet) - port of services/auth-service.

Used to encrypt integration secrets at rest (e.g. dialer API tokens).  The key
is derived from the control plane's ``secret_key`` so no extra secret material
needs to be provisioned.
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings

_FERNET: Fernet | None = None


def _fernet() -> Fernet:
    global _FERNET
    if _FERNET is None:
        digest = hashlib.sha256(settings.secret_key.encode()).digest()
        _FERNET = Fernet(base64.urlsafe_b64encode(digest))
    return _FERNET


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()