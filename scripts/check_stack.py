#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qa.client import SafeDeskClient
from qa.config import settings


@dataclass(slots=True)
class Check:
    name: str
    passed: bool
    detail: str


def _wait_for_url(name: str, url: str, seconds: float) -> Check:
    deadline = time.monotonic() + seconds
    last_error = ""
    while True:
        try:
            response = httpx.get(url, timeout=5, follow_redirects=True)
            if response.status_code < 400:
                return Check(name, True, f"{response.status_code} {url}")
            last_error = f"HTTP {response.status_code}"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if time.monotonic() >= deadline:
            return Check(name, False, f"{url} ({last_error})")
        time.sleep(2)


def _check_roles() -> list[Check]:
    checks: list[Check] = []
    accounts = settings.accounts.by_role()
    for role, email in accounts.items():
        client = SafeDeskClient(settings.api_url, timeout=10)
        try:
            response = client.login(email, settings.password)
            if response.status_code != 200:
                checks.append(Check(f"login:{role}", False, f"HTTP {response.status_code}"))
                continue
            me = client.get("/api/me").json()
            actual = me.get("user", {}).get("role")
            checks.append(
                Check(
                    f"login:{role}",
                    actual == role,
                    f"{email} -> {actual or 'unknown'}",
                )
            )
        finally:
            client.close()
    return checks


def _check_datasets() -> Check:
    client = SafeDeskClient(settings.api_url, timeout=15)
    try:
        client.login_ok(settings.accounts.evaluator, settings.password)
        response = client.get("/api/eval/datasets")
        if response.status_code != 200:
            return Check("eval:datasets", False, f"HTTP {response.status_code}")
        items = response.json()["items"]
        counts = {item["dataset_type"]: item["item_count"] for item in items}
        expected = {"knowledge": 40, "triage": 80, "security": 15}
        passed = all(counts.get(key) == value for key, value in expected.items())
        return Check("eval:datasets", passed, str(counts))
    finally:
        client.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check SafeDesk QA target readiness.")
    parser.add_argument("--wait", type=float, default=0, help="Seconds to wait for HTTP")
    parser.add_argument("--skip-web", action="store_true")
    parser.add_argument("--skip-datasets", action="store_true")
    args = parser.parse_args(argv)

    checks = [
        _wait_for_url(
            "api:health",
            f"{settings.api_url}/api/health",
            args.wait,
        )
    ]
    if not args.skip_web:
        checks.append(
            _wait_for_url("web:login", f"{settings.web_url}/login", args.wait)
        )
    checks.extend(_check_roles())
    if not args.skip_datasets:
        checks.append(_check_datasets())

    for check in checks:
        print(f"[{'PASS' if check.passed else 'FAIL'}] {check.name}: {check.detail}")
    return 0 if all(check.passed for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
