"""OAuth image-model names and correction of the short-lived API-only choices."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant.exceptions import ConfigEntryAuthFailed
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from custom_components.openai_oauth_conversation import async_setup_entry
from custom_components.openai_oauth_conversation import client as client_module
from custom_components.openai_oauth_conversation.client import ChatGPTOAuthClient
from custom_components.openai_oauth_conversation.config_flow import (
    ChatGPTOAuthConfigFlow,
    _account_defaults,
    _account_schema,
    _parse_account_form,
)
from custom_components.openai_oauth_conversation.const import (
    CONF_ACCESS_TOKEN,
    CONF_IMAGE_MODEL,
    CONF_MODEL,
    CONF_REASONING_EFFORT,
    CONF_REFRESH_TOKEN,
    DEFAULT_IMAGE_MODEL,
    DOMAIN,
)
from custom_components.openai_oauth_conversation.exceptions import (
    AuthenticationError,
    RequestValidationError,
)
from custom_components.openai_oauth_conversation.image_models import (
    IMAGE_MODELS,
    migrate_legacy_image_model,
    validate_image_model,
)

LEGACY = ("gpt-image-2.5-flare", "gpt-image-2.5-sunburst")


def _client(hass, entry):
    client = object.__new__(ChatGPTOAuthClient)
    client.hass = hass
    client.entry = entry
    return client


@pytest.mark.parametrize("previous", LEGACY)
async def test_saved_api_variants_use_unified_oauth_choice(hass, previous):
    data = {
        CONF_IMAGE_MODEL: previous,
        CONF_MODEL: "gpt-6-astra",
        CONF_REASONING_EFFORT: "high",
    }
    before = dict(data)
    defaults = _account_defaults(data)
    assert defaults[CONF_IMAGE_MODEL] == "gpt-image-2.5"
    assert data == before
    selector = _account_schema(defaults, name_default="Account").schema[
        CONF_IMAGE_MODEL
    ]
    assert selector("gpt-image-2.5") == "gpt-image-2.5"
    with pytest.raises(vol.Invalid):
        selector(previous)
    _, updated = _parse_account_form({}, defaults=defaults, fallback_name="Account")
    assert updated[CONF_IMAGE_MODEL] == "gpt-image-2.5"
    client = _client(hass, SimpleNamespace(data=data))
    assert client.image_model == "gpt-image-2.5"
    assert client.model == "gpt-6-astra"
    assert client.reasoning_effort == "high"
    assert data == before


@pytest.mark.parametrize("previous", LEGACY)
async def test_api_only_explicit_overrides_are_rejected_before_request(hass, previous):
    assert previous not in IMAGE_MODELS
    with pytest.raises(ValueError):
        validate_image_model(previous)
    with pytest.raises(ValueError):
        _parse_account_form(
            {CONF_IMAGE_MODEL: previous},
            defaults=_account_defaults(),
            fallback_name="Account",
        )
    client = _client(
        hass,
        SimpleNamespace(
            data={CONF_MODEL: "gpt-6-astra", CONF_IMAGE_MODEL: "gpt-image-2.5"}
        ),
    )
    client._async_response = AsyncMock()
    with pytest.raises(RequestValidationError):
        await client.async_create_image_response(
            model="gpt-6-astra", image_model=previous, content=[]
        )
    client._async_response.assert_not_called()


@pytest.mark.parametrize("previous", LEGACY)
async def test_setup_persists_only_the_corrected_image_setting(hass, previous):
    data = {
        CONF_IMAGE_MODEL: previous,
        CONF_MODEL: "gpt-6-astra",
        CONF_REASONING_EFFORT: "high",
        CONF_ACCESS_TOKEN: "test-access",
        CONF_REFRESH_TOKEN: "test-refresh",
        "prompt": "Existing prompt",
        "web_search_include_sources": False,
    }
    entry = MockConfigEntry(domain=DOMAIN, version=14, data=data)
    entry.add_to_hass(hass)
    stop_before_network = SimpleNamespace(
        token_manager=SimpleNamespace(
            async_get_access_token=AsyncMock(
                side_effect=AuthenticationError("Test stop before network")
            )
        )
    )
    with patch(
        "custom_components.openai_oauth_conversation.ChatGPTOAuthClient",
        return_value=stop_before_network,
    ):
        with pytest.raises(ConfigEntryAuthFailed):
            await async_setup_entry(hass, entry)
    assert dict(entry.data) == {**data, CONF_IMAGE_MODEL: "gpt-image-2.5"}
    assert entry.version == 14


@pytest.mark.parametrize("previous", LEGACY)
async def test_reauth_corrects_legacy_image_choice(hass, previous):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Existing account",
        data={
            CONF_MODEL: "gpt-6-astra",
            CONF_IMAGE_MODEL: previous,
            CONF_REASONING_EFFORT: "high",
        },
    )
    flow = ChatGPTOAuthConfigFlow()
    flow.hass = hass
    with (
        patch.object(flow, "_get_reauth_entry", return_value=entry),
        patch.object(
            flow,
            "async_step_auth_manual",
            AsyncMock(return_value={"step_id": "auth_manual"}),
        ),
    ):
        await flow.async_step_reauth(dict(entry.data))
    assert flow._oauth_input[CONF_IMAGE_MODEL] == "gpt-image-2.5"
    assert flow._oauth_input[CONF_MODEL] == "gpt-6-astra"
    assert flow._oauth_input[CONF_REASONING_EFFORT] == "high"


@pytest.mark.parametrize("value", (None, "gpt-image-2", "gpt-image-2.5", "unknown", 5))
def test_correction_does_not_change_other_settings(value):
    assert migrate_legacy_image_model(value) == value
    assert DEFAULT_IMAGE_MODEL == "gpt-image-2"
    assert set(IMAGE_MODELS) == {"gpt-image-2", "gpt-image-2.5"}


@pytest.mark.parametrize("previous", LEGACY)
async def test_saved_legacy_choice_never_sends_api_variant(hass, monkeypatch, previous):
    client = _client(
        hass,
        SimpleNamespace(data={CONF_MODEL: "gpt-6-astra", CONF_IMAGE_MODEL: previous}),
    )
    captured = []
    image_result = object()

    @asynccontextmanager
    async def response(payload, **kwargs):
        captured.append((payload, kwargs))
        yield object()

    async def events(_response):
        yield (
            "response.output_item.done",
            {
                "type": "response.output_item.done",
                "item": {"type": "image_generation_call", "status": "completed"},
            },
        )

    client._async_response = response
    monkeypatch.setattr(client_module, "iter_sse_json", events)
    monkeypatch.setattr(client_module, "decode_image_item", lambda _item: image_result)
    assert (
        await client.async_create_image_response(
            model="gpt-6-astra",
            content=[{"type": "input_text", "text": "Draw a landscape"}],
        )
        is image_result
    )
    assert len(captured) == 1
    payload, options = captured[0]
    assert payload["model"] == "gpt-6-astra"
    assert payload["tools"][0]["model"] == "gpt-image-2.5"
    assert options["responses_lite"] is False
