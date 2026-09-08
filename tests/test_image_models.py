"""Image renderer selection stays separate from Assist's reasoning model."""

from __future__ import annotations

import asyncio
import base64
from contextlib import asynccontextmanager
import json
from pathlib import Path
import struct
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.exceptions import ServiceValidationError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from custom_components.openai_oauth_conversation import client as client_module
from custom_components.openai_oauth_conversation.ai_task import ChatGPTOAuthTaskEntity
from custom_components.openai_oauth_conversation.client import (
    ChatGPTOAuthClient,
    build_turn_payload,
    serialize_request_payload,
)
from custom_components.openai_oauth_conversation.config_flow import (
    ChatGPTOAuthConfigFlow,
    _account_defaults,
    _account_schema,
    _model_schema,
    _parse_account_form,
    _profile_schema,
)
from custom_components.openai_oauth_conversation.const import (
    CONF_ACCESS_TOKEN,
    CONF_IMAGE_MODEL,
    CONF_MODEL,
    CONF_REASONING_EFFORT,
    CONF_REFRESH_TOKEN,
    DEFAULT_IMAGE_MODEL,
    DEFAULT_MODEL,
    DOMAIN,
    MAX_IMAGE_ATTACHMENTS,
)
from custom_components.openai_oauth_conversation.exceptions import (
    RequestValidationError,
)
from custom_components.openai_oauth_conversation.image_models import (
    IMAGE_MODELS,
    SUPPORTED_IMAGE_MODELS,
    validate_image_model,
)
from custom_components.openai_oauth_conversation.models import MODEL_PROFILES
from custom_components.openai_oauth_conversation.responses import ChatGPTImageResponse

ASTRA = "gpt-6-astra"
PNG = (
    b"\x89PNG\r\n\x1a\n"
    + b"\x00\x00\x00\rIHDR"
    + struct.pack(">II", 1024, 1024)
    + b"\x08\x06\x00\x00\x00"
)


def _client(hass, image_model: str | None = None) -> ChatGPTOAuthClient:
    client = object.__new__(ChatGPTOAuthClient)
    client.hass = hass
    data = {CONF_MODEL: ASTRA, CONF_REASONING_EFFORT: "low"}
    if image_model is not None:
        data[CONF_IMAGE_MODEL] = image_model
    client.entry = SimpleNamespace(data=data)
    return client


def _events(monkeypatch, *, reported_model: str | None = None):
    async def events(_response):
        yield (
            "response.output_item.done",
            {
                "type": "response.output_item.done",
                "item": {
                    "type": "image_generation_call",
                    "status": "completed",
                    "model": reported_model,
                    "result": base64.b64encode(PNG).decode("ascii"),
                    "output_format": "png",
                    "size": "1024x1024",
                },
            },
        )

    monkeypatch.setattr(client_module, "iter_sse_json", events)


def test_catalog_has_only_the_three_requested_renderers() -> None:
    assert SUPPORTED_IMAGE_MODELS == (
        "gpt-image-2",
        "gpt-image-2.5-flare",
        "gpt-image-2.5-sunburst",
    )
    assert not set(IMAGE_MODELS) & set(MODEL_PROFILES)
    assert DEFAULT_IMAGE_MODEL == "gpt-image-2"
    assert DEFAULT_MODEL == "gpt-5.6-terra"


@pytest.mark.parametrize("model", SUPPORTED_IMAGE_MODELS)
def test_account_form_and_validation(model: str) -> None:
    defaults = _account_defaults({CONF_IMAGE_MODEL: model, CONF_MODEL: ASTRA})
    fields = _account_schema(defaults, name_default="Account").schema
    image_validator = fields[CONF_IMAGE_MODEL]
    assert image_validator(model) == model
    assert validate_image_model(f" {model.upper()} ") == model
    assert (
        CONF_IMAGE_MODEL
        not in _profile_schema(defaults, name_default="Voice profile").schema
    )
    with pytest.raises(vol.Invalid):
        _model_schema(ASTRA)(model)
    _, saved = _parse_account_form(
        {CONF_IMAGE_MODEL: model}, defaults=defaults, fallback_name="Account"
    )
    assert saved[CONF_IMAGE_MODEL] == model
    assert saved[CONF_MODEL] == ASTRA
    _, resaved = _parse_account_form(
        {}, defaults=_account_defaults(saved), fallback_name="Account"
    )
    assert resaved[CONF_IMAGE_MODEL] == model


