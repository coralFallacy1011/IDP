"""Property-based and unit tests for the biometric authentication feature.

Covers all 12 correctness properties from the design document plus
6 targeted unit/example tests.

Run with:
    pytest backend/tests/test_biometric_auth.py -v
"""

from __future__ import annotations

import sys
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, call
import uuid

import jwt as pyjwt
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from flask import Flask

# Ensure backend/ is on sys.path
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


# ---------------------------------------------------------------------------
# Helpers: build a minimal Flask test app with mocked MongoDB
# ---------------------------------------------------------------------------

def _make_app(users_store: dict | None = None):
    """Return a Flask test app with biometric blueprint + auth middleware.

    *users_store* is a dict keyed by fingerprint_id used to back the mock
    MongoDB collection so tests are fully in-memory.
    """
    if users_store is None:
        users_store = {}

    # Build mock collection
    mock_collection = MagicMock()

    def _insert_one(doc):
        fid = doc["fingerprint_id"]
        if fid in users_store:
            err = MagicMock()
            err.code = 11000
            raise Exception("duplicate key error 11000")
        users_store[fid] = {k: v for k, v in doc.items() if k != "_id"}
        return MagicMock(inserted_id="fake_id")

    def _find_one(query, projection=None):
        fid = query.get("fingerprint_id")
        if fid is None:
            return None
        doc = users_store.get(fid)
        if doc is None:
            return None
        return {k: v for k, v in doc.items()}

    mock_collection.insert_one.side_effect = _insert_one
    mock_collection.find_one.side_effect = _find_one
    mock_collection.create_index = MagicMock(return_value="index")

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)

    app = Flask(__name__)
    app.config["TESTING"] = True

    import sys
    import importlib

    # Patch _users inside the module for the lifetime of the app
    import services.biometric_service as svc
    svc._users = mock_collection

    # Force reload route and middleware if already imported to ensure they use mock
    if "routes.biometric" in sys.modules:
        importlib.reload(sys.modules["routes.biometric"])
    if "middleware.auth" in sys.modules:
        importlib.reload(sys.modules["middleware.auth"])

    from routes.biometric import biometric_bp
    from middleware.auth import init_auth

    # Re-create blueprint registration (avoid duplicate registration)
    app2 = Flask(__name__)
    app2.config["TESTING"] = True
    app2.register_blueprint(biometric_bp, url_prefix="/api/biometric")
    init_auth(app2)

    return app2, mock_collection, users_store


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def store():
    return {}


@pytest.fixture
def app_ctx(store):
    application, col, s = _make_app(store)
    with application.test_client() as client:
        yield client, col, s


# ---------------------------------------------------------------------------
# Property 1: Registration stores correct document schema
# Feature: biometric-authentication, Property 1
# Validates: Requirements 2.1, 2.5
# ---------------------------------------------------------------------------

@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"))),
    fingerprint_id=st.integers(min_value=1, max_value=500),
    role=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("Lu", "Ll"))),
)
def test_property1_registration_schema(name, fingerprint_id, role):
    """Property 1: Registration stores correct document schema."""
    store = {}
    _, col, s = _make_app(store)

    import services.biometric_service as svc
    name = name.strip()
    role = role.strip()
    if not name or not role:
        return  # skip degenerate cases

    try:
        user = svc.register_user(name=name, fingerprint_id=fingerprint_id, role=role)
    except ValueError:
        return  # duplicate from hypothesis, skip

    assert set(user.keys()) == {"user_id", "name", "fingerprint_id", "role"}
    assert user["name"] == name
    assert user["fingerprint_id"] == fingerprint_id
    assert user["role"] == role
    assert isinstance(user["user_id"], str) and len(user["user_id"]) > 0


# ---------------------------------------------------------------------------
# Property 2: Registration generates unique user IDs
# Feature: biometric-authentication, Property 2
# Validates: Requirements 2.4
# ---------------------------------------------------------------------------

@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(fids=st.lists(st.integers(min_value=1, max_value=10000), min_size=2, max_size=10, unique=True))
def test_property2_unique_user_ids(fids):
    """Property 2: Registration generates unique user IDs."""
    store = {}
    _, col, s = _make_app(store)

    import services.biometric_service as svc
    user_ids = []
    for fid in fids:
        user = svc.register_user(name="Test User", fingerprint_id=fid, role="clerk")
        user_ids.append(user["user_id"])

    assert len(user_ids) == len(set(user_ids)), "Duplicate user_ids detected"


