# Implementation Plan: Face Recognition 2FA

## Overview

Add face recognition as an additive, optional biometric authentication method to the LexAI IDP
platform. The implementation follows a strict backend-first order: service layer, then routes,
then blueprint registration in `app.py`, then frontend. No existing code paths are modified;
everything is either a new file or a clearly-scoped addition.

---

## Tasks

- [x] 1. Implement `services/face_recognition_service.py`
  - [x] 1.1 Create the service module skeleton and MongoDB index initialisation
    - Create `backend/services/face_recognition_service.py`
    - Import `face_recognition`, `numpy`, `PIL`, `datetime`, `os`, `logging`
    - Import `db` from `models.document`, `generate_access_token` and `verify_token` from
      `services.biometric_service`, and `log_action` from `services.audit_service`
    - Read `FACE_SIMILARITY_THRESHOLD` from the environment, defaulting to `0.6`
    - Obtain the `_face_embeddings` collection handle and create a unique index on `user_id`
      inside a `try/except` block (idempotent, mirrors the pattern in `biometric_service.py`)
    - Define the `_cosine_similarity(a, b)` helper function using `numpy`
    - _Requirements: 4.1, 5.3, 8.2_

  - [x] 1.2 Implement `encode_face(image_bytes: bytes) -> list[float]`
    - Open `image_bytes` with `PIL.Image` → convert to RGB → `numpy` array
    - Call `face_recognition.face_locations()` to count detected faces
    - Raise `ValueError("no_face")` when count is 0; raise `ValueError("multiple_faces")`
      when count > 1
    - Call `face_recognition.face_encodings()` and return `encodings[0].tolist()`
    - Do NOT write the image bytes to disk or any MongoDB collection
    - _Requirements: 5.1, 4.4, 1.1, 1.2, 1.3_

  - [ ]* 1.3 Write property test — Property 7: `encode_face` output is a valid embedding vector
    - File: `backend/tests/test_face_properties.py`
    - **Property 7: `encode_face` returns a list of exactly 128 finite floats**
    - Mock `face_recognition.face_locations` and `face_recognition.face_encodings` to return
      a controlled single-face result; generate random `image_bytes` via `st.binary`
    - Assert `len(result) == 128` and all values are finite (not NaN, not Inf)
    - Tag: `# Feature: face-recognition-2fa, Property 7`
    - **Validates: Requirements 5.1**

  - [x] 1.4 Implement `find_match(embedding: list[float]) -> dict | None`
    - Iterate all documents in `_face_embeddings` using `find({}, {"_id": 0})`
    - Compute `_cosine_similarity` for each stored embedding; track the best score and document
    - Return the best document when `best_score >= FACE_SIMILARITY_THRESHOLD`, else `None`
    - _Requirements: 5.2, 5.3, 2.1, 2.3_

  - [ ]* 1.5 Write property test — Property 1: Embedding serialisation round-trip
    - **Property 1: JSON round-trip preserves cosine similarity of 1.0**
    - Use `@given(st.lists(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False), min_size=128, max_size=128))`
    - `@settings(max_examples=200)`
    - Serialise embedding to JSON and back; assert `abs(_cosine_similarity(original, restored) - 1.0) < 1e-9`
    - Tag: `# Feature: face-recognition-2fa, Property 1`
    - **Validates: Requirements 5.4**

  - [ ]* 1.6 Write property test — Property 2: Identity retrieval
    - **Property 2: `find_match` returns the enrolled user's document**
    - Use `@given(st.text(min_size=1), st.text(min_size=1), st.text(min_size=1), st.lists(...))`
    - Insert the embedding directly into a mocked `_face_embeddings` collection; call `find_match`
    - Assert returned document's `user_id` equals the enrolled user's `user_id`
    - Tag: `# Feature: face-recognition-2fa, Property 2`
    - **Validates: Requirements 5.5, 2.1**

  - [ ]* 1.7 Write property test — Property 3: Non-match below threshold returns None
    - **Property 3: Dissimilar embedding produces `None` from `find_match`**
    - Generate two embeddings whose cosine similarity is guaranteed below threshold
      (e.g., embed query as the negation of all stored vectors)
    - Assert `find_match(query_embedding) is None`
    - Tag: `# Feature: face-recognition-2fa, Property 3`
    - **Validates: Requirements 2.3, 5.2**

  - [x] 1.8 Implement `enroll_face(user_id, name, role, image_bytes) -> None`
    - Call `encode_face(image_bytes)` — let `ValueError` propagate to the route layer
    - Call `_face_embeddings.update_one({"user_id": user_id}, {"$set": {...}}, upsert=True)`
      with fields `name`, `role`, `embedding`, `enrolled_at` (UTC ISO-8601)
    - Wrap `log_action(user=name, role=role, action="face_enrolled")` in `try/except Exception`
    - _Requirements: 1.1, 1.6, 1.7, 4.2, 4.3, 9.3, 9.4_

  - [ ]* 1.9 Write property test — Property 4: Stored document schema invariant
    - **Property 4: Enrolled document contains exactly the specified fields**
    - Mock `encode_face` to return a controlled 128-float list; call `enroll_face`; fetch document
    - Assert document has exactly `user_id`, `name`, `role`, `embedding`, `enrolled_at`
    - Assert `embedding` is a non-empty list of floats; assert no field contains bytes or base64
    - Tag: `# Feature: face-recognition-2fa, Property 4`
    - **Validates: Requirements 4.2, 4.3, 4.4, 1.6**

  - [ ]* 1.10 Write property test — Property 5: Upsert idempotence
    - **Property 5: Second enrollment overwrites the first; exactly one document remains**
    - Mock `encode_face` to return two distinct 128-float embeddings in sequence
    - Call `enroll_face` twice for the same `user_id`; query `_face_embeddings.count_documents`
    - Assert count == 1 and the stored embedding matches the second call's embedding
    - Tag: `# Feature: face-recognition-2fa, Property 5`
    - **Validates: Requirements 1.7**

  - [x] 1.11 Implement `authenticate_face(image_bytes) -> dict | None`
    - Call `encode_face(image_bytes)` — let `ValueError` propagate
    - Call `find_match(embedding)`; if `None`, wrap `log_action(user="unknown", role="unknown", action="login_face_failed")` in `try/except`, return `None`
    - On match, call `generate_access_token` from `biometric_service` to produce the JWT
    - Wrap `log_action(user=name, role=role, action="login_face")` in `try/except Exception`
    - Return `{"token": token, "name": name, "role": role, "user_id": user_id}`
    - _Requirements: 2.1, 2.4, 2.5, 9.1, 9.2, 9.4_

  - [ ]* 1.12 Write property test — Property 6: Audit failure does not block response
    - **Property 6: `log_action` exception does not propagate from `enroll_face` or `authenticate_face`**
    - Patch `log_action` to always raise `Exception("audit down")`
    - Call `enroll_face` (with mocked `encode_face`) and `authenticate_face` (with mocked `find_match`)
    - Assert neither call raises; assert the expected return value is still produced
    - Tag: `# Feature: face-recognition-2fa, Property 6`
    - **Validates: Requirements 9.4**

