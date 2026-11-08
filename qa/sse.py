from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SSEFrame:
    event: str
    data: Any
    event_id: str | None = None
    raw: str = ""


def parse_sse(text: str) -> list[SSEFrame]:
    """Parse a finite SSE body, including CRLF and multi-line data fields."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    frames: list[SSEFrame] = []
    for block in normalized.split("\n\n"):
        if not block.strip():
            continue
        event = "message"
        event_id: str | None = None
        data_lines: list[str] = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
            elif line.startswith("id:"):
                event_id = line[3:].strip()
        if not data_lines:
            continue
        data_text = "\n".join(data_lines)
        try:
            data: Any = json.loads(data_text)
        except json.JSONDecodeError:
            data = data_text
        frames.append(SSEFrame(event=event, data=data, event_id=event_id, raw=block))
    return frames


def frame_data(frames: list[SSEFrame], event: str) -> list[Any]:
    return [frame.data for frame in frames if frame.event == event]


def first_frame(frames: list[SSEFrame], event: str) -> Any | None:
    for frame in frames:
        if frame.event == event:
            return frame.data
    return None

