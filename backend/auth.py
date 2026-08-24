"""JWT Authentication — API key + token-based access control for production.

In local dev mode (no SENTINEL_API_KEY set), auth is disabled for convenience.
In production, all /api/v1/* endpoints require a valid JWT token obtained via
POST /api/v1/auth/login. The /health and /docs endpoints are always public.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from functools import wraps
from typing import Any, Dict, Optional

from core.config import get_settings
from core.logging import get_logger

log = get_logger("sentinel.auth")

# Simple HMAC-SHA256 JWT (no external dependency needed)
_SECRET_CACHE: Optional[str] = None


def _get_secret() -> str:
    global _SECRET_CACHE
    if _SECRET_CACHE is None:
        settings = get_settings()
        _SECRET_CACHE = settings.jwt_secret or settings.openai_api_key or "sentinel-dev-secret-change-in-production"
    return _SECRET_CACHE


def _b64url_encode(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    import base64
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def create_token(payload: Dict[str, Any], expires_in: int = 86400) -> str:
    """Create a simple HMAC-signed JWT token."""
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload["iat"] = now
    payload["exp"] = now + expires_in

    header_b64 = _b64url_encode(json.dumps(header).encode())
    payload_b64 = _b64url_encode(json.dumps(payload).encode())
    message = f"{header_b64}.{payload_b64}"
    signature = hmac.new(_get_secret().encode(), message.encode(), hashlib.sha256).digest()
    sig_b64 = _b64url_encode(signature)
    return f"{message}.{sig_b64}"


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode a JWT token. Returns payload or None if invalid."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        message = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(_get_secret().encode(), message.encode(), hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def authenticate_request(auth_header: Optional[str]) -> Optional[Dict[str, Any]]:
    """Extract and verify token from Authorization header. Returns user dict or None."""
    settings = get_settings()
    if not settings.jwt_enabled:
        return {"user": "dev", "role": "admin"}
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    return verify_token(token)


def get_password_hash(password: str) -> str:
    """Hash a password with SHA-256 + salt. For production use bcrypt/argon2."""
    salt = "sentinel-agent-salt"
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(get_password_hash(password), password_hash)


# Default admin credentials (override via env vars in production)
DEFAULT_USERS = {
    "admin": {
        "password_hash": get_password_hash("sentinel2026"),
        "role": "admin",
        "display_name": "Administrator",
    },
    "operator": {
        "password_hash": get_password_hash("operator2026"),
        "role": "operator",
        "display_name": "Factory Operator",
    },
}
