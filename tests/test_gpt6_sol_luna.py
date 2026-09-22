"""Regression coverage for the new GPT-6 OAuth model choices."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import voluptuous as vol

from custom_components.openai_oauth_conversation import _model_validator
from custom_components.openai_oauth_conversation.client import (
    build_request_headers,
    build_turn_payload,
)
from custom_components.openai_oauth_conversation.config_flow import (
    _model_schema,
    _reasoning_schema,
)
from custom_components.openai_oauth_conversation.const import (
    CONF_MODEL,
    CONF_REASONING_EFFORT,
    DEFAULT_MODEL,
)
from custom_components.openai_oauth_conversation.models import (
    get_model_profile,
    normalize_reasoning_effort,
    validate_reasoning_effort,
)
from custom_components.openai_oauth_conversation.profiles import profile_data_defaults

GPT6_MODELS = ("gpt-6-sol", "gpt-6-luna")
LEVELS = ("low", "medium", "high", "xhigh", "max")


@pytest.mark.parametrize("model", GPT6_MODELS)
def test_model_is_selectable_and_profile_defaults_preserve_choice(model: str) -> None:
    """Account and action validators accept each model; profile defaults retain it."""
    assert _model_schema(DEFAULT_MODEL)(model) == model
    assert _model_validator(model) == model
    assert get_model_profile(model).display_name in ("GPT-6 Sol", "GPT-6 Luna")
    assert get_model_profile(model).default_reasoning_effort == "medium"
    data = profile_data_defaults({CONF_MODEL: model, CONF_REASONING_EFFORT: "high"})
    assert data[CONF_MODEL] == model
    assert data[CONF_REASONING_EFFORT] == "high"
    assert profile_data_defaults()[CONF_MODEL] == DEFAULT_MODEL


@pytest.mark.parametrize("model", GPT6_MODELS)
@pytest.mark.parametrize("level", LEVELS)
def test_gpt6_request_uses_full_responses_and_current_client_identity(
    model: str, level: str
) -> None:
    """Tool requests stay on full Responses with a current Codex identity."""
    assert _reasoning_schema(model)(level) == level
    payload, lite = build_turn_payload(
        model=model,
        reasoning_effort=level,
        instructions="Answer the user.",
        input_items=[
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Hello"}],
            }
        ],
        tools=[
            {"type": "function", "name": "ReadState", "parameters": {"type": "object"}}
        ],
        parallel_tool_calls=False,
    )
    assert lite is False
    assert payload["model"] == model
    assert payload["reasoning"] == {"effort": level}
    assert payload["instructions"] == "Answer the user."
    assert payload["tools"][0]["name"] == "ReadState"
    assert payload["parallel_tool_calls"] is False
    assert not any(item.get("type") == "additional_tools" for item in payload["input"])

    headers = build_request_headers(
        "synthetic-token", SimpleNamespace(data={}), responses_lite=lite
    )
    assert headers["version"] == "0.155.1"
    assert headers["User-Agent"].startswith("codex_cli_rs/0.155.1 ")
    assert "X-OpenAI-Internal-Codex-Responses-Lite" not in headers


@pytest.mark.parametrize("model", GPT6_MODELS)
def test_gpt6_unsupported_levels_are_not_sent(model: str) -> None:
    """OAuth exposes model reasoning, without claiming Codex delegation."""
    assert normalize_reasoning_effort(model, "ultra") == "medium"
    for level in ("none", "minimal", "ultra"):
        with pytest.raises(ValueError, match="not available"):
            validate_reasoning_effort(model, level)
        with pytest.raises(vol.Invalid):
            _reasoning_schema(model)(level)
