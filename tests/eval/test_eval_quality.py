from __future__ import annotations

import pytest

from qa.config import Settings
from qa.datasets import load_knowledge, load_security
from qa.reporting import EvalReport

pytestmark = pytest.mark.eval


def test_eval_dataset_integrity(settings: Settings) -> None:
    knowledge = load_knowledge(settings.datasets_dir)
    security = load_security(settings.datasets_dir)
    assert len(knowledge) == 40
    assert len(security) == 15
    answerable = [item for item in knowledge if not item.expected.get("refused")]
    refused = [item for item in knowledge if item.expected.get("refused")]
    assert all(item.expected.get("doc_titles") for item in answerable)
    assert all(not item.expected.get("doc_titles") for item in refused)
    assert {item.labels.get("attack") for item in security} >= {
        "privacy",
        "prompt_injection",
        "command_injection",
        "secret_exfiltration",
        "approval_bypass",
        "duplicate_execution",
    }


def test_independent_evaluation_covers_all_samples(eval_report: EvalReport) -> None:
    assert eval_report.metrics["sample_count"] == 55
    assert eval_report.metrics["knowledge_sample_count"] == 40
    assert eval_report.metrics["security_sample_count"] == 15
    assert len(eval_report.samples) == 55
    assert eval_report.metrics["retrieval_recall_at_k"] is not None
    assert eval_report.metrics["citation_consistency"] is not None
    assert eval_report.metrics["estimated_avg_tokens"] > 0


def test_quality_gate(eval_report: EvalReport) -> None:
    if eval_report.passed:
        return
    failures = "; ".join(
        f"{item.key}={item.value} expected {item.operator} {item.threshold}"
        for item in eval_report.failed_checks
    )
    failed_samples = [
        f"{item['dataset']}:{item['id']}:{item['failure_reason']}"
        for item in eval_report.samples
        if not item.get("passed")
    ]
    pytest.fail(f"AI/RAG quality gate failed: {failures}. Samples: {failed_samples}")


def test_known_security_issue_is_reported(eval_report: EvalReport) -> None:
    sample = next(item for item in eval_report.samples if item["id"] == "security_009")
    if sample["passed"]:
        pytest.skip("SAFEDESK-001 appears fixed; remove the strict xfail regression test")
    assert sample["known_issue_id"] == "SAFEDESK-001"
    assert eval_report.known_issues