# ---------------------------------------------------------------------------
# Property 3: Duplicate fingerprint_id → 409
# Feature: biometric-authentication, Property 3
# Validates: Requirements 2.3
# ---------------------------------------------------------------------------

@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(fingerprint_id=st.integers(min_value=1, max_value=1000))
def test_property3_duplicate_fingerprint_409(fingerprint_id):
    """Property 3: Duplicate fingerprint_id is rejected with 409."""
    store = {}
    app, col, s = _make_app(store)

    with app.test_client() as client:
        payload = {"name": "Judge A", "fingerprint_id": fingerprint_id, "role": "judge"}
        r1 = client.post("/api/biometric/register", json=payload)
        assert r1.status_code == 201

        r2 = client.post("/api/biometric/register", json=payload)
        assert r2.status_code == 409


# ---------------------------------------------------------------------------
# Property 4: Missing required fields → 400
# Feature: biometric-authentication, Property 4
# Validates: Requirements 2.2
# ---------------------------------------------------------------------------

ALL_FIELDS = ["name", "fingerprint_id", "role"]

@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    missing=st.frozensets(
        st.sampled_from(ALL_FIELDS), min_size=1, max_size=3
    )
)
def test_property4_missing_fields_400(missing):
    """Property 4: Missing required registration fields return 400."""
    store = {}
    app, col, s = _make_app(store)

    full = {"name": "Alice", "fingerprint_id": 1, "role": "clerk"}
    payload = {k: v for k, v in full.items() if k not in missing}

    with app.test_client() as client:
        r = client.post("/api/biometric/register", json=payload)
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Property 5: Authentication round-trip preserves claims and respects expiry
# Feature: biometric-authentication, Property 5
# Validates: Requirements 3.1, 3.2, 3.3, 3.4
# ---------------------------------------------------------------------------

@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    name=st.text(min_size=1, max_size=40, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Zs"))),
    role=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll"))),
    fingerprint_id=st.integers(min_value=1, max_value=5000),
)
def test_property5_authenticate_roundtrip(name, role, fingerprint_id):
    """Property 5: Authentication round-trip preserves claims and respects expiry."""
    name = name.strip()
    role = role.strip()
    if not name or not role:
        return

    store = {}
    app, col, s = _make_app(store)

    with app.test_client() as client:
        reg = client.post("/api/biometric/register", json={
            "name": name, "fingerprint_id": fingerprint_id, "role": role
        })
        assert reg.status_code == 201
        user_id = reg.get_json()["user_id"]

        auth = client.post("/api/biometric/authenticate", json={"fingerprint_id": fingerprint_id})
        assert auth.status_code == 200

        body = auth.get_json()
        assert "token" in body
        assert body["name"] == name
        assert body["role"] == role

        import services.biometric_service as svc
        claims = svc.verify_token(body["token"])
        assert claims["user_id"] == user_id
        assert claims["name"] == name
        assert claims["role"] == role

        # exp should be ~1 hour from now (±5 seconds tolerance)
        exp = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        delta = exp - now
        assert timedelta(seconds=3595) <= delta <= timedelta(seconds=3605)


# ---------------------------------------------------------------------------
# Property 6: Unregistered fingerprint → 404
# Feature: biometric-authentication, Property 6
# Validates: Requirements 3.5
# ---------------------------------------------------------------------------

@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(fingerprint_id=st.integers(min_value=9000, max_value=99999))
def test_property6_unregistered_fingerprint_404(fingerprint_id):
    """Property 6: Authentication returns 404 for unregistered fingerprint IDs."""
    store = {}
    app, col, s = _make_app(store)

    with app.test_client() as client:
        r = client.post("/api/biometric/authenticate", json={"fingerprint_id": fingerprint_id})
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Property 7: JWT generate/verify round-trip preserves all claims
# Feature: biometric-authentication, Property 7
# Validates: Requirements 4.2, 4.5
# ---------------------------------------------------------------------------

