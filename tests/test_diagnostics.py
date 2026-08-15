"""Tests for redacted integration diagnostics."""

from __future__ import annotations

import json
from pathlib import Path

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openai_oauth_conversation.const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_ID,
    CONF_ENABLE_AI_MEDIA_TOOLS,
    CONF_ENABLE_HASS_CONTROL,
    CONF_ENABLED_LOCAL_SKILLS,
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
    CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION,
    DOMAIN,
)
from custom_components.openai_oauth_conversation.diagnostics import (
    async_get_config_entry_diagnostics,
)


def _write_private_skill(skills_path: Path) -> None:
    skills_path.mkdir(parents=True, exist_ok=True)
    (skills_path / "private-valid.toml").write_text(
        'schema_version = 1\nname = "private skill name"\n'
        'instructions = "private skill instructions"\n',
        encoding="utf-8",
    )


async def test_diagnostics_exclude_sensitive_and_user_content(hass) -> None:
    """Tokens, account identifiers, and prompts never enter diagnostics."""
    await hass.async_add_executor_job(
        _write_private_skill,
        Path(hass.config.path("openai_oauth_conversation", "skills")),
    )
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
            CONF_ENABLE_AI_MEDIA_TOOLS: True,
            CONF_ENABLED_LOCAL_SKILLS: [
                "private-valid",
                "missing-private-skill",
            ],
            CONF_MODEL: "gpt-5.6-terra",
            CONF_REASONING_EFFORT: "high",
            CONF_WEB_SEARCH_MODE: "required",
            CONF_WEB_SEARCH_CONTEXT_SIZE: "high",
            CONF_WEB_SEARCH_INCLUDE_SOURCES: False,
            CONF_WEB_SEARCH_LIVE_ACCESS: False,
            CONF_WEB_SEARCH_USE_HASS_LOCATION: True,
            CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION: True,
        },
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    serialized = json.dumps(diagnostics)
    for value in secrets.values():
        assert value not in serialized
    assert "missing-private-skill" not in serialized
    assert "private-valid" not in serialized
    assert "private skill name" not in serialized
    assert "private skill instructions" not in serialized
    assert diagnostics["config_entry"]["assistant_profile_count"] == 1
    profile = diagnostics["assistant_profiles"][0]
    assert profile["profile_type"] == "default"
    assert profile["home_assistant_control_enabled"] is False
    assert profile["ai_task_and_camera_tools"] == {
        "enabled": True,
        "camera_access": "on_demand_snapshot_only",
        "requires_assist_exposure": True,
        "requires_user_entity_permissions": True,
        "generated_image_bytes_in_diagnostics": False,
    }
    assert profile["selected_script_tools"] == {
        "enabled": False,
        "selected_count": 0,
        "script_entity_ids_in_diagnostics": False,
        "requires_user_entity_permissions": True,
    }
    assert profile["local_skills"] == {
        "configured_enabled_count": 2,
        "valid_selected_count": 1,
        "instruction_pack_count": 1,
        "missing_selected_count": 1,
        "skipped_instruction_count": 0,
        "declared_scope": False,
        "effective_fail_closed_scope": True,
        "declared_web_policy": "disabled",
        "effective_web_search_mode": "disabled",
        "effective_confirmation_policy": "inherit",
        "skill_ids_in_diagnostics": False,
        "names_in_diagnostics": False,
        "file_paths_in_diagnostics": False,
        "instructions_in_diagnostics": False,
        "automatic_downloads": False,
        "executable_files": False,
    }
    assert profile["restricted_prompt_template"] == {
        "enabled": True,
        "selected_entity_count": 0,
        "prompt_source_in_diagnostics": False,
        "unrestricted_state_access": False,
    }
    assert profile["model"]["slug"] == "gpt-5.6-terra"
    assert profile["model"]["thinking_level"] == "high"
    assert profile["model"]["supports_web_search"] is True
    assert profile["request_context"] == {
        "user_display_name_enabled": False,
        "satellite_and_room_labels_enabled": False,
        "exposed_room_entities_enabled": False,
        "internal_ids_sent_to_model": False,
        "home_location_sent_by_request_context": False,
    }
    assert profile["tool_safety"] == {
        "maximum_calls_per_turn": 5,
        "maximum_total_time_seconds": 60,
        "loop_detection": True,
    }
    assert profile["web_search"] == {
        "mode": "required",
        "context_size": "high",
        "includes_sources_in_response_text": False,
        "live_access": False,
        "uses_home_assistant_location": True,
        "uses_precise_home_assistant_location": True,
        "location_detail": "coordinates_location_name_country_and_timezone",
    }
