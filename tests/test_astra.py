"""Regression tests for GPT-6 Astra model selection and request routing."""

from __future__ import annotations

from contextlib import asynccontextmanager
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from homeassistant.helpers import llm
import pytest
import voluptuous as vol
import yaml

from custom_components.openai_oauth_conversation import _model_validator
from custom_components.openai_oauth_conversation import client as client_module
from custom_components.openai_oauth_conversation.client import (
    ChatGPTOAuthClient,
    build_request_headers,
    build_turn_payload,
    serialize_request_payload,
)
from custom_components.openai_oauth_conversation.config_flow import (
    _model_schema,
    _reasoning_schema,
)
from custom_components.openai_oauth_conversation.const import (
    CONF_MODEL,
    CONF_REASONING_EFFORT,
    DEFAULT_MODEL,
    LEGACY_OUTPUT_LIMIT_KEY,
)
from custom_components.openai_oauth_conversation.models import (
    MODEL_PROFILES,
    RESPONSES_LITE_MODELS,
    default_reasoning_effort,
    get_model_profile,
    reasoning_efforts_for_model,
    validate_reasoning_effort,
)
from custom_components.openai_oauth_conversation.profiles import profile_data_defaults
from custom_components.openai_oauth_conversation.responses import ChatGPTTurn
from custom_components.openai_oauth_conversation.web_search import WebSearchOptions

ASTRA = "gpt-6-astra"
LEVELS = ("low", "medium", "high", "xhigh", "max")


def test_astra_catalog_and_selectors() -> None:
    """Account, profile, and action validation accept the same canonical model."""
    profile = get_model_profile(ASTRA)
    assert profile.slug == ASTRA
    assert profile.display_name == "GPT-6 Astra"
    assert reasoning_efforts_for_model(ASTRA) == LEVELS
    assert default_reasoning_effort(ASTRA) == "low"
    assert profile.supports_images
    assert profile.supports_files
    assert profile.supports_tools
    assert profile.supports_structured_output
    assert profile.supports_web_search
    assert ASTRA not in RESPONSES_LITE_MODELS
    assert _model_schema(DEFAULT_MODEL)(ASTRA) == ASTRA
    assert _model_schema(ASTRA)(ASTRA) == ASTRA
    assert _model_validator(ASTRA) == ASTRA
    for level in LEVELS:
        assert _reasoning_schema(ASTRA)(level) == level
        assert validate_reasoning_effort(ASTRA, level) == level


@pytest.mark.parametrize("level", ("none", "minimal", "ultra"))
def test_astra_rejects_unsupported_explicit_levels(level: str) -> None:
    """Do not invent unsupported Astra reasoning levels or silently accept them."""
    with pytest.raises(ValueError, match="not available"):
        validate_reasoning_effort(ASTRA, level)
    with pytest.raises(vol.Invalid):
        _reasoning_schema(ASTRA)(level)


def test_action_selectors_match_catalog() -> None:
    """Every action with a model override exposes Astra, without stale lists."""
    path = Path(client_module.__file__).with_name("services.yaml")
    descriptions = yaml.safe_load(path.read_text(encoding="utf-8"))
    for service in ("generate_content", "analyze_image", "web_search"):
        options = descriptions[service]["fields"]["model"]["selector"]["select"][
            "options"
        ]
        assert {option["value"] for option in options} == set(MODEL_PROFILES)
        assert len(options) == len(MODEL_PROFILES)


@pytest.mark.parametrize("model", tuple(MODEL_PROFILES))
def test_existing_profile_models_are_not_migrated(model: str) -> None:
    """Adding Astra must not replace a user's selected model or valid effort."""
    data = profile_data_defaults({CONF_MODEL: model, CONF_REASONING_EFFORT: "high"})
    assert data[CONF_MODEL] == model
    assert data[CONF_REASONING_EFFORT] == "high"
    assert DEFAULT_MODEL == "gpt-5.6-terra"
    assert profile_data_defaults()[CONF_MODEL] == DEFAULT_MODEL


@pytest.mark.parametrize("level", LEVELS)
def test_astra_uses_full_responses_at_every_level(level: str) -> None:
    """Astra is never routed through the GPT-5.6-only Responses Lite protocol."""
    payload, lite = build_turn_payload(
        model=ASTRA,
        reasoning_effort=level,
        instructions="Answer naturally.",
        input_items=[
            {"role": "user", "content": [{"type": "input_text", "text": "Hello"}]}
        ],
        tools=[
            {"type": "function", "name": "ReadState", "parameters": {"type": "object"}}
        ],
        parallel_tool_calls=False,
    )
    assert lite is False
    assert payload["model"] == ASTRA
    assert payload["reasoning"] == {"effort": level}
    assert payload["instructions"] == "Answer naturally."
    assert payload["tools"][0]["name"] == "ReadState"
    assert payload["stream"] is True
    assert payload["store"] is False
    assert not any(item.get("type") == "additional_tools" for item in payload["input"])
    assert (
        not {"temperature", "top_p", "top_logprobs", LEGACY_OUTPUT_LIMIT_KEY}
        & payload.keys()
    )
    headers = build_request_headers(
        "test-token", SimpleNamespace(data={}), responses_lite=lite
    )
    assert "X-OpenAI-Internal-Codex-Responses-Lite" not in headers
    assert json.loads(serialize_request_payload(payload)) == payload


