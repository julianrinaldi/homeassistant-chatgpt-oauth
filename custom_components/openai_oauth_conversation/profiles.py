"""Assistant-profile settings shared by setup, entities, and diagnostics."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry

from .const import (
    CONF_ENABLE_AI_MEDIA_TOOLS,
    CONF_ENABLE_HASS_CONTROL,
    CONF_ENABLE_HISTORY_TOOLS,
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
    CONF_REASONING_EFFORT,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_INCLUDE_SOURCES,
    CONF_WEB_SEARCH_LIVE_ACCESS,
    CONF_WEB_SEARCH_MODE,
    CONF_WEB_SEARCH_USE_HASS_LOCATION,
    CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION,
    DEFAULT_ENABLE_AI_MEDIA_TOOLS,
    DEFAULT_ENABLE_HASS_CONTROL,
    DEFAULT_ENABLE_HISTORY_TOOLS,
    DEFAULT_INCLUDE_ROOM_ENTITIES,
    DEFAULT_INCLUDE_SATELLITE_ROOM_CONTEXT,
    DEFAULT_INCLUDE_USER_CONTEXT,
    DEFAULT_MAX_TOOL_CALLS,
    DEFAULT_MAX_TOOL_TIME,
    DEFAULT_MEMORY_MAX_CHARACTERS,
    DEFAULT_MEMORY_MAX_TURNS,
    DEFAULT_MEMORY_MODE,
    DEFAULT_MODEL,
    DEFAULT_PROMPT,
    DEFAULT_WEB_SEARCH_CONTEXT_SIZE,
    DEFAULT_WEB_SEARCH_INCLUDE_SOURCES,
    DEFAULT_WEB_SEARCH_LIVE_ACCESS,
    DEFAULT_WEB_SEARCH_MODE,
    DEFAULT_WEB_SEARCH_USE_HASS_LOCATION,
    DEFAULT_WEB_SEARCH_USE_HASS_PRECISE_LOCATION,
    MAX_MEMORY_MAX_CHARACTERS,
    MAX_MEMORY_MAX_TURNS,
    MAX_TOOL_CALLS,
    MAX_TOOL_TIME,
    MEMORY_MODES,
    MIN_MEMORY_MAX_CHARACTERS,
    MIN_MEMORY_MAX_TURNS,
    MIN_TOOL_CALLS,
    MIN_TOOL_TIME,
    SUBENTRY_TYPE_ASSISTANT,
)
from .models import get_model_profile, normalize_model, normalize_reasoning_effort
from .web_search import (
    WebSearchOptions,
    normalize_web_search_context_size,
    normalize_web_search_mode,
)


@dataclass(frozen=True, slots=True)
class AssistantProfileSettings:
    """Resolved settings for one Home Assistant conversation agent."""

    title: str
    profile_id: str
    model: str
    reasoning_effort: str
    prompt: str
    enable_home_assistant_control: bool
    enable_history_tools: bool
    enable_ai_media_tools: bool
    include_user_context: bool
    include_satellite_room_context: bool
    include_room_entities: bool
    max_tool_calls: int
    max_tool_time: int
    web_search: WebSearchOptions
    memory_mode: str
    memory_max_turns: int
    memory_max_characters: int


def normalize_memory_mode(value: object, *, default: str = DEFAULT_MEMORY_MODE) -> str:
    """Return one supported conversation-memory mode."""
    if not isinstance(value, str) or not value.strip():
        return default
    normalized = value.strip().lower()
    aliases = {
        "none": "current_turn",
        "off": "current_turn",
        "current": "current_turn",
        "recent_turns": "recent",
        "summary": "summarized",
        "summarize": "summarized",
        "all": "full",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in MEMORY_MODES:
        raise ValueError(
            f"Unsupported conversation-memory mode {normalized!r}. "
            f"Available modes: {', '.join(MEMORY_MODES)}"
        )
    return normalized


def normalize_memory_max_turns(
    value: object,
    *,
    default: int = DEFAULT_MEMORY_MAX_TURNS,
) -> int:
    """Return a bounded recent-turn count."""
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    if not MIN_MEMORY_MAX_TURNS <= result <= MAX_MEMORY_MAX_TURNS:
        raise ValueError(
            "Conversation memory turns must be between "
            f"{MIN_MEMORY_MAX_TURNS} and {MAX_MEMORY_MAX_TURNS}"
        )
    return result


def normalize_memory_max_characters(
    value: object,
    *,
    default: int = DEFAULT_MEMORY_MAX_CHARACTERS,
) -> int:
    """Return a bounded character budget for visible conversation history."""
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    if not MIN_MEMORY_MAX_CHARACTERS <= result <= MAX_MEMORY_MAX_CHARACTERS:
        raise ValueError(
            "Conversation memory characters must be between "
            f"{MIN_MEMORY_MAX_CHARACTERS} and {MAX_MEMORY_MAX_CHARACTERS}"
        )
    return result


def _normalize_bounded_integer(
    value: object,
    *,
    default: int,
    minimum: int,
    maximum: int,
    label: str,
) -> int:
    """Return a validated integer setting within an inclusive range."""
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    if not minimum <= result <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return result


def normalize_max_tool_calls(
    value: object,
    *,
    default: int = DEFAULT_MAX_TOOL_CALLS,
) -> int:
    """Return the maximum Home Assistant tool calls for one turn."""
    return _normalize_bounded_integer(
        value,
        default=default,
        minimum=MIN_TOOL_CALLS,
        maximum=MAX_TOOL_CALLS,
        label="Maximum tool calls",
    )


def normalize_max_tool_time(
    value: object,
    *,
    default: int = DEFAULT_MAX_TOOL_TIME,
) -> int:
    """Return the total Home Assistant tool execution time limit."""
    return _normalize_bounded_integer(
        value,
        default=default,
        minimum=MIN_TOOL_TIME,
        maximum=MAX_TOOL_TIME,
        label="Maximum tool time",
    )


def profile_data_defaults(
    source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return normalized defaults suitable for a profile form."""
    source = source or {}
    model = normalize_model(source.get(CONF_MODEL, DEFAULT_MODEL))
    try:
        model = get_model_profile(model).slug
    except ValueError:
        model = DEFAULT_MODEL
    return {
        CONF_MODEL: model,
        CONF_REASONING_EFFORT: normalize_reasoning_effort(
            model,
            source.get(CONF_REASONING_EFFORT),
        ),
        CONF_PROMPT: _nonempty_prompt(source.get(CONF_PROMPT)),
        CONF_ENABLE_HASS_CONTROL: _bool_setting(
            source,
            CONF_ENABLE_HASS_CONTROL,
            DEFAULT_ENABLE_HASS_CONTROL,
        ),
        CONF_ENABLE_HISTORY_TOOLS: _bool_setting(
            source,
            CONF_ENABLE_HISTORY_TOOLS,
            DEFAULT_ENABLE_HISTORY_TOOLS,
        ),
        CONF_ENABLE_AI_MEDIA_TOOLS: _bool_setting(
            source,
            CONF_ENABLE_AI_MEDIA_TOOLS,
            DEFAULT_ENABLE_AI_MEDIA_TOOLS,
        ),
        CONF_INCLUDE_USER_CONTEXT: _bool_setting(
            source,
            CONF_INCLUDE_USER_CONTEXT,
            DEFAULT_INCLUDE_USER_CONTEXT,
        ),
        CONF_INCLUDE_SATELLITE_ROOM_CONTEXT: _bool_setting(
            source,
            CONF_INCLUDE_SATELLITE_ROOM_CONTEXT,
            DEFAULT_INCLUDE_SATELLITE_ROOM_CONTEXT,
        ),
        CONF_INCLUDE_ROOM_ENTITIES: _bool_setting(
            source,
            CONF_INCLUDE_ROOM_ENTITIES,
            DEFAULT_INCLUDE_ROOM_ENTITIES,
        ),
        CONF_MAX_TOOL_CALLS: normalize_max_tool_calls(
            source.get(CONF_MAX_TOOL_CALLS),
        ),
        CONF_MAX_TOOL_TIME: normalize_max_tool_time(
            source.get(CONF_MAX_TOOL_TIME),
        ),
        CONF_WEB_SEARCH_MODE: normalize_web_search_mode(
            source.get(CONF_WEB_SEARCH_MODE),
            default=DEFAULT_WEB_SEARCH_MODE,
        ),
        CONF_WEB_SEARCH_CONTEXT_SIZE: normalize_web_search_context_size(
            source.get(CONF_WEB_SEARCH_CONTEXT_SIZE),
            default=DEFAULT_WEB_SEARCH_CONTEXT_SIZE,
        ),
        CONF_WEB_SEARCH_INCLUDE_SOURCES: _bool_setting(
            source,
            CONF_WEB_SEARCH_INCLUDE_SOURCES,
            DEFAULT_WEB_SEARCH_INCLUDE_SOURCES,
        ),
        CONF_WEB_SEARCH_LIVE_ACCESS: _bool_setting(
            source,
            CONF_WEB_SEARCH_LIVE_ACCESS,
            DEFAULT_WEB_SEARCH_LIVE_ACCESS,
        ),
        CONF_WEB_SEARCH_USE_HASS_LOCATION: _bool_setting(
            source,
            CONF_WEB_SEARCH_USE_HASS_LOCATION,
            DEFAULT_WEB_SEARCH_USE_HASS_LOCATION,
        ),
        CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION: _bool_setting(
            source,
            CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION,
            DEFAULT_WEB_SEARCH_USE_HASS_PRECISE_LOCATION,
        ),
        CONF_MEMORY_MODE: normalize_memory_mode(
            source.get(CONF_MEMORY_MODE),
            default=DEFAULT_MEMORY_MODE,
        ),
        CONF_MEMORY_MAX_TURNS: normalize_memory_max_turns(
            source.get(CONF_MEMORY_MAX_TURNS),
        ),
        CONF_MEMORY_MAX_CHARACTERS: normalize_memory_max_characters(
            source.get(CONF_MEMORY_MAX_CHARACTERS),
        ),
    }


