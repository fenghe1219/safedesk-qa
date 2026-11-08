from __future__ import annotations

import pytest

from qa.client import SafeDeskClient

pytestmark = pytest.mark.api

EXPECTED_PERMISSIONS = {
    "employee": {
        "case:create",
        "case:read",
        "ticket:view",
    },
    "support": {
        "case:create",
        "case:read",
        "case:read_all",
        "ticket:view",
        "ticket:manage",
        "dashboard:view",
    },
    "approver": {
        "case:create",
        "case:read",
        "case:read_all",
        "ticket:view",
        "approval:view",
        "approval:decide",
        "dashboard:view",
    },
    "admin": {
        "case:create",
        "case:read",
        "case:read_all",
        "ticket:view",
        "ticket:manage",
        "approval:view",
        "knowledge:view",
        "knowledge:manage",
        "eval:manage",
        "audit:view",
        "dashboard:view",
        "settings:manage",
    },
    "evaluator": {"knowledge:view", "eval:manage"},
    "auditor": {"case:read", "case:read_all", "audit:view", "dashboard:view"},
}


@pytest.mark.parametrize("role", sorted(EXPECTED_PERMISSIONS))
def test_permission_matrix_matches_role_contract(
    role: str, role_clients: dict[str, SafeDeskClient]
) -> None:
    me = role_clients[role].get_json("/api/me")
    assert me["user"]["role"] == role
    actual = {key for key, allowed in me["permissions"].items() if allowed}
    assert actual == EXPECTED_PERMISSIONS[role]


@pytest.mark.parametrize(
    ("role", "path", "expected_status"),
    [
        ("employee", "/api/knowledge/documents", 403),
        ("employee", "/api/audit/events", 403),
        ("employee", "/api/eval/datasets", 403),
        ("employee", "/api/admin/settings", 403),
        ("employee", "/api/approvals", 403),
        ("support", "/api/approvals", 403),
        ("support", "/api/audit/events", 403),
        ("approver", "/api/knowledge/documents", 403),
        ("approver", "/api/eval/datasets", 403),
        ("approver", "/api/admin/settings", 403),
        ("evaluator", "/api/cases", 403),
        ("evaluator", "/api/tickets", 403),
        ("evaluator", "/api/audit/events", 403),
        ("auditor", "/api/tickets", 403),
        ("auditor", "/api/eval/datasets", 403),
        ("auditor", "/api/approvals", 403),
        ("employee", "/api/cases", 200),
        ("support", "/api/cases", 200),
        ("approver", "/api/approvals", 200),
        ("admin", "/api/admin/settings", 200),
        ("admin", "/api/audit/events", 200),
        ("evaluator", "/api/eval/datasets", 200),
        ("auditor", "/api/audit/events", 200),
    ],
)
def test_endpoint_authorization_matrix(
    role: str,
    path: str,
    expected_status: int,
    role_clients: dict[str, SafeDeskClient],
) -> None:
    response = role_clients[role].get(path)
    assert response.status_code == expected_status, response.text
    if expected_status == 403:
        assert response.json()["error"]["code"] == "FORBIDDEN"


def test_admin_can_view_but_cannot_decide_approval(admin: SafeDeskClient) -> None:
    response = admin.post(
        "/api/approvals/approval_does_not_exist/approve",
        csrf=True,
        json={
            "expected_args_hash": "x" * 16,
            "approval_version": 1,
            "reason": "QA RBAC probe",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_evaluator_cannot_create_case(evaluator: SafeDeskClient, unique) -> None:
    response = evaluator.post(
        "/api/cases",
        csrf=True,
        json={"title": unique("evaluator-case")},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"

