from __future__ import annotations

import pytest

from qa.client import SafeDeskClient

pytestmark = pytest.mark.api


def _request_vpn_action(client: SafeDeskClient, unique) -> tuple[dict, dict]:
    case = client.create_case(unique("approval"))
    stream = client.send_message(
        case["id"],
        "我的 VPN 证书过期了，帮我重置证书",
    )
    action = stream.first("action")
    assert action is not None, stream.text[-1000:]
    assert action["action"]["tool_name"] == "reset_vpn_certificate"
    assert action["approval"]["status"] == "PENDING"
    assert action["case"]["status"] == "AWAITING_APPROVAL"
    assert action.get("execution") is None
    return case, action


def _approval_payload(action: dict) -> dict:
    return {
        "expected_args_hash": action["action"]["args_hash"],
        "approval_version": action["approval"]["version"],
        "reason": "QA：已核对影响范围与验证方案。",
    }


def test_action_proposal_creates_checkpoints_and_pending_approval(
    employee: SafeDeskClient,
    auditor: SafeDeskClient,
    unique,
) -> None:
    case, action = _request_vpn_action(employee, unique)
    detail = employee.get(f"/api/cases/{case['id']}/action")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "AWAITING_APPROVAL"
    assert body["approval"]["status"] == "PENDING"
    assert body["permissions"]["can_decide"] is False
    assert body["evidence_ids"]
    assert body["verification_plan"]
    assert body["rollback_plan"]

    checkpoints = employee.get_json(f"/api/cases/{case['id']}/checkpoints")["items"]
    nodes = {item["node"] for item in checkpoints}
    assert {"propose_action", "await_approval"} <= nodes

    events = auditor.audit_events(case_id=case["id"])["items"]
    event_types = {item["event_type"] for item in events}
    assert {"tool.read_executed", "action.proposed", "approval.requested"} <= event_types


def test_approval_executes_once_and_repeat_is_idempotent(
    employee: SafeDeskClient,
    approver: SafeDeskClient,
    auditor: SafeDeskClient,
    unique,
) -> None:
    case, action = _request_vpn_action(employee, unique)
    payload = _approval_payload(action)

    approved = approver.post(
        f"/api/approvals/{action['approval']['id']}/approve",
        csrf=True,
        json=payload,
    )
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["case"]["status"] == "RESOLVED"
    assert body["approval"]["status"] == "APPROVED"
    assert body["action"]["status"] == "SUCCEEDED"
    assert body["execution"]["status"] == "SUCCEEDED"
    execution_id = body["execution"]["id"]

    repeated = approver.post(
        f"/api/approvals/{action['approval']['id']}/approve",
        csrf=True,
        json=payload,
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["execution"]["id"] == execution_id
    assert "未重复" in repeated.json()["message"]

    events = auditor.audit_events(case_id=case["id"])["items"]
    executed = [item for item in events if item["event_type"] == "tool.executed"]
    duplicate = [item for item in events if item["event_type"] == "tool.duplicate_blocked"]
    assert len(executed) == 1
    assert duplicate
    assert duplicate[0]["payload"]["execution_id"] == execution_id


def test_hash_mismatch_is_rejected(
    employee: SafeDeskClient, approver: SafeDeskClient, unique
) -> None:
    _, action = _request_vpn_action(employee, unique)
    response = approver.post(
        f"/api/approvals/{action['approval']['id']}/approve",
        csrf=True,
        json={
            "expected_args_hash": "sha256:tampered",
            "approval_version": action["approval"]["version"],
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TYPE_CONFLICT"


def test_requester_cannot_self_approve(approver: SafeDeskClient, unique) -> None:
    _, action = _request_vpn_action(approver, unique)
    response = approver.post(
        f"/api/approvals/{action['approval']['id']}/approve",
        csrf=True,
        json=_approval_payload(action),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SELF_APPROVAL_FORBIDDEN"


def test_kill_switch_blocks_execution_and_is_restored(
    employee: SafeDeskClient,
    approver: SafeDeskClient,
    admin: SafeDeskClient,
    unique,
) -> None:
    _, action = _request_vpn_action(employee, unique)
    original = admin.get_json("/api/admin/kill-switch")
    try:
        enabled = admin.put(
            "/api/admin/kill-switch",
            csrf=True,
            json={"enabled": True, "reason": "QA kill switch drill"},
        )
        assert enabled.status_code == 200, enabled.text
        blocked = approver.post(
            f"/api/approvals/{action['approval']['id']}/approve",
            csrf=True,
            json=_approval_payload(action),
        )
        assert blocked.status_code == 409
        assert blocked.json()["error"]["code"] == "KILL_SWITCH_ENABLED"
    finally:
        restored = admin.put(
            "/api/admin/kill-switch",
            csrf=True,
            json={"enabled": original["enabled"], "reason": original.get("reason")},
        )
        assert restored.status_code == 200, restored.text


def test_disabled_tool_blocks_execution_and_is_restored(
    employee: SafeDeskClient,
    approver: SafeDeskClient,
    admin: SafeDeskClient,
    unique,
) -> None:
    _, action = _request_vpn_action(employee, unique)
    tools = admin.get_json("/api/admin/tools")["items"]
    target = next(item for item in tools if item["name"] == "reset_vpn_certificate")
    try:
        disabled = admin.patch(
            "/api/admin/tools/reset_vpn_certificate",
            csrf=True,
            json={"enabled": False},
        )
        assert disabled.status_code == 200, disabled.text
        blocked = approver.post(
            f"/api/approvals/{action['approval']['id']}/approve",
            csrf=True,
            json=_approval_payload(action),
        )
        assert blocked.status_code == 409
        assert blocked.json()["error"]["code"] == "TOOL_DISABLED"
    finally:
        restored = admin.patch(
            "/api/admin/tools/reset_vpn_certificate",
            csrf=True,
            json={"enabled": target["enabled"], "mock_mode": target["mock_mode"]},
        )
        assert restored.status_code == 200, restored.text


def test_approval_queue_and_material_projection(
    employee: SafeDeskClient,
    approver: SafeDeskClient,
    unique,
) -> None:
    case, action = _request_vpn_action(employee, unique)
    queue = approver.get_json("/api/approvals", params={"status": "PENDING"})["items"]
    item = next(entry for entry in queue if entry["id"] == action["approval"]["id"])
    assert item["case_id"] == case["id"]
    assert item["case_title"] == case["title"]
    assert item["can_decide"] is True

    detail = approver.get_json(f"/api/approvals/{action['approval']['id']}")
    assert detail["approval"]["args_hash"] == action["action"]["args_hash"]
    assert detail["action"]["args_hash"] == action["action"]["args_hash"]
    assert detail["permissions"]["can_decide"] is True
    assert detail["blockers"] == []