@settings(max_examples=25)
@given(
    user_id=st.text(min_size=1, max_size=40),
    name=st.text(min_size=1, max_size=40),
    role=st.text(min_size=1, max_size=20),
)
def test_property7_jwt_roundtrip(user_id, name, role):
    """Property 7: JWT generate/verify round-trip preserves all claims."""
    import services.biometric_service as svc

    token = svc.generate_access_token(user_id=user_id, name=name, role=role)
    claims = svc.verify_token(token)

    assert claims["user_id"] == user_id
    assert claims["name"] == name
    assert claims["role"] == role

    exp = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
    assert exp > datetime.now(tz=timezone.utc), "Token should not be expired"


# ---------------------------------------------------------------------------
# Property 8: Tokens signed with wrong key are rejected
# Feature: biometric-authentication, Property 8
# Validates: Requirements 4.4
# ---------------------------------------------------------------------------

@settings(max_examples=25)
@given(
    user_id=st.text(min_size=1, max_size=40),
    name=st.text(min_size=1, max_size=40),
    role=st.text(min_size=1, max_size=20),
    wrong_key=st.text(min_size=1, max_size=40),
)
def test_property8_wrong_key_rejected(user_id, name, role, wrong_key):
    """Property 8: Tokens signed with wrong key are rejected."""
    import services.biometric_service as svc

    # Only meaningful if wrong_key differs from actual secret
    if wrong_key == svc.JWT_SECRET:
        return

    bad_token = pyjwt.encode(
        {"user_id": user_id, "name": name, "role": role,
         "exp": datetime.now(tz=timezone.utc) + timedelta(hours=1)},
        wrong_key,
        algorithm="HS256",
    )
    with pytest.raises(pyjwt.InvalidTokenError):
        svc.verify_token(bad_token)


# ---------------------------------------------------------------------------
# Property 9: Protected routes reject all requests without valid JWT
# Feature: biometric-authentication, Property 9
# Validates: Requirements 5.2, 5.4
# ---------------------------------------------------------------------------

PROTECTED_PATHS = ["/api/blockchain/", "/api/documents"]

@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(path=st.sampled_from(PROTECTED_PATHS))
def test_property9_protected_rejects_no_jwt(path):
    """Property 9: Protected routes reject all requests without valid JWT."""
    store = {}
    app, col, s = _make_app(store)

    with app.test_client() as client:
        # No Authorization header
        r = client.get(path)
        assert r.status_code == 401

        # Expired token
        import services.biometric_service as svc
        expired_token = pyjwt.encode(
            {"user_id": "u1", "name": "x", "role": "y",
             "exp": datetime.now(tz=timezone.utc) - timedelta(hours=2)},
            svc.JWT_SECRET,
            algorithm="HS256",
        )
        r2 = client.get(path, headers={"Authorization": f"Bearer {expired_token}"})
        assert r2.status_code == 401


# ---------------------------------------------------------------------------
# Property 10: Protected routes pass requests with valid JWT
# Feature: biometric-authentication, Property 10
# Validates: Requirements 5.3, 5.6
# ---------------------------------------------------------------------------

@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(path=st.sampled_from(PROTECTED_PATHS))
def test_property10_protected_passes_valid_jwt(path):
    """Property 10: Protected routes pass requests with valid JWT."""
    store = {}
    app, col, s = _make_app(store)

    # Add a dummy route so we can observe the middleware allows it through
    @app.route("/api/blockchain/")
    def _bc():
        return "ok", 200

    @app.route("/api/documents")
    def _docs():
        return "ok", 200

    with app.test_client() as client:
        import services.biometric_service as svc
        token = svc.generate_access_token("uid1", "Alice", "judge")
        r = client.get(path, headers={"Authorization": f"Bearer {token}"})
        # Middleware must NOT return 401
        assert r.status_code != 401


# ---------------------------------------------------------------------------
# Property 11: Unprotected routes are never blocked by auth middleware
# Feature: biometric-authentication, Property 11
# Validates: Requirements 5.5, 7.2
# ---------------------------------------------------------------------------

UNPROTECTED_PATHS = ["/api/ocr/upload", "/api/ai/classify", "/api/biometric/register"]

