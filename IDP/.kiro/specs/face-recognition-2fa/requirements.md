# Requirements Document

## Introduction

This document specifies requirements for adding face recognition as an optional, additive biometric
authentication method to the LexAI IDP platform. The existing authentication flow — fingerprint
sensor (ESP32 hardware) or manual fingerprint ID entry — remains **completely unchanged**. Face
recognition is introduced as a second, independent biometric option that users may choose at the
login screen. A user may enroll a face, authenticate via face, or continue to use fingerprint
authentication; the two methods coexist and neither depends on the other.

The backend is a Python/Flask application backed by MongoDB. The frontend is a Next.js application
that communicates with the backend over HTTP. Face recognition processing runs on the backend using
a server-side library (e.g., `face_recognition` or `DeepFace`) so that no biometric data is stored
or processed on the client.

---

## Glossary

- **Face_Recognition_Service**: The new Python backend service responsible for encoding, storing,
  and comparing facial embeddings.
- **Face_Recognition_Route**: The new Flask blueprint mounted at `/api/face` that exposes face
  enrollment and authentication endpoints.
- **Face_Enrollment**: The process by which a registered user associates one or more facial
  embeddings with their existing user account.
- **Face_Embedding**: A numeric vector representation of a face, produced by the
  Face_Recognition_Service from an uploaded image. Embeddings are stored in MongoDB; raw images
  are not persisted.
- **Authentication_Method**: The biometric technique a user chooses at login time — either
  `fingerprint` (existing) or `face` (new).
- **Login_Page**: The existing Next.js page at `/auth/login/page.tsx` that currently presents
  Sensor and Manual ID tabs.
- **Face_Auth_Tab**: The new third tab added to the Login_Page to allow face-based authentication,
  alongside the existing Sensor and Manual ID tabs.
- **Face_Enrollment_Page**: A new Next.js page at `/auth/face-enroll` where an authenticated user
  may enroll their face.
- **Webcam_Component**: The browser-side React component that captures a still frame from the
  user's webcam and submits it to the backend.
- **JWT**: A signed JSON Web Token issued by the existing `generate_access_token` function in
  `services/biometric_service.py`. Face authentication reuses this function without modification.
- **Audit_Service**: The existing `services/audit_service.py` module that writes structured records
  to the `audit_logs` MongoDB collection.
- **face_embeddings**: The new MongoDB collection used exclusively by the Face_Recognition_Service
  to store face enrollment records.
- **Auth_Middleware**: The existing `middleware/auth.py` before-request guard that enforces JWT on
  `/api/blockchain/` and `/api/documents`. It is not modified by this feature.

---

## Requirements

### Requirement 1: Face Enrollment Backend Endpoint

**User Story:** As a registered user, I want to enroll my face so that I can authenticate using
facial recognition in the future.

#### Acceptance Criteria

1. WHEN a POST request is received at `/api/face/enroll` with a valid JWT and a multipart image
   file, THE Face_Recognition_Route SHALL extract a face embedding from the image and store it in
   the `face_embeddings` collection linked to the authenticated user's `user_id`.
2. WHEN the submitted image contains no detectable face, THE Face_Recognition_Route SHALL return
   HTTP 422 with a JSON body containing an `"error"` key and a human-readable description.
3. WHEN the submitted image contains more than one detectable face, THE Face_Recognition_Route
   SHALL return HTTP 422 with a JSON body containing an `"error"` key indicating that exactly one
   face is required.
4. WHEN enrollment succeeds, THE Face_Recognition_Route SHALL return HTTP 201 with a JSON body
   containing `"enrolled": true` and the `"user_id"` of the enrolled user.
5. WHEN the `/api/face/enroll` endpoint receives a request without a valid Bearer JWT,
   THE Face_Recognition_Route SHALL return HTTP 401.
6. THE Face_Recognition_Service SHALL store only the numeric Face_Embedding vector in the
   `face_embeddings` collection; THE Face_Recognition_Service SHALL NOT persist the original image
   or any raw pixel data to any storage medium.
7. WHEN a user re-enrolls (submits a new image while a prior embedding exists for the same
   `user_id`), THE Face_Recognition_Service SHALL overwrite the existing embedding with the new one
   so that exactly one embedding exists per `user_id`.

---

### Requirement 2: Face Authentication Backend Endpoint

**User Story:** As an enrolled user, I want to authenticate by submitting a photo of my face so
that I receive a JWT without using the fingerprint sensor.

#### Acceptance Criteria

1. WHEN a POST request is received at `/api/face/authenticate` with a multipart image file,
   THE Face_Recognition_Route SHALL compare the face detected in the image against all stored
   Face_Embeddings and return HTTP 200 with `token`, `name`, `role`, and `user_id` fields when a
   match is found above the configured similarity threshold.
