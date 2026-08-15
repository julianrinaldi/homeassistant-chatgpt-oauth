"""Diagnostics support for ChatGPT OAuth."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import __version__ as HOME_ASSISTANT_VERSION
from homeassistant.core import HomeAssistant

from .client import ChatGPTOAuthClient
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_ID,
    CONF_EXPIRES,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    INTEGRATION_VERSION,
    MAX_IMAGE_ATTACHMENTS,
    SUBENTRY_TYPE_ASSISTANT,
)
from .models import get_model_profile
from .profiles import AssistantProfileSettings, resolve_assistant_profile


def _iso_timestamp(value: object) -> str | None:
    try:
        milliseconds = int(value)
    except (TypeError, ValueError):
        return None
    if milliseconds <= 0:
        return None
    return datetime.fromtimestamp(milliseconds / 1000, tz=UTC).isoformat()


def _serialize_entry_time(value: object) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None


def _profile_diagnostics(
    settings: AssistantProfileSettings,
    *,
    subentry: ConfigSubentry | None,
) -> dict[str, Any]:
    """Return non-sensitive settings for one conversation profile."""
    model = get_model_profile(settings.model)
    return {
        "title": settings.title,
        "profile_type": "default" if subentry is None else "additional",
        "subentry_id": None if subentry is None else subentry.subentry_id,
        "model": {
            "slug": model.slug,
            "display_name": model.display_name,
            "thinking_level": settings.reasoning_effort,
            "available_thinking_levels": list(model.reasoning_efforts),
            "default_text_transport": (
                "responses_lite" if model.responses_lite else "responses"
            ),
            "web_search_transport": "responses",
            "supports_tools": model.supports_tools,
            "supports_structured_output": model.supports_structured_output,
            "supports_image_inputs": model.supports_images,
            "supports_pdf_inputs": model.supports_files,
            "supports_web_search": model.supports_web_search,
        },
        "home_assistant_control_enabled": settings.enable_home_assistant_control,
        "history_tools_enabled": settings.enable_history_tools,
        "ai_task_and_camera_tools": {
            "enabled": settings.enable_ai_media_tools,
            "camera_access": "on_demand_snapshot_only",
            "requires_assist_exposure": True,
            "requires_user_entity_permissions": True,
            "generated_image_bytes_in_diagnostics": False,
        },
        "request_context": {
            "user_display_name_enabled": settings.include_user_context,
            "satellite_and_room_labels_enabled": (
                settings.include_satellite_room_context
            ),
            "exposed_room_entities_enabled": settings.include_room_entities,
            "internal_ids_sent_to_model": False,
            "home_location_sent_by_request_context": False,
        },
        "tool_safety": {
            "maximum_calls_per_turn": settings.max_tool_calls,
            "maximum_total_time_seconds": settings.max_tool_time,
            "loop_detection": True,
        },
        "memory": {
            "mode": settings.memory_mode,
            "maximum_recent_turns": settings.memory_max_turns,
            "maximum_characters": settings.memory_max_characters,
        },
        "web_search": {
            "mode": settings.web_search.mode,
            "context_size": settings.web_search.context_size,
            "includes_sources_in_response_text": settings.web_search.include_sources,
            "live_access": settings.web_search.live_access,
            "uses_home_assistant_location": (
                settings.web_search.use_home_assistant_location
                or settings.web_search.use_home_assistant_precise_location
            ),
            "uses_precise_home_assistant_location": (
                settings.web_search.use_home_assistant_precise_location
            ),
            "location_detail": (
                "coordinates_location_name_country_and_timezone"
                if settings.web_search.use_home_assistant_precise_location
                else (
                    "country_and_timezone_only"
                    if settings.web_search.use_home_assistant_location
                    else "disabled"
                )
            ),
        },
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return useful diagnostics without credentials, prompts, or content."""
    runtime_data = getattr(entry, "runtime_data", None)
    profiles = [_profile_diagnostics(resolve_assistant_profile(entry), subentry=None)]
    profiles.extend(
        _profile_diagnostics(
            resolve_assistant_profile(entry, subentry),
            subentry=subentry,
        )
        for subentry in entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_TYPE_ASSISTANT
    )

    return {
        "integration": {
            "domain": DOMAIN,
            "version": INTEGRATION_VERSION,
            "home_assistant_version": HOME_ASSISTANT_VERSION,
        },
        "config_entry": {
            "title": entry.title,
            "version": entry.version,
            "state": getattr(entry.state, "value", str(entry.state)),
            "created_at": _serialize_entry_time(getattr(entry, "created_at", None)),
            "modified_at": _serialize_entry_time(getattr(entry, "modified_at", None)),
            "runtime_client_loaded": isinstance(runtime_data, ChatGPTOAuthClient),
            "assistant_profile_count": len(profiles),
        },
        "authentication": {
            "has_access_token": bool(entry.data.get(CONF_ACCESS_TOKEN)),
            "has_refresh_token": bool(entry.data.get(CONF_REFRESH_TOKEN)),
            "has_account_id": bool(entry.data.get(CONF_ACCOUNT_ID)),
            "access_token_expires_at": _iso_timestamp(entry.data.get(CONF_EXPIRES)),
        },
        "capabilities": {
            "maximum_image_attachments": MAX_IMAGE_ATTACHMENTS,
            "additional_assistant_profiles": True,
            "read_only_history_tools": True,
            "conversation_memory_policies": True,
            "precise_web_search_location": True,
            "user_satellite_and_room_context": True,
            "bounded_tool_loops": True,
            "privacy_safe_conversation_finished_event": True,
            "conversation_ai_task_tools": True,
            "exposed_camera_snapshot_analysis": True,
            "assist_image_generation": True,
        },
        "assistant_profiles": profiles,
    }
