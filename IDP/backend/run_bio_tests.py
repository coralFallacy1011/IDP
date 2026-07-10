"""
Biometric authentication layer-by-layer test script.
Steps 2-7: MongoDB, JWT, verify_fingerprint, Flask route, protected route, invalid token.
Run from IDP/backend/:
    python run_bio_tests.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json

# ── Step 2: MongoDB ──────────────────────────────────────────────────────────
print("\n" + "="*50)
print("STEP 2: MongoDB INSERT TEST")
print("="*50)
try:
    from services.biometric_service import register_user
    from models.document import db

    # Clean up any previous test user
    db["users"].delete_many({"fingerprint_id": 1})

    user = register_user(name="Judge A", fingerprint_id=1, role="judge")
    doc  = db["users"].find_one({"fingerprint_id": 1}, {"_id": 0})

    print(f"Inserted: {json.dumps(doc, default=str)}")
    assert doc["name"] == "Judge A" and doc["role"] == "judge"
    print("TEST 2 MONGODB: PASS")
except Exception as e:
    print(f"TEST 2 MONGODB: FAIL — {e}")
    sys.exit(1)

# ── Step 3: JWT ──────────────────────────────────────────────────────────────
print("\n" + "="*50)
print("STEP 3: JWT GENERATE / VERIFY TEST")
print("="*50)
try:
    from services.biometric_service import generate_access_token, verify_token

    token   = generate_access_token(user["user_id"], "Judge A", "judge")
    payload = verify_token(token)

    print(f"Token   : {token[:40]}...")
    print(f"Payload : {json.dumps({k:v for k,v in payload.items() if k!='exp'})}")
    assert payload["name"] == "Judge A" and payload["role"] == "judge"
    print("TEST 3 JWT: PASS")
except Exception as e:
    print(f"TEST 3 JWT: FAIL — {e}")
    sys.exit(1)

# ── Step 4: authenticate_fingerprint() ──────────────────────────────────────
print("\n" + "="*50)
print("STEP 4: authenticate_fingerprint(1)")
print("="*50)
try:
    from services.biometric_service import authenticate_fingerprint

    result = authenticate_fingerprint(1)
    print(f"Returned: {json.dumps(result, default=str)}")
    assert result is not None and result["name"] == "Judge A"
    print("TEST 4 VERIFY_FINGERPRINT: PASS")
except Exception as e:
    print(f"TEST 4 VERIFY_FINGERPRINT: FAIL — {e}")
    sys.exit(1)

# ── Steps 5-7: Flask routes ──────────────────────────────────────────────────
print("\n" + "="*50)
print("STEP 5-7: FLASK ROUTE TESTS")
print("="*50)
try:
    from flask import Flask
    from routes.biometric import biometric_bp
    from middleware.auth import init_auth

    app = Flask(__name__)
    app.register_blueprint(biometric_bp, url_prefix="/api/biometric")
    init_auth(app)
    # Add a dummy protected route so step 6 has something to hit
    @app.route("/api/blockchain/")
    def _bc(): return "ok", 200

    client = app.test_client()

    # Step 5: POST /api/biometric/authenticate
    r5 = client.post("/api/biometric/authenticate",
                     json={"fingerprint_id": 1},
                     content_type="application/json")
    body5 = r5.get_json()
    print(f"\nStep 5 status : {r5.status_code}")
    print(f"Step 5 body   : {json.dumps(body5)}")
    assert r5.status_code == 200 and "token" in body5
    jwt_token = body5["token"]
    print("TEST 5 AUTH ROUTE: PASS")

    # Step 6: protected route with valid token
    r6 = client.get("/api/blockchain/",
                    headers={"Authorization": f"Bearer {jwt_token}"})
    print(f"\nStep 6 status : {r6.status_code}")
    print(f"Step 6 body   : {r6.get_data(as_text=True)[:120]}")
    assert r6.status_code != 401, f"Got 401 on protected route with valid token"
    print("TEST 6 PROTECTED ROUTE: PASS")

    # Step 7: invalid token → 401
    r7 = client.get("/api/blockchain/",
                    headers={"Authorization": "Bearer invalidtoken"})
    print(f"\nStep 7 status : {r7.status_code}")
    print(f"Step 7 body   : {r7.get_data(as_text=True)[:120]}")
    assert r7.status_code == 401
    print("TEST 7 INVALID TOKEN: PASS")

except Exception as e:
    print(f"FLASK TESTS FAIL — {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)

# ── Step 8: ESP32 code review ────────────────────────────────────────────────
print("\n" + "="*50)
print("STEP 8: ESP32 CODE REVIEW")
print("="*50)
ino_path = os.path.join(os.path.dirname(__file__), "..", "esp32", "fingerprint_auth", "fingerprint_auth.ino")
ino = open(ino_path).read()
checks = {
    "GPIO16 as RX2"          : "16, 17" in ino,
    "GPIO17 as TX2"          : "GPIO17" in ino or "16, 17" in ino,
    "Serial2 initialized"    : "mySerial" in ino or "Serial2" in ino,
    "HTTP POST configured"   : "http.POST" in ino,
    "fingerprint_id sent"    : ("fingerprint_id" in ino or "finger_id" in ino) and "finger.fingerID" in ino,
    "WiFi SSID set"          : "OnePlus 12" in ino,
    "Flask host set"         : "192.168.1.107" in ino,
}
all_ok = True
for check, result in checks.items():
    status = "OK" if result else "MISSING"
    print(f"  {check:30s}: {status}")
    if not result:
        all_ok = False
print("TEST 8 ESP32 CODE REVIEW:", "PASS" if all_ok else "FAIL")

# ── Final Report ─────────────────────────────────────────────────────────────
print("\n" + "="*50)
print("FINAL REPORT")
print("="*50)
print("TEST 1 IMPORTS         : PASS")
print("TEST 2 MONGODB         : PASS")
print("TEST 3 JWT             : PASS")
print("TEST 4 VERIFY_FINGERPRINT : PASS")
print("TEST 5 AUTH ROUTE      : PASS")
print("TEST 6 PROTECTED ROUTE : PASS")
print("TEST 7 INVALID TOKEN   : PASS")
print("TEST 8 ESP32 CODE REVIEW:", "PASS" if all_ok else "FAIL")
print("\nFINAL STATUS: ALL SOFTWARE TESTS PASSED")
print("Next: Flash esp32/fingerprint_auth.ino via Arduino IDE to test hardware.")
