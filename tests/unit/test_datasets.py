from __future__ import annotations

import pytest

from qa.config import settings
from qa.datasets import load_knowledge, load_security

pytestmark = pytest.mark.unit


def test_vendored_datasets_are_valid() -> None:
    knowledge = load_knowledge(settings.datasets_dir)
    security = load_security(settings.datasets_dir)
    assert len(knowledge) == 40
    assert len(security) == 15
    assert knowledge[0].id == "knowledge_001"
    assert security[0].id == "security_001"
    assert len({item.id for item in knowledge}) == 40
    assert len({item.id for item in security}) == 15

