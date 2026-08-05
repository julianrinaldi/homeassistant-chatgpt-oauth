"""Tests for chunk-safe Server-Sent Events parsing."""
from __future__ import annotations

import json

import pytest

from custom_components.openai_oauth_conversation.sse import iter_sse_json


class _FakeContent:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    async def iter_any(self):
        for chunk in self._chunks:
            yield chunk


class _FakeResponse:
    def __init__(self, chunks: list[bytes]) -> None:
        self.content = _FakeContent(chunks)


@pytest.mark.asyncio
async def test_multimegabyte_single_line_event_is_parsed() -> None:
    """The parser never delegates giant image lines to aiohttp.readline()."""
    data = {"type": "response.completed", "payload": "A" * 1_100_000}
    wire = b"event: completed\r\ndata: " + json.dumps(data).encode() + b"\r\n\r\n"
    chunks = [wire[:7], wire[7:524_300], wire[524_300:900_000], wire[900_000:]]

    events = [event async for event in iter_sse_json(_FakeResponse(chunks))]
    assert len(events) == 1
    assert events[0][0] == "completed"
    assert events[0][1] == data


@pytest.mark.asyncio
@pytest.mark.parametrize("separator", [b"\n", b"\r", b"\r\n"])
async def test_line_endings_and_unterminated_final_event(separator: bytes) -> None:
    """LF, CR, CRLF, arbitrary chunks, and no final blank line are supported."""
    data = {"type": "response.output_text.done", "text": "complete"}
    wire = b"event: message" + separator + b"data: " + json.dumps(data).encode()
    chunks = [wire[:3], wire[3:17], wire[17:]]

    events = [event async for event in iter_sse_json(_FakeResponse(chunks))]
    assert events == [("message", data)]


@pytest.mark.asyncio
async def test_done_sentinel_is_ignored() -> None:
    """The Responses [DONE] sentinel does not become a malformed JSON event."""
    events = [
        event
        async for event in iter_sse_json(
            _FakeResponse([b"data: [DONE]\n\n"])
        )
    ]
    assert events == []
