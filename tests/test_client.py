"""Tests for request construction and serialization."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from homeassistant.helpers import llm
import pytest

from custom_components.openai_oauth_conversation.client import (
    ChatGPTOAuthClient,
    _render_response_text,
    _validate_required_web_search,
    build_request_headers,
    build_turn_payload,
    serialize_request_payload,
)
from custom_components.openai_oauth_conversation.const import (
    CONF_ACCOUNT_ID,
    LEGACY_OUTPUT_LIMIT_KEY,
)
from custom_components.openai_oauth_conversation.exceptions import (
    RequestValidationError,
    ResponseParseError,
)
from custom_components.openai_oauth_conversation.models import MODEL_PROFILES
from custom_components.openai_oauth_conversation.responses import (
    ChatGPTTurn,
    WebCitation,
    WebSearchAction,
)
from custom_components.openai_oauth_conversation.web_search import (
    WEB_SEARCH_REQUIRED,
    WebSearchOptions,
)


@pytest.mark.parametrize("model", tuple(MODEL_PROFILES))
def test_payload_for_every_model_and_level(model: str) -> None:
    """Every selectable thinking level reaches the correct transport payload."""
    profile = MODEL_PROFILES[model]
    for level in profile.reasoning_efforts:
        payload, responses_lite = build_turn_payload(
            model=model,
            instructions="System instructions",
            input_items=[
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Hello"}],
                }
            ],
            tools=[
                {
                    "type": "function",
                    "name": "test_tool",
                    "description": "Test",
                    "parameters": {"type": "object", "properties": {}},
                }
            ],
            tool_choice="auto",
            parallel_tool_calls=False,
            reasoning_effort=level,
        )
        assert responses_lite is profile.responses_lite
        assert payload["model"] == model
        assert payload["reasoning"]["effort"] == ("max" if level == "ultra" else level)
        assert payload["stream"] is True
        assert payload["store"] is False

        if profile.responses_lite:
            assert "instructions" not in payload
            assert "tools" not in payload
            assert payload["reasoning"]["context"] == "all_turns"
            assert payload["input"][0]["type"] == "additional_tools"
            assert payload["input"][1]["role"] == "developer"
        else:
            assert payload["instructions"] == "System instructions"
            assert payload["tools"][0]["name"] == "test_tool"


def test_request_serialization_is_ascii_for_large_inline_image() -> None:
    """Large base64-style strings bypass Home Assistant's shared JSON serializer."""
    payload = {
        "model": "gpt-5.6-terra",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": "data:image/png;base64," + "A" * 1_200_000,
                    },
                    {"type": "input_text", "text": "Café 🏠"},
                ],
            }
        ],
    }
    body = serialize_request_payload(payload)
    assert body.isascii()
    assert b"\x80" not in body
    assert json.loads(body) == payload


def test_legacy_output_limit_is_never_serialized() -> None:
    """The hosted backend's rejected legacy field is blocked recursively."""
    with pytest.raises(RequestValidationError, match="obsolete"):
        serialize_request_payload({"nested": {LEGACY_OUTPUT_LIMIT_KEY: 1000}})


def test_request_headers_include_account_and_lite_transport() -> None:
    """Account routing and Responses Lite identity are explicit."""
    entry = SimpleNamespace(data={CONF_ACCOUNT_ID: "account-123"})
    headers = build_request_headers("token", entry, responses_lite=True)
    assert headers["Authorization"] == "Bearer token"
    assert headers["ChatGPT-Account-ID"] == "account-123"
    assert headers["X-OpenAI-Internal-Codex-Responses-Lite"] == "true"


@pytest.mark.parametrize("model", tuple(MODEL_PROFILES))
def test_web_search_uses_full_responses_transport(model: str) -> None:
    """Native hosted web search stays top-level and disables Responses Lite."""
    payload, responses_lite = build_turn_payload(
        model=model,
        instructions="Search and cite sources.",
        input_items=[
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Latest news"}],
            }
        ],
        tools=[
            {
                "type": "web_search",
                "search_context_size": "high",
                "external_web_access": True,
            }
        ],
        tool_choice="required",
        include=["web_search_call.action.sources"],
        reasoning_effort=MODEL_PROFILES[model].default_reasoning_effort,
    )

    assert responses_lite is False
    assert payload["tools"] == [
        {
            "type": "web_search",
            "search_context_size": "high",
            "external_web_access": True,
        }
    ]
    assert payload["tool_choice"] == "required"
    assert payload["include"] == ["web_search_call.action.sources"]
    assert payload["instructions"] == "Search and cite sources."


