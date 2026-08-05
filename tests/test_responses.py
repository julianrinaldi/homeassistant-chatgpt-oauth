"""Tests for streamed response parsing helpers."""
from __future__ import annotations

import base64
import struct

from custom_components.openai_oauth_conversation.responses import (
    decode_image_item,
    image_items_from_event,
    parse_reported_size,
    png_dimensions,
    response_output_items,
    text_from_output_items,
)


def _png(width: int, height: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(
        ">II", width, height
    ) + b"\x08\x06\x00\x00\x00"


def test_completed_text_is_extracted() -> None:
    """Final-only Responses output is supported even without delta events."""
    event = {
        "type": "response.completed",
        "response": {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "Hello"},
                        {"type": "output_text", "text": " world"},
                    ],
                }
            ]
        },
    }
    items = response_output_items(event)
    assert text_from_output_items(items) == "Hello world"


def test_image_result_decoding_and_dimensions() -> None:
    """A final image tool result becomes a native AI Task image result."""
    image_data = _png(1536, 1024)
    item = {
        "type": "image_generation_call",
        "status": "completed",
        "result": base64.b64encode(image_data).decode(),
        "output_format": "png",
        "revised_prompt": "A refined prompt",
        "model": "gpt-image-1",
    }
    result = decode_image_item(item)
    assert result is not None
    assert result.image_data == image_data
    assert result.mime_type == "image/png"
    assert (result.width, result.height) == (1536, 1024)
    assert result.revised_prompt == "A refined prompt"
    assert result.model == "gpt-image-1"
    assert png_dimensions(image_data) == (1536, 1024)


def test_image_items_and_reported_sizes() -> None:
    """Image results are found in direct and completed response events."""
    direct = {"item": {"type": "image_generation_call", "status": "completed"}}
    completed = {
        "response": {
            "output": [
                {"type": "image_generation_call", "status": "completed"}
            ]
        }
    }
    assert len(image_items_from_event(direct)) == 1
    assert len(image_items_from_event(completed)) == 1
    assert parse_reported_size("1024x1536") == (1024, 1536)
    assert parse_reported_size({"width": 512, "height": 768}) == (512, 768)