2. WHEN the submitted image contains no detectable face, THE Face_Recognition_Route SHALL return
   HTTP 422 with a JSON body containing an `"error"` key.
3. WHEN no stored Face_Embedding matches the submitted face above the similarity threshold,
   THE Face_Recognition_Route SHALL return HTTP 401 with a JSON body containing `"error":
   "Face not recognised"`.
4. WHEN face authentication succeeds, THE Face_Recognition_Service SHALL call
   `log_action(user=name, role=role, action="login_face")` via the existing Audit_Service so that
   the event is recorded in `audit_logs`.
5. THE Face_Recognition_Route SHALL reuse the existing `generate_access_token` function from
   `services/biometric_service.py` to produce the JWT; THE Face_Recognition_Route SHALL NOT
   implement a separate token-generation mechanism.
6. WHEN the `/api/face/authenticate` endpoint is called without an Authorization header,
   THE Face_Recognition_Route SHALL NOT require a JWT and SHALL process the request as an
   unauthenticated login attempt (matching the behaviour of
   `POST /api/biometric/authenticate`).

---

### Requirement 3: Face Enrollment Status Endpoint

**User Story:** As a registered user, I want to check whether I have enrolled a face so that the
frontend can display the correct UI state.

#### Acceptance Criteria

1. WHEN a GET request is received at `/api/face/status` with a valid Bearer JWT,
   THE Face_Recognition_Route SHALL return HTTP 200 with a JSON body containing
   `"enrolled": true` if a Face_Embedding exists for the requesting user's `user_id`, and
   `"enrolled": false` otherwise.
2. WHEN the `/api/face/status` endpoint receives a request without a valid Bearer JWT,
   THE Face_Recognition_Route SHALL return HTTP 401.

---

### Requirement 4: Face Embedding Storage

**User Story:** As a system operator, I want face embeddings to be stored securely and efficiently
so that lookups remain fast and raw biometric images are never persisted.

#### Acceptance Criteria

1. THE Face_Recognition_Service SHALL create a unique index on the `user_id` field of the
   `face_embeddings` collection at service initialisation time.
2. THE Face_Recognition_Service SHALL store each Face_Embedding as a list of floating-point numbers
   in a field named `"embedding"` within the `face_embeddings` document.
3. THE Face_Recognition_Service SHALL store the `user_id`, `name`, `role`, and `enrolled_at`
   (UTC ISO-8601 timestamp) fields alongside every Face_Embedding in the `face_embeddings`
   collection.
4. THE Face_Recognition_Service SHALL NOT store base64-encoded image data or any pixel-level
   representation of the captured face in any MongoDB collection; image files MAY be stored
   temporarily on the filesystem during processing but SHALL be deleted immediately after the
   Face_Embedding is extracted.

---

### Requirement 5: Face Recognition Service — Encoding and Comparison

**User Story:** As a developer, I want a well-defined service layer for face encoding and
comparison so that the recognition logic is testable in isolation.

#### Acceptance Criteria

1. THE Face_Recognition_Service SHALL expose an `encode_face(image_bytes: bytes) -> list[float]`
   function that returns a Face_Embedding vector when exactly one face is detected, raises
   `ValueError("no_face")` when no face is detected, and raises `ValueError("multiple_faces")`
   when more than one face is detected.
2. THE Face_Recognition_Service SHALL expose a
   `find_match(embedding: list[float]) -> dict | None` function that queries the `face_embeddings`
   collection, computes cosine similarity between the candidate embedding and each stored
   embedding, and returns the user document with the highest similarity score when that score is
   at or above the configured threshold, or `None` when no document meets the threshold.
3. THE Face_Recognition_Service SHALL use a similarity threshold that is configurable via the
   `FACE_SIMILARITY_THRESHOLD` environment variable, defaulting to `0.6` when the variable is
   absent.
4. FOR ALL valid Face_Embedding vectors `e`, encoding the serialised form of `e` back to an
   embedding and comparing with the original SHALL produce a cosine similarity of `1.0` (round-trip
   property).
5. WHEN `find_match` is called with an embedding that was produced from a previously enrolled
   face image for user U, THE Face_Recognition_Service SHALL return the document belonging to
   user U (identity retrieval property).

---

### Requirement 6: Frontend — Face Auth Tab on Login Page

**User Story:** As a user, I want to see a "Face ID" tab on the login page so that I can choose
face recognition as my authentication method without affecting the existing Sensor and Manual ID
tabs.

#### Acceptance Criteria

1. THE Login_Page SHALL display a third tab labelled "Face ID" alongside the existing "Sensor" and
   "Manual ID" tabs without removing or reordering those tabs.
