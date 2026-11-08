from __future__ import annotations

import pytest

from qa.sse import first_frame, frame_data, parse_sse

pytestmark = pytest.mark.unit


def test_parse_sse_handles_crlf_ids_and_json() -> None:
    text = (
        "id: 1\r\nevent: step\r\ndata: {\"name\": \"retrieve\"}\r\n\r\n"
        "id: 2\r\nevent: done\r\ndata: {\"refused\": false}\r\n"
    )
    frames = parse_sse(text)
    assert [frame.event for frame in frames] == ["step", "done"]
    assert frames[0].event_id == "1"
    assert frames[0].data == {"name": "retrieve"}
    assert first_frame(frames, "done") == {"refused": False}
    assert frame_data(frames, "step") == [{"name": "retrieve"}]


def test_parse_sse_multiline_data_and_plain_text() -> None:
    text = "event: note\ndata: first\ndata: second\n\n"
    frames = parse_sse(text)
    assert frames[0].data == "first\nsecond"

