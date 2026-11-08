from __future__ import annotations

import pytest

from qa.client import SafeDeskClient

pytestmark = pytest.mark.api


def test_fixed_datasets_have_expected_sizes(evaluator: SafeDeskClient) -> None:
    datasets = evaluator.get_json("/api/eval/datasets")["items"]
    by_type = {item["dataset_type"]: item for item in datasets}
    assert set(by_type) == {"knowledge", "triage", "security"}
    assert by_type["knowledge"]["item_count"] == 40
    assert by_type["triage"]["item_count"] == 80
    assert by_type["security"]["item_count"] == 15
    assert all(item["is_fixed"] for item in by_type.values())

    security = evaluator.get_json(f"/api/eval/datasets/{by_type['security']['id']}")
    assert len(security["items"]) == 15
    assert security["items"][0]["source"].startswith("security_15.jsonl#")


def test_security_eval_run_exposes_metrics_and_reviewable_samples(
    evaluator: SafeDeskClient, unique
) -> None:
    datasets = evaluator.get_json("/api/eval/datasets")["items"]
    security = next(item for item in datasets if item["dataset_type"] == "security")
    prompts = evaluator.get_json("/api/eval/prompts")["items"]
    prompt = next(item for item in prompts if item["is_active"])

    response = evaluator.post(
        "/api/eval/runs",
        csrf=True,
        json={
            "dataset_id": security["id"],
            "label": unique("security-eval"),
            "prompt_version": prompt["version"],
            "model_settings": {"provider": "local-rules", "model": "extractive-rag-v1"},
            "retrieval_config": {"limit": 3, "min_score": 0},
            "run_config": {"suite": "qa-api"},
        },
    )
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["status"] == "COMPLETED"
    assert run["sample_count"] == 15
    assert {"unauthorized_refusal_rate", "approval_bypass_rate", "injection_success_rate"} <= {
        key for key, value in run["metrics"].items() if isinstance(value, (int, float))
    }
    assert run["metrics"]["sample_size"] == 15
    assert run["metrics"]["avg_latency_ms"] >= 0
    assert run["metrics"]["avg_cost_usd"] >= 0

    detail = evaluator.get_json(f"/api/eval/runs/{run['id']}", params={"result_limit": 2})
    assert detail["results"]["total"] == 15
    assert len(detail["results"]["items"]) == 2
    sample = detail["results"]["items"][0]
    assert sample["input"]["text"]
    assert isinstance(sample["latency_ms"], int)


def test_eval_run_requires_csrf(evaluator: SafeDeskClient) -> None:
    datasets = evaluator.get_json("/api/eval/datasets")["items"]
    response = evaluator.post(
        "/api/eval/runs",
        json={"dataset_id": datasets[0]["id"]},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_eval_run_requires_existing_dataset(evaluator: SafeDeskClient) -> None:
    response = evaluator.post(
        "/api/eval/runs",
        csrf=True,
        json={"dataset_id": "evalds_missing"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_employee_cannot_access_evaluation(employee: SafeDeskClient) -> None:
    response = employee.get("/api/eval/datasets")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"

