"""Audit logging service.

Writes structured action records to the `audit_logs` MongoDB collection.

Usage
-----
    from services.audit_service import log_action
    log_action(user="Judge A", role="judge", action="login")
    log_action(user="Judge A", role="judge", action="verify_document", document_id="abc123")
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from models.document import db

logger = logging.getLogger(__name__)

_audit_logs = db["audit_logs"] if db is not None else None


def log_action(user: str, role: str, action: str, document_id: str | None = None) -> None:
    """Insert one audit record into the audit_logs collection.

    Never raises — failures are logged and swallowed so the caller's
    primary response is never blocked.
    """
    if _audit_logs is None:
        logger.warning("audit_service: MongoDB not available, skipping log.")
        return
    record = {
        "user":        user,
        "role":        role,
        "action":      action,
        "document_id": document_id,
        "timestamp":   datetime.now(tz=timezone.utc),
    }
    try:
        _audit_logs.insert_one(record)
        logger.debug("audit_service: logged %s by %s", action, user)
    except Exception as exc:
        logger.error("audit_service: failed to insert log: %s", exc)
