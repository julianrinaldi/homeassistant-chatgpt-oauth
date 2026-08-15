"""Runtime enforcement helpers for explicitly enabled local skill packs."""

from __future__ import annotations

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components.homeassistant import async_should_expose
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import llm

from .local_skills import ResolvedLocalSkillPolicy


async def async_resolve_local_skill_scope(
    hass: HomeAssistant,
    policy: ResolvedLocalSkillPolicy,
    llm_context: llm.LLMContext,
) -> frozenset[str] | None:
    """Resolve a pack scope to exposed, readable entity IDs.

    ``None`` means no skill declared a scope. An empty set means a scope was
    declared but no configured entity is currently accessible; callers must
    fail closed and expose no general Home Assistant tools in that case.
    """
    if policy.missing_skill_ids or policy.skipped_skill_ids:
        return frozenset()
    if not policy.has_scope:
        return None

    entity_ids = set(policy.allowed_entities)
    area_ids = _resolve_area_ids(hass, policy.allowed_areas)
    if area_ids:
        entity_registry = er.async_get(hass)
        device_registry = dr.async_get(hass)
        for entry in entity_registry.entities.values():
            area_id = entry.area_id
            if area_id is None and entry.device_id:
                device = device_registry.async_get(entry.device_id)
                area_id = device.area_id if device else None
            if area_id in area_ids:
                entity_ids.add(entry.entity_id)

    accessible: set[str] = set()
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        if (
            state is None
            or state.state == STATE_UNAVAILABLE
            or not llm_context.assistant
            or not async_should_expose(hass, llm_context.assistant, entity_id)
            or not await _user_can_read(hass, llm_context, entity_id)
        ):
            continue
        accessible.add(entity_id)
    return frozenset(accessible)


def _resolve_area_ids(hass: HomeAssistant, area_names: tuple[str, ...]) -> set[str]:
    registry = ar.async_get(hass)
    requested = {name.casefold() for name in area_names}
    if not requested:
        return set()
    result: set[str] = set()
    for area in registry.async_list_areas():
        labels = {area.name.casefold()}
        aliases = getattr(area, "aliases", ())
        if isinstance(aliases, (list, tuple, set, frozenset)):
            labels.update(
                alias.casefold()
                for alias in aliases
                if isinstance(alias, str) and alias
            )
        if labels.intersection(requested):
            result.add(area.id)
    return result


async def _user_can_read(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    entity_id: str,
) -> bool:
    context = llm_context.context
    if context is None or context.user_id is None:
        return False
    user = await hass.auth.async_get_user(context.user_id)
    return bool(user and user.permissions.check_entity(entity_id, POLICY_READ))
