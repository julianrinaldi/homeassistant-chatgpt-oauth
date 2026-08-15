"""Tests for explicitly selected, strongly typed Home Assistant script tools."""

from __future__ import annotations

from types import SimpleNamespace

from homeassistant.core import Context, SupportsResponse
from homeassistant.helpers import llm
import pytest
import voluptuous as vol
from voluptuous_openapi import convert

from custom_components.openai_oauth_conversation.const import DOMAIN
from custom_components.openai_oauth_conversation.script_tools import (
    SelectedScriptsAPI,
)


def _context() -> llm.LLMContext:
    return llm.LLMContext(
        platform=DOMAIN,
        context=Context(),
        language="en",
        assistant="conversation",
        device_id=None,
    )


async def test_selected_script_is_exposed_with_validated_fields(hass) -> None:
    """Only the selected predetermined script becomes a typed LLM tool."""
    entity = SimpleNamespace(
        entity_id="script.movie_night",
        unique_id="movie_night",
        name="Movie Night",
        description="Prepare the living room for a movie.",
        fields={
            "brightness": {
                "description": "Living-room brightness percentage",
                "required": True,
                "selector": {"number": {"min": 1, "max": 100, "step": 1}},
            },
            "mode": {
                "required": False,
                "selector": {"select": {"options": ["cinema", "sports", "quiet"]}},
            },
        },
    )
    hass.data["script"] = SimpleNamespace(
        get_entity=lambda entity_id: entity if entity_id == entity.entity_id else None
    )
    hass.states.async_set(
        entity.entity_id,
        "off",
        {"friendly_name": "Living Room Movie Night"},
    )

    async def run_script(call):
        return {"brightness": call.data["brightness"], "ready": True}

    hass.services.async_register(
        "script",
        "movie_night",
        run_script,
        schema=vol.Schema(dict),
        supports_response=SupportsResponse.OPTIONAL,
    )
    api = SelectedScriptsAPI(
        hass=hass,
        profile_id="primary",
        script_entity_ids=(entity.entity_id, "script.not_selected"),
        base_api_ids=None,
    )

    instance = await api.async_get_api_instance(_context())

    assert len(instance.tools) == 1
    tool = instance.tools[0]
    assert len(tool.name) <= 64
    assert "Living Room Movie Night" in tool.description
    converted = convert(tool.parameters, custom_serializer=llm.selector_serializer)
    assert converted["required"] == ["brightness"]
    assert converted["properties"]["brightness"]["minimum"] == 1
    assert converted["properties"]["brightness"]["maximum"] == 100
    assert converted["properties"]["mode"]["enum"] == [
        "cinema",
        "sports",
        "quiet",
    ]

    result = await instance.async_call_tool(
        llm.ToolInput(
            tool_name=tool.name,
            tool_args={"brightness": 20, "mode": "cinema"},
        )
    )

    assert result == {
        "success": True,
        "script": "Living Room Movie Night",
        "response": {"brightness": 20, "ready": True},
    }
    with pytest.raises(vol.Invalid):
        await instance.async_call_tool(
            llm.ToolInput(
                tool_name=tool.name,
                tool_args={"brightness": 101},
            )
        )


async def test_selected_script_tool_rejects_undeclared_arguments(hass) -> None:
    """The model cannot smuggle arbitrary service data into a selected script."""
    entity = SimpleNamespace(
        entity_id="script.safe_scene",
        unique_id="safe_scene",
        name="Safe Scene",
        description="",
        fields={},
    )
    hass.data["script"] = SimpleNamespace(get_entity=lambda _entity_id: entity)
    hass.services.async_register(
        "script",
        "safe_scene",
        lambda _call: None,
    )
    instance = await SelectedScriptsAPI(
        hass=hass,
        profile_id="primary",
        script_entity_ids=(entity.entity_id,),
        base_api_ids=None,
    ).async_get_api_instance(_context())

    with pytest.raises(vol.Invalid):
        await instance.async_call_tool(
            llm.ToolInput(
                tool_name=instance.tools[0].name,
                tool_args={"entity_id": "lock.front_door"},
            )
        )
