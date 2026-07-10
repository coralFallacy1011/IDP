# Requirements Document

## Introduction

This feature connects all existing modules of the Legal Document Management System (OCR pipeline, classification, metadata extraction, summarization, blockchain registration/verification, and ESP32 fingerprint authentication) into a unified, secured API surface. It also introduces a persistent audit logging layer that records every significant user action — login, document upload, document view, and blockchain verification — into a dedicated MongoDB collection. Finally, it seeds a set of demo users and exposes a read-only demo-users endpoint to support front-end development and testing.

The feature spans six implementation phases:
1. Confirm JWT route protection (already in place)
2. Create the `audit_service` with its MongoDB-backed `log_action` function
3. Instrument existing route handlers with audit log calls
4. Seed demo users into the `users` collection
5. Expose a `GET /api/biometric/demo-users` endpoint
6. Provide an automated validation test script

No existing OCR, classification, blockchain, or fingerprint logic is modified.

---

## Glossary

- **System**: The Flask-based Legal Document Management System (backend).
- **Auth_Middleware**: The `before_request` guard defined in `middleware/auth.py` that validates JWT tokens on protected URL prefixes.
- **Audit_Service**: The module `backend/services/audit_service.py` responsible for writing structured records to the `audit_logs` MongoDB collection.
- **Audit_Log**: A single structured record in the `audit_logs` collection capturing who did what and when.
- **JWT**: JSON Web Token issued by `POST /api/biometric/authenticate` and verified by `Auth_Middleware`.
- **g.current_user**: The Flask request-context object populated by `Auth_Middleware` with the decoded JWT claims (`user_id`, `name`, `role`).
- **Demo_User**: A pre-seeded user document in the `users` collection used for development and testing.
- **Fingerprint_ID**: A positive integer that uniquely identifies a registered user's fingerprint in the `users` collection.
- **OCR_Pipeline**: The route handler at `POST /api/ocr/scan` and all services it invokes.
- **Blockchain_Service**: The service module and route handlers under `/api/blockchain/`.
- **Validation_Script**: The Python test script that exercises the API end-to-end and verifies audit records.

---

## Requirements

### Requirement 1: JWT Route Protection

**User Story:** As a system administrator, I want protected API endpoints to reject unauthenticated requests, so that only authenticated users can access sensitive document and blockchain data.

#### Acceptance Criteria

1. WHEN a request is made to any URL beginning with `/api/blockchain/` without an `Authorization: Bearer <token>` header, THE Auth_Middleware SHALL return HTTP 401 with body `{"error": "Unauthorized"}`.
2. WHEN a request is made to any URL beginning with `/api/documents` without an `Authorization: Bearer <token>` header, THE Auth_Middleware SHALL return HTTP 401 with body `{"error": "Unauthorized"}`.
3. WHEN a request is made to `/api/blockchain/` or `/api/documents` with a valid JWT in the `Authorization: Bearer <token>` header, THE Auth_Middleware SHALL set `g.current_user` to the decoded token claims and allow the request to proceed to the route handler.
4. WHEN a request is made to `/api/blockchain/` or `/api/documents` with an expired or malformed JWT, THE Auth_Middleware SHALL return HTTP 401 with body `{"error": "Invalid or expired token"}`.
5. WHEN a request is made to any URL not beginning with `/api/blockchain/` or `/api/documents`, THE Auth_Middleware SHALL allow the request to proceed without performing any token validation.

---

### Requirement 2: Audit Service

**User Story:** As a compliance officer, I want every significant user action to be persisted in a dedicated audit log, so that I can review who accessed or modified documents and when.

#### Acceptance Criteria

1. THE Audit_Service SHALL expose a function `log_action(user, role, action, document_id=None)` that inserts one Audit_Log record into the `audit_logs` MongoDB collection.
2. WHEN `log_action` is called, THE Audit_Service SHALL construct an Audit_Log record with the following fields: `user` (string), `role` (string), `action` (string), `document_id` (string or null), and `timestamp` (UTC datetime).
3. THE Audit_Service SHALL obtain the MongoDB `db` object by importing it from `models.document`, reusing the existing `legal_idp` database connection.
4. IF the MongoDB insert operation raises an exception, THEN THE Audit_Service SHALL log the error using Python's standard `logging` module and return without propagating the exception to the caller.
5. THE Audit_Service SHALL be importable without side effects (no network calls or schema changes at import time).

---

### Requirement 3: Audit Logging — Fingerprint Login

**User Story:** As a security auditor, I want each successful fingerprint authentication to be recorded, so that I can track who logged in and when.

#### Acceptance Criteria

1. WHEN `POST /api/biometric/authenticate` returns HTTP 200, THE System SHALL call `log_action` with `user=<name from response>`, `role=<role from response>`, `action="login"`, and `document_id=None`.
2. WHEN `POST /api/biometric/authenticate` does not return HTTP 200 (e.g., fingerprint not registered), THE System SHALL NOT write an Audit_Log record for that request.
3. THE System SHALL call `log_action` after the JWT token has been successfully generated and before the HTTP response is sent.
4. IF `log_action` raises an exception, THEN THE System SHALL still return the HTTP 200 response with the JWT token to the caller.

---

### Requirement 4: Audit Logging — Document Upload

**User Story:** As a compliance officer, I want each document upload via OCR to be recorded in the audit log, so that I can trace the origin and uploader of every document.

#### Acceptance Criteria

