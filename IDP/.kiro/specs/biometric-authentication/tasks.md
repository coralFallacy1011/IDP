# Implementation Plan: Biometric Authentication

## Overview

Additive implementation of fingerprint-based authentication using an ESP32 + fingerprint sensor, Flask backend services, JWT-based route protection, and Hypothesis property tests. No existing files are modified except for two additive lines in `app.py`.

## Tasks

- [x] 1. Implement Biometric Service (`backend/services/biometric_service.py`)
  - Create `register_user(name, fingerprint_id, role) -> dict`
  - Create `authenticate_fingerprint(fingerprint_id) -> dict | None`
  - Create `generate_access_token(user_id, name, role) -> str`
  - Create `verify_token(token) -> dict`
  - Use `db["users"]` from `models.document`, PyJWT HS256, UUID4 for user_id
  - Create unique indexes on `fingerprint_id` and `user_id` at module load
  - _Requirements: 2.4, 2.5, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4_

  - [ ]* 1.1 Write property test for JWT round-trip (Property 7)
    - **Property 7: JWT generate/verify round-trip preserves all claims**
    - **Validates: Requirements 4.2, 4.5**

  - [ ]* 1.2 Write property test for wrong-key rejection (Property 8)
    - **Property 8: Tokens signed with wrong key are rejected**
    - **Validates: Requirements 4.4**

- [x] 2. Implement Biometric Router (`backend/routes/biometric.py`)
  - Define `biometric_bp = Blueprint("biometric", __name__)`
  - Implement `POST /register` → 201/400/409
  - Implement `POST /authenticate` → 200/400/404
  - Implement `GET /profile` → reads claims from JWT only, no DB lookup; returns 200/401
  - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.4, 3.5, 3.6, 6.1, 6.2, 6.3_

  - [ ]* 2.1 Write property test for registration schema (Property 1)
    - **Property 1: Registration stores correct document schema**
    - **Validates: Requirements 2.1, 2.5**

  - [ ]* 2.2 Write property test for unique user IDs (Property 2)
    - **Property 2: Registration generates unique user IDs**
    - **Validates: Requirements 2.4**

  - [ ]* 2.3 Write property test for duplicate fingerprint_id → 409 (Property 3)
    - **Property 3: Duplicate fingerprint_id is rejected with 409**
    - **Validates: Requirements 2.3**

  - [ ]* 2.4 Write property test for missing fields → 400 (Property 4)
    - **Property 4: Missing required registration fields return 400**
    - **Validates: Requirements 2.2**

  - [ ]* 2.5 Write property test for authenticate round-trip (Property 5)
    - **Property 5: Authentication round-trip preserves claims and respects expiry**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4**

  - [ ]* 2.6 Write property test for unregistered fingerprint → 404 (Property 6)
    - **Property 6: Authentication returns 404 for unregistered fingerprint IDs**
    - **Validates: Requirements 3.5**

  - [ ]* 2.7 Write property test for profile from claims (Property 12)
    - **Property 12: Profile endpoint returns JWT claims without DB lookup**
    - **Validates: Requirements 6.1, 6.3**

- [x] 3. Implement Auth Middleware (`backend/middleware/auth.py`)
  - Create `middleware/` directory with `__init__.py`
  - Implement `init_auth(app)` registering `before_request` hook
  - `PROTECTED_PREFIXES = ("/api/blockchain/", "/api/documents")`
  - Extract Bearer token, call `verify_token`, store in `flask.g.current_user`
  - Return 401 for missing/invalid/expired tokens on protected routes only
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 3.1 Write property test for protected routes reject invalid JWT (Property 9)
    - **Property 9: Protected routes reject all requests without valid JWT**
    - **Validates: Requirements 5.2, 5.4**

  - [ ]* 3.2 Write property test for protected routes pass valid JWT (Property 10)
    - **Property 10: Protected routes pass requests with valid JWT**
    - **Validates: Requirements 5.3, 5.6**

  - [ ]* 3.3 Write property test for unprotected routes not blocked (Property 11)
    - **Property 11: Unprotected routes are never blocked by auth middleware**
    - **Validates: Requirements 5.5, 7.2**

- [x] 4. Register blueprint and middleware in `app.py` (additive only)
  - Add `from routes.biometric import biometric_bp` after existing imports
  - Add `from middleware.auth import init_auth` after existing imports
  - Add `app.register_blueprint(biometric_bp, url_prefix="/api/biometric")`
  - Add `init_auth(app)` after existing blueprint registrations
  - Do NOT touch any existing lines
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 5. Implement ESP32 firmware (`esp32/fingerprint_auth.ino`)
  - `HardwareSerial Serial2(2)`, init at 57600 baud (RX=16, TX=17)
  - WiFi connect, init Adafruit_Fingerprint sensor on Serial2
  - Poll loop: getImage → image2Tz → fingerSearch
  - On match: HTTP POST to `http://<FLASK_HOST>:5050/api/biometric/authenticate` with `{"fingerprint_id": <int>}`
  - Print response body to serial; no enrollment code
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

- [x] 6. Write property-based tests (`backend/tests/test_biometric_auth.py`)
  - Use Hypothesis + Flask test client; mock MongoDB where needed
  - Implement all 12 property tests + 6 unit/example tests
  - _Requirements: all_

- [x] 7. Checkpoint — Ensure all tests pass
  - Run `pytest backend/tests/test_biometric_auth.py -v`
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional property/unit test sub-tasks; they are implemented as part of task 6
- Each task references specific requirements for traceability
- No existing blueprints, OCR pipeline, AI models, or blockchain service are modified
- Property tests validate all 12 correctness properties from the design document
