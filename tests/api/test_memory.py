from __future__ import annotations

import pytest

from qa.client import SafeDeskClient

pytestmark = pytest.mark.api


def test_memory_is_recorded_scoped_and_deletable(
    employee: SafeDeskClient,
    second_employee: SafeDeskClient,
    unique,
) -> None:
    case = employee.create_case(unique("memory"))
    employee.send_message(
        case["id"],
        "我的公司电脑是 Windows 11，VPN 报错 0x80072745，还是不行",
    )
    employee.send_message(case["id"], "以后回答请详细一些")

    items = employee.get_json("/api/memory", params={"case_id": case["id"]})["items"]
    by_key = {item["key"]: item for item in items}
    assert "Windows 11" in by_key["environment"]["value"]
    assert "0x80072745" in by_key["error_message"]["value"]
    assert by_key["answer_style"]["scope"] == "USER"
    assert by_key["answer_style"]["value"] == "detailed"

    other_items = second_employee.get_json(
        "/api/memory", params={"case_id": case["id"]}
    )["items"]
    assert other_items == []

    entry = by_key["environment"]
    denied = second_employee.delete(f"/api/memory/{entry['id']}", csrf=True)
    assert denied.status_code == 404

    deleted = employee.delete(f"/api/memory/{entry['id']}", csrf=True)
    assert deleted.status_code == 200, deleted.text
    remaining = employee.get_json("/api/memory", params={"case_id": case["id"]})["items"]
    assert entry["id"] not in {item["id"] for item in remaining}

