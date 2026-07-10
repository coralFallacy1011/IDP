# Requirements Document

## Introduction

This document covers the biometric authentication feature for the existing Flask-based Legal Document Management System. The system currently provides OCR, classification, metadata extraction, summarization, MongoDB storage, and blockchain verification. This feature adds fingerprint-based authentication using a connected ESP32 microcontroller and fingerprint sensor. Authenticated users receive a JWT that gates access to protected API routes (`/api/blockchain/` and `/api/documents`).

No existing functionality (OCR, blockchain logic, AI models) shall be modified. The feature is additive only.

## Glossary

- **ESP32**: The microcontroller responsible for reading the fingerprint sensor and sending authentication requests to the Flask backend over WiFi.
- **Fingerprint_Sensor**: The hardware fingerprint sensor connected to the ESP32 via UART2 (TX→GPIO17, RX→GPIO16). Fingerprints are pre-enrolled on the sensor; this feature does not perform enrollment.
- **Biometric_Service**: The Python service module (`backend/services/biometric_service.py`) that handles user lookup, JWT generation, and token verification against MongoDB.
- **Biometric_Router**: The Flask blueprint (`backend/routes/biometric.py`) that exposes the biometric REST API endpoints.
- **Auth_Middleware**: The middleware function (`backend/middleware/auth.py`) that enforces JWT authentication on protected routes.
- **JWT**: A JSON Web Token with a 1-hour expiry, issued by the Biometric_Service upon successful fingerprint verification and used to authorize subsequent API calls.
- **Users_Collection**: The MongoDB collection named `users` with documents conforming to the schema `{ "user_id": "...", "name": "...", "fingerprint_id": <int>, "role": "..." }`.
- **fingerprint_id**: An integer identifier assigned to a fingerprint slot on the Fingerprint_Sensor. Values start at 1.
- **Protected_Routes**: The URL prefixes `/api/blockchain/` and `/api/documents` that require a valid JWT in the `Authorization` header.

---

## Requirements

### Requirement 1: ESP32 Fingerprint Capture and Transmission

**User Story:** As a legal system user, I want to place my finger on the sensor and have the ESP32 automatically send an authentication request to the backend, so that I do not need to interact with a computer to initiate login.

#### Acceptance Criteria

1. WHEN the ESP32 powers on, THE ESP32 SHALL initialize `HardwareSerial Serial2` at 57600 baud using pins RX2=GPIO16 and TX2=GPIO17.
2. WHEN the ESP32 powers on, THE ESP32 SHALL connect to the configured WiFi network before attempting any fingerprint operations.
3. WHILE the ESP32 is waiting for a finger, THE ESP32 SHALL poll the Fingerprint_Sensor continuously until a finger is detected.
4. WHEN a finger is detected and the Fingerprint_Sensor returns a successful match, THE ESP32 SHALL send an HTTP POST request to `/api/biometric/authenticate` with a JSON body containing the matched `fingerprint_id` as an integer.
5. WHEN the Fingerprint_Sensor reports no match for the detected finger, THE ESP32 SHALL print a failure message to the serial monitor and resume polling without sending an HTTP request.
6. WHEN the Flask backend returns a response to the POST request, THE ESP32 SHALL print the full HTTP response body to the serial monitor.
7. THE ESP32 firmware SHALL use the Adafruit Fingerprint Library for all sensor communication.
8. THE ESP32 firmware SHALL contain no enrollment code, as fingerprints are pre-enrolled on the sensor.

---

### Requirement 2: User Registration via API

**User Story:** As a system administrator, I want to register a user with their fingerprint ID through a REST API call, so that the system can associate a fingerprint slot with a named user and role.

#### Acceptance Criteria

1. WHEN a POST request is sent to `/api/biometric/register` with a valid JSON body containing `name`, `fingerprint_id`, and `role`, THE Biometric_Router SHALL store the user document in the Users_Collection and return HTTP 201 with the created user's `user_id`.
2. WHEN a POST request to `/api/biometric/register` is missing any of the required fields (`name`, `fingerprint_id`, `role`), THE Biometric_Router SHALL return HTTP 400 with a descriptive error message.
3. WHEN a POST request to `/api/biometric/register` contains a `fingerprint_id` that already exists in the Users_Collection, THE Biometric_Router SHALL return HTTP 409 with an error indicating the fingerprint ID is already registered.
4. THE Biometric_Service SHALL generate a unique `user_id` string for each registered user and store it in the Users_Collection.
5. THE Biometric_Service SHALL store the user document with the exact schema `{ "user_id": "...", "name": "...", "fingerprint_id": <int>, "role": "..." }` in the Users_Collection.

---

### Requirement 3: Fingerprint-Based Authentication and JWT Issuance

**User Story:** As a legal system user, I want my fingerprint match to result in a JWT being returned, so that I can use that token to access protected parts of the system.

