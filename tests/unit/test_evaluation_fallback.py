from __future__ import annotations

from types import SimpleNamespace

from qa.evaluation import _fallback, _title


def test_evaluation_case_title_does_not_add_retrieval_tokens() -> None:
    title = _title("knowledge_001")
    assert title
    assert not any(character.isalnum() for character in title)


def test_fallback_is_detected_from_answer_audit_payload() -> None:
    probe = SimpleNamespace(answer={"fallback_reason": "LLM_TIMEOUT"}, audit=[])
    assert _fallback(probe) is True


def test_fallback_is_detected_from_agent_event() -> None:
    probe = SimpleNamespace(
        answer={},
        audit=[{"event_type": "agent.fallback", "payload": {"reason": "INVALID_JSON"}}],
    )
    assert _fallback(probe) is True


def test_primary_answer_is_not_marked_as_fallback() -> None:
    probe = SimpleNamespace(answer={"fallback_reason": None}, audit=[])
    assert _fallback(probe) is False
