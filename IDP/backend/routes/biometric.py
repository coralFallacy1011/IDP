"""Biometric authentication blueprint.

Endpoints
---------
POST /api/biometric/register     — register a new user (name, fingerprint_id, role)
POST /api/biometric/authenticate — authenticate by fingerprint_id, receive JWT
GET  /api/biometric/profile      — return profile from JWT claims (no DB lookup)
GET  /api/biometric/poll         — long-poll: returns JWT when sensor triggers auth
GET  /api/biometric/demo-users   — list demo users (no auth required)
"""

from __future__ import annotations

import time
import threading
import jwt as pyjwt
from flask import Blueprint, g, jsonify, request

from services.biometric_service import (
    authenticate_fingerprint,
    generate_access_token,
    register_user,
    verify_token,
)
from services.audit_service import log_action
from models.document import db

biometric_bp = Blueprint("biometric", __name__)


def _face_enrolled_for(user_id: str) -> bool:
    """Return True if the user has a face embedding stored."""
    try:
        return db["face_embeddings"].find_one({"user_id": user_id}) is not None
    except Exception:
        return False

# ---------------------------------------------------------------------------
# In-memory slot: ESP32 posts here, browser polls here
# Protected by a lock so concurrent requests are safe.
# ---------------------------------------------------------------------------
_sensor_lock = threading.Lock()
_sensor_pending: dict | None = None   # set by ESP32, expires after 10s
_sensor_time: float = 0.0


def _set_sensor_result(result: dict) -> None:
    global _sensor_pending, _sensor_time
    with _sensor_lock:
        _sensor_pending = result
        _sensor_time = time.time()


def _get_sensor_result() -> dict | None:
    global _sensor_pending, _sensor_time
    with _sensor_lock:
        if _sensor_pending:
            if time.time() - _sensor_time < 10.0:
                return _sensor_pending
            else:
                _sensor_pending = None
                _sensor_time = 0.0
    return None


# ---------------------------------------------------------------------------
# POST /register
# ---------------------------------------------------------------------------

@biometric_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    missing = [f for f in ("name", "fingerprint_id", "role") if f not in data]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    name = data["name"]
    fingerprint_id = data["fingerprint_id"]
    role = data["role"]

    # Basic type / value validation
    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "name must be a non-empty string"}), 400
    if not isinstance(fingerprint_id, int) or isinstance(fingerprint_id, bool) or fingerprint_id < 1:
        return jsonify({"error": "fingerprint_id must be a positive integer"}), 400
    if not isinstance(role, str) or not role.strip():
        return jsonify({"error": "role must be a non-empty string"}), 400

    try:
        user = register_user(name=name, fingerprint_id=fingerprint_id, role=role)
    except ValueError:
        return jsonify({"error": "fingerprint_id already registered"}), 409
    except Exception:
        return jsonify({"error": "Internal server error"}), 500

    return jsonify({"user_id": user["user_id"]}), 201


# ---------------------------------------------------------------------------
# POST /authenticate
# ---------------------------------------------------------------------------

@biometric_bp.route("/authenticate", methods=["POST"])
def authenticate():
    data = request.get_json(silent=True) or {}

    fingerprint_id = data.get("fingerprint_id") if "fingerprint_id" in data else data.get("finger_id")
    if fingerprint_id is None:
        return jsonify({"error": "fingerprint_id or finger_id is required"}), 400

    if not isinstance(fingerprint_id, int) or isinstance(fingerprint_id, bool):
        return jsonify({"error": "fingerprint_id must be an integer"}), 400

    try:
        user = authenticate_fingerprint(fingerprint_id)
    except Exception:
        return jsonify({"error": "Internal server error"}), 500

    if user is None:
        return jsonify({"error": "Fingerprint not registered"}), 404

    token = generate_access_token(
        user_id=user["user_id"],
        name=user["name"],
        role=user["role"],
    )

    # Audit: login event
    try:
        log_action(user=user["name"], role=user["role"], action="login")
    except Exception:
        pass

    result = {
        "token": token,
        "name": user["name"],
        "role": user["role"],
        "fingerprint_id": user["fingerprint_id"],
        "user_id": user["user_id"],
        "face_enrolled": _face_enrolled_for(user["user_id"]),
    }

    # Notify any waiting browser poll (ESP32 flow)
    _set_sensor_result(result)

    return jsonify(result), 200


# ---------------------------------------------------------------------------
# GET /poll  — browser long-polls this while waiting for sensor scan
# Returns {"waiting": true} until the ESP32 triggers /authenticate,
# then returns the JWT payload exactly once.
# ---------------------------------------------------------------------------

@biometric_bp.route("/poll", methods=["GET"])
def poll():
    """Short-poll endpoint. Browser calls this every 1s while waiting for sensor.
    Returns 202 {"waiting": true} if no scan yet, or 200 {token, name, role} on match.
    """
    result = _get_sensor_result()
    if result:
        return jsonify(result), 200
    return jsonify({"waiting": True}), 202


# ---------------------------------------------------------------------------
# GET /profile
# ---------------------------------------------------------------------------

@biometric_bp.route("/profile", methods=["GET"])
def profile():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Authorization header missing or malformed"}), 401

    token = auth_header[len("Bearer "):]
    try:
        claims = verify_token(token)
    except pyjwt.ExpiredSignatureError:
        return jsonify({"error": "Invalid or expired token"}), 401
    except pyjwt.InvalidTokenError:
        return jsonify({"error": "Invalid or expired token"}), 401

    return jsonify({
        "user_id": claims["user_id"],
        "name": claims["name"],
        "role": claims["role"],
    }), 200


# ---------------------------------------------------------------------------
# GET /demo-users  (demo only — no auth required)
# ---------------------------------------------------------------------------

@biometric_bp.route("/demo-users", methods=["GET"])
def demo_users():
    try:
        users = list(db["users"].find({}, {"_id": 0, "name": 1, "role": 1, "fingerprint_id": 1}))
        return jsonify(users), 200
    except Exception:
        return jsonify({"error": "Internal server error"}), 500
