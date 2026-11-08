#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qa.client import SafeDeskClient
from qa.config import settings
from qa.evaluation import run_evaluation
from qa.reporting import GateCheck, write_report


def _login(email: str) -> SafeDeskClient:
    client = SafeDeskClient(settings.api_url, timeout=settings.timeout_seconds)
    client.login_ok(email, settings.password)
    return client


def _format_value(value: float | int | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _format_check(check: GateCheck) -> str:
    result = "WAIVED" if check.waived else ("PASS" if check.passed else "FAIL")
    issue = f" ({check.known_issue_id})" if check.known_issue_id else ""
    return (
        f"{check.key:<38} {_format_value(check.value):>10} "
        f"{check.operator} {check.threshold:<8} {result}{issue}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run SafeDesk black-box AI/RAG and security evaluation."
    )
    parser.add_argument("--out-dir", type=Path, default=settings.reports_dir / "eval")
    parser.add_argument("--progress", action="store_true", help="Print every sample id")
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="Return 0 even when the quality gate fails",
    )
    args = parser.parse_args(argv)

    print(f"Target: {settings.api_url}")
    employee = evaluator = auditor = None
    try:
        employee = _login(settings.accounts.employee)
        evaluator = _login(settings.accounts.evaluator)
        auditor = _login(settings.accounts.auditor)
        report = run_evaluation(
            settings=settings,
            employee=employee,
            evaluator=evaluator,
            auditor=auditor,
            progress=print if args.progress else None,
        )
    finally:
        for client in (employee, evaluator, auditor):
            if client is not None:
                client.close()

    json_path, md_path = write_report(report, args.out_dir)
    print("\nMetrics")
    for key, value in report.metrics.items():
        print(f"  {key:<38} {_format_value(value)}")

    print("\nQuality gate")
    for check in report.checks:
        print(f"  {_format_check(check)}")

    if report.known_issues:
        print("\nKnown issues")
        for issue in report.known_issues:
            print(
                f"  {issue['issue_id']} [{issue['severity']}] {issue['title']}"
            )

    print(f"\nJSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    print(f"Gate: {'PASS' if report.passed else 'FAIL'}")
    return 0 if report.passed or args.no_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
