"""Diagnostics support for ChatGPT OAuth."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as HOME_ASSISTANT_VERSION
from homeassistant.core import HomeAssistant

from .client import ChatGPTOAuthClient
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_ID,
    CONF_EXPIRES,
    CONF_ENABLE_HASS_CONTROL,
    CONF_MODEL,
    CONF_REASONING_EFFORT,
    CONF_REFRESH_TOKEN,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_INCLUDE_SOURCES,
    CONF_WEB_SEARCH_LIVE_ACCESS,
    CONF_WEB_SEARCH_MODE,
    CONF_WEB_SEARCH_USE_HASS_LOCATION,
    DEFAULT_ENABLE_HASS_CONTROL,
    DEFAULT_MODEL,
    DEFAULT_WEB_SEARCH_CONTEXT_SIZE,
    DEFAULT_WEB_SEARCH_INCLUDE_SOURCES,
    DEFAULT_WEB_SEARCH_LIVE_ACCESS,
    DEFAULT_WEB_SEARCH_MODE,
    DEFAULT_WEB_SEARCH_USE_HASS_LOCATION,
    DOMAIN,
    INTEGRATION_VERSION,
    MAX_IMAGE_ATTACHMENTS,
)
from .models import get_model_profile, normalize_model, normalize_reasoning_effort
from .web_search import (
    normalize_web_search_context_size,
    normalize_web_search_mode,
)


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


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return useful diagnostics without credentials, prompts, or content."""
    model = normalize_model(entry.data.get(CONF_MODEL, DEFAULT_MODEL))
    profile = get_model_profile(model)
    reasoning_effort = normalize_reasoning_effort(
        model,
        entry.data.get(CONF_REASONING_EFFORT),
    )
    runtime_data = getattr(entry, "runtime_data", None)
    web_search_mode = normalize_web_search_mode(
        entry.data.get(CONF_WEB_SEARCH_MODE),
        default=DEFAULT_WEB_SEARCH_MODE,
    )
    web_search_context_size = normalize_web_search_context_size(
        entry.data.get(CONF_WEB_SEARCH_CONTEXT_SIZE),
        default=DEFAULT_WEB_SEARCH_CONTEXT_SIZE,
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
            "modified_at": _serialize_entry_time(
                getattr(entry, "modified_at", None)
            ),
            "runtime_client_loaded": isinstance(runtime_data, ChatGPTOAuthClient),
            "home_assistant_control_enabled": bool(
                entry.data.get(
                    CONF_ENABLE_HASS_CONTROL,
                    DEFAULT_ENABLE_HASS_CONTROL,
                )
            ),
        },
        "authentication": {
            "has_access_token": bool(entry.data.get(CONF_ACCESS_TOKEN)),
            "has_refresh_token": bool(entry.data.get(CONF_REFRESH_TOKEN)),
            "has_account_id": bool(entry.data.get(CONF_ACCOUNT_ID)),
            "access_token_expires_at": _iso_timestamp(entry.data.get(CONF_EXPIRES)),
        },
        "model": {
            "slug": profile.slug,
            "display_name": profile.display_name,
            "thinking_level": reasoning_effort,
            "available_thinking_levels": list(profile.reasoning_efforts),
            "default_text_transport": (
                "responses_lite" if profile.responses_lite else "responses"
            ),
            "web_search_transport": "responses",
            "supports_tools": profile.supports_tools,
            "supports_structured_output": profile.supports_structured_output,
            "supports_image_inputs": profile.supports_images,
            "supports_pdf_inputs": profile.supports_files,
            "supports_web_search": profile.supports_web_search,
            "maximum_image_attachments": MAX_IMAGE_ATTACHMENTS,
        },
        "web_search": {
            "mode": web_search_mode,
            "context_size": web_search_context_size,
            "includes_sources_in_response_text": bool(
                entry.data.get(
                    CONF_WEB_SEARCH_INCLUDE_SOURCES,
                    DEFAULT_WEB_SEARCH_INCLUDE_SOURCES,
                )
            ),
            "live_access": bool(
                entry.data.get(
                    CONF_WEB_SEARCH_LIVE_ACCESS,
                    DEFAULT_WEB_SEARCH_LIVE_ACCESS,
                )
            ),
            "uses_home_assistant_location": bool(
                entry.data.get(
                    CONF_WEB_SEARCH_USE_HASS_LOCATION,
                    DEFAULT_WEB_SEARCH_USE_HASS_LOCATION,
                )
            ),
            "location_detail": "country_and_timezone_only",
        },
    }
