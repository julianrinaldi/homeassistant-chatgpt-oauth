"""Tests for the public setup flow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.helpers import translation
import pytest
from yarl import URL

from custom_components.openai_oauth_conversation.auth import OAuthTokenData
from custom_components.openai_oauth_conversation.config_flow import _parse_profile_form
from custom_components.openai_oauth_conversation.const import (
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
    CONF_SELECTED_SCRIPT_ENTITIES,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_INCLUDE_SOURCES,
    CONF_WEB_SEARCH_LIVE_ACCESS,
    CONF_WEB_SEARCH_MODE,
    CONF_WEB_SEARCH_USE_HASS_LOCATION,
    CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION,
    DOMAIN,
    MAX_ENABLED_LOCAL_SKILLS,
)
from custom_components.openai_oauth_conversation.profiles import profile_data_defaults


def _write_test_skill(skills_path: Path) -> None:
    """Create one local skill outside Home Assistant's event loop."""
    skills_path.mkdir(parents=True, exist_ok=True)
    (skills_path / "energy_analyst.toml").write_text(
        'schema_version = 1\nname = "Energy Analyst"\n'
        'instructions = "Explain measured energy use."\n',
        encoding="utf-8",
    )


def test_profile_form_rejects_too_many_local_skills() -> None:
    """The UI cannot silently truncate restrictive selected packs."""
    defaults = profile_data_defaults()

    with pytest.raises(ValueError, match="At most"):
        _parse_profile_form(
            {
                CONF_ENABLED_LOCAL_SKILLS: [
                    f"skill_{index}" for index in range(MAX_ENABLED_LOCAL_SKILLS + 1)
                ]
            },
            defaults=defaults,
            fallback_name="Assistant",
        )


async def test_english_profile_translations(hass) -> None:
    """Human-readable labels and help text load for both profile flows."""
    config = await translation.async_get_translations(
        hass,
        "en",
        "config",
        {DOMAIN},
    )
    subentries = await translation.async_get_translations(
        hass,
        "en",
        "config_subentries",
        {DOMAIN},
    )

    assert (
        config[f"component.{DOMAIN}.config.step.reconfigure.data.enable_history_tools"]
        == "Use Home Assistant history"
    )
    assert config[
        f"component.{DOMAIN}.config.step.reconfigure.data_description."
        "enable_history_tools"
    ].startswith("Allows this assistant to answer questions about past states")
    assert (
        config[f"component.{DOMAIN}.config.step.reconfigure.data.enable_ai_media_tools"]
        == "Let Assist analyze cameras and create images"
    )
    assert config[
        f"component.{DOMAIN}.config.step.reconfigure.data_description."
        "enable_ai_media_tools"
    ].startswith("Lets this assistant use ChatGPT OAuth AI Task")
    assert (
        config[f"component.{DOMAIN}.config.step.reconfigure.data.selected_script_tools"]
        == "Scripts this assistant may run"
    )
    assert (
        config[f"component.{DOMAIN}.config.step.reconfigure.data.enabled_local_skills"]
        == "Local skill packs"
    )
    assert (
        config[
            f"component.{DOMAIN}.config.step.reconfigure.data.enable_scheduled_actions"
        ]
        == "Allow reminders and scheduled actions"
    )
    assert subentries[
        f"component.{DOMAIN}.config_subentries.assistant.step.reconfigure."
        "data_description.prompt_template_entities"
    ].startswith("Allows restricted states()")
    assert (
        subentries[
            f"component.{DOMAIN}.config_subentries.assistant.step.reconfigure.data."
            "memory_mode"
        ]
        == "What should this assistant remember?"
    )
    assert subentries[
        f"component.{DOMAIN}.config_subentries.assistant.step.reconfigure."
        "data_description.web_search_include_sources"
    ].startswith("Adds clickable source links")
    assert (
        subentries[
            f"component.{DOMAIN}.config_subentries.assistant.step.reconfigure.data."
            "web_search_use_home_assistant_precise_location"
        ]
        == "Share precise home location"
    )
    assert (
        config[
            f"component.{DOMAIN}.config.step.reconfigure.data."
            "include_satellite_room_context"
        ]
        == "Use the voice satellite and current room"
    )
    assert subentries[
        f"component.{DOMAIN}.config_subentries.assistant.step.reconfigure."
        "data_description.include_user_context"
    ].startswith("Shares only the initiating Home Assistant user's resolved")


