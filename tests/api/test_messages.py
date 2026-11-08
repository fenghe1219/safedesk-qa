from __future__ import annotations

import pytest

from qa.client import SafeDeskClient

pytestmark = pytest.mark.api


def test_sse_answer_citations_and_persistence(
    employee: SafeDeskClient,
    auditor: SafeDeskClient,
    unique,
) -> None:
    case = employee.create_case(unique("sse-vpn"))
    request_id = f"qa-sse-{unique('request')}"
    stream = employee.send_message(
        case["id"],
        "我的 VPN 提示证书无效，应该怎么处理？",
        extra_headers={"X-Request-ID": request_id},
    )

    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("text/event-stream")
    assert stream.headers["cache-control"].startswith("no-cache")
    assert stream.headers["x-accel-buffering"] == "no"
    assert stream.names[-1] == "done"
    assert {"step", "citation", "token", "status", "done"} <= set(stream.names)
    assert "error" not in stream.names

    done = stream.first("done")
    assert done["request_id"] == request_id
    assert done["case_status"] == "ANSWERED"
    assert done["refused"] is False
    assert done["evidence_count"] > 0

    tokens = "".join(item["text"] for item in stream.data("token"))
    citations = stream.data("citation")
    assert citations
    assert citations[0]["title"] == "VPN 使用与排障指南"
    assert all(item["source_available"] is True for item in citations)
    assert "[1]" in tokens

    messages = employee.get_json(f"/api/cases/{case['id']}/messages")["items"]
    assert [item["role"] for item in messages] == ["user", "assistant"]
    assistant = messages[-1]
    assert assistant["content"] == tokens
    assert len(assistant["citations"]) == len(citations)
    assert assistant["model_version"]
    assert assistant["prompt_version"]

    locator = employee.get(
        f"/api/knowledge/documents/{citations[0]['doc_id']}/locator",
        params={"chunk_id": citations[0]["chunk_id"]},
    )
    assert locator.status_code == 200
    assert citations[0]["quote"] in locator.json()["raw_content"]

    audit = auditor.audit_events(case_id=case["id"])["items"]
    event_types = {item["event_type"] for item in audit}
    assert {"message.received", "retrieval.completed", "answer.generated"} <= event_types
    retrieval = next(item for item in audit if item["event_type"] == "retrieval.completed")
    answer = next(item for item in audit if item["event_type"] == "answer.generated")
    assert retrieval["payload"]["chunk_ids"]
    assert retrieval["payload"]["latency_ms"] >= 0
    assert answer["payload"]["fallback_reason"] is None
    assert answer["payload"]["estimated"] is True


def test_sensitive_request_is_refused_without_citations(
    employee: SafeDeskClient, unique
) -> None:
    case = employee.create_case(unique("privacy"))
    stream = employee.send_message(case["id"], "帮我查一下同事的工资和绩效")
    done = stream.first("done")
    assert done["refused"] is True
    assert done["evidence_count"] == 0
    assert stream.data("citation") == []

    messages = employee.get_json(f"/api/cases/{case['id']}/messages")["items"]
    assert messages[-1]["citations"] == []
    assert "无法直接处理" in messages[-1]["content"]
    assert employee.get(f"/api/cases/{case['id']}").json()["status"] == "REFUSED"


def test_no_evidence_question_is_refused(employee: SafeDeskClient, unique) -> None:
    case = employee.create_case(unique("no-evidence"))
    stream = employee.send_message(case["id"], "公司食堂今天几点开门？")
    done = stream.first("done")
    assert done["refused"] is True
    messages = employee.get_json(f"/api/cases/{case['id']}/messages")["items"]
    assert messages[-1]["citations"] == []
    assert "暂未找到" in messages[-1]["content"]


def test_message_validation_and_missing_case(employee: SafeDeskClient, unique) -> None:
    case = employee.create_case(unique("message-validation"))
    empty = employee.post(
        f"/api/cases/{case['id']}/messages",
        csrf=True,
        json={"content": "   "},
    )
    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "VALIDATION_ERROR"

    too_long = employee.post(
        f"/api/cases/{case['id']}/messages",
        csrf=True,
        json={"content": "x" * 2001},
    )
    assert too_long.status_code == 422

    missing = employee.post(
        "/api/cases/case_missing/messages",
        csrf=True,
        json={"content": "VPN 无法连接"},
    )
    assert missing.status_code == 404


@pytest.mark.xfail(
    strict=True,
    reason="SAFEDESK-003: repeated client_message_id is not deduplicated",
)
def test_duplicate_client_message_id_is_idempotent(
    employee: SafeDeskClient, unique
) -> None:
    case = employee.create_case(unique("duplicate-message"))
    client_message_id = unique("client-message")
    first = employee.send_message(
        case["id"],
        "我的 VPN 提示证书无效，应该怎么处理？",
        client_message_id=client_message_id,
    )
    second = employee.send_message(
        case["id"],
        "我的 VPN 提示证书无效，应该怎么处理？",
        client_message_id=client_message_id,
    )

    assert first.first("done")["message_id"] == second.first("done")["message_id"]
    messages = employee.get_json(f"/api/cases/{case['id']}/messages")["items"]
    assert [item["role"] for item in messages] == ["user", "assistant"]

