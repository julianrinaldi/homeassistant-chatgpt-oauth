"""Response models and parsers for ChatGPT OAuth."""
from __future__ import annotations

import base64
import binascii
import json
import struct
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.helpers import llm

from .exceptions import ResponseParseError


@dataclass(slots=True)
class ChatGPTTextResponse:
    """Collected text response from the hosted backend."""

    text: str
    raw_events: list[dict[str, Any]]


@dataclass(slots=True)
class ChatGPTDataResponse:
    """Plain or structured data returned by the hosted backend."""

    data: Any
    text: str
    raw_events: list[dict[str, Any]]


@dataclass(slots=True)
class ChatGPTImageResponse:
    """Generated image returned by the hosted image tool."""

    image_data: bytes
    mime_type: str
    width: int | None = None
    height: int | None = None
    model: str | None = None
    revised_prompt: str | None = None


@dataclass(slots=True)
class ChatGPTTurn:
    """One Responses turn, optionally containing function calls."""

    text: str
    function_calls: list[llm.ToolInput]
    raw_events: list[dict[str, Any]]


def response_output_items(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Return Responses output items present in one SSE event."""
    items: list[dict[str, Any]] = []
    direct_item = event.get("item")
    if isinstance(direct_item, dict):
        items.append(direct_item)

    response = event.get("response")
    if isinstance(response, dict):
        output = response.get("output")
        if isinstance(output, list):
            items.extend(item for item in output if isinstance(item, dict))

    output = event.get("output")
    if isinstance(output, list):
        items.extend(item for item in output if isinstance(item, dict))
    return items


def text_from_output_items(items: list[dict[str, Any]]) -> str:
    """Extract final text from completed Responses message items."""
    chunks: list[str] = []
    for item in items:
        if item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") not in {"output_text", "text"}:
                continue
            part_text = part.get("text")
            if isinstance(part_text, str):
                chunks.append(part_text)
    return "".join(chunks).strip()


def response_error_message(event: dict[str, Any]) -> str:
    """Extract the most useful error text from a Responses event."""
    response = event.get("response")
    if isinstance(response, dict):
        error = response.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"]
        incomplete = response.get("incomplete_details")
        if isinstance(incomplete, dict) and incomplete.get("reason"):
            return str(incomplete["reason"])

    error = event.get("error")
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"]
    if isinstance(event.get("message"), str):
        return event["message"]
    return json.dumps(event, default=str)[:500]


def parse_tool_arguments(arguments: Any) -> dict[str, Any]:
    """Parse a function-call argument payload."""
    if arguments in (None, ""):
        return {}
    if isinstance(arguments, dict):
        return arguments
    if not isinstance(arguments, str):
        raise ResponseParseError(
            "ChatGPT returned function-call arguments in an unsupported format"
        )
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError as err:
        raise ResponseParseError(
            "ChatGPT returned invalid JSON function-call arguments"
        ) from err
    if not isinstance(parsed, dict):
        raise ResponseParseError(
            "ChatGPT returned function-call arguments that were not an object"
        )
    return parsed


def extract_function_call(item: dict[str, Any]) -> llm.ToolInput | None:
    """Convert one Responses function-call item to Home Assistant input."""
    if item.get("type") != "function_call":
        return None
    name = item.get("name")
    if not isinstance(name, str) or not name:
        return None
    call_id = item.get("call_id") or item.get("id")
    if call_id is None:
        return None
    return llm.ToolInput(
        id=str(call_id),
        tool_name=name,
        tool_args=parse_tool_arguments(item.get("arguments")),
    )


def image_items_from_event(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Return completed image-generation items from one event."""
    return [
        item
        for item in response_output_items(event)
        if item.get("type") == "image_generation_call"
    ]


def mime_type_from_output_format(output_format: Any) -> str:
    """Map a hosted image output format to a MIME type."""
    if not isinstance(output_format, str) or not output_format:
        return "image/png"
    normalized = output_format.lower().lstrip(".")
    if normalized == "jpg":
        normalized = "jpeg"
    if normalized not in {"png", "jpeg", "webp"}:
        return "image/png"
    return f"image/{normalized}"


def parse_reported_size(size: Any) -> tuple[int | None, int | None]:
    """Parse image dimensions returned as ``WIDTHxHEIGHT`` or an object."""
    if isinstance(size, Mapping):
        width_value = size.get("width")
        height_value = size.get("height")
    elif isinstance(size, str):
        try:
            width_value, height_value = size.lower().split("x", 1)
        except ValueError:
            return None, None
    else:
        return None, None

    try:
        width = int(width_value)
        height = int(height_value)
    except (TypeError, ValueError):
        return None, None
    if width <= 0 or height <= 0:
        return None, None
    return width, height


def png_dimensions(image_data: bytes) -> tuple[int | None, int | None]:
    """Read PNG dimensions without adding an image-library dependency."""
    if (
        len(image_data) >= 24
        and image_data[:8] == b"\x89PNG\r\n\x1a\n"
        and image_data[12:16] == b"IHDR"
    ):
        width, height = struct.unpack(">II", image_data[16:24])
        return width, height
    return None, None


def _validate_image_data(image_data: bytes, mime_type: str) -> None:
    """Reject an empty or malformed image result before returning it to HA."""
    signatures = {
        "image/png": image_data.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": image_data.startswith(b"\xff\xd8\xff"),
        "image/webp": (
            len(image_data) >= 12
            and image_data.startswith(b"RIFF")
            and image_data[8:12] == b"WEBP"
        ),
    }
    if not signatures.get(mime_type, False):
        raise ResponseParseError(
            f"ChatGPT image generation returned invalid {mime_type} data"
        )


def decode_image_item(item: dict[str, Any]) -> ChatGPTImageResponse | None:
    """Decode one completed image-generation output item."""
    result = item.get("result")
    if not isinstance(result, str) or not result:
        return None
    try:
        image_data = base64.b64decode(result, validate=True)
    except (binascii.Error, ValueError) as err:
        raise ResponseParseError(
            "ChatGPT image generation returned invalid base64 image data"
        ) from err
    if not image_data:
        raise ResponseParseError("ChatGPT image generation returned an empty image")

    mime_type = mime_type_from_output_format(item.get("output_format"))
    _validate_image_data(image_data, mime_type)

    width, height = parse_reported_size(item.get("size"))
    if width is None or height is None:
        width, height = png_dimensions(image_data)

    model = item.get("model")
    if not isinstance(model, str):
        model = None
    revised_prompt = item.get("revised_prompt")
    if not isinstance(revised_prompt, str):
        revised_prompt = None

    return ChatGPTImageResponse(
        image_data=image_data,
        mime_type=mime_type,
        width=width,
        height=height,
        model=model,
        revised_prompt=revised_prompt,
    )