1. WHEN `POST /api/ocr/scan` returns HTTP 200, THE System SHALL call `log_action` with `user=<g.current_user["name"]>`, `role=<g.current_user["role"]>`, `action="upload_document"`, and `document_id=<returned document_id>`.
2. WHEN `POST /api/ocr/scan` is called without a valid JWT (and the route is protected), THE Auth_Middleware SHALL reject the request before `log_action` is ever called.
3. THE System SHALL call `log_action` after the MongoDB document insert and blockchain registration are complete and before the HTTP response is sent.
4. IF `log_action` raises an exception, THEN THE System SHALL still return the HTTP 200 OCR response to the caller.

---

### Requirement 5: Audit Logging — Document View

**User Story:** As a compliance officer, I want each retrieval of a blockchain-registered document record to be logged, so that I have a complete access trail for every document.

#### Acceptance Criteria

1. WHEN `GET /api/blockchain/document/<doc_id>` returns HTTP 200, THE System SHALL call `log_action` with `user=<g.current_user["name"]>`, `role=<g.current_user["role"]>`, `action="view_document"`, and `document_id=<doc_id>`.
2. WHEN `GET /api/blockchain/document/<doc_id>` does not return HTTP 200 (e.g., document not found), THE System SHALL NOT write an Audit_Log record for that request.
3. THE System SHALL call `log_action` after the on-chain record has been successfully retrieved and before the HTTP response is sent.
4. IF `log_action` raises an exception, THEN THE System SHALL still return the HTTP 200 response to the caller.

---

### Requirement 6: Audit Logging — Blockchain Verification

**User Story:** As a compliance officer, I want each blockchain document verification attempt to be recorded, so that I can audit which users verified which documents.

#### Acceptance Criteria

1. WHEN `POST /api/blockchain/verify` returns HTTP 200, THE System SHALL call `log_action` with `user=<g.current_user["name"]>`, `role=<g.current_user["role"]>`, `action="verify_document"`, and `document_id=<document_id from request body>`.
2. WHEN `POST /api/blockchain/verify` does not return HTTP 200 (e.g., document not found, invalid ID), THE System SHALL NOT write an Audit_Log record for that request.
3. THE System SHALL call `log_action` after the verification result has been determined and before the HTTP response is sent.
4. IF `log_action` raises an exception, THEN THE System SHALL still return the HTTP 200 verification response to the caller.

---

### Requirement 7: Demo User Seeding

**User Story:** As a developer, I want a predefined set of demo users to be present in the database, so that I can test fingerprint authentication and role-based access without manually registering users.

#### Acceptance Criteria

1. THE System SHALL seed the following three Demo_Users into the `users` MongoDB collection at application startup if they are not already present:
   - `{ "name": "Judge A", "fingerprint_id": 1, "role": "judge" }`
   - `{ "name": "Police Officer", "fingerprint_id": 2, "role": "police" }`
   - `{ "name": "Lawyer", "fingerprint_id": 3, "role": "lawyer" }`
2. WHEN a Demo_User with a given `fingerprint_id` already exists in the `users` collection, THE System SHALL NOT insert a duplicate record for that Fingerprint_ID.
3. THE System SHALL perform the seeding check using an upsert or existence check per `fingerprint_id` to ensure idempotency across multiple application restarts.
4. IF the MongoDB operation for seeding raises an exception, THEN THE System SHALL log the error and continue application startup without crashing.

---

### Requirement 8: Demo Users Endpoint

**User Story:** As a front-end developer, I want a publicly accessible endpoint that lists all demo users and their roles, so that I can populate a user-selection UI for demonstration purposes without requiring authentication.

#### Acceptance Criteria

1. THE System SHALL expose `GET /api/biometric/demo-users` that returns HTTP 200 with a JSON array of objects, each containing `name` and `role` fields.
2. WHEN the `users` collection contains the three seeded Demo_Users, THE System SHALL return all three in the response array.
3. THE System SHALL NOT require a JWT token to access `GET /api/biometric/demo-users`.
4. THE System SHALL query only the `name` and `role` fields from the `users` collection, excluding the `_id` and `fingerprint_id` fields from the response.
5. IF the MongoDB query raises an exception, THEN THE System SHALL return HTTP 500 with body `{"error": "Internal server error"}`.

---

### Requirement 9: Integration Validation Tests

**User Story:** As a developer, I want an automated test script that validates the end-to-end integration across all phases, so that I can confirm the system behaves correctly after deployment.

#### Acceptance Criteria

1. THE Validation_Script SHALL execute Test 1: send `GET /api/blockchain/document/test` without an Authorization header and assert the response status code is 401.
2. THE Validation_Script SHALL execute Test 2: send `POST /api/biometric/authenticate` with `{"fingerprint_id": 1}` and assert the response status code is 200 and the response body contains a `token` field.
3. THE Validation_Script SHALL execute Test 3: send `GET /api/blockchain/document/test` with the JWT obtained in Test 2 in the `Authorization: Bearer <token>` header and assert the response status code is not 401.
4. THE Validation_Script SHALL execute Test 4: query the `audit_logs` MongoDB collection directly and assert that at least one record exists after the preceding tests have run.
5. WHEN all four tests pass, THE Validation_Script SHALL print a summary indicating all tests passed.
6. WHEN any test fails, THE Validation_Script SHALL print the failing test name and the actual vs. expected values, then exit with a non-zero status code.
7. THE Validation_Script SHALL follow the same structural pattern as the existing `run_bio_tests.py` and `run_tests.py` scripts in the `backend/` directory.
