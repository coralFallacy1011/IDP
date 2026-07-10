"""Face recognition blueprint.

Endpoints
---------
POST /api/face/enroll         — enroll face (JWT required), multipart image
POST /api/face/authenticate   — authenticate by face (no JWT), multipart image
GET  /api/face/status         — check enrollment status (JWT required)
POST /api/face/verify-login   — 2FA step: verify face after fingerprint match
"""

from __future__ import annotations

import jwt as pyjwt
from flask import Blueprint, jsonify, request

from models.document import db
from services.biometric_service import verify_token, generate_access_token
from services import face_recognition_service

face_bp = Blueprint("face", __name__)

# MongoDB collection reference used by /status and /verify-login
_face_embeddings = db["face_embeddings"]


# ---------------------------------------------------------------------------
# JWT helper
# ---------------------------------------------------------------------------

def _require_jwt():
    """Extract and verify a Bearer JWT from the Authorization header.

    Returns ``(claims_dict, None)`` on success.
    Returns ``(None, (response, 401))`` on failure.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, (jsonify({"error": "Authorization header missing or malformed"}), 401)
    token = auth[len("Bearer "):]
    try:
        claims = verify_token(token)
        return claims, None
    except pyjwt.ExpiredSignatureError:
        return None, (jsonify({"error": "Invalid or expired token"}), 401)
    except pyjwt.InvalidTokenError:
        return None, (jsonify({"error": "Invalid or expired token"}), 401)


# ---------------------------------------------------------------------------
# POST /enroll
# ---------------------------------------------------------------------------

@face_bp.route("/enroll", methods=["POST"])
def enroll():
    """Enroll a face for the authenticated user."""
    claims, err = _require_jwt()
    if err:
        return err

    if "file" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["file"]
    image_bytes = file.read()

    user_id = claims["user_id"]
    name = claims["name"]
    role = claims["role"]

    try:
        face_recognition_service.enroll_face(user_id, name, role, image_bytes)
    except ValueError as exc:
        if str(exc) == "no_face":
            return jsonify({"error": "No face detected in the image"}), 422
        if str(exc) == "multiple_faces":
            return jsonify({"error": "Image must contain exactly one face"}), 422
        return jsonify({"error": "Internal server error"}), 500
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Internal server error: {str(exc)}"}), 500

    return jsonify({"enrolled": True, "user_id": user_id}), 201


# ---------------------------------------------------------------------------
# POST /authenticate  (standalone face-only login, kept for compatibility)
# ---------------------------------------------------------------------------

@face_bp.route("/authenticate", methods=["POST"])
def authenticate():
    """Authenticate a user by face — no JWT required."""
    if "file" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["file"]
    image_bytes = file.read()

    try:
        result = face_recognition_service.authenticate_face(image_bytes)
    except ValueError as exc:
        if str(exc) == "no_face":
            return jsonify({"error": "No face detected in the image"}), 422
        return jsonify({"error": "Internal server error"}), 500
    except Exception:
        return jsonify({"error": "Internal server error"}), 500

    if result is None:
        return jsonify({"error": "Face not recognised"}), 401

    return jsonify({
        "token": result["token"],
        "name": result["name"],
        "role": result["role"],
        "user_id": result["user_id"],
    }), 200


# ---------------------------------------------------------------------------
# GET /status
# ---------------------------------------------------------------------------

@face_bp.route("/status", methods=["GET"])
def status():
    """Return whether the authenticated user has a stored face embedding."""
    claims, err = _require_jwt()
    if err:
        return err

    doc = _face_embeddings.find_one({"user_id": claims["user_id"]})
    return jsonify({"enrolled": doc is not None}), 200


# ---------------------------------------------------------------------------
# POST /verify-login  — 2FA second step after fingerprint match
# ---------------------------------------------------------------------------

@face_bp.route("/verify-login", methods=["POST"])
def verify_login():
    """Second factor: verify face after fingerprint has already matched.

    Expects:
      - ``user_id``  (form field or JSON)
      - ``file``     (multipart image)

    Returns 200 + full JWT on success, 401 on face mismatch, 422 on no face.
    The user_id from the fingerprint step identifies whose embedding to check.
    """
    # Accept user_id from either multipart form field or JSON body
    user_id = request.form.get("user_id") or (
        request.get_json(silent=True) or {}
    ).get("user_id")

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    if "file" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["file"]
    image_bytes = file.read()

    # Look up the stored embedding for this specific user
    doc = _face_embeddings.find_one({"user_id": user_id}, {"_id": 0})
    if not doc:
        return jsonify({"error": "No face enrolled for this user. Please enroll first."}), 404

    try:
        from services.face_recognition_service import encode_face, verify_face_match
        candidate = encode_face(image_bytes)
    except ValueError as exc:
        if str(exc) == "no_face":
            return jsonify({"error": "No face detected in the image"}), 422
        if str(exc) == "multiple_faces":
            return jsonify({"error": "Image must contain exactly one face"}), 422
        return jsonify({"error": "Internal server error"}), 500
    except Exception:
        return jsonify({"error": "Internal server error"}), 500

    from services.face_recognition_service import _euclidean_distance, FACE_SIMILARITY_THRESHOLD
    dist = _euclidean_distance(candidate, doc["embedding"])
    try:
        safe_name = str(doc.get('name')).encode('ascii', 'replace').decode('ascii')
        print(f"\n[FACE_LOG] Candidate vs Stored distance for {safe_name}: {dist:.4f} (Threshold: {FACE_SIMILARITY_THRESHOLD})\n")
    except Exception:
        pass

    if not verify_face_match(candidate, doc["embedding"]):
        try:
            from services.audit_service import log_action
            log_action(user=doc["name"], role=doc["role"], action="login_face_failed_2fa")
        except Exception:
            pass
        return jsonify({"error": "Face not recognised"}), 401

    # Face matched — issue the real JWT
    token = generate_access_token(
        user_id=doc["user_id"],
        name=doc["name"],
        role=doc["role"],
    )

    try:
        from services.audit_service import log_action
        log_action(user=doc["name"], role=doc["role"], action="login_face_2fa")
    except Exception:
        pass

    return jsonify({
        "token": token,
        "name": doc["name"],
        "role": doc["role"],
        "user_id": doc["user_id"],
    }), 200