@pytest.mark.parametrize(
    "invalid", [None, 5, "", "auto", "gpt-6-astra", "flare-unknown"]
)
def test_invalid_image_models_are_not_silently_replaced(invalid) -> None:
    with pytest.raises(ValueError):
        validate_image_model(invalid)
    with pytest.raises(ValueError):
        _parse_account_form(
            {CONF_IMAGE_MODEL: invalid},
            defaults=_account_defaults(),
            fallback_name="Account",
        )


def test_existing_accounts_default_to_image_2(hass) -> None:
    client = _client(hass)
    assert client.image_model == DEFAULT_IMAGE_MODEL
    assert client.model == ASTRA
    assert client.entry.data == {CONF_MODEL: ASTRA, CONF_REASONING_EFFORT: "low"}
    assert _account_defaults()[CONF_IMAGE_MODEL] == DEFAULT_IMAGE_MODEL


@pytest.mark.parametrize("model", SUPPORTED_IMAGE_MODELS)
@pytest.mark.parametrize("image_count", [0, 10])
@pytest.mark.parametrize("reasoning_model", [ASTRA, "gpt-5.6-terra"])
async def test_actual_request_and_image_decoding(
    hass, monkeypatch, model: str, image_count: int, reasoning_model: str
) -> None:
    """Exercise real payload construction, serialization, and image decoding."""
    client = _client(hass, model)
    calls = []

    @asynccontextmanager
    async def response(payload, **kwargs):
        calls.append((json.loads(serialize_request_payload(payload)), kwargs))
        yield object()

    client._async_response = response
    _events(monkeypatch, reported_model=model)
    content = [{"type": "input_text", "text": "An album cover: café 🏠"}]
    content.extend(
        {"type": "input_image", "image_url": "data:image/png;base64," + "A" * 160000}
        for _ in range(image_count)
    )
    result = await client.async_create_image_response(
        model=reasoning_model, reasoning_effort="high", content=content
    )
    assert result.image_data == PNG
    assert result.model == model
    assert (result.width, result.height) == (1024, 1024)
    assert len(calls) == 1
    payload, options = calls[0]
    assert payload["model"] == reasoning_model
    assert payload["reasoning"] == {"effort": "high"}
    assert payload["tools"] == [
        {
            "type": "image_generation",
            "model": model,
            "output_format": "png",
            "size": "auto",
            "quality": "auto",
            "background": "auto",
            "partial_images": 0,
        }
    ]
    assert payload["tool_choice"] == {"type": "image_generation"}
    assert payload["input"][0]["content"] == content
    assert payload["store"] is False
    assert payload["stream"] is True
    assert options["responses_lite"] is False
    assert "max_output_tokens" not in payload
    assert CONF_IMAGE_MODEL not in payload


async def test_concurrent_request_overrides_are_isolated(hass, monkeypatch) -> None:
    client = _client(hass, DEFAULT_IMAGE_MODEL)
    captured = []

    @asynccontextmanager
    async def response(payload, **_kwargs):
        await asyncio.sleep(0)
        captured.append(payload["tools"][0]["model"])
        yield object()

    client._async_response = response
    _events(monkeypatch)
    await asyncio.gather(
        *(
            client.async_create_image_response(
                model=ASTRA,
                image_model=model,
                content=[{"type": "input_text", "text": "Create artwork"}],
            )
            for model in SUPPORTED_IMAGE_MODELS
        )
    )
    assert set(captured) == set(SUPPORTED_IMAGE_MODELS)
    assert client.image_model == DEFAULT_IMAGE_MODEL
    assert client.model == ASTRA


@pytest.mark.parametrize("model", SUPPORTED_IMAGE_MODELS)
async def test_rejected_model_is_not_removed_or_substituted(hass, model: str) -> None:
    client = _client(hass, model)
    called = []

    @asynccontextmanager
    async def response(payload, **_kwargs):
        called.append(payload)
        raise RequestValidationError("Unsupported image generation model")
        yield  # pragma: no cover

    client._async_response = response
    with pytest.raises(RequestValidationError, match="Unsupported image generation"):
        await client.async_create_image_response(
            model=ASTRA, content=[{"type": "input_text", "text": "Create artwork"}]
        )
    assert len(called) == 1
    assert called[0]["tools"][0]["model"] == model


async def test_direct_client_also_enforces_ten_references(hass) -> None:
    client = _client(hass)
    with pytest.raises(RequestValidationError, match="at most 10"):
        await client.async_create_image_response(
            model=ASTRA,
            content=[{"type": "input_image"}] * (MAX_IMAGE_ATTACHMENTS + 1),
        )


