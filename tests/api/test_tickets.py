from __future__ import annotations

import pytest

from qa.client import SafeDeskClient

pytestmark = pytest.mark.api

TICKET_FIELD_KEYS = (
    "title",
    "description",
    "category",
    "priority",
    "priority_reason",
    "affected_system",
    "environment",
    "error_message",
    "urgency_reason",
    "suggested_assignee_id",
)


def _create_draft(employee: SafeDeskClient, unique) -> tuple[dict, dict]:
    case = employee.create_case(unique("ticket"))
    stream = employee.send_message(
        case["id"],
        "打印机报错 0x0000011b，Windows 11，帮我建个工单",
    )
    draft = stream.first("ticket_draft")
    assert draft is not None
    assert draft["status"] == "DRAFT"
    assert draft["category"] == "hardware"
    assert draft["priority"] == "P2"
    assert draft["missing_fields"] == []
    return case, draft


def _fields(draft: dict) -> dict:
    return {key: draft[key] for key in TICKET_FIELD_KEYS}


def test_employee_draft_is_confirmed_by_support_and_duplicate_is_rejected(
    employee: SafeDeskClient,
    support: SafeDeskClient,
    unique,
) -> None:
    case, draft = _create_draft(employee, unique)

    employee_denied = employee.post(
        "/api/tickets",
        csrf=True,
        json={
            "case_id": case["id"],
            "draft_version": draft["version"],
            "fields": _fields(draft),
        },
    )
    assert employee_denied.status_code == 403

    confirmed = support.post(
        "/api/tickets",
        csrf=True,
        json={
            "case_id": case["id"],
            "draft_version": draft["version"],
            "fields": _fields(draft),
        },
    )
    assert confirmed.status_code == 201, confirmed.text
    body = confirmed.json()
    ticket = body["ticket"]
    assert ticket["status"] == "OPEN"
    assert ticket["case_id"] == case["id"]
    assert ticket["requester_id"] == employee.user["id"]
    assert body["case"]["status"] == "TICKET_OPEN"
    assert body["case"]["ticket_id"] == ticket["id"]

    duplicate = support.post(
        "/api/tickets",
        csrf=True,
        json={
            "case_id": case["id"],
            "draft_version": draft["version"],
            "fields": _fields(draft),
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "INVALID_STATE"

    listed = employee.get_json("/api/tickets", params={"limit": 50})["items"]
    assert ticket["id"] in {item["id"] for item in listed}


def test_ticket_update_uses_optimistic_lock(
    employee: SafeDeskClient,
    support: SafeDeskClient,
    unique,
) -> None:
    case, draft = _create_draft(employee, unique)
    created = support.post(
        "/api/tickets",
        csrf=True,
        json={
            "case_id": case["id"],
            "draft_version": draft["version"],
            "fields": _fields(draft),
        },
    ).json()["ticket"]

    updated = support.patch(
        f"/api/tickets/{created['id']}",
        csrf=True,
        json={
            "version": created["version"],
            "fields": {"priority": "P1", "priority_reason": "多人受影响，需要优先处理。"},
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["priority"] == "P1"

    stale = support.patch(
        f"/api/tickets/{created['id']}",
        csrf=True,
        json={
            "version": created["version"],
            "fields": {"priority": "P4"},
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "TYPE_CONFLICT"


def test_read_only_roles_cannot_write_internal_notes(
    employee: SafeDeskClient,
    approver: SafeDeskClient,
    support: SafeDeskClient,
    unique,
) -> None:
    case, draft = _create_draft(employee, unique)
    ticket = support.post(
        "/api/tickets",
        csrf=True,
        json={
            "case_id": case["id"],
            "draft_version": draft["version"],
            "fields": _fields(draft),
        },
    ).json()["ticket"]

    for client in (employee, approver):
        denied = client.post(
            f"/api/tickets/{ticket['id']}/notes",
            csrf=True,
            json={"content": "QA read-only probe"},
        )
        assert denied.status_code == 403

