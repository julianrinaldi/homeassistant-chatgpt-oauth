"""Tests for privacy-filtered user, satellite, and room context."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components import conversation
from homeassistant.core import Context
from homeassistant.helpers import (
    area_registry as ar,
)
from homeassistant.helpers import (
    device_registry as dr,
)
from homeassistant.helpers import (
    entity_registry as er,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser

from custom_components.openai_oauth_conversation.request_context import (
    async_resolve_request_context,
)


async def test_opt_in_context_uses_display_labels_and_exposed_room_entities(
    hass,
) -> None:
    """Model context contains useful labels but no Home Assistant identifiers."""
    user = MockUser(
        id="private-user-id",
        name="Julian Rinaldi",
        is_owner=True,
    ).add_to_hass(hass)
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    area = ar.async_get(hass).async_create("Kitchen")
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "satellite-device")},
        name="Voice Preview Edition",
    )
    device_registry.async_update_device(device.id, area_id=area.id)

    entity_registry = er.async_get(hass)
    satellite = entity_registry.async_get_or_create(
        "assist_satellite",
        "test",
        "satellite",
        suggested_object_id="kitchen_satellite",
        device_id=device.id,
        original_name="Kitchen Satellite",
    )
    light = entity_registry.async_get_or_create(
        "light",
        "test",
        "ceiling-light",
        suggested_object_id="kitchen_ceiling",
        device_id=device.id,
        original_name="Kitchen Ceiling",
    )
    hass.states.async_set(
        satellite.entity_id,
        "idle",
        {"friendly_name": "Kitchen Voice Satellite"},
    )
    hass.states.async_set(
        light.entity_id,
        "on",
        {"friendly_name": "Ceiling Lights"},
    )

    user_input = conversation.ConversationInput(
        text="Turn the lights off in here",
        context=Context(user_id=user.id),
        conversation_id="conversation-123",
        device_id=None,
        satellite_id=satellite.entity_id,
        language="en",
        agent_id="conversation.chatgpt_oauth",
    )
    settings = SimpleNamespace(
        include_user_context=True,
        include_satellite_room_context=True,
        include_room_entities=True,
    )

    with patch(
        "custom_components.openai_oauth_conversation.request_context."
        "async_should_expose",
        return_value=True,
    ):
        resolved = await async_resolve_request_context(hass, user_input, settings)

    assert resolved.user_display_name == "Julian Rinaldi"
    assert resolved.satellite_display_name == "Kitchen Voice Satellite"
    assert resolved.device_display_name == "Voice Preview Edition"
    assert resolved.area_display_name == "Kitchen"
    assert resolved.room_entities == (
        {"name": "Ceiling Lights", "kind": "light", "state": "on"},
    )
    assert resolved.satellite_device_id == device.id
    assert resolved.area_id == area.id

    instructions = resolved.model_instructions
    assert instructions is not None
    assert "Julian Rinaldi" in instructions
    assert "Kitchen Voice Satellite" in instructions
    assert "Ceiling Lights" in instructions
    assert user.id not in instructions
    assert device.id not in instructions
    assert area.id not in instructions
    assert satellite.entity_id not in instructions

    with patch(
        "custom_components.openai_oauth_conversation.request_context."
        "async_should_expose",
        return_value=True,
    ):
        scoped = await async_resolve_request_context(
            hass,
            user_input,
            settings,
            allowed_entity_ids=frozenset(),
        )

    assert scoped.room_entities == ()

    check_entity = Mock(return_value=False)
    restricted_user = SimpleNamespace(
        name="Restricted User",
        permissions=SimpleNamespace(check_entity=check_entity),
    )
    with (
        patch(
            "custom_components.openai_oauth_conversation.request_context."
            "async_should_expose",
            return_value=True,
        ),
        patch.object(
            hass.auth,
            "async_get_user",
            AsyncMock(return_value=restricted_user),
        ),
    ):
        restricted = await async_resolve_request_context(
            hass,
            user_input,
            settings,
        )

    assert restricted.user_display_name == "Restricted User"
    assert restricted.room_entities == ()
    check_entity.assert_called_once_with(light.entity_id, POLICY_READ)

    anonymous_input = conversation.ConversationInput(
        text="What is happening in here?",
        context=Context(),
        conversation_id="conversation-anonymous",
        device_id=None,
        satellite_id=satellite.entity_id,
        language="en",
        agent_id="conversation.chatgpt_oauth",
    )
    with patch(
        "custom_components.openai_oauth_conversation.request_context."
        "async_should_expose",
        return_value=True,
    ):
        anonymous = await async_resolve_request_context(
            hass,
            anonymous_input,
            settings,
        )

    assert anonymous.room_entities == ()


async def test_context_is_not_sent_without_opt_in(hass) -> None:
    """Local event routing can resolve IDs while the model receives nothing."""
    area = ar.async_get(hass).async_create("Bedroom")
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "bedroom-satellite")},
        name="Bedroom Satellite",
    )
    device_registry.async_update_device(device.id, area_id=area.id)
    satellite = er.async_get(hass).async_get_or_create(
        "assist_satellite",
        "test",
        "bedroom",
        suggested_object_id="bedroom_satellite",
        device_id=device.id,
        original_name="Bedroom Satellite",
    )
    resolved = await async_resolve_request_context(
        hass,
        conversation.ConversationInput(
            text="Hello",
            context=Context(),
            conversation_id=None,
            device_id=None,
            satellite_id=satellite.entity_id,
            language="en",
            agent_id="conversation.chatgpt_oauth",
        ),
        SimpleNamespace(
            include_user_context=False,
            include_satellite_room_context=False,
            include_room_entities=False,
        ),
    )

    assert resolved.model_instructions is None
    assert resolved.satellite_device_id == device.id
    assert resolved.area_id == area.id
