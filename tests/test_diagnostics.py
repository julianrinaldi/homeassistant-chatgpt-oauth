"""Tests for redacted integration diagnostics."""

from __future__ import annotations

import json

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openai_oauth_conversation.const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_ID,
    CONF_ENABLE_HASS_CONTROL,
    CONF_EXPIRES,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_REASONING_EFFORT,
    CONF_REFRESH_TOKEN,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_INCLUDE_SOURCES,
    CONF_WEB_SEARCH_LIVE_ACCESS,
    CONF_WEB_SEARCH_MODE,
    CONF_WEB_SEARCH_USE_HASS_LOCATION,
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
        version=8,
        data={
            **secrets,
            CONF_EXPIRES: 4_000_000_000_000,
            CONF_ENABLE_HASS_CONTROL: False,
            CONF_MODEL: "gpt-5.6-terra",
            CONF_REASONING_EFFORT: "high",
            CONF_WEB_SEARCH_MODE: "required",
            CONF_WEB_SEARCH_CONTEXT_SIZE: "high",
            CONF_WEB_SEARCH_INCLUDE_SOURCES: False,
            CONF_WEB_SEARCH_LIVE_ACCESS: False,
            CONF_WEB_SEARCH_USE_HASS_LOCATION: True,
        },
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    serialized = json.dumps(diagnostics)
    for value in secrets.values():
        assert value not in serialized
    assert diagnostics["config_entry"]["assistant_profile_count"] == 1
    profile = diagnostics["assistant_profiles"][0]
    assert profile["profile_type"] == "default"
    assert profile["home_assistant_control_enabled"] is False
    assert profile["model"]["slug"] == "gpt-5.6-terra"
    assert profile["model"]["thinking_level"] == "high"
    assert profile["model"]["supports_web_search"] is True
    assert profile["web_search"] == {
        "mode": "required",
        "context_size": "high",
        "includes_sources_in_response_text": False,
        "live_access": False,
        "uses_home_assistant_location": True,
        "location_detail": "country_and_timezone_only",
    }
