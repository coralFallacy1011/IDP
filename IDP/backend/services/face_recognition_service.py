"""Face recognition authentication service.

Handles face encoding, storage, similarity comparison, enrollment, and
authentication for the face recognition 2FA feature.

Public interface
----------------
encode_face(image_bytes: bytes) -> list[float]
find_match(embedding: list[float]) -> dict | None
enroll_face(user_id, name, role, image_bytes) -> None
authenticate_face(image_bytes) -> dict | None
"""

from __future__ import annotations

import io
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import face_recognition
import numpy as np
from PIL import Image

from models.document import db
from services.audit_service import log_action
from services.biometric_service import generate_access_token, verify_token

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FACE_SIMILARITY_THRESHOLD: float = float(
    os.environ.get("FACE_SIMILARITY_THRESHOLD", "0.4")
)

# ---------------------------------------------------------------------------
# Collection + index (created at module import time — idempotent)
# ---------------------------------------------------------------------------

_face_embeddings = db["face_embeddings"]

try:
    _face_embeddings.create_index("user_id", unique=True)
    logger.info("face_recognition_service: face_embeddings index ensured.")
except Exception as _exc:  # pragma: no cover
    logger.warning("face_recognition_service: could not create index: %s", _exc)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Returns a float in [-1.0, 1.0].  Returns 0.0 when either vector has
    zero magnitude to avoid a division-by-zero error.
    """
    va = np.array(a)
    vb = np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def _euclidean_distance(a: list[float], b: list[float]) -> float:
    """Compute Euclidean distance between two vectors."""
    return float(np.linalg.norm(np.array(a) - np.array(b)))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def encode_face(image_bytes: bytes) -> list[float]:
    """Decode *image_bytes* and extract a face embedding."""
    image = Image.open(io.BytesIO(image_bytes))
    # Strip alpha, ensure RGB, force contiguous uint8 array that dlib accepts
    if image.mode != "RGB":
        image = image.convert("RGB")
    rgb_array = np.ascontiguousarray(np.array(image, dtype=np.uint8))

    locations = face_recognition.face_locations(rgb_array)
    if len(locations) == 0:
        raise ValueError("no_face")
    
    # If multiple faces are detected, select the largest one (the main user)
    # to avoid false alerts from background posters/pictures.
    if len(locations) > 1:
        largest_face = max(locations, key=lambda loc: (loc[2] - loc[0]) * (loc[1] - loc[3]))
        locations = [largest_face]

    encodings = face_recognition.face_encodings(rgb_array, known_face_locations=locations)
    return encodings[0].tolist()


def verify_face_match(candidate_embedding: list[float], stored_embedding: list[float]) -> bool:
    """Compare a candidate face embedding against a stored face embedding.

    Returns True if they match within the tolerance/threshold.
    """
    matches = face_recognition.compare_faces(
        [np.array(stored_embedding)],
        np.array(candidate_embedding),
        tolerance=FACE_SIMILARITY_THRESHOLD
    )
    return bool(matches[0]) if matches else False


def find_match(embedding: list[float]) -> Optional[dict]:
    """Query *face_embeddings*, compare face encodings, and return the best match.

    Uses face_recognition.compare_faces and face_recognition.face_distance
    to identify the stored face with the minimum distance, matching the video reference.
    """
    docs = list(_face_embeddings.find({}, {"_id": 0}))
    if not docs:
        return None

    known_encodings = [np.array(doc["embedding"]) for doc in docs]
    candidate_encoding = np.array(embedding)

    # 1. Compare faces to get True/False list
    matches = face_recognition.compare_faces(
        known_encodings, candidate_encoding, tolerance=FACE_SIMILARITY_THRESHOLD
    )

    # 2. Get face distance to find the best match
    face_distances = face_recognition.face_distance(known_encodings, candidate_encoding)

    if len(face_distances) == 0:
        return None

    # 3. Find the index of the minimum distance (best match)
    match_index = np.argmin(face_distances)

    if matches[match_index]:
        return docs[match_index]

    return None


def enroll_face(user_id: str, name: str, role: str, image_bytes: bytes) -> None:
    """Encode *image_bytes* and upsert the embedding into *face_embeddings*.

    Uses ``update_one(..., upsert=True)`` so that exactly one embedding exists
    per ``user_id`` at all times (re-enrollment overwrites the existing record).

    Raises
    ------
    ValueError("no_face")
        Propagated from :func:`encode_face`.
    ValueError("multiple_faces")
        Propagated from :func:`encode_face`.
    """
    embedding = encode_face(image_bytes)

    _face_embeddings.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "name": name,
                "role": role,
                "embedding": embedding,
                "enrolled_at": datetime.now(tz=timezone.utc),
            }
        },
        upsert=True,
    )

    try:
        log_action(user=name, role=role, action="face_enrolled")
    except Exception as exc:  # pragma: no cover
        logger.warning("face_recognition_service: audit log failed during enroll: %s", exc)


def authenticate_face(image_bytes: bytes) -> Optional[dict]:
    """Full authentication flow: encode → find_match → generate token → audit.

    Returns a dict with keys ``token``, ``name``, ``role``, ``user_id`` on
    success, or ``None`` when no stored embedding matches the submitted face.

    ``log_action`` calls are wrapped in ``try/except`` so that an unreachable
    audit service never blocks the authentication response.
    """
    embedding = encode_face(image_bytes)
    matched_doc = find_match(embedding)

    if matched_doc is None:
        try:
            log_action(user="unknown", role="unknown", action="login_face_failed")
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "face_recognition_service: audit log failed for failed auth: %s", exc
            )
        return None

    user_id = matched_doc["user_id"]
    name = matched_doc["name"]
    role = matched_doc["role"]

    token = generate_access_token(user_id=user_id, name=name, role=role)

    try:
        log_action(user=name, role=role, action="login_face")
    except Exception as exc:  # pragma: no cover
        logger.warning(
            "face_recognition_service: audit log failed for successful auth: %s", exc
        )

    return {
        "token": token,
        "name": name,
        "role": role,
        "user_id": user_id,
    }
