"""Calendar surface for persistent ChatGPT OAuth scheduled actions."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, override

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityFeature,
    CalendarEvent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .scheduled_actions import (
    ACTIVE_STATUSES,
    ScheduledAction,
    ScheduledActionManager,
    get_scheduled_action_manager,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add one read-only scheduled-actions calendar per ChatGPT account."""
    manager = get_scheduled_action_manager(hass, entry.entry_id)
    if manager is None:
        return
    async_add_entities([ScheduledActionsCalendarEntity(entry, manager)], True)


class ScheduledActionsCalendarEntity(CalendarEntity):
    """Display stored actions in Home Assistant's native Calendar UI."""

    _attr_has_entity_name = True
    _attr_name = "Scheduled actions"
    _attr_icon = "mdi:calendar-clock"
    _attr_should_poll = False
    _attr_supported_features = CalendarEntityFeature.DELETE_EVENT

    def __init__(
        self,
        entry: ConfigEntry,
        manager: ScheduledActionManager,
    ) -> None:
        self._attr_unique_id = f"{entry.entry_id}_scheduled_actions"
        self._manager = manager
        self._remove_listener: Any = None

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the next active scheduled action."""
        now = dt_util.utcnow()
        active = [
            record
            for record in self._manager.records
            if record.status in ACTIVE_STATUSES and record.run_at >= now
        ]
        if not active:
            return None
        return _calendar_event(active[0])

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to persistent manager changes."""
        await super().async_added_to_hass()
        self._remove_listener = self._manager.async_add_listener(
            self._async_manager_updated
        )

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Stop listening before the calendar entity is removed."""
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None
        await super().async_will_remove_from_hass()

    @callback
    def _async_manager_updated(self) -> None:
        if self.hass is not None:
            self.async_write_ha_state()

    @override
    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return actions overlapping a requested calendar range."""
        del hass
        start_utc = dt_util.as_utc(start_date)
        end_utc = dt_util.as_utc(end_date)
        result: list[CalendarEvent] = []
        for record in self._manager.records:
            event_end = record.run_at + timedelta(minutes=1)
            if record.run_at < end_utc and event_end > start_utc:
                result.append(_calendar_event(record))
        return result

    @override
    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Cancel/remove an action after Calendar checked entity permissions."""
        if recurrence_id is not None or recurrence_range is not None:
            raise HomeAssistantError("Scheduled actions do not recur")
        await self._manager.async_delete_from_calendar(uid)


def _calendar_event(record: ScheduledAction) -> CalendarEvent:
    """Create a privacy-safe native calendar event."""
    status = record.status.replace("_", " ").title()
    description_parts = [
        f"Status: {status}",
        f"Created by: {record.creator_name}",
        f"Reference: {record.action_id}",
    ]
    if record.target_names:
        description_parts.append("Targets: " + ", ".join(record.target_names))
    if record.error_type:
        description_parts.append("Result: " + record.error_type.replace("_", " "))
    return CalendarEvent(
        start=record.run_at,
        end=record.run_at + timedelta(minutes=1),
        summary=f"{status}: {record.summary}"[:200],
        description="\n".join(description_parts)[:1_000],
        uid=record.action_id,
    )
