"""Helpers for composing registered and request-scoped Home Assistant LLM APIs."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

type LLMAPISelection = str | list[str] | llm.API | None


async def async_resolve_llm_api(
    hass: HomeAssistant,
    selection: LLMAPISelection,
    llm_context: llm.LLMContext,
) -> llm.APIInstance | None:
    """Resolve a registered API identifier or an unregistered wrapper API."""
    if selection is None:
        return None
    if isinstance(selection, llm.API):
        return await selection.async_get_api_instance(llm_context)
    return await llm.async_get_api(hass, selection, llm_context)