@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(path=st.sampled_from(UNPROTECTED_PATHS))
def test_property11_unprotected_not_blocked(path):
    """Property 11: Unprotected routes are never blocked by auth middleware."""
    store = {}
    app, col, s = _make_app(store)

    with app.test_client() as client:
        # No Authorization header — middleware must NOT return 401
        r = client.get(path)
        assert r.status_code != 401


# ---------------------------------------------------------------------------
# Property 12: Profile endpoint returns JWT claims without DB lookup
# Feature: biometric-authentication, Property 12
# Validates: Requirements 6.1, 6.3
# ---------------------------------------------------------------------------

@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    user_id=st.text(min_size=1, max_size=40),
    name=st.text(min_size=1, max_size=40),
    role=st.text(min_size=1, max_size=20),
)
def test_property12_profile_from_claims_no_db(user_id, name, role):
    """Property 12: Profile endpoint returns JWT claims without DB lookup."""
    store = {}
    app, col, s = _make_app(store)

    with app.test_client() as client:
        import services.biometric_service as svc
        token = svc.generate_access_token(user_id=user_id, name=name, role=role)

        # Reset call count to verify no DB lookup happens
        col.find_one.reset_mock()

        r = client.get("/api/biometric/profile",
                       headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200

        body = r.get_json()
        assert body["user_id"] == user_id
        assert body["name"] == name
        assert body["role"] == role

        # No DB lookup should have occurred
        col.find_one.assert_not_called()


# ===========================================================================
# Unit / Example Tests
# ===========================================================================

def test_unit_register_returns_201_with_user_id():
    """Successful registration returns 201 and a user_id."""
    store = {}
    app, col, s = _make_app(store)
    with app.test_client() as client:
        r = client.post("/api/biometric/register",
                        json={"name": "Judge A", "fingerprint_id": 1, "role": "judge"})
        assert r.status_code == 201
        body = r.get_json()
        assert "user_id" in body
        assert len(body["user_id"]) > 0


def test_unit_authenticate_missing_fingerprint_id_returns_400():
    """Missing fingerprint_id in authenticate returns 400."""
    store = {}
    app, col, s = _make_app(store)
    with app.test_client() as client:
        r = client.post("/api/biometric/authenticate", json={})
        assert r.status_code == 400


def test_unit_profile_returns_401_without_header():
    """GET /profile without Authorization header returns 401."""
    store = {}
    app, col, s = _make_app(store)
    with app.test_client() as client:
        r = client.get("/api/biometric/profile")
        assert r.status_code == 401


def test_unit_verify_token_expired_raises():
    """verify_token raises ExpiredSignatureError for expired tokens."""
    import services.biometric_service as svc

    expired = pyjwt.encode(
        {"user_id": "u1", "name": "x", "role": "y",
         "exp": datetime.now(tz=timezone.utc) - timedelta(hours=2)},
        svc.JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(pyjwt.ExpiredSignatureError):
        svc.verify_token(expired)


def test_unit_biometric_blueprint_registered():
    """Biometric blueprint is registered at /api/biometric."""
    store = {}
    app, col, s = _make_app(store)
    rules = [str(r) for r in app.url_map.iter_rules()]
    biometric_rules = [r for r in rules if "/api/biometric" in r]
    assert len(biometric_rules) >= 3  # register, authenticate, profile


def test_unit_full_auth_flow():
    """End-to-end: register → authenticate → get JWT → access profile."""
    store = {}
    app, col, s = _make_app(store)
    with app.test_client() as client:
        # Register
        reg = client.post("/api/biometric/register",
                          json={"name": "Judge A", "fingerprint_id": 1, "role": "judge"})
        assert reg.status_code == 201

        # Authenticate
        auth = client.post("/api/biometric/authenticate", json={"fingerprint_id": 1})
        assert auth.status_code == 200
        auth_data = auth.get_json()
        assert auth_data["fingerprint_id"] == 1
        token = auth_data["token"]

        # Profile
        profile = client.get("/api/biometric/profile",
                             headers={"Authorization": f"Bearer {token}"})
        assert profile.status_code == 200
        body = profile.get_json()
        assert body["name"] == "Judge A"
        assert body["role"] == "judge"

