from __future__ import annotations

import pytest

from qa.client import SafeDeskClient
from qa.config import Settings

pytestmark = pytest.mark.api


def test_health_and_security_headers(anonymous: SafeDeskClient) -> None:
    response = anonymous.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "version": "0.1.0",
        "app_env": "development",
    }
    assert response.headers["X-Request-ID"].startswith("req_")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_unauthenticated_error_is_safe_and_correlated(anonymous: SafeDeskClient) -> None:
    request_id = "qa-correlation-0001"
    response = anonymous.get("/api/me", headers={"X-Request-ID": request_id})
    assert response.status_code == 401
    body = response.json()["error"]
    assert body["code"] == "UNAUTHENTICATED"
    assert body["request_id"] == request_id
    assert response.headers["X-Request-ID"] == request_id
    assert "traceback" not in response.text.lower()


def test_login_sets_session_and_csrf_cookies(
    anonymous: SafeDeskClient, settings: Settings
) -> None:
    response = anonymous.login(settings.accounts.employee, settings.password)
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["role"] == "employee"
    assert body["permissions"]["case:create"] is True
    assert body["csrf_token"]
    assert anonymous.csrf_token

    cookie_headers = response.headers.get_list("set-cookie")
    session_cookie = next(item for item in cookie_headers if item.startswith("sd_session="))
    csrf_cookie = next(item for item in cookie_headers if item.startswith("sd_csrf="))
    assert "HttpOnly" in session_cookie
    assert "SameSite=lax" in session_cookie
    assert "HttpOnly" not in csrf_cookie

    me = anonymous.get("/api/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == settings.accounts.employee


def test_bad_password_and_invalid_payload(anonymous: SafeDeskClient, settings: Settings) -> None:
    bad = anonymous.login(settings.accounts.employee, "wrong-password")
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "UNAUTHENTICATED"

    invalid = anonymous.post("/api/auth/login", json={"email": "not-an-email"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"


def test_state_change_requires_matching_csrf_token(
    new_client, unique
) -> None:
    client = new_client("lin.xiao@example.test")
    title = unique("csrf")
    missing = client.post("/api/cases", json={"title": title})
    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "FORBIDDEN"

    mismatched = client.post(
        "/api/cases",
        json={"title": title},
        headers={"X-CSRF-Token": "not-the-session-token"},
    )
    assert mismatched.status_code == 403
    assert mismatched.json()["error"]["code"] == "FORBIDDEN"

    accepted = client.post("/api/cases", csrf=True, json={"title": title})
    assert accepted.status_code == 201, accepted.text


def test_logout_revokes_session_and_clears_cookies(new_client, settings: Settings) -> None:
    client = new_client(settings.accounts.employee)
    response = client.post("/api/auth/logout", csrf=True)
    assert response.status_code == 204
    assert client.get("/api/me").status_code == 401
    cleared = " ".join(response.headers.get_list("set-cookie"))
    assert "sd_session=" in cleared
    assert "Max-Age=0" in cleared or "expires=Thu, 01 Jan 1970" in cleared.lower()


def test_demo_switch_requires_csrf_and_changes_role(new_client, settings: Settings) -> None:
    client = new_client(settings.accounts.employee)
    denied = client.post("/api/demo/switch-user", json={"role": "approver"})
    assert denied.status_code == 403

    switched = client.post(
        "/api/demo/switch-user",
        csrf=True,
        json={"role": "approver"},
    )
    assert switched.status_code == 200, switched.text
    assert switched.json()["user"]["role"] == "approver"
    assert client.get("/api/me").json()["user"]["role"] == "approver"