def test_required_web_search_must_produce_search_evidence() -> None:
    """Required mode never silently returns an unsearched answer."""
    options = WebSearchOptions(mode=WEB_SEARCH_REQUIRED)
    with pytest.raises(ResponseParseError, match="required OpenAI web search"):
        _validate_required_web_search(options, citations=[], searches=[])

    _validate_required_web_search(
        options,
        citations=[WebCitation(url="https://example.com", title="Example")],
        searches=[],
    )


def test_source_rendering_can_be_hidden_for_voice_responses() -> None:
    """Citation metadata is retained without adding it to spoken text."""
    text = "The current answer is concise."
    citations = [
        WebCitation(
            url="https://example.com/current",
            title="Current source",
            start_index=0,
            end_index=len(text),
        )
    ]
    searches = [
        WebSearchAction(
            call_id="ws_1",
            action="search",
            query="current answer",
        )
    ]

    assert (
        _render_response_text(
            text,
            citations,
            searches,
            WebSearchOptions(mode="auto", include_sources=False),
        )
        == text
    )

    cited = _render_response_text(
        text,
        citations,
        searches,
        WebSearchOptions(mode="auto", include_sources=True),
    )
    assert "Sources:" in cited
    assert "https://example.com/current" in cited


async def test_tool_response_stops_a_repeated_completed_action() -> None:
    """The client returns a precise safety response instead of a generic error."""
    call = llm.ToolInput(
        tool_name="HassTurnOff",
        tool_args={"entity_id": "light.kitchen"},
        id="call-1",
    )
    repeated = llm.ToolInput(
        tool_name="HassTurnOff",
        tool_args={"entity_id": "light.kitchen"},
        id="call-2",
    )
    client = object.__new__(ChatGPTOAuthClient)
    client._async_create_turn = AsyncMock(
        side_effect=[
            ChatGPTTurn(text="", function_calls=[call], raw_events=[]),
            ChatGPTTurn(text="", function_calls=[repeated], raw_events=[]),
        ]
    )
    api = SimpleNamespace(
        tools=[],
        custom_serializer=None,
        async_call_tool=AsyncMock(return_value={"success": True}),
    )

    result = await client.async_create_tool_response(
        model="gpt-5.6-terra",
        instructions="Help.",
        user_text="Turn it off",
        llm_api=api,
        max_tool_calls=5,
        max_tool_time=60,
    )

    assert result.tool_error_type == "repeated_identical_tool_call"
    assert result.tool_call_count == 1
    assert result.tool_names == ["HassTurnOff"]
    assert "already completed" in result.text
    api.async_call_tool.assert_awaited_once()


async def test_tool_response_stops_after_a_completed_answer() -> None:
    """A final answer prevents a redundant follow-up tool from running."""
    client = object.__new__(ChatGPTOAuthClient)
    client._async_create_turn = AsyncMock(
        side_effect=[
            ChatGPTTurn(
                text="",
                function_calls=[
                    llm.ToolInput(tool_name="GetLiveContext", tool_args={}, id="one")
                ],
                raw_events=[],
            ),
            ChatGPTTurn(
                text="The kitchen light is now off.",
                function_calls=[
                    llm.ToolInput(
                        tool_name="HassTurnOff",
                        tool_args={"entity_id": "light.kitchen"},
                        id="two",
                    )
                ],
                raw_events=[],
            ),
        ]
    )
    api = SimpleNamespace(
        tools=[],
        custom_serializer=None,
        async_call_tool=AsyncMock(return_value={"state": "off"}),
    )

    result = await client.async_create_tool_response(
        model="gpt-5.6-terra",
        instructions="Help.",
        user_text="Turn it off",
        llm_api=api,
        max_tool_calls=5,
        max_tool_time=60,
    )

    assert result.text == "The kitchen light is now off."
    assert result.tool_error_type is None
    assert result.tool_call_count == 1
    api.async_call_tool.assert_awaited_once()


async def test_tool_response_enforces_aggregate_time_limit() -> None:
    """A slow Home Assistant tool produces the configured timeout explanation."""

    async def slow_tool(_call: llm.ToolInput) -> dict[str, bool]:
        await asyncio.sleep(0.05)
        return {"success": True}

    client = object.__new__(ChatGPTOAuthClient)
    client._async_create_turn = AsyncMock(
        return_value=ChatGPTTurn(
            text="",
            function_calls=[
                llm.ToolInput(tool_name="SlowTool", tool_args={}, id="slow")
            ],
            raw_events=[],
        )
    )
    api = SimpleNamespace(
        tools=[],
        custom_serializer=None,
        async_call_tool=AsyncMock(side_effect=slow_tool),
    )

    result = await client.async_create_tool_response(
        model="gpt-5.6-terra",
        instructions="Help.",
        user_text="Do it",
        llm_api=api,
        max_tool_calls=5,
        max_tool_time=0.01,
    )

    assert result.tool_error_type == "tool_time_limit"
    assert result.tool_call_count == 1
    assert "configured time limit" in result.text
