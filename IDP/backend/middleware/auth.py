"""Auth middleware for the Flask application.

Enforces JWT authentication on protected URL prefixes only:
  - /api/blockchain/
  - /api/documents

All other routes are passed through without any auth check.

Usage
-----
    from middleware.auth import init_auth
    init_auth(app)
"""

from __future__ import annotations

from flask import Flask, g, jsonify, request

from services.biometric_service import verify_token

PROTECTED_PREFIXES = ("/api/blockchain/", "/api/documents")


def init_auth(app: Flask) -> None:
    """Register the before_request auth guard on *app*."""

    @app.before_request
    def _auth_guard():
        if not request.path.startswith(PROTECTED_PREFIXES):
            return None  # not a protected route — let it through

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header missing or malformed"}), 401

        token = auth_header[len("Bearer "):]
        try:
            g.current_user = verify_token(token)
        except Exception:
            return jsonify({"error": "Invalid or expired token"}), 401

        return None  # token valid — proceed to route handler
