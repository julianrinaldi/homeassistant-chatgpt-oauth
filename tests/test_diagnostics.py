"""Tests for redacted integration diagnostics."""
from __future__ import annotations

import json

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openai_oauth_conversation.const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_ID,
    CONF_EXPIRES,
    CONF_ENABLE_HASS_CONTROL,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_REASONING_EFFORT,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from custom_components.openai_oauth_conversation.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_exclude_sensitive_and_user_content(hass) -> None:
    """Tokens, account identifiers, and prompts never enter diagnostics."""
    secrets = {
        CONF_ACCESS_TOKEN: "access-secret-value",
        CONF_REFRESH_TOKEN: "refresh-secret-value",
        CONF_ACCOUNT_ID: "private-account-id",
        CONF_PROMPT: "private prompt text",
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Primary account",
        version=6,
        data={
            **secrets,
            CONF_EXPIRES: 4_000_000_000_000,
            CONF_ENABLE_HASS_CONTROL: False,
            CONF_MODEL: "gpt-5.6-terra",
            CONF_REASONING_EFFORT: "high",
        },
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    serialized = json.dumps(diagnostics)
    for value in secrets.values():
        assert value not in serialized
    assert diagnostics["config_entry"]["home_assistant_control_enabled"] is False
    assert diagnostics["model"]["slug"] == "gpt-5.6-terra"
    assert diagnostics["model"]["thinking_level"] == "high"