- [x] 2. Checkpoint — verify service layer
  - Ensure all tests in `backend/tests/test_face_properties.py` pass, ask the user if questions arise.

- [x] 3. Implement `routes/face_routes.py`
  - [x] 3.1 Create the Flask blueprint and `_require_jwt()` helper
    - Create `backend/routes/face_routes.py`
    - Define `face_bp = Blueprint("face", __name__)`
    - Implement `_require_jwt()`: extract `Authorization: Bearer <token>` header, call
      `verify_token(token)`, return `(claims, None)` on success or `(None, (response, 401))` on
      failure — same inline-check pattern as `biometric.py /profile`
    - _Requirements: 1.5, 3.2, 8.1, 8.3_

  - [x] 3.2 Implement `POST /api/face/enroll` route handler
    - Call `_require_jwt()`; return 401 immediately on failure
    - Read the `file` field from `request.files`; return 400 `{"error": "No image file provided"}` if absent
    - Read `image_bytes = file.read()`
    - Call `face_recognition_service.enroll_face(user_id, name, role, image_bytes)`
    - Catch `ValueError("no_face")` → 422 `{"error": "No face detected in the image"}`
    - Catch `ValueError("multiple_faces")` → 422 `{"error": "Image must contain exactly one face"}`
    - On success → 201 `{"enrolled": true, "user_id": user_id}`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 3.3 Implement `POST /api/face/authenticate` route handler
    - No JWT required; read `file` from `request.files`; return 400 if absent
    - Call `face_recognition_service.authenticate_face(image_bytes)`
    - Catch `ValueError("no_face")` → 422 `{"error": "No face detected in the image"}`
    - On `None` result → 401 `{"error": "Face not recognised"}`
    - On success → 200 `{"token": ..., "name": ..., "role": ..., "user_id": ...}`
    - _Requirements: 2.1, 2.2, 2.3, 2.6_

  - [x] 3.4 Implement `GET /api/face/status` route handler
    - Call `_require_jwt()`; return 401 on failure
    - Query `_face_embeddings.find_one({"user_id": claims["user_id"]})`
    - Return 200 `{"enrolled": true}` if document exists, `{"enrolled": false}` otherwise
    - _Requirements: 3.1, 3.2_

  - [ ]* 3.5 Write unit tests for route layer (`backend/tests/test_face_routes.py`)
    - Test `POST /api/face/enroll` returns 401 with no Authorization header (Req 1.5)
    - Test `POST /api/face/enroll` returns 401 with an expired JWT (Req 1.5)
    - Test `POST /api/face/authenticate` returns 401 `{"error": "Face not recognised"}` when
      `authenticate_face` returns `None` (Req 2.3)
    - Test `GET /api/face/status` returns `{"enrolled": false}` for a user with no embedding (Req 3.1)
    - Test `GET /api/face/status` returns `{"enrolled": true}` for a user with an embedding (Req 3.1)
    - Test `log_action` called with `action="login_face"` on successful authentication (Req 9.1)
    - Test `log_action` called with `action="login_face_failed"` on failed authentication (Req 9.2)
    - Test `log_action` called with `action="face_enrolled"` on successful enrollment (Req 9.3)
    - Test `FACE_SIMILARITY_THRESHOLD` defaults to `0.6`; respects env var override (Req 5.3)
    - _Requirements: 1.5, 2.3, 3.1, 5.3, 9.1, 9.2, 9.3_

