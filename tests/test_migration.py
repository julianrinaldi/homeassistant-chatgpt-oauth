"""Tests for backward-compatible config-entry migration."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openai_oauth_conversation import async_migrate_entry
from custom_components.openai_oauth_conversation.const import (
    CONF_ACCESS_TOKEN,
    CONF_ENABLE_AI_MEDIA_TOOLS,
    CONF_ENABLE_HASS_CONTROL,
    CONF_ENABLE_HISTORY_TOOLS,
    CONF_ENABLE_SCHEDULED_ACTIONS,
    CONF_ENABLED_LOCAL_SKILLS,
    CONF_INCLUDE_ROOM_ENTITIES,
    CONF_INCLUDE_SATELLITE_ROOM_CONTEXT,
    CONF_INCLUDE_USER_CONTEXT,
    CONF_MAX_TOOL_CALLS,
    CONF_MAX_TOOL_TIME,
    CONF_MEMORY_MAX_CHARACTERS,
    CONF_MEMORY_MAX_TURNS,
    CONF_MEMORY_MODE,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_PROMPT_TEMPLATE_ENTITIES,
    CONF_REASONING_EFFORT,
    CONF_REFRESH_TOKEN,
    CONF_SELECTED_SCRIPT_ENTITIES,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_INCLUDE_SOURCES,
    CONF_WEB_SEARCH_LIVE_ACCESS,
    CONF_WEB_SEARCH_MODE,
    CONF_WEB_SEARCH_USE_HASS_LOCATION,
    CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION,
    DOMAIN,
    LEGACY_OUTPUT_LIMIT_KEY,
    MIGRATED_MEMORY_MAX_CHARACTERS,
    MIGRATED_MEMORY_MODE,
)


async def test_migration_preserves_entry_and_removes_obsolete_field(hass) -> None:
    """Pre-v1 entries retain credentials and receive normalized settings."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=4,
        title="Existing account",
        unique_id="account-123",
        data={
            CONF_ACCESS_TOKEN: "access",
            CONF_REFRESH_TOKEN: "refresh",
            CONF_MODEL: "gpt-5.6",
            CONF_PROMPT: "Existing prompt",
            LEGACY_OUTPUT_LIMIT_KEY: 1000,
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    assert entry.version == 14
    assert entry.unique_id == "account-123"
    assert entry.data[CONF_ACCESS_TOKEN] == "access"
    assert entry.data[CONF_REFRESH_TOKEN] == "refresh"
    assert entry.data[CONF_MODEL] == "gpt-5.6-sol"
    assert entry.data[CONF_REASONING_EFFORT] == "low"
    assert entry.data[CONF_ENABLE_HASS_CONTROL] is True
    assert entry.data[CONF_ENABLE_AI_MEDIA_TOOLS] is False
    assert entry.data[CONF_ENABLE_HISTORY_TOOLS] is False
    assert entry.data[CONF_ENABLE_SCHEDULED_ACTIONS] is False
    assert entry.data[CONF_SELECTED_SCRIPT_ENTITIES] == []
    assert entry.data[CONF_ENABLED_LOCAL_SKILLS] == []
    assert entry.data[CONF_PROMPT_TEMPLATE_ENTITIES] == []
    assert entry.data[CONF_INCLUDE_USER_CONTEXT] is False
    assert entry.data[CONF_INCLUDE_SATELLITE_ROOM_CONTEXT] is False
    assert entry.data[CONF_INCLUDE_ROOM_ENTITIES] is False
    assert entry.data[CONF_MAX_TOOL_CALLS] == 5
    assert entry.data[CONF_MAX_TOOL_TIME] == 60
    assert entry.data[CONF_MEMORY_MODE] == MIGRATED_MEMORY_MODE
    assert entry.data[CONF_MEMORY_MAX_TURNS] == 12
    assert entry.data[CONF_MEMORY_MAX_CHARACTERS] == MIGRATED_MEMORY_MAX_CHARACTERS
    assert entry.data[CONF_WEB_SEARCH_MODE] == "disabled"
    assert entry.data[CONF_WEB_SEARCH_CONTEXT_SIZE] == "medium"
    assert entry.data[CONF_WEB_SEARCH_INCLUDE_SOURCES] is False
    assert entry.data[CONF_WEB_SEARCH_LIVE_ACCESS] is True
    assert entry.data[CONF_WEB_SEARCH_USE_HASS_LOCATION] is False
    assert entry.data[CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION] is False
    assert LEGACY_OUTPUT_LIMIT_KEY not in entry.data


async def test_migration_resets_invalid_web_search_settings(hass) -> None:
    """Invalid manually edited search settings cannot block an upgrade."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        title="Invalid settings",
        data={
            CONF_ACCESS_TOKEN: "access",
            CONF_REFRESH_TOKEN: "refresh",
            CONF_MODEL: "gpt-5.6-terra",
            CONF_WEB_SEARCH_MODE: "sometimes",
            CONF_WEB_SEARCH_CONTEXT_SIZE: "enormous",
            CONF_WEB_SEARCH_INCLUDE_SOURCES: "true",
            CONF_WEB_SEARCH_LIVE_ACCESS: "false",
            CONF_WEB_SEARCH_USE_HASS_LOCATION: 1,
            CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION: "true",
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    assert entry.data[CONF_WEB_SEARCH_MODE] == "disabled"
    assert entry.data[CONF_WEB_SEARCH_CONTEXT_SIZE] == "medium"
    assert entry.data[CONF_WEB_SEARCH_INCLUDE_SOURCES] is False
    assert entry.data[CONF_WEB_SEARCH_LIVE_ACCESS] is True
    assert entry.data[CONF_WEB_SEARCH_USE_HASS_LOCATION] is False
    assert entry.data[CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION] is False


async def test_migration_keeps_existing_subentries_opted_out(hass) -> None:
    """New profile capabilities do not later leak in from the parent profile."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=13,
        title="Account",
        data={
            CONF_ACCESS_TOKEN: "access",
            CONF_REFRESH_TOKEN: "refresh",
            CONF_MODEL: "gpt-5.6-terra",
        },
        subentries_data=(
            {
                "subentry_type": "assistant",
                "title": "Private assistant",
                "unique_id": None,
                "data": {CONF_MODEL: "gpt-5.6-terra"},
            },
        ),
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    subentry = next(iter(entry.subentries.values()))
    assert subentry.data[CONF_ENABLE_SCHEDULED_ACTIONS] is False
    assert subentry.data[CONF_ENABLED_LOCAL_SKILLS] == []
