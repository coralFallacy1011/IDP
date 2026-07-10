from flask import Flask
from flask_cors import CORS
from routes.documents import doc_bp
from routes.ocr import ocr_bp
from routes.ai import ai_bp
from routes.blockchain import blockchain_bp

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "Legal AI Platform Running"

app.register_blueprint(doc_bp, url_prefix="/api/documents")
app.register_blueprint(ocr_bp, url_prefix="/api/ocr")
app.register_blueprint(ai_bp, url_prefix="/api/ai")
app.register_blueprint(blockchain_bp, url_prefix="/api/blockchain")
from routes.biometric import biometric_bp
from middleware.auth import init_auth
app.register_blueprint(biometric_bp, url_prefix="/api/biometric")
from routes.face_routes import face_bp
app.register_blueprint(face_bp, url_prefix="/api/face")
init_auth(app)

@app.route("/verify", methods=["POST"])
def verify_root():
    from flask import request, jsonify
    from services.biometric_service import authenticate_fingerprint, generate_access_token
    from routes.biometric import _set_sensor_result
    from services.audit_service import log_action
    
    data = request.get_json(silent=True) or {}
    fingerprint_id = data.get("fingerprint_id") if "fingerprint_id" in data else data.get("finger_id")
    confidence = data.get("confidence", 99)
    
    if fingerprint_id is None or not isinstance(fingerprint_id, int) or isinstance(fingerprint_id, bool):
        return jsonify({
            "status": "unauthorized",
            "user": "Unknown"
        }), 200
        
    try:
        user = authenticate_fingerprint(fingerprint_id)
    except Exception:
        return jsonify({
            "status": "unauthorized",
            "user": "Unknown"
        }), 200
        
    if user is None:
        return jsonify({
            "status": "unauthorized",
            "user": "Unknown"
        }), 200
        
    token = generate_access_token(
        user_id=user["user_id"],
        name=user["name"],
        role=user["role"],
    )
    
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
        "face_enrolled": db["face_embeddings"].find_one({"user_id": user["user_id"]}) is not None,
    }
    
    _set_sensor_result(result)
    
    return jsonify({
        "confidence": confidence,
        "status": "authorized",
        "user": user["name"]
    }), 200

if __name__ == "__main__":
    # Ensure MongoDB indexes exist before serving requests
    from models.document import ensure_indexes, db
    ensure_indexes()

    # Seed demo users (idempotent)
    _demo_users = [
        {"name": "Judge A",        "fingerprint_id": 1, "role": "judge"},
        {"name": "Police Officer", "fingerprint_id": 2, "role": "police"},
        {"name": "Lawyer",         "fingerprint_id": 3, "role": "lawyer"},
    ]
    for _u in _demo_users:
        try:
            if not db["users"].find_one({"fingerprint_id": _u["fingerprint_id"]}):
                from services.biometric_service import register_user
                register_user(name=_u["name"], fingerprint_id=_u["fingerprint_id"], role=_u["role"])
                print(f"[SEED] Inserted demo user: {_u['name']}")
            else:
                print(f"[SEED] Already exists: {_u['name']}")
        except Exception as _e:
            print(f"[SEED] Warning: {_e}")

    app.run(debug=True, host="0.0.0.0", port=5000)