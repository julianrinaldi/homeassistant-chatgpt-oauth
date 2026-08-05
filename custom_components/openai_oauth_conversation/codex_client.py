"""Compatibility facade for the ChatGPT OAuth client.

The v1 implementation is split into focused modules. These aliases preserve the
public helper names used by v0.x automations, downstream forks, and tests.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from .auth import ConfigEntryLike, extract_account_id
from .client import (
    ChatGPTOAuthClient,
    build_request_headers as _request_headers,
    build_turn_payload as _build_turn_payload,
    serialize_request_payload as _serialize_codex_payload,
)
from .content import file_bytes_part, image_bytes_part, image_url_part, text_part
from .exceptions import ChatGPTOAuthError
from .responses import (
    ChatGPTDataResponse,
    ChatGPTImageResponse,
    ChatGPTTextResponse,
    ChatGPTTurn,
    decode_image_item as _decode_image_item,
    image_items_from_event as _image_items_from_event,
    mime_type_from_output_format as _mime_type_from_output_format,
    parse_reported_size as _parse_reported_size,
    png_dimensions as _png_dimensions,
    response_error_message as _response_error_message,
    response_output_items as _response_output_items,
    text_from_output_items as _text_from_output_items,
)
from .schema import (
    fallback_json_instructions as _fallback_json_instructions,
    format_structured_output,
    is_structured_output_error as _is_structured_output_error,
    parse_and_validate_structured_text as _parse_and_validate_structured_text,
    structured_output_format as _structured_output_format,
)
from .sse import iter_sse_json as _iter_sse

__all__ = [
    "ChatGPTOAuthClient",
    "CodexDataResponse",
    "CodexImageResponse",
    "CodexResponse",
    "CodexTurn",
    "OpenAIOAuthError",
    "_build_turn_payload",
    "_decode_image_item",
    "_fallback_json_instructions",
    "_image_items_from_event",
    "_is_structured_output_error",
    "_iter_sse",
    "_mime_type_from_output_format",
    "_parse_and_validate_structured_text",
    "_parse_reported_size",
    "_png_dimensions",
    "_request_headers",
    "_response_error_message",
    "_response_output_items",
    "_serialize_codex_payload",
    "_structured_output_format",
    "_text_from_output_items",
    "client_for_entry",
    "create_data_response",
    "create_image_response",
    "create_response",
    "create_tool_response",
    "extract_account_id",
    "file_bytes_part",
    "format_structured_output",
    "image_bytes_part",
    "image_url_part",
    "refresh_token",
    "text_part",
]


# Backward-compatible type and exception names.
CodexResponse = ChatGPTTextResponse
CodexDataResponse = ChatGPTDataResponse
CodexImageResponse = ChatGPTImageResponse
CodexTurn = ChatGPTTurn
OpenAIOAuthError = ChatGPTOAuthError


def client_for_entry(
    hass: HomeAssistant,
    entry: ConfigEntryLike,
) -> ChatGPTOAuthClient:
    """Return the entry runtime client or construct a temporary one."""
    runtime_data = getattr(entry, "runtime_data", None)
    if isinstance(runtime_data, ChatGPTOAuthClient):
        return runtime_data
    return ChatGPTOAuthClient(hass, entry)


async def refresh_token(hass: HomeAssistant, entry: ConfigEntryLike) -> str:
    """Return a valid access token for a config entry."""
    return await client_for_entry(hass, entry).token_manager.async_get_access_token()


async def create_response(
    hass: HomeAssistant,
    entry: ConfigEntryLike,
    *,
    model: str,
    instructions: str | None,
    content: list[dict[str, Any]] | None = None,
    input_items: list[dict[str, Any]] | None = None,
    text_format: dict[str, Any] | None = None,
    reasoning_effort: str | None = None,
) -> ChatGPTTextResponse:
    """Create a text response."""
    return await client_for_entry(hass, entry).async_create_response(
        model=model,
        instructions=instructions,
        content=content,
        input_items=input_items,
        text_format=text_format,
        reasoning_effort=reasoning_effort,
    )


async def create_image_response(
    hass: HomeAssistant,
    entry: ConfigEntryLike,
    *,
    model: str,
    content: list[dict[str, Any]],
    reasoning_effort: str | None = None,
) -> ChatGPTImageResponse:
    """Generate or edit one image."""
    return await client_for_entry(hass, entry).async_create_image_response(
        model=model,
        content=content,
        reasoning_effort=reasoning_effort,
    )


async def create_data_response(
    hass: HomeAssistant,
    entry: ConfigEntryLike,
    *,
    model: str,
    instructions: str,
    content: list[dict[str, Any]],
    structure_name: str,
    structure: vol.Schema | None,
    llm_api: llm.APIInstance | None = None,
    reasoning_effort: str | None = None,
) -> ChatGPTDataResponse:
    """Generate plain text or structured data."""
    return await client_for_entry(hass, entry).async_create_data_response(
        model=model,
        instructions=instructions,
        content=content,
        structure_name=structure_name,
        structure=structure,
        llm_api=llm_api,
        reasoning_effort=reasoning_effort,
    )


async def create_tool_response(
    hass: HomeAssistant,
    entry: ConfigEntryLike,
    *,
    model: str,
    instructions: str,
    llm_api: llm.APIInstance,
    user_text: str | None = None,
    content: list[dict[str, Any]] | None = None,
    input_items: list[dict[str, Any]] | None = None,
    text_format: dict[str, Any] | None = None,
    reasoning_effort: str | None = None,
) -> ChatGPTTextResponse:
    """Create a response with Home Assistant tools enabled."""
    return await client_for_entry(hass, entry).async_create_tool_response(
        model=model,
        instructions=instructions,
        llm_api=llm_api,
        user_text=user_text,
        content=content,
        input_items=input_items,
        text_format=text_format,
        reasoning_effort=reasoning_effort,
    )
