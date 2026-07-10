"""MongoDB connection and collection helpers.

Provides a module-level `db` object (pymongo Database) used by all routes
and services.  Also exposes `ensure_indexes()` which creates the indexes
required by the NLP module on the `ocr_documents` collection.

Usage
-----
    from models.document import db, ensure_indexes

    # In app startup:
    ensure_indexes()
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

try:
    from pymongo import ASCENDING, DESCENDING, MongoClient
    _PYMONGO_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PYMONGO_AVAILABLE = False
    ASCENDING = 1   # type: ignore[assignment]
    DESCENDING = -1  # type: ignore[assignment]
    MongoClient = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

MONGO_URI: str = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME: str = os.environ.get("MONGO_DB", "legal_idp")

if _PYMONGO_AVAILABLE:
    _client: MongoClient = MongoClient(MONGO_URI)
    db = _client[DB_NAME]
    # Legacy collection reference used by routes/documents.py
    documents = db["documents"]
else:  # pragma: no cover
    # Provide a stub so that imports don't fail in test environments
    # where pymongo is not installed. Tests should mock routes.ai.db.
    db = None  # type: ignore[assignment]
    documents = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Index management
# ---------------------------------------------------------------------------

def ensure_indexes() -> None:
    """Create required indexes on *ocr_documents* if they do not already exist.

    Indexes created:
    - ``nlp.classification.doc_type``  (ascending)  — filter by document type
    - ``nlp.risk.risk_level``          (ascending)  — filter by risk level
    - ``created_at``                   (descending) — sort by upload time

    This function is idempotent: calling it multiple times is safe because
    MongoDB's ``create_index`` is a no-op when the index already exists.
    """
    if not _PYMONGO_AVAILABLE or db is None:  # pragma: no cover
        logger.warning("pymongo not available; skipping index creation.")
        return

    collection = db["ocr_documents"]

    try:
        collection.create_index(
            [("nlp.classification.doc_type", ASCENDING)],
            name="nlp_classification_doc_type",
            background=True,
        )
        collection.create_index(
            [("nlp.risk.risk_level", ASCENDING)],
            name="nlp_risk_risk_level",
            background=True,
        )
        collection.create_index(
            [("created_at", DESCENDING)],
            name="created_at_desc",
            background=True,
        )
        logger.info("MongoDB indexes on ocr_documents verified/created.")
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not create MongoDB indexes: %s", exc)