- [x] 4. Checkpoint — verify route layer
  - Ensure all tests in `backend/tests/test_face_routes.py` pass, ask the user if questions arise.

- [x] 5. Register the blueprint in `app.py` (additive only)
  - [x] 5.1 Add the two blueprint-registration lines to `backend/app.py`
    - After the last existing `app.register_blueprint(...)` call, append:
      ```python
      from routes.face_routes import face_bp
      app.register_blueprint(face_bp, url_prefix="/api/face")
      ```
    - Touch no other line in `app.py`
    - _Requirements: 8.1_

  - [ ]* 5.2 Write integration test for additive registration
    - File: `backend/tests/test_face_integration.py`
    - Spin up the Flask test client with the full `app` (real blueprint registration)
    - Assert `POST /api/biometric/authenticate` and other existing routes still return expected
      status codes (not 404) after `face_bp` is registered — verifying additive integration
    - Assert `POST /api/face/authenticate` with no file returns 400 (not 404), confirming
      the blueprint is mounted
    - _Requirements: 8.1, 8.4_

- [x] 6. Checkpoint — verify backend end-to-end
  - Ensure all backend tests pass. Verify Flask app starts without import errors. Ask the user if questions arise.

- [x] 7. Implement `frontend/src/components/WebcamCapture.tsx`
  - [x] 7.1 Create the `WebcamCapture` component with `useImperativeHandle`
    - Create `frontend/src/components/WebcamCapture.tsx`
    - Define `WebcamCaptureHandle` interface with `captureFrame(): Promise<Blob>`
    - Define `WebcamCaptureProps` with optional `ref`, `onReady`, `onError`, `className`
    - Use `forwardRef` + `useImperativeHandle` to expose `captureFrame`
    - On mount (`useEffect`), call `navigator.mediaDevices.getUserMedia({ video: true })`,
      attach the stream to a `<video>` element (muted, autoPlay, playsInline)
    - Implement `captureFrame`: draw video frame onto a hidden `<canvas>`, call
      `canvas.toBlob(resolve, "image/jpeg", 0.92)`
    - On unmount, call `stream.getTracks().forEach(t => t.stop())` to release camera hardware
    - Render an inline error message when camera access is denied or unavailable
    - _Requirements: 6.2, 6.7, 7.3_

  - [ ]* 7.2 Write frontend unit test for `WebcamCapture`
    - File: `frontend/src/__tests__/WebcamCapture.test.tsx`
    - Mock `navigator.mediaDevices.getUserMedia`
    - Assert `getTracks()[].stop()` is called when the component unmounts
    - _Requirements: 6.7_

- [x] 8. Add API helper functions to `frontend/src/lib/api.ts` (additive only)
  - [x] 8.1 Add `FaceAuthResponse`, `FaceStatusResponse` interfaces and three API functions
    - Add `FaceAuthResponse` and `FaceStatusResponse` TypeScript interfaces
    - Implement `authenticateFace(imageBlob: Blob): Promise<FaceAuthResponse>` —
      `POST /api/face/authenticate` with `multipart/form-data`, no auth header needed
    - Implement `enrollFace(imageBlob: Blob): Promise<{ enrolled: boolean; user_id: string }>` —
      `POST /api/face/enroll` with `multipart/form-data`; JWT attached automatically by the
      existing axios interceptor
    - Implement `getFaceStatus(): Promise<FaceStatusResponse>` —
      `GET /api/face/status`; JWT attached automatically
    - Append only; do not modify any existing export
    - _Requirements: 6.3, 7.4, 3.1_