@pytest.mark.parametrize("model", SUPPORTED_IMAGE_MODELS)
@pytest.mark.parametrize("reported_model", [None, "backend-reported-model"])
async def test_native_ai_task_uses_renderer_and_correct_metadata(
    hass, model: str, reported_model: str | None
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Account", data={CONF_MODEL: ASTRA})
    client = _client(hass, model)
    client.async_create_image_response = AsyncMock(
        return_value=ChatGPTImageResponse(
            image_data=PNG,
            mime_type="image/png",
            width=1024,
            height=1024,
            model=reported_model,
        )
    )
    entry.runtime_data = client
    entity = ChatGPTOAuthTaskEntity(entry)
    entity.hass = hass
    result = await entity._async_generate_image(
        SimpleNamespace(instructions="Draw a square album cover", attachments=[]),
        SimpleNamespace(conversation_id="image-test"),
    )
    args = client.async_create_image_response.await_args.kwargs
    assert args["model"] == ASTRA
    assert args["image_model"] == model
    assert result.model == (reported_model or model)
    assert result.conversation_id == "image-test"
    assert result.image_data == PNG
    assert entity.extra_state_attributes["configured_image_model"] == model
    assert entity.unique_id == f"{entry.entry_id}_image_generation"


async def test_native_ai_task_rejects_invalid_image_configuration(hass) -> None:
    client = _client(hass, "not-a-renderer")
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.runtime_data = client
    entity = ChatGPTOAuthTaskEntity(entry)
    entity.hass = hass
    with pytest.raises(ServiceValidationError, match="Unsupported image generation"):
        await entity._async_generate_image(
            SimpleNamespace(instructions="Draw artwork", attachments=[]),
            SimpleNamespace(conversation_id="test"),
        )


@pytest.mark.parametrize("model", SUPPORTED_IMAGE_MODELS)
async def test_account_reconfiguration_persists_selection(hass, model: str) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=ChatGPTOAuthConfigFlow.VERSION,
        title="Account",
        data={
            CONF_MODEL: ASTRA,
            CONF_REASONING_EFFORT: "high",
            CONF_ACCESS_TOKEN: "test-access",
            CONF_REFRESH_TOKEN: "test-refresh",
        },
    )
    entry.add_to_hass(hass)
    with (
        patch("homeassistant.config_entries.async_process_deps_reqs", AsyncMock()),
        patch("homeassistant.config_entries.ConfigEntries.async_reload", AsyncMock()),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        assert CONF_IMAGE_MODEL in result["data_schema"].schema
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IMAGE_MODEL: model}
        )
        assert result["step_id"] == "reconfigure_reasoning"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_REASONING_EFFORT: "high"}
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert entry.data[CONF_IMAGE_MODEL] == model
    assert entry.data[CONF_MODEL] == ASTRA
    assert entry.data[CONF_ACCESS_TOKEN] == "test-access"
    assert entry.data[CONF_REFRESH_TOKEN] == "test-refresh"


@pytest.mark.parametrize("model", SUPPORTED_IMAGE_MODELS)
async def test_reauthentication_keeps_renderer(hass, model: str) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Account",
        data={
            CONF_MODEL: ASTRA,
            CONF_IMAGE_MODEL: model,
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
    assert flow._oauth_input[CONF_IMAGE_MODEL] == model
    assert flow._oauth_input[CONF_MODEL] == ASTRA
    assert flow._oauth_input[CONF_REASONING_EFFORT] == "high"


def test_image_setting_is_not_sent_in_text_requests() -> None:
    payload, _ = build_turn_payload(
        model=ASTRA,
        instructions="Answer briefly",
        input_items=[{"role": "user", "content": "Hello"}],
        reasoning_effort="low",
    )
    assert payload["model"] == ASTRA
    assert "gpt-image-" not in json.dumps(payload)


def test_renderer_translations_are_account_only() -> None:
    root = Path(client_module.__file__).parent
    strings = json.loads((root / "strings.json").read_text())
    assert strings == json.loads((root / "translations/en.json").read_text())
    for step in ("user", "reconfigure"):
        account = strings["config"]["step"][step]
        assert account["data"][CONF_IMAGE_MODEL] == "Image generation model"
        assert "separate" in account["data_description"][CONF_IMAGE_MODEL]
        assert (
            CONF_IMAGE_MODEL
            not in strings["config_subentries"]["assistant"]["step"][step]["data"]
        )
