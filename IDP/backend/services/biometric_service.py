"""Biometric authentication service.

Handles user registration, fingerprint lookup, JWT generation and verification
for the biometric authentication feature.

Public interface
----------------
register_user(name, fingerprint_id, role) -> dict
authenticate_fingerprint(fingerprint_id) -> dict | None
generate_access_token(user_id, name, role) -> str
verify_token(token) -> dict
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from models.document import db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

JWT_SECRET: str = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 1

# ---------------------------------------------------------------------------
# Collection + indexes (created lazily / at import time)
# ---------------------------------------------------------------------------

_users = db["users"]

try:
    _users.create_index("fingerprint_id", unique=True)
    _users.create_index("user_id", unique=True)
    logger.info("biometric_service: users collection indexes ensured.")
except Exception as _exc:  # pragma: no cover
    logger.warning("biometric_service: could not create indexes: %s", _exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def register_user(name: str, fingerprint_id: int, role: str) -> dict:
    """Insert a new user document.

    Returns the stored document (with generated *user_id*).
    Raises :class:`ValueError` if *fingerprint_id* already exists.
    """
    user_id = str(uuid.uuid4())
    document = {
        "user_id": user_id,
        "name": name,
        "fingerprint_id": fingerprint_id,
        "role": role,
    }
    try:
        _users.insert_one(document)
    except Exception as exc:
        # DuplicateKeyError from pymongo has code 11000
        if "11000" in str(exc) or "duplicate" in str(exc).lower():
            raise ValueError(f"fingerprint_id {fingerprint_id} already registered") from exc
        raise
    # Return a clean copy without the internal MongoDB _id
    return {k: v for k, v in document.items() if k != "_id"}


def authenticate_fingerprint(fingerprint_id: int) -> dict | None:
    """Look up a user by *fingerprint_id*.

    Returns the user dict (without ``_id``) or ``None`` if not found.
    """
    doc = _users.find_one({"fingerprint_id": fingerprint_id}, {"_id": 0})
    return doc


def generate_access_token(user_id: str, name: str, role: str) -> str:
    """Generate a signed JWT with a 1-hour expiry.

    Claims: ``user_id``, ``name``, ``role``, ``exp``, ``iat``.
    """
    now = datetime.now(tz=timezone.utc)
    payload = {
        "user_id": user_id,
        "name": name,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """Decode and validate *token*.

    Returns the decoded claims dict on success.
    Raises :class:`jwt.ExpiredSignatureError` or :class:`jwt.InvalidTokenError`
    on failure.
    """
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