- [x] 9. Implement `frontend/src/app/auth/face-enroll/page.tsx`
  - [x] 9.1 Create the Face Enrollment page
    - Create `frontend/src/app/auth/face-enroll/page.tsx`
    - On mount, read `auth_token` from `localStorage`; if absent, call `router.push("/auth/login")`
    - Call `getFaceStatus()` to populate the initial enrollment status indicator
      (badge: "Enrolled" / "Not enrolled")
    - Render `<WebcamCapture ref={webcamRef} />`, the status badge, and an "Enroll Face" button
    - On "Enroll Face" click: `captureFrame()` → `FormData` → `enrollFace(blob)` with Bearer JWT
    - On HTTP 201: show success message, update status badge to "Enrolled"
    - On HTTP 422: display the `"error"` value from response body inline
    - During in-flight request: set `loading = true`, disable button, show `Loader2` spinner
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

  - [ ]* 9.2 Write frontend unit tests for Face Enrollment page
    - File: `frontend/src/__tests__/FaceEnrollPage.test.tsx`
    - Unauthenticated user (no `auth_token` in `localStorage`) → assert redirect to `/auth/login`
    - HTTP 201 response → assert success message displayed, status indicator shows "Enrolled"
    - HTTP 422 response → assert `error` field from response body shown inline
    - _Requirements: 7.2, 7.5, 7.6_

- [x] 10. Add Face ID tab to `frontend/src/app/auth/login/page.tsx` (additive only)
  - [x] 10.1 Add `activeTab` state and Face ID tab button
    - In `frontend/src/app/auth/login/page.tsx`, replace the existing `sensorMode` boolean with
      a three-value `activeTab` state: `"sensor" | "manual" | "face"` — map the existing
      `sensorMode = true` path to `"sensor"` and `sensorMode = false` path to `"manual"` so all
      existing conditional rendering blocks are unchanged
    - Add the third tab button with `onClick={() => { setActiveTab("face"); setError(null); }}`
      using `Camera` from `lucide-react`; preserve the existing "Sensor" and "Manual ID" button
      `onClick` handlers verbatim
    - _Requirements: 6.1, 8.4_

  - [x] 10.2 Implement the Face ID tab content panel
    - When `activeTab === "face"`: render `<WebcamCapture ref={webcamRef} />` and a "Scan Face"
      button; do NOT render the fingerprint sensor polling UI or the manual ID input form
    - On "Scan Face" click: `captureFrame()` → `authenticateFace(blob)` from `api.ts`
    - On 200 + `token`: call existing `saveAuth(data)` and `router.push("/dashboard")`
    - On 401 / 422: set the shared `error` state (same state variable used by existing tabs)
    - During in-flight request: `loading = true`, disable button, show `Loader2` spinner
    - Mount `<WebcamCapture>` only when `activeTab === "face"` so switching tabs auto-stops stream
    - _Requirements: 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 8.5_

  - [ ]* 10.3 Write frontend unit tests for Login page Face ID tab
    - File: `frontend/src/__tests__/LoginPage.test.tsx`
    - Assert three tabs render with labels "Sensor", "Manual ID", "Face ID" in that order
    - Clicking "Face ID" tab hides fingerprint polling UI, shows webcam and "Scan Face" button
    - Successful face auth response calls `saveAuth` and routes to `/dashboard`
    - HTTP 401 response shows inline error message, does not redirect
    - _Requirements: 6.1, 6.2, 6.4, 6.5_

- [x] 11. Final checkpoint — Ensure all tests pass
  - Run `pytest backend/tests/` and the frontend test suite; ensure all tests pass.
  - Verify the Flask dev server starts without errors after blueprint registration.
  - Ask the user if any questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Property tests use Hypothesis; each tag follows the format
  `# Feature: face-recognition-2fa, Property N: description`
- The `face_recognition` library (dlib-based) must be installed in the backend virtual
  environment: `pip install face_recognition Pillow numpy`
- Backend tasks (1–6) are completed entirely before any frontend task begins
- Blueprint registration (task 5) is a discrete step separate from route implementation
- The existing `sensorMode` boolean refactor in task 10.1 is purely a rename — all existing
  conditional branches are preserved; it is not a behavioural change
- `enrollFace` and `getFaceStatus` inherit the Bearer JWT automatically from the existing
  axios request interceptor; no extra header wiring is needed in the frontend

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3", "1.4"] },
    { "id": 3, "tasks": ["1.5", "1.6", "1.7", "1.8"] },
    { "id": 4, "tasks": ["1.9", "1.10", "1.11"] },
    { "id": 5, "tasks": ["1.12", "3.1"] },
    { "id": 6, "tasks": ["3.2", "3.3", "3.4"] },
    { "id": 7, "tasks": ["3.5", "5.1"] },
    { "id": 8, "tasks": ["5.2", "7.1", "8.1"] },
    { "id": 9, "tasks": ["7.2", "9.1"] },
    { "id": 10, "tasks": ["9.2", "10.1"] },
    { "id": 11, "tasks": ["10.2"] },
    { "id": 12, "tasks": ["10.3"] }
  ]
}
```
