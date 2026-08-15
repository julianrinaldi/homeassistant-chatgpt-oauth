"""Tests for restricted Jinja system-prompt rendering."""

from __future__ import annotations

from homeassistant.core import Context
import pytest

from custom_components.openai_oauth_conversation.const import DEFAULT_PROMPT
from custom_components.openai_oauth_conversation.prompt_template import (
    async_render_system_prompt,
    validate_prompt_template_source,
)
from custom_components.openai_oauth_conversation.request_context import (
    ResolvedRequestContext,
)


async def test_prompt_template_uses_context_and_only_selected_states(hass) -> None:
    """Templates receive opted-in labels and an allowlisted state lookup."""
    hass.states.async_set(
        "input_boolean.quiet_mode",
        "on",
        {"friendly_name": "Quiet Mode"},
    )
    hass.states.async_set("sensor.private_value", "secret")

    rendered = await async_render_system_prompt(
        hass,
        source=(
            "You are Jeeves in {{ area_name }}. User={{ user_name }}. "
            "Quiet={{ states('input_boolean.quiet_mode') }}. "
            "Private={{ states('sensor.private_value') }}."
        ),
        request_context=ResolvedRequestContext(
            user_display_name="Julian",
            area_display_name="Kitchen",
        ),
        context=Context(),
        selected_entity_ids=("input_boolean.quiet_mode",),
    )

    assert rendered == (
        "You are Jeeves in Kitchen. User=Julian. Quiet=on. Private=unknown."
    )
    assert "secret" not in rendered


async def test_prompt_state_text_cannot_trigger_a_second_jinja_render(hass) -> None:
    """Template-looking entity data is neutralized before Home Assistant sees it."""
    hass.states.async_set(
        "sensor.status_message",
        "{{ states('sensor.private_value') }}",
    )

    rendered = await async_render_system_prompt(
        hass,
        source="Status: {{ states('sensor.status_message') }}",
        request_context=ResolvedRequestContext(),
        context=Context(),
        selected_entity_ids=("sensor.status_message",),
    )

    assert "{{" not in rendered
    assert "sensor.private_value" in rendered


async def test_prompt_template_supports_local_time_formatting(hass) -> None:
    """The deliberately supplied local time behaves like a datetime."""
    rendered = await async_render_system_prompt(
        hass,
        source="Local year: {{ now().strftime('%Y') }}",
        request_context=ResolvedRequestContext(),
        context=Context(),
        selected_entity_ids=(),
    )

    assert rendered.startswith("Local year: 20")
    assert len(rendered) == len("Local year: 2026")


async def test_invalid_prompt_template_falls_back_without_crashing(hass) -> None:
    """A runtime template problem keeps Assist available with the safe default."""
    rendered = await async_render_system_prompt(
        hass,
        source="Hello {{ missing_variable }}",
        request_context=ResolvedRequestContext(),
        context=Context(),
        selected_entity_ids=(),
    )

    assert rendered == DEFAULT_PROMPT


def test_prompt_template_syntax_is_validated_on_save() -> None:
    with pytest.raises(ValueError, match="Invalid system prompt template"):
        validate_prompt_template_source("Hello {% if broken %}")
