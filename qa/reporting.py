from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class GateCheck:
    key: str
    label: str
    value: float | None
    operator: str
    threshold: float
    passed: bool
    waived: bool = False
    known_issue_id: str | None = None


@dataclass(slots=True)
class EvalReport:
    generated_at: str
    target: str
    metrics: dict[str, float | int | None]
    samples: list[dict[str, Any]]
    checks: list[GateCheck]
    known_issues: list[dict[str, str]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks if not check.waived)

    @property
    def failed_checks(self) -> list[GateCheck]:
        return [check for check in self.checks if not check.passed and not check.waived]

    @property
    def waived_checks(self) -> list[GateCheck]:
        return [check for check in self.checks if check.waived]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "target": self.target,
            "passed": self.passed,
            "metrics": self.metrics,
            "checks": [asdict(check) for check in self.checks],
            "known_issues": self.known_issues,
            "samples": self.samples,
        }


def build_report(
    *,
    target: str,
    metrics: dict[str, float | int | None],
    samples: list[dict[str, Any]],
    checks: list[GateCheck],
    known_issues: list[dict[str, str]],
) -> EvalReport:
    return EvalReport(
        generated_at=datetime.now(UTC).isoformat(),
        target=target,
        metrics=metrics,
        samples=samples,
        checks=checks,
        known_issues=known_issues,
    )


def _fmt(value: float | int | None, *, percent: bool = False) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value * 100:.2f}%" if percent else f"{value:.4f}"
    return str(value)


def render_markdown(report: EvalReport) -> str:
    lines = [
        "# SafeDesk QA · AI/RAG Evaluation Report",
        "",
        f"- Generated: `{report.generated_at}`",
        f"- Target: `{report.target}`",
        f"- Gate: **{'PASS' if report.passed else 'FAIL'}**",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    for key in sorted(report.metrics):
        value = report.metrics[key]
        percent = key.endswith(("_rate", "_accuracy", "_consistency", "_coverage", "_at_k"))
        lines.append(f"| `{key}` | {_fmt(value, percent=percent)} |")

    lines.extend(
        [
            "",
            "## Quality Gate",
            "",
            "| Check | Actual | Rule | Result |",
            "| --- | ---: | ---: | --- |",
        ]
    )
    for check in report.checks:
        percent = check.key.endswith(
            ("_rate", "_accuracy", "_consistency", "_coverage", "_at_k")
        )
        lines.append(
            f"| {check.label} | {_fmt(check.value, percent=percent)} | "
            f"{check.operator} {_fmt(check.threshold, percent=percent)} | "
            f"{'WAIVED' if check.waived else ('PASS' if check.passed else 'FAIL')}"
            f"{f' ({check.known_issue_id})' if check.known_issue_id else ''} |"
        )

    failed = [sample for sample in report.samples if not sample.get("passed")]
    lines.extend(["", "## Failed Samples", ""])
    if not failed:
        lines.append("None.")
    else:
        lines.extend(
            [
                "| Dataset | Sample | Known issue | Reason |",
                "| --- | --- | --- | --- |",
            ]
        )
        for sample in failed[:50]:
            lines.append(
                f"| {sample['dataset']} | `{sample['id']}` | "
                f"{sample.get('known_issue_id') or '—'} | {sample.get('failure_reason', '')} |"
            )

    if report.known_issues:
        lines.extend(["", "## Known Issues", ""])
        for issue in report.known_issues:
            lines.append(
                f"- **{issue['issue_id']}** ({issue['severity']}): "
                f"{issue['title']} — {issue['summary']}"
            )
    return "\n".join(lines) + "\n"


def write_report(report: EvalReport, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = out_dir / f"eval-{stamp}.json"
    md_path = out_dir / f"eval-{stamp}.md"
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    json_path.write_text(payload + "\n", encoding="utf-8")
    (out_dir / "latest.json").write_text(payload + "\n", encoding="utf-8")
    markdown = render_markdown(report)
    md_path.write_text(markdown, encoding="utf-8")
    (out_dir / "latest.md").write_text(markdown, encoding="utf-8")
    return json_path, md_path

