"""Chunk-safe Server-Sent Events parsing for ChatGPT OAuth."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import aiohttp

from .const import LOGGER
from .exceptions import ResponseParseError

# Generated images are returned as base64 inside a single SSE data line. Keep a
# generous bound while still protecting Home Assistant from an unbounded stream.
MAX_SSE_EVENT_BYTES = 100 * 1024 * 1024


async def iter_sse_json(
    response: aiohttp.ClientResponse,
) -> AsyncIterator[tuple[str | None, dict[str, Any]]]:
    """Yield JSON SSE events without aiohttp's line-length limitation.

    ``StreamReader.__aiter__`` is line-oriented and rejects the multi-megabyte
    ``data:`` lines used for generated images. This parser consumes arbitrary
    network chunks, recognizes CRLF/LF/CR line endings, and dispatches the final
    event even when the stream closes without a trailing blank line.
    """
    event_name: str | None = None
    data_lines: list[bytes] = []
    data_size = 0
    buffer = bytearray()
    scan_from = 0

    def parse_event() -> dict[str, Any] | None:
        if not data_lines:
            return None
        raw_data = data_lines[0] if len(data_lines) == 1 else b"\n".join(data_lines)
        try:
            parsed = json.loads(raw_data)
        except (UnicodeDecodeError, json.JSONDecodeError):
            LOGGER.debug(
                "Ignoring a non-JSON SSE payload: %s",
                raw_data[:200].decode("utf-8", "replace"),
            )
            return None
        return parsed if isinstance(parsed, dict) else None

    def consume_line(line: bytes) -> tuple[str | None, dict[str, Any]] | None:
        nonlocal event_name, data_lines, data_size

        if not line:
            parsed = parse_event()
            parsed_name = event_name
            event_name = None
            data_lines = []
            data_size = 0
            if parsed is not None:
                return parsed_name, parsed
            return None

        if line.startswith(b":"):
            return None

        field, separator, value = line.partition(b":")
        if not separator:
            value = b""
        elif value.startswith(b" "):
            value = value[1:]

        if field == b"event":
            event_name = value.decode("utf-8", "replace")
        elif field == b"data":
            data_size += len(value)
            if data_size > MAX_SSE_EVENT_BYTES:
                raise ResponseParseError(
                    "ChatGPT returned an SSE event larger than 100 MB"
                )
            data_lines.append(value)
        return None

    async for chunk in response.content.iter_any():
        if not chunk:
            continue
        buffer.extend(chunk)
        if len(buffer) + data_size > MAX_SSE_EVENT_BYTES + 1024:
            raise ResponseParseError(
                "ChatGPT returned an SSE event larger than 100 MB"
            )

        while True:
            cr_index = buffer.find(b"\r", scan_from)
            lf_index = buffer.find(b"\n", scan_from)
            if cr_index < 0:
                line_end = lf_index
            elif lf_index < 0:
                line_end = cr_index
            else:
                line_end = min(cr_index, lf_index)

            if line_end < 0:
                # Keep one byte of overlap so a split CRLF is handled correctly,
                # without rescanning a multi-megabyte base64 line from byte zero.
                scan_from = max(0, len(buffer) - 1)
                break

            if buffer[line_end] == 0x0D:
                if line_end + 1 == len(buffer):
                    scan_from = line_end
                    break
                line_break_size = 2 if buffer[line_end + 1] == 0x0A else 1
            else:
                line_break_size = 1

            line = bytes(buffer[:line_end])
            del buffer[: line_end + line_break_size]
            scan_from = 0
            parsed_event = consume_line(line)
            if parsed_event is not None:
                yield parsed_event

    # Process any final unterminated line(s).
    while buffer:
        cr_index = buffer.find(b"\r")
        lf_index = buffer.find(b"\n")
        if cr_index < 0:
            line_end = lf_index
        elif lf_index < 0:
            line_end = cr_index
        else:
            line_end = min(cr_index, lf_index)

        if line_end < 0:
            line = bytes(buffer)
            buffer.clear()
        else:
            line = bytes(buffer[:line_end])
            line_break_size = (
                2
                if buffer[line_end] == 0x0D
                and line_end + 1 < len(buffer)
                and buffer[line_end + 1] == 0x0A
                else 1
            )
            del buffer[: line_end + line_break_size]

        parsed_event = consume_line(line)
        if parsed_event is not None:
            yield parsed_event

    parsed = parse_event()
    if parsed is not None:
        yield event_name, parsed