async def test_full_user_flow(hass) -> None:
    """Setup links model-specific thinking selection to OAuth validation."""
    skills_path = Path(hass.config.path("openai_oauth_conversation", "skills"))
    await hass.async_add_executor_job(_write_test_skill, skills_path)
    with patch(
        "homeassistant.config_entries.async_process_deps_reqs",
        AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Primary account",
            CONF_ENABLE_HASS_CONTROL: False,
            CONF_ENABLE_AI_MEDIA_TOOLS: True,
            CONF_ENABLE_HISTORY_TOOLS: True,
            CONF_ENABLE_SCHEDULED_ACTIONS: True,
            CONF_ENABLED_LOCAL_SKILLS: ["energy_analyst"],
            CONF_SELECTED_SCRIPT_ENTITIES: [
                "script.movie_night",
                "script.lock_up",
            ],
            CONF_PROMPT_TEMPLATE_ENTITIES: [
                "input_boolean.quiet_mode",
                "sensor.indoor_temperature",
            ],
            CONF_INCLUDE_USER_CONTEXT: True,
            CONF_INCLUDE_SATELLITE_ROOM_CONTEXT: True,
            CONF_INCLUDE_ROOM_ENTITIES: True,
            CONF_MAX_TOOL_CALLS: 7,
            CONF_MAX_TOOL_TIME: 45,
            CONF_MEMORY_MODE: "summarized",
            CONF_MEMORY_MAX_TURNS: 8,
            CONF_MEMORY_MAX_CHARACTERS: 12000,
            CONF_MODEL: "gpt-5.6-luna",
            CONF_PROMPT: "Be helpful.",
            CONF_WEB_SEARCH_MODE: "auto",
            CONF_WEB_SEARCH_CONTEXT_SIZE: "high",
            CONF_WEB_SEARCH_INCLUDE_SOURCES: False,
            CONF_WEB_SEARCH_LIVE_ACCESS: False,
            CONF_WEB_SEARCH_USE_HASS_LOCATION: True,
            CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION: True,
        },
    )
    assert result["step_id"] == "reasoning"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_REASONING_EFFORT: "max"},
    )
    assert result["step_id"] == "auth_manual"
    authorize_url = result["description_placeholders"]["authorize_url"]
    state = URL(authorize_url).query["state"]

    token_data = OAuthTokenData(
        access_token="access-token",
        refresh_token="refresh-token",
        expires_ms=4_000_000_000_000,
        account_id="account-123",
    )
    with (
        patch(
            "custom_components.openai_oauth_conversation.config_flow."
            "async_exchange_authorization_code",
            AsyncMock(return_value=token_data),
        ),
        patch(
            "custom_components.openai_oauth_conversation.config_flow."
            "ChatGPTOAuthClient.async_test_connection",
            AsyncMock(return_value=None),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "callback_url": (
                    "http://localhost:1455/auth/callback?code=code&state=" + state
                )
            },
        )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Primary account"
    assert result["data"][CONF_ENABLE_HASS_CONTROL] is False
    assert result["data"][CONF_ENABLE_AI_MEDIA_TOOLS] is True
    assert result["data"][CONF_ENABLE_HISTORY_TOOLS] is True
    assert result["data"][CONF_ENABLE_SCHEDULED_ACTIONS] is True
    assert result["data"][CONF_ENABLED_LOCAL_SKILLS] == ["energy_analyst"]
    assert result["data"][CONF_SELECTED_SCRIPT_ENTITIES] == [
        "script.movie_night",
        "script.lock_up",
    ]
    assert result["data"][CONF_PROMPT_TEMPLATE_ENTITIES] == [
        "input_boolean.quiet_mode",
        "sensor.indoor_temperature",
    ]
    assert result["data"][CONF_INCLUDE_USER_CONTEXT] is True
    assert result["data"][CONF_INCLUDE_SATELLITE_ROOM_CONTEXT] is True
    assert result["data"][CONF_INCLUDE_ROOM_ENTITIES] is True
    assert result["data"][CONF_MAX_TOOL_CALLS] == 7
    assert result["data"][CONF_MAX_TOOL_TIME] == 45
    assert result["data"][CONF_MEMORY_MODE] == "summarized"
    assert result["data"][CONF_MEMORY_MAX_TURNS] == 8
    assert result["data"][CONF_MEMORY_MAX_CHARACTERS] == 12000
    assert result["data"][CONF_MODEL] == "gpt-5.6-luna"
    assert result["data"][CONF_REASONING_EFFORT] == "max"
    assert result["data"][CONF_WEB_SEARCH_MODE] == "auto"
    assert result["data"][CONF_WEB_SEARCH_CONTEXT_SIZE] == "high"
    assert result["data"][CONF_WEB_SEARCH_INCLUDE_SOURCES] is False
    assert result["data"][CONF_WEB_SEARCH_LIVE_ACCESS] is False
    assert result["data"][CONF_WEB_SEARCH_USE_HASS_LOCATION] is True
    assert result["data"][CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION] is True