2. WHEN the "Face ID" tab is selected, THE Login_Page SHALL display the Webcam_Component and a
   "Scan Face" button; THE Login_Page SHALL NOT display the fingerprint sensor polling UI or the
   manual ID input form.
3. WHEN the user activates the "Scan Face" button, THE Login_Page SHALL capture a still frame from
   the Webcam_Component, encode it as a JPEG, and POST it to `/api/face/authenticate` as
   multipart form data.
4. WHEN the `/api/face/authenticate` response contains a `token` field, THE Login_Page SHALL call
   the existing `saveAuth` function and redirect the user to `/dashboard`, matching the behaviour
   of the existing fingerprint authentication success path.
5. WHEN the `/api/face/authenticate` response is HTTP 401 or HTTP 422, THE Login_Page SHALL
   display an inline error message and SHALL NOT redirect the user.
6. WHILE the face authentication request is in progress — from the moment the "Scan Face" button
   is activated until the response is received and handled — THE Login_Page SHALL display a loading
   indicator and SHALL disable the "Scan Face" button; the loading indicator SHALL remain visible
   throughout all intermediate states including camera capture and server processing.
7. WHEN the user switches away from the "Face ID" tab, THE Webcam_Component SHALL stop the
   webcam stream to release the camera hardware resource.

---

### Requirement 7: Frontend — Face Enrollment Page

**User Story:** As an authenticated user, I want a dedicated page to enroll my face so that I can
set up face authentication for future logins.

#### Acceptance Criteria

1. THE Face_Enrollment_Page SHALL be accessible at the `/auth/face-enroll` route.
2. WHEN an unauthenticated user navigates to `/auth/face-enroll`, THE Face_Enrollment_Page SHALL
   redirect the user to `/auth/login`.
3. THE Face_Enrollment_Page SHALL display the Webcam_Component, an enrollment status indicator
   that reflects the result of a GET `/api/face/status` call, and a "Enroll Face" button.
4. WHEN the user activates the "Enroll Face" button, THE Face_Enrollment_Page SHALL capture a
   still frame from the Webcam_Component and POST it with the Bearer JWT to `/api/face/enroll`.
5. WHEN the `/api/face/enroll` response is HTTP 201, THE Face_Enrollment_Page SHALL display a
   success message and update the enrollment status indicator to reflect that the user is now
   enrolled.
6. WHEN the `/api/face/enroll` response is HTTP 422, THE Face_Enrollment_Page SHALL display the
   `"error"` value from the response body as an inline error message.
7. WHILE the enrollment request is in progress, THE Face_Enrollment_Page SHALL display a loading
   indicator and SHALL disable the "Enroll Face" button.

---

### Requirement 8: Additive Integration — No Changes to Existing Auth Flow

**User Story:** As a system operator, I want the face recognition feature to be purely additive so
that the existing fingerprint authentication flow is not disrupted.

#### Acceptance Criteria

1. THE Face_Recognition_Route SHALL be registered as a new Flask blueprint at `/api/face` and
   SHALL NOT modify any existing blueprint, route handler, or middleware in the application.
2. THE Face_Recognition_Service SHALL NOT modify the `users` MongoDB collection schema or add any
   fields to existing user documents.
3. THE Auth_Middleware SHALL NOT be modified; the `/api/face/enroll` and `/api/face/status`
   endpoints SHALL enforce JWT by reading the Authorization header directly within the
   Face_Recognition_Route, NOT by relying on the Auth_Middleware.
4. THE Login_Page SHALL preserve the existing "Sensor" and "Manual ID" tab behaviour without any
   changes to their event handlers, state, or polling logic.
5. WHEN the Face_Recognition_Route is unavailable or returns an unexpected error, THE Login_Page
   SHALL display an error message on the Face ID tab only and SHALL NOT affect the Sensor or
   Manual ID tabs.

---

### Requirement 9: Audit Logging for Face Authentication Events

**User Story:** As a system operator, I want face authentication attempts to be logged in the
audit trail so that I have a complete record of all login events.

#### Acceptance Criteria

1. WHEN a face authentication attempt succeeds, THE Face_Recognition_Service SHALL call
   `log_action(user=name, role=role, action="login_face")` using the existing Audit_Service.
2. WHEN a face authentication attempt fails due to an unrecognised face, THE Face_Recognition_Service
   SHALL call `log_action(user="unknown", role="unknown", action="login_face_failed")` using the
   existing Audit_Service.
3. WHEN a face enrollment succeeds, THE Face_Recognition_Service SHALL call
   `log_action(user=name, role=role, action="face_enrolled")` using the existing Audit_Service.
4. THE Face_Recognition_Service SHALL invoke Audit_Service calls inside a try/except block so that
   an Audit_Service failure does not prevent the primary authentication or enrollment response from
   being returned to the caller; face authentication SHALL succeed even if the Audit_Service call
   raises an exception.
