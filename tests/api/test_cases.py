from __future__ import annotations

import pytest

from qa.client import SafeDeskClient

pytestmark = pytest.mark.api


def test_create_read_list_and_timeline(employee: SafeDeskClient, unique) -> None:
    title = unique("case-create")
    created = employee.create_case(title)
    assert created["title"] == title
    assert created["status"] == "NEW"
    assert created["status_label"] == "新问题"
    assert created["phase"] == "intake"
    assert created["requester_id"] == employee.user["id"]

    detail = employee.get(f"/api/cases/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == created["id"]

    listed = employee.get_json("/api/cases", params={"limit": 50})["items"]
    assert created["id"] in {item["id"] for item in listed}

    timeline = employee.get_json(f"/api/cases/{created['id']}/timeline")["items"]
    assert timeline[0]["event_type"] == "case.created"
    assert timeline[0]["actor_id"] == employee.user["id"]


def test_title_is_trimmed_and_validated(employee: SafeDeskClient, unique) -> None:
    title = f"  {unique('trim')}  "
    created = employee.create_case(title)
    assert created["title"] == title.strip()

    blank = employee.post("/api/cases", csrf=True, json={"title": "   "})
    assert blank.status_code == 422
    assert blank.json()["error"]["code"] == "VALIDATION_ERROR"

    too_long = employee.post("/api/cases", csrf=True, json={"title": "x" * 81})
    assert too_long.status_code == 422
    assert too_long.json()["error"]["code"] == "VALIDATION_ERROR"


def test_missing_case_and_invalid_list_limit(employee: SafeDeskClient) -> None:
    missing = employee.get("/api/cases/case_does_not_exist")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"

    invalid = employee.get("/api/cases", params={"limit": 0})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"


def test_case_scope_is_enforced_between_employees(
    employee: SafeDeskClient,
    second_employee: SafeDeskClient,
    unique,
) -> None:
    created = employee.create_case(unique("isolation"))
    denied = second_employee.get(f"/api/cases/{created['id']}")
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "NOT_FOUND"

    admin = second_employee.get("/api/admin/users")
    assert admin.status_code == 403


@pytest.mark.parametrize("role", ["support", "approver", "admin", "auditor"])
def test_read_all_roles_can_read_case(
    role: str,
    role_clients: dict[str, SafeDeskClient],
    employee: SafeDeskClient,
    unique,
) -> None:
    created = employee.create_case(unique(f"read-{role}"))
    response = role_clients[role].get(f"/api/cases/{created['id']}")
    assert response.status_code == 200, response.text
    assert response.json()["id"] == created["id"]


def test_request_id_can_be_supplied_and_is_echoed(employee: SafeDeskClient, unique) -> None:
    request_id = f"qa-case-{unique('req')}"
    response = employee.post(
        "/api/cases",
        csrf=True,
        json={"title": unique("request-id")},
        headers={"X-Request-ID": request_id},
    )
    assert response.status_code == 201
    assert response.headers["X-Request-ID"] == request_id