def resolve_assistant_profile(
    entry: ConfigEntry,
    subentry: ConfigSubentry | None = None,
) -> AssistantProfileSettings:
    """Resolve the default or an additional assistant profile."""
    # Additional profiles are stored as complete settings. Falling back to the
    # parent entry keeps partially-created development entries usable.
    data: dict[str, Any] = dict(entry.data)
    if subentry is not None:
        data.update(subentry.data)

    normalized = profile_data_defaults(data)
    title = subentry.title if subentry is not None else entry.title
    profile_id = subentry.subentry_id if subentry is not None else entry.entry_id
    return AssistantProfileSettings(
        title=title,
        profile_id=profile_id,
        model=normalized[CONF_MODEL],
        reasoning_effort=normalized[CONF_REASONING_EFFORT],
        prompt=normalized[CONF_PROMPT],
        enable_home_assistant_control=normalized[CONF_ENABLE_HASS_CONTROL],
        enable_history_tools=normalized[CONF_ENABLE_HISTORY_TOOLS],
        enable_ai_media_tools=normalized[CONF_ENABLE_AI_MEDIA_TOOLS],
        include_user_context=normalized[CONF_INCLUDE_USER_CONTEXT],
        include_satellite_room_context=normalized[CONF_INCLUDE_SATELLITE_ROOM_CONTEXT],
        include_room_entities=normalized[CONF_INCLUDE_ROOM_ENTITIES],
        max_tool_calls=normalized[CONF_MAX_TOOL_CALLS],
        max_tool_time=normalized[CONF_MAX_TOOL_TIME],
        web_search=WebSearchOptions(
            mode=normalized[CONF_WEB_SEARCH_MODE],
            context_size=normalized[CONF_WEB_SEARCH_CONTEXT_SIZE],
            include_sources=normalized[CONF_WEB_SEARCH_INCLUDE_SOURCES],
            live_access=normalized[CONF_WEB_SEARCH_LIVE_ACCESS],
            use_home_assistant_location=normalized[CONF_WEB_SEARCH_USE_HASS_LOCATION],
            use_home_assistant_precise_location=normalized[
                CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION
            ],
        ),
        memory_mode=normalized[CONF_MEMORY_MODE],
        memory_max_turns=normalized[CONF_MEMORY_MAX_TURNS],
        memory_max_characters=normalized[CONF_MEMORY_MAX_CHARACTERS],
    )


