"""Tests for local-skill entity and area scope enforcement."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Context
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import llm
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openai_oauth_conversation.const import DOMAIN
from custom_components.openai_oauth_conversation.local_skill_runtime import (
    async_resolve_local_skill_scope,
)
from custom_components.openai_oauth_conversation.local_skills import (
    ResolvedLocalSkillPolicy,
)


def _context(
    *,
    user_id: str | None = None,
    assistant: str | None = "conversation",
) -> llm.LLMContext:
    return llm.LLMContext(
        platform=DOMAIN,
        context=Context(user_id=user_id),
        language="en",
        assistant=assistant,
        device_id=None,
    )


def _policy(
    *,
    entities: tuple[str, ...] = (),
    areas: tuple[str, ...] = (),
) -> ResolvedLocalSkillPolicy:
    return ResolvedLocalSkillPolicy(
        allowed_entities=entities,
        allowed_areas=areas,
    )


def _permitted_user() -> SimpleNamespace:
    return SimpleNamespace(
        permissions=SimpleNamespace(check_entity=Mock(return_value=True)),
    )


async def test_no_declared_scope_returns_none(hass) -> None:
    """No scope preserves the profile's normal Home Assistant tool behavior."""
    result = await async_resolve_local_skill_scope(
        hass,
        _policy(),
        _context(),
    )

    assert result is None


async def test_declared_scope_resolving_to_nothing_fails_closed(hass) -> None:
    """An unusable explicit scope is an empty allowlist, never no restriction."""
    result = await async_resolve_local_skill_scope(
        hass,
        _policy(entities=("sensor.does_not_exist",)),
        _context(),
    )

    assert result == frozenset()
    assert result is not None


async def test_missing_selected_pack_fails_closed_without_declared_scope(hass) -> None:
    """An unavailable selected pack is never treated as an unrestricted profile."""
    result = await async_resolve_local_skill_scope(
        hass,
        ResolvedLocalSkillPolicy(missing_skill_ids=("missing",)),
        _context(),
    )

    assert result == frozenset()
    assert result is not None


async def test_size_skipped_selected_pack_fails_closed_without_declared_scope(
    hass,
) -> None:
    """A prose-budget skip cannot silently restore unrestricted profile tools."""
    result = await async_resolve_local_skill_scope(
        hass,
        ResolvedLocalSkillPolicy(skipped_skill_ids=("oversized",)),
        _context(),
    )

    assert result == frozenset()
    assert result is not None


async def test_direct_exposed_readable_entity_is_in_scope(hass) -> None:
    hass.states.async_set("sensor.kitchen_temperature", "72")
    user = _permitted_user()

    with (
        patch(
            "custom_components.openai_oauth_conversation.local_skill_runtime."
            "async_should_expose",
            return_value=True,
        ) as expose,
        patch.object(
            hass.auth,
            "async_get_user",
            AsyncMock(return_value=user),
        ),
    ):
        result = await async_resolve_local_skill_scope(
            hass,
            _policy(entities=("sensor.kitchen_temperature",)),
            _context(user_id="permitted-user"),
        )

    assert result == frozenset({"sensor.kitchen_temperature"})
    expose.assert_called_once_with(
        hass,
        "conversation",
        "sensor.kitchen_temperature",
    )
    user.permissions.check_entity.assert_called_once_with(
        "sensor.kitchen_temperature",
        POLICY_READ,
    )


@pytest.mark.parametrize("request_context", [None, Context()])
async def test_missing_authenticated_user_fails_closed(
    hass,
    request_context: Context | None,
) -> None:
    """Scoped entity data requires an authenticated initiating user."""
    hass.states.async_set("sensor.kitchen_temperature", "72")
    llm_context = llm.LLMContext(
        platform=DOMAIN,
        context=request_context,
        language="en",
        assistant="conversation",
        device_id=None,
    )

    with patch(
        "custom_components.openai_oauth_conversation.local_skill_runtime."
        "async_should_expose",
        return_value=True,
    ):
        result = await async_resolve_local_skill_scope(
            hass,
            _policy(entities=("sensor.kitchen_temperature",)),
            llm_context,
        )

    assert result == frozenset()


async def test_initiating_user_read_permission_is_required(hass) -> None:
    hass.states.async_set("sensor.private_temperature", "72")
    check_entity = Mock(return_value=False)
    user = SimpleNamespace(
        permissions=SimpleNamespace(check_entity=check_entity),
    )

    with (
        patch(
            "custom_components.openai_oauth_conversation.local_skill_runtime."
            "async_should_expose",
            return_value=True,
        ),
        patch.object(
            hass.auth,
            "async_get_user",
            AsyncMock(return_value=user),
        ),
    ):
        result = await async_resolve_local_skill_scope(
            hass,
            _policy(entities=("sensor.private_temperature",)),
            _context(user_id="restricted-user"),
        )

    assert result == frozenset()
    check_entity.assert_called_once_with("sensor.private_temperature", POLICY_READ)


async def test_area_scope_expands_entity_and_device_area_assignments(hass) -> None:
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    kitchen = ar.async_get(hass).async_create(
        "Kitchen",
        aliases={"Cooking Area"},
    )

    entity_registry = er.async_get(hass)
    direct = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "direct-area",
        suggested_object_id="direct_area_sensor",
        config_entry=config_entry,
    )
    entity_registry.async_update_entity(direct.entity_id, area_id=kitchen.id)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "kitchen-device")},
        name="Kitchen device",
    )
    device_registry.async_update_device(device.id, area_id=kitchen.id)
    through_device = entity_registry.async_get_or_create(
        "binary_sensor",
        "test",
        "device-area",
        suggested_object_id="device_area_sensor",
        config_entry=config_entry,
        device_id=device.id,
    )

    hass.states.async_set(direct.entity_id, "10")
    hass.states.async_set(through_device.entity_id, "off")

    with (
        patch(
            "custom_components.openai_oauth_conversation.local_skill_runtime."
            "async_should_expose",
            return_value=True,
        ),
        patch.object(
            hass.auth,
            "async_get_user",
            AsyncMock(return_value=_permitted_user()),
        ),
    ):
        result = await async_resolve_local_skill_scope(
            hass,
            _policy(areas=("cooking area",)),
            _context(user_id="permitted-user"),
        )

    assert result == frozenset({direct.entity_id, through_device.entity_id})


async def test_unavailable_and_unexposed_entities_are_excluded(hass) -> None:
    unavailable = "sensor.unavailable_temperature"
    unexposed = "sensor.unexposed_temperature"
    hass.states.async_set(unavailable, STATE_UNAVAILABLE)
    hass.states.async_set(unexposed, "72")

    with (
        patch(
            "custom_components.openai_oauth_conversation.local_skill_runtime."
            "async_should_expose",
            side_effect=lambda _hass, _assistant, entity_id: entity_id != unexposed,
        ),
        patch.object(
            hass.auth,
            "async_get_user",
            AsyncMock(return_value=_permitted_user()),
        ),
    ):
        result = await async_resolve_local_skill_scope(
            hass,
            _policy(entities=(unavailable, unexposed)),
            _context(user_id="permitted-user"),
        )

    assert result == frozenset()