#### Acceptance Criteria

1. WHEN a POST request is sent to `/api/biometric/authenticate` with a JSON body containing a valid integer `fingerprint_id`, THE Biometric_Router SHALL query the Users_Collection for a user with that `fingerprint_id`.
2. WHEN a matching user is found in the Users_Collection, THE Biometric_Service SHALL generate a signed JWT containing the user's `user_id`, `name`, and `role` as claims.
3. WHEN a JWT is generated, THE Biometric_Service SHALL set the token expiry to exactly 1 hour from the time of generation.
4. WHEN a matching user is found and a JWT is generated, THE Biometric_Router SHALL return HTTP 200 with a JSON body containing the `token` and the user's `name` and `role`.
5. WHEN no user is found in the Users_Collection matching the provided `fingerprint_id`, THE Biometric_Router SHALL return HTTP 404 with an error message indicating the fingerprint is not registered.
6. WHEN a POST request to `/api/biometric/authenticate` is missing the `fingerprint_id` field, THE Biometric_Router SHALL return HTTP 400 with a descriptive error message.

---

### Requirement 4: JWT Verification

**User Story:** As the system, I want to validate JWTs on incoming requests, so that only legitimately authenticated users can access protected routes.

#### Acceptance Criteria

1. THE Biometric_Service SHALL expose a `verify_token(token)` function that decodes and validates the JWT signature and expiry.
2. WHEN `verify_token` is called with a valid, non-expired JWT, THE Biometric_Service SHALL return the decoded claims dictionary.
3. WHEN `verify_token` is called with an expired JWT, THE Biometric_Service SHALL raise an exception indicating token expiry.
4. WHEN `verify_token` is called with a JWT that has an invalid signature, THE Biometric_Service SHALL raise an exception indicating the token is invalid.
5. FOR ALL valid JWTs issued by `generate_access_token`, calling `verify_token` immediately after SHALL return claims containing the same `user_id`, `name`, and `role` that were used to generate the token (round-trip property).

---

### Requirement 5: Route Protection via Auth Middleware

**User Story:** As a system administrator, I want all blockchain and document management endpoints to require a valid JWT, so that only authenticated users can access sensitive legal data.

#### Acceptance Criteria

1. THE Auth_Middleware SHALL expose a `require_auth()` decorator function that extracts and validates the JWT from the `Authorization` request header.
2. WHEN a request arrives at any endpoint under `/api/blockchain/` or `/api/documents` without an `Authorization` header, THE Auth_Middleware SHALL return HTTP 401 with an error message.
3. WHEN a request arrives at a Protected_Route with an `Authorization` header containing a valid, non-expired JWT, THE Auth_Middleware SHALL allow the request to proceed to the route handler.
4. WHEN a request arrives at a Protected_Route with an `Authorization` header containing an expired or invalid JWT, THE Auth_Middleware SHALL return HTTP 401 with an error message.
5. THE Auth_Middleware SHALL NOT modify, intercept, or affect any route outside of the Protected_Routes (`/api/blockchain/` and `/api/documents`).
6. THE Auth_Middleware SHALL extract the token from the header value using the `Bearer <token>` format.

---

### Requirement 6: Authenticated User Profile Retrieval

**User Story:** As an authenticated user, I want to retrieve my profile information using my JWT, so that the frontend can display my identity and role after login.

#### Acceptance Criteria

1. WHEN a GET request is sent to `/api/biometric/profile` with a valid JWT in the `Authorization` header, THE Biometric_Router SHALL return HTTP 200 with a JSON body containing the user's `user_id`, `name`, and `role`.
2. WHEN a GET request is sent to `/api/biometric/profile` without an `Authorization` header or with an invalid JWT, THE Biometric_Router SHALL return HTTP 401 with an error message.
3. THE Biometric_Router SHALL derive the user identity for the profile response solely from the JWT claims, without performing an additional MongoDB lookup.

---

### Requirement 7: Integration with Existing Flask Application

**User Story:** As a developer, I want the biometric authentication components to be registered in the existing Flask app without disturbing any other routes, so that the system continues to function correctly after the feature is added.

#### Acceptance Criteria

1. WHEN the Flask application starts, THE Flask_App SHALL register the Biometric_Router blueprint at the URL prefix `/api/biometric`.
2. THE Flask_App SHALL register the Auth_Middleware on `/api/blockchain/` and `/api/documents` routes only, leaving `/api/ocr` and `/api/ai` routes unaffected.
3. WHEN the Flask application starts, THE Flask_App SHALL call `ensure_indexes()` on the MongoDB connection as it currently does, with no changes to the existing startup sequence.
4. THE Flask_App SHALL NOT modify or remove any existing blueprint registrations (`doc_bp`, `ocr_bp`, `ai_bp`, `blockchain_bp`).
