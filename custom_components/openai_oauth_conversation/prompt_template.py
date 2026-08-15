"""Restricted Jinja rendering for per-request conversation system prompts."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.util import dt as dt_util
from jinja2 import StrictUndefined, TemplateError
from jinja2 import Template as JinjaTemplate
from jinja2.sandbox import ImmutableSandboxedEnvironment

from .const import (
    DEFAULT_PROMPT,
    LOGGER,
    MAX_PROMPT_TEMPLATE_SOURCE_CHARACTERS,
    MAX_RENDERED_PROMPT_CHARACTERS,
)
from .request_context import ResolvedRequestContext

_ENVIRONMENT = ImmutableSandboxedEnvironment(
    autoescape=False,
    undefined=StrictUndefined,
)
_ENVIRONMENT.globals.clear()


def validate_prompt_template_source(source: str) -> str:
    """Validate a configured prompt's size and Jinja syntax without rendering it."""
    normalized = source.strip()
    if not normalized:
        raise ValueError("System prompt cannot be empty")
    if len(normalized) > MAX_PROMPT_TEMPLATE_SOURCE_CHARACTERS:
        raise ValueError(
            "System prompt must be no more than "
            f"{MAX_PROMPT_TEMPLATE_SOURCE_CHARACTERS} characters"
        )
    try:
        _compiled_template(normalized)
    except TemplateError as err:
        raise ValueError(f"Invalid system prompt template: {err}") from err
    return normalized


async def async_render_system_prompt(
    hass: HomeAssistant,
    *,
    source: str,
    request_context: ResolvedRequestContext,
    context: Context | None,
    selected_entity_ids: tuple[str, ...],
) -> str:
    """Render approved context and selected entity states for one Assist request."""
    try:
        source = validate_prompt_template_source(source)
        selected_states = await _async_selected_states(
            hass,
            context,
            selected_entity_ids,
        )

        def states(entity_id: object) -> str:
            state = _selected_state(selected_states, entity_id)
            return "unknown" if state is None else _safe_text(state.state)

        def is_state(entity_id: object, expected: object) -> bool:
            state = _selected_state(selected_states, entity_id)
            return state is not None and state.state == str(expected)

        def state_attr(entity_id: object, attribute: object) -> Any:
            state = _selected_state(selected_states, entity_id)
            if state is None or not isinstance(attribute, str):
                return None
            return _safe_template_value(state.attributes.get(attribute))

        rendered = (
            _compiled_template(source)
            .render(
                user_name=_safe_text(request_context.user_display_name or ""),
                area_name=_safe_text(request_context.area_display_name or ""),
                room_name=_safe_text(request_context.area_display_name or ""),
                satellite_name=_safe_text(request_context.satellite_display_name or ""),
                device_name=_safe_text(request_context.device_display_name or ""),
                room_entities=_safe_template_value(list(request_context.room_entities)),
                local_time=dt_util.now(),
                now=dt_util.now,
                states=states,
                is_state=is_state,
                state_attr=state_attr,
            )
            .strip()
        )
        if not rendered or len(rendered) > MAX_RENDERED_PROMPT_CHARACTERS:
            raise ValueError("Rendered system prompt is empty or too large")
        # Home Assistant performs its own prompt-template expansion after this.
        # Neutralize any Jinja opener produced by entity data or by a template
        # expression so the restricted output cannot trigger a second evaluation.
        return _neutralize_template_syntax(rendered)
    except (TemplateError, TypeError, ValueError) as err:
        LOGGER.warning(
            "Could not render a restricted system prompt template (%s); using the "
            "default prompt",
            type(err).__name__,
        )
        return DEFAULT_PROMPT


@lru_cache(maxsize=128)
def _compiled_template(source: str) -> JinjaTemplate:
    return _ENVIRONMENT.from_string(source)


async def _async_selected_states(
    hass: HomeAssistant,
    context: Context | None,
    entity_ids: tuple[str, ...],
) -> dict[str, State]:
    user = None
    if context is not None and context.user_id is not None:
        user = await hass.auth.async_get_user(context.user_id)
        if user is None:
            return {}

    selected: dict[str, State] = {}
    for entity_id in entity_ids:
        if user is not None and not user.permissions.check_entity(
            entity_id,
            POLICY_READ,
        ):
            continue
        if state := hass.states.get(entity_id):
            selected[entity_id] = state
    return selected


def _selected_state(
    selected_states: dict[str, State],
    entity_id: object,
) -> State | None:
    if not isinstance(entity_id, str):
        return None
    return selected_states.get(entity_id)


def _safe_text(value: object, *, maximum: int = 2_000) -> str:
    text = " ".join(str(value).split())[:maximum]
    return _neutralize_template_syntax(text)


def _safe_template_value(value: Any, *, depth: int = 0) -> Any:
    """Bound template data and remove executable-looking Jinja delimiters."""
    if depth >= 4:
        return _safe_text(value, maximum=500)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, (list, tuple)):
        return [_safe_template_value(item, depth=depth + 1) for item in value[:40]]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in list(value.items())[:40]:
            if not isinstance(key, str):
                continue
            result[_safe_text(key, maximum=120)] = _safe_template_value(
                item,
                depth=depth + 1,
            )
        return result
    return _safe_text(value)


def _neutralize_template_syntax(value: str) -> str:
    return (
        value.replace("{{", "\uff5b\uff5b")
        .replace("{%", "\uff5b\uff05")
        .replace("{#", "\uff5b\uff03")
    )
