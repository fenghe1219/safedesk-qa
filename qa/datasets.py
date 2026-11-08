from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class DatasetSample:
    id: str
    input: str
    expected: dict[str, Any]
    labels: dict[str, Any]
    raw: dict[str, Any]


def load_jsonl(path: Path) -> list[DatasetSample]:
    samples: list[DatasetSample] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        samples.append(
            DatasetSample(
                id=str(value["id"]),
                input=str(value.get("input") or value.get("text") or ""),
                expected=dict(value.get("expected") or {}),
                labels=dict(value.get("labels") or {}),
                raw=value,
            )
        )
    if not samples:
        raise ValueError(f"Dataset is empty: {path}")
    if len({item.id for item in samples}) != len(samples):
        raise ValueError(f"Dataset has duplicate ids: {path}")
    return samples


def load_knowledge(datasets_dir: Path) -> list[DatasetSample]:
    return load_jsonl(datasets_dir / "knowledge_40.jsonl")


def load_security(datasets_dir: Path) -> list[DatasetSample]:
    return load_jsonl(datasets_dir / "security_15.jsonl")

