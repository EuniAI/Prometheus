import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from prometheus.app.middlewares.jwt_middleware import JWTMiddleware
from prometheus.exceptions.jwt_exception import JWTException
from prometheus.utils.jwt_utils import JWTUtils


@pytest.fixture
def app():
    """
    Create a FastAPI app with JWTMiddleware installed.
    We mark certain (method, path) pairs as login-required.
    """
    app = FastAPI()

    # Only these routes require login:
    login_required_routes = {
        ("GET", "/protected"),
        ("OPTIONS", "/protected"),  # include options here if you want middleware to check it
        ("GET", "/me"),
    }

    app.add_middleware(JWTMiddleware, login_required_routes=login_required_routes)

    @app.get("/public")
    def public():
        return {"ok": True, "route": "public"}

    @app.get("/protected")
    def protected(request: Request):
        # Return back the user_id the middleware stores on request.state
        return {"ok": True, "route": "protected", "user_id": getattr(request.state, "user_id", None)}

    @app.get("/me")
    def me(request: Request):
        return {"user_id": getattr(request.state, "user_id", None)}

    # Explicit OPTIONS route to ensure 200/204 so we can assert behavior
    @app.options("/protected")
    def options_protected():
        return Response(status_code=204)

    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_non_protected_route_bypasses_auth(client):
    """
    Requests to routes not listed in login_required_routes must bypass JWT check.
    """
    resp = client.get("/public")
    assert resp.status_code == 200
    assert resp.json()["route"] == "public"


def test_missing_authorization_returns_401_on_protected(client):
    """
    Missing Authorization header on a protected endpoint should return 401.
    """
    resp = client.get("/protected")
    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == 401
    assert "Valid JWT Token is missing" in body["message"]


def test_wrong_scheme_returns_401_on_protected(client):
    """
    Wrong Authorization scheme (not Bearer) should return 401 on protected endpoint.
    """
    resp = client.get("/protected", headers={"Authorization": "Token abc.def.ghi"})
    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == 401
    assert "Valid JWT Token is missing" in body["message"]


def test_invalid_token_raises_and_returns_error(client, monkeypatch):
    """
    If JWTUtils.decode_token raises JWTException, middleware should map it to the response.
    """

    def fake_decode(_self, _: str):
        raise JWTException(code=403, message="Invalid or expired token")

    # Patch the method on the class; middleware instantiates JWTUtils() internally
    monkeypatch.setattr(JWTUtils, "decode_token", fake_decode, raising=True)

    resp = client.get("/protected", headers={"Authorization": "Bearer bad.token"})
    assert resp.status_code == 403
    body = resp.json()
    assert body["code"] == 403
    assert body["message"] == "Invalid or expired token"


def test_valid_token_sets_user_id_and_passes(client, monkeypatch):
    """
    With a valid token, request should pass and user_id should be present on request.state.
    """

    def fake_decode(_self, _: str):
        # Return payload with user_id as middleware expects
        return {"user_id": 123}

    monkeypatch.setattr(JWTUtils, "decode_token", fake_decode, raising=True)

    resp = client.get("/protected", headers={"Authorization": "Bearer good.token"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["user_id"] == 123


def test_options_request_passes_through(client, monkeypatch):
    """
    OPTIONS preflight should be allowed through without requiring a valid token.
    The middleware explicitly bypasses OPTIONS before checking Authorization.
    """
    # Even if decode_token would fail, OPTIONS should not trigger it.
    def boom(_self, _: str):
        raise AssertionError("decode_token should not be called for OPTIONS")

    monkeypatch.setattr(JWTUtils, "decode_token", boom, raising=True)

    resp = client.options("/protected")
    # Our route returns 204; any 2xx is acceptable depending on your route
    assert resp.status_code in (200, 204)
