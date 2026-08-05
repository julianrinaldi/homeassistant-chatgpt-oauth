"""Tests for backward-compatible config-entry migration."""
from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openai_oauth_conversation import async_migrate_entry
from custom_components.openai_oauth_conversation.const import (
    CONF_ACCESS_TOKEN,
    CONF_ENABLE_HASS_CONTROL,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_REASONING_EFFORT,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    LEGACY_OUTPUT_LIMIT_KEY,
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
    assert entry.version == 6
    assert entry.unique_id == "account-123"
    assert entry.data[CONF_ACCESS_TOKEN] == "access"
    assert entry.data[CONF_REFRESH_TOKEN] == "refresh"
    assert entry.data[CONF_MODEL] == "gpt-5.6-sol"
    assert entry.data[CONF_REASONING_EFFORT] == "low"
    assert entry.data[CONF_ENABLE_HASS_CONTROL] is True
    assert LEGACY_OUTPUT_LIMIT_KEY not in entry.data
