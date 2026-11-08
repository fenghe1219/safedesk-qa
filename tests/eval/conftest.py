from __future__ import annotations

import pytest

from qa.client import SafeDeskClient
from qa.config import Settings
from qa.evaluation import run_evaluation
from qa.reporting import EvalReport, write_report


@pytest.fixture(scope="session")
def eval_report(
    settings: Settings,
    employee: SafeDeskClient,
    evaluator: SafeDeskClient,
    auditor: SafeDeskClient,
) -> EvalReport:
    def progress(message: str) -> None:
        print(f"[eval] {message}", flush=True)

    report = run_evaluation(
        settings=settings,
        employee=employee,
        evaluator=evaluator,
        auditor=auditor,
        progress=progress,
    )
    json_path, md_path = write_report(report, settings.reports_dir / "eval")
    print(f"[eval] JSON report: {json_path}")
    print(f"[eval] Markdown report: {md_path}")
    return report