def assistant_profiles_fingerprint(
    entry: ConfigEntry,
) -> tuple[AssistantProfileSettings, ...]:
    """Return settings that require conversation entities to be reloaded.

    Authentication tokens are intentionally excluded so normal OAuth token refreshes do
    not reload the integration. Config-entry and config-subentry profile changes are
    represented by the resolved immutable settings instead.
    """
    profiles = [resolve_assistant_profile(entry)]
    profiles.extend(
        resolve_assistant_profile(entry, subentry)
        for subentry in sorted(
            entry.subentries.values(),
            key=lambda item: item.subentry_id,
        )
        if subentry.subentry_type == SUBENTRY_TYPE_ASSISTANT
    )
    return tuple(profiles)


def profile_data_from_input(
    user_input: Mapping[str, Any],
    *,
    defaults: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate and normalize one setup or profile form submission."""
    base = profile_data_defaults(defaults)
    model = get_model_profile(user_input.get(CONF_MODEL, base[CONF_MODEL])).slug
    prompt = user_input.get(CONF_PROMPT, base[CONF_PROMPT])
    merged = {**base, **user_input}
    result = {
        CONF_MODEL: model,
        CONF_PROMPT: _nonempty_prompt(prompt),
        CONF_ENABLE_HASS_CONTROL: _bool_setting(
            merged,
            CONF_ENABLE_HASS_CONTROL,
            base[CONF_ENABLE_HASS_CONTROL],
        ),
        CONF_ENABLE_HISTORY_TOOLS: _bool_setting(
            merged,
            CONF_ENABLE_HISTORY_TOOLS,
            base[CONF_ENABLE_HISTORY_TOOLS],
        ),
        CONF_ENABLE_AI_MEDIA_TOOLS: _bool_setting(
            merged,
            CONF_ENABLE_AI_MEDIA_TOOLS,
            base[CONF_ENABLE_AI_MEDIA_TOOLS],
        ),
        CONF_INCLUDE_USER_CONTEXT: _bool_setting(
            merged,
            CONF_INCLUDE_USER_CONTEXT,
            base[CONF_INCLUDE_USER_CONTEXT],
        ),
        CONF_INCLUDE_SATELLITE_ROOM_CONTEXT: _bool_setting(
            merged,
            CONF_INCLUDE_SATELLITE_ROOM_CONTEXT,
            base[CONF_INCLUDE_SATELLITE_ROOM_CONTEXT],
        ),
        CONF_INCLUDE_ROOM_ENTITIES: _bool_setting(
            merged,
            CONF_INCLUDE_ROOM_ENTITIES,
            base[CONF_INCLUDE_ROOM_ENTITIES],
        ),
        CONF_MAX_TOOL_CALLS: normalize_max_tool_calls(
            user_input.get(CONF_MAX_TOOL_CALLS),
            default=base[CONF_MAX_TOOL_CALLS],
        ),
        CONF_MAX_TOOL_TIME: normalize_max_tool_time(
            user_input.get(CONF_MAX_TOOL_TIME),
            default=base[CONF_MAX_TOOL_TIME],
        ),
        CONF_WEB_SEARCH_MODE: normalize_web_search_mode(
            user_input.get(CONF_WEB_SEARCH_MODE),
            default=base[CONF_WEB_SEARCH_MODE],
        ),
        CONF_WEB_SEARCH_CONTEXT_SIZE: normalize_web_search_context_size(
            user_input.get(CONF_WEB_SEARCH_CONTEXT_SIZE),
            default=base[CONF_WEB_SEARCH_CONTEXT_SIZE],
        ),
        CONF_WEB_SEARCH_INCLUDE_SOURCES: _bool_setting(
            merged,
            CONF_WEB_SEARCH_INCLUDE_SOURCES,
            base[CONF_WEB_SEARCH_INCLUDE_SOURCES],
        ),
        CONF_WEB_SEARCH_LIVE_ACCESS: _bool_setting(
            merged,
            CONF_WEB_SEARCH_LIVE_ACCESS,
            base[CONF_WEB_SEARCH_LIVE_ACCESS],
        ),
        CONF_WEB_SEARCH_USE_HASS_LOCATION: _bool_setting(
            merged,
            CONF_WEB_SEARCH_USE_HASS_LOCATION,
            base[CONF_WEB_SEARCH_USE_HASS_LOCATION],
        ),
        CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION: _bool_setting(
            merged,
            CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION,
            base[CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION],
        ),
        CONF_MEMORY_MODE: normalize_memory_mode(
            user_input.get(CONF_MEMORY_MODE),
            default=base[CONF_MEMORY_MODE],
        ),
        CONF_MEMORY_MAX_TURNS: normalize_memory_max_turns(
            user_input.get(CONF_MEMORY_MAX_TURNS),
            default=base[CONF_MEMORY_MAX_TURNS],
        ),
        CONF_MEMORY_MAX_CHARACTERS: normalize_memory_max_characters(
            user_input.get(CONF_MEMORY_MAX_CHARACTERS),
            default=base[CONF_MEMORY_MAX_CHARACTERS],
        ),
    }
    return result


def _nonempty_prompt(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return DEFAULT_PROMPT


def _bool_setting(
    source: Mapping[str, Any],
    key: str,
    default: bool,
) -> bool:
    value = source.get(key)
    return value if isinstance(value, bool) else default
