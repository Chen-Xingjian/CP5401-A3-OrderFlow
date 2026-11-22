"""Authenticate pre-provisioned users against salted scrypt password verifiers."""

import hashlib
import hmac
import secrets

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .db import transaction
from .models import OrderError, Principal


def _digest(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode(), salt=salt, n=2**15, r=8, p=3, dklen=32, maxmem=64 << 20
    )


def password_record(password: str) -> dict:
    salt = secrets.token_bytes(16)
    return {"salt": salt, "digest": _digest(password, salt)}


def authenticate(engine: Engine, username: str, password: str) -> Principal:
    denied = OrderError("INVALID_CREDENTIALS", "Check your username and password.")
    if (
        not username
        or len(username) > 100
        or not password
        or len(password) > 256
        or "\x00" in username
    ):
        raise denied
    with transaction(engine) as db:
        row = db.execute(
            text("""
            SELECT u.id, p.salt, p.digest FROM users u JOIN account_passwords p ON p.user_id = u.id
            WHERE u.username = :name AND u.active
        """),
            {"name": username.strip()},
        ).one_or_none()
    candidate = _digest(password, bytes(row.salt) if row else bytes(16))
    if row is None or not hmac.compare_digest(candidate, bytes(row.digest)):
        raise denied
    return Principal(row.id)
