from __future__ import annotations

import time
from collections.abc import Callable, Iterator

import pytest

from qa.client import SafeDeskClient
from qa.config import Settings
from qa.config import settings as default_settings


@pytest.fixture(scope="session")
def settings() -> Settings:
    return default_settings


@pytest.fixture(scope="session")
def stack_ready(settings: Settings) -> None:
    with SafeDeskClient(settings.api_url, timeout=5) as probe:
        ready = probe.health()
    if ready:
        return
    message = (
        f"SafeDesk API is unavailable at {settings.api_url}. "
        "Start it with `docker compose up -d` in the SafeDesk repository."
    )
    if settings.require_stack:
        pytest.fail(message)
    pytest.skip(message)


def _authenticated(settings: Settings, email: str) -> SafeDeskClient:
    client = SafeDeskClient(settings.api_url, timeout=settings.timeout_seconds)
    client.login_ok(email, settings.password)
    return client


@pytest.fixture(scope="session")
def employee(settings: Settings, stack_ready: None) -> Iterator[SafeDeskClient]:
    client = _authenticated(settings, settings.accounts.employee)
    yield client
    client.close()


@pytest.fixture(scope="session")
def support(settings: Settings, stack_ready: None) -> Iterator[SafeDeskClient]:
    client = _authenticated(settings, settings.accounts.support)
    yield client
    client.close()


@pytest.fixture(scope="session")
def approver(settings: Settings, stack_ready: None) -> Iterator[SafeDeskClient]:
    client = _authenticated(settings, settings.accounts.approver)
    yield client
    client.close()


@pytest.fixture(scope="session")
def admin(settings: Settings, stack_ready: None) -> Iterator[SafeDeskClient]:
    client = _authenticated(settings, settings.accounts.admin)
    yield client
    client.close()


@pytest.fixture(scope="session")
def evaluator(settings: Settings, stack_ready: None) -> Iterator[SafeDeskClient]:
    client = _authenticated(settings, settings.accounts.evaluator)
    yield client
    client.close()


@pytest.fixture(scope="session")
def auditor(settings: Settings, stack_ready: None) -> Iterator[SafeDeskClient]:
    client = _authenticated(settings, settings.accounts.auditor)
    yield client
    client.close()


@pytest.fixture
def anonymous(settings: Settings, stack_ready: None) -> Iterator[SafeDeskClient]:
    client = SafeDeskClient(settings.api_url, timeout=settings.timeout_seconds)
    yield client
    client.close()


@pytest.fixture
def new_client(settings: Settings, stack_ready: None) -> Iterator[Callable[[str], SafeDeskClient]]:
    clients: list[SafeDeskClient] = []

    def factory(email: str) -> SafeDeskClient:
        client = _authenticated(settings, email)
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.close()


@pytest.fixture
def unique() -> Callable[[str], str]:
    def make(label: str) -> str:
        return f"QA-{label}-{time.time_ns()}"

    return make


@pytest.fixture
def second_employee(
    settings: Settings,
    admin: SafeDeskClient,
) -> Iterator[SafeDeskClient]:
    users = admin.get_json("/api/admin/users")["items"]
    target = next(item for item in users if item["email"] == settings.accounts.support)
    original_role = target["role"]
    original_department = target["department"]
    changed = admin.patch(
        f"/api/admin/users/{target['id']}",
        csrf=True,
        json={"role": "employee"},
    )
    assert changed.status_code == 200, changed.text
    client = _authenticated(settings, settings.accounts.support)
    try:
        yield client
    finally:
        client.close()
        restored = admin.patch(
            f"/api/admin/users/{target['id']}",
            csrf=True,
            json={"role": original_role, "department": original_department},
        )
        assert restored.status_code == 200, restored.text


@pytest.fixture(scope="session")
def role_clients(
    employee: SafeDeskClient,
    support: SafeDeskClient,
    approver: SafeDeskClient,
    admin: SafeDeskClient,
    evaluator: SafeDeskClient,
    auditor: SafeDeskClient,
) -> dict[str, SafeDeskClient]:
    return {
        "employee": employee,
        "support": support,
        "approver": approver,
        "admin": admin,
        "evaluator": evaluator,
        "auditor": auditor,
    }