def _client(hass) -> ChatGPTOAuthClient:
    """Create a client without an HTTP session or real account credentials."""
    client = object.__new__(ChatGPTOAuthClient)
    client.hass = hass
    client.entry = SimpleNamespace(
        data={CONF_MODEL: ASTRA, CONF_REASONING_EFFORT: "low"}
    )
    return client


@pytest.mark.parametrize("structured", (False, True))
async def test_astra_ai_task_data_request(hass, structured: bool) -> None:
    """Plain and structured AI Tasks exercise actual request construction."""
    client = _client(hass)
    client._async_collect_turn = AsyncMock(
        return_value=ChatGPTTurn(
            text='{"answer":"Ready"}' if structured else "Ready",
            function_calls=[],
            raw_events=[],
        )
    )
    result = await client.async_create_data_response(
        model=ASTRA,
        instructions="Report readiness.",
        content=[{"type": "input_text", "text": "Are you ready?"}],
        structure_name="astra_check",
        structure=vol.Schema({vol.Required("answer"): str}) if structured else None,
        reasoning_effort="medium",
    )
    assert result.data == ({"answer": "Ready"} if structured else "Ready")
    call = client._async_collect_turn.await_args
    assert call.kwargs["responses_lite"] is False
    payload = call.args[0]
    assert payload["model"] == ASTRA
    assert payload["reasoning"]["effort"] == "medium"
    if structured:
        assert payload["text"]["format"]["type"] == "json_schema"
        assert payload["text"]["format"]["strict"] is True
    serialize_request_payload(payload)


async def test_astra_assist_tool_round_trip(hass) -> None:
    """Home Assistant tool output returns to Astra before the final answer."""
    client = _client(hass)
    client._async_collect_turn = AsyncMock(
        side_effect=[
            ChatGPTTurn(
                text="",
                function_calls=[
                    llm.ToolInput(tool_name="ReadState", tool_args={}, id="one")
                ],
                raw_events=[],
            ),
            ChatGPTTurn(text="The light is off.", function_calls=[], raw_events=[]),
        ]
    )
    api = SimpleNamespace(
        tools=[
            SimpleNamespace(
                name="ReadState", description="Read state", parameters=vol.Schema({})
            )
        ],
        custom_serializer=llm.selector_serializer,
        async_call_tool=AsyncMock(return_value={"state": "off"}),
    )
    result = await client.async_create_tool_response(
        model=ASTRA,
        instructions="Use the available tool to read the light state.",
        user_text="Is the light on?",
        llm_api=api,
        reasoning_effort="low",
    )
    assert result.text == "The light is off."
    api.async_call_tool.assert_awaited_once()
    assert client._async_collect_turn.await_count == 2
    second = client._async_collect_turn.await_args.args[0]
    assert any(item.get("type") == "function_call_output" for item in second["input"])
    for call in client._async_collect_turn.await_args_list:
        assert call.args[0]["model"] == ASTRA
        assert call.kwargs["responses_lite"] is False
        serialize_request_payload(call.args[0])


async def test_astra_web_search_with_image_input(hass) -> None:
    """Astra forwards vision input and search settings through full Responses."""
    client = _client(hass)
    client._async_collect_turn = AsyncMock(
        return_value=ChatGPTTurn(
            text="A concise answer.", function_calls=[], raw_events=[]
        )
    )
    content = [
        {"type": "input_text", "text": "Research this object."},
        {"type": "input_image", "image_url": "data:image/png;base64,AAAA"},
    ]
    result = await client.async_create_response(
        model=ASTRA,
        instructions="Answer briefly.",
        content=content,
        reasoning_effort="high",
        web_search=WebSearchOptions(mode="auto", include_sources=False),
    )
    assert result.text == "A concise answer."
    call = client._async_collect_turn.await_args
    assert call.kwargs["responses_lite"] is False
    payload = call.args[0]
    assert payload["model"] == ASTRA
    assert payload["input"][0]["content"] == content
    assert payload["tools"][0]["type"] == "web_search"
    assert "web_search_call.action.sources" in payload["include"]
    serialize_request_payload(payload)


@pytest.mark.parametrize("image_count", (0, 10))
async def test_astra_image_generation_request(
    hass, monkeypatch, image_count: int
) -> None:
    """Generate and ten-reference edit requests use Astra and preserve image settings."""
    client = _client(hass)
    image_result = object()
    content = [{"type": "input_text", "text": "Create a square illustration."}]
    content.extend(
        {"type": "input_image", "image_url": "data:image/png;base64,AAAA"}
        for _ in range(image_count)
    )
    captured = {}

    @asynccontextmanager
    async def fake_response(payload, **kwargs):
        captured.update(payload=payload, **kwargs)
        yield object()

    async def fake_events(_response):
        yield (
            "response.output_item.done",
            {
                "type": "response.output_item.done",
                "item": {"type": "image_generation_call", "status": "completed"},
            },
        )

    client._async_response = fake_response
    monkeypatch.setattr(client_module, "iter_sse_json", fake_events)
    monkeypatch.setattr(client_module, "decode_image_item", lambda _item: image_result)
    result = await client.async_create_image_response(
        model=ASTRA, content=content, reasoning_effort="max"
    )
    assert result is image_result
    assert captured["responses_lite"] is False
    payload = captured["payload"]
    assert payload["model"] == ASTRA
    assert payload["reasoning"]["effort"] == "max"
    assert payload["input"][0]["content"] == content
    assert payload["tool_choice"] == {"type": "image_generation"}
    assert payload["tools"][0]["output_format"] == "png"
    assert payload["tools"][0]["partial_images"] == 0
    assert payload["store"] is False
    serialize_request_payload(payload)
