"""Read-only Home Assistant history, statistics, and energy LLM tools."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components import energy
from homeassistant.components.homeassistant import async_should_expose
from homeassistant.components.recorder import history as recorder_history
from homeassistant.components.recorder import statistics as recorder_statistics
from homeassistant.core import HomeAssistant, State, valid_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import llm
from homeassistant.helpers.recorder import get_instance
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonObjectType
import voluptuous as vol

from .const import (
    DEFAULT_ENERGY_DAYS,
    DEFAULT_ENERGY_POINTS,
    DEFAULT_HISTORY_HOURS,
    DEFAULT_HISTORY_POINTS,
    DEFAULT_STATISTICS_DAYS,
    DEFAULT_STATISTICS_POINTS,
    HISTORY_LLM_API_ID,
    MAX_ENERGY_POINTS,
    MAX_HISTORY_DAYS,
    MAX_HISTORY_ENTITY_IDS,
    MAX_HISTORY_POINTS,
    MAX_STATISTIC_IDS,
    MAX_STATISTICS_DAYS,
    MAX_STATISTICS_POINTS,
)

_HISTORY_PROMPT = """These tools provide read-only access to Home Assistant's recorder.
Use them only when the user asks about past states, trends, long-term statistics,
or configured energy data. Query the shortest useful period. Every requested
entity must be exposed to this voice assistant. Never imply that these tools can
change, delete, or repair recorded data."""

_STATISTIC_PERIODS = ("5minute", "hour", "day", "week", "month", "year")
_STATISTIC_TYPES = ("change", "last_reset", "max", "mean", "min", "state", "sum")
_MAX_ENERGY_STATISTIC_IDS = 20


class HomeHistoryAPI(llm.API):
    """Home Assistant LLM API exposing bounded read-only recorder tools."""

    async def async_get_api_instance(
        self,
        llm_context: llm.LLMContext,
    ) -> llm.APIInstance:
        """Return tools for one conversation context."""
        return llm.APIInstance(
            api=self,
            api_prompt=_HISTORY_PROMPT,
            llm_context=llm_context,
            tools=[
                GetEntityHistoryTool(),
                GetEntityStatisticsTool(),
                GetEnergySummaryTool(),
            ],
        )


def create_history_api(hass: HomeAssistant) -> HomeHistoryAPI:
    """Create the integration's globally registered read-only LLM API."""
    return HomeHistoryAPI(
        hass=hass,
        id=HISTORY_LLM_API_ID,
        name="Home History",
    )


class GetEntityHistoryTool(llm.Tool):
    """Return bounded state changes for exposed entities."""

    name = "GetEntityHistory"
    description = (
        "Get past state changes for up to five Home Assistant entities exposed "
        "to this assistant. Use this for questions such as when a door opened, "
        "whether a device was on, or how a sensor changed recently."
    )
    parameters = vol.Schema(
        {
            vol.Required("entity_ids"): vol.All(
                cv.ensure_list,
                [cv.entity_id],
                vol.Length(min=1, max=MAX_HISTORY_ENTITY_IDS),
            ),
            vol.Optional("hours", default=DEFAULT_HISTORY_HOURS): vol.All(
                vol.Coerce(int),
                vol.Range(min=1, max=MAX_HISTORY_DAYS * 24),
            ),
            vol.Optional("end_time"): cv.string,
            vol.Optional("significant_changes_only", default=True): cv.boolean,
            vol.Optional(
                "max_points_per_entity",
                default=DEFAULT_HISTORY_POINTS,
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=1, max=MAX_HISTORY_POINTS),
            ),
        }
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Query recorder history without permitting arbitrary database access."""
        arguments = self.parameters(tool_input.tool_args)
        entity_ids = _validated_exposed_entity_ids(
            hass,
            llm_context,
            arguments["entity_ids"],
            maximum=MAX_HISTORY_ENTITY_IDS,
        )
        end_time = _parse_end_time(arguments.get("end_time"))
        start_time = end_time - timedelta(hours=arguments["hours"])
        instance = get_instance(hass)
        raw_result = await instance.async_add_executor_job(
            _get_history,
            hass,
            start_time,
            end_time,
            entity_ids,
            arguments["significant_changes_only"],
        )
        maximum = arguments["max_points_per_entity"]
        result: dict[str, list[dict[str, Any]]] = {}
        for entity_id in entity_ids:
            states = list(raw_result.get(entity_id, []))
            result[entity_id] = [
                _state_to_dict(item) for item in _sample(states, maximum)
            ]
        return {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "significant_changes_only": arguments["significant_changes_only"],
            "entities": result,
        }


class GetEntityStatisticsTool(llm.Tool):
    """Return bounded recorder statistics for exposed entity statistic IDs."""

    name = "GetEntityStatistics"
    description = (
        "Get aggregated long-term statistics for up to five exposed Home "
        "Assistant entity statistic IDs. Use this for averages, minimums, "
        "maximums, totals, and changes over time."
    )
    parameters = vol.Schema(
        {
            vol.Required("statistic_ids"): vol.All(
                cv.ensure_list,
                [cv.entity_id],
                vol.Length(min=1, max=MAX_STATISTIC_IDS),
            ),
            vol.Optional("days", default=DEFAULT_STATISTICS_DAYS): vol.All(
                vol.Coerce(int),
                vol.Range(min=1, max=MAX_STATISTICS_DAYS),
            ),
            vol.Optional("end_time"): cv.string,
            vol.Optional("period", default="day"): vol.In(_STATISTIC_PERIODS),
            vol.Optional(
                "types",
                default=["change", "mean", "min", "max", "sum"],
            ): vol.All(
                cv.ensure_list,
                [vol.In(_STATISTIC_TYPES)],
                vol.Length(min=1, max=len(_STATISTIC_TYPES)),
            ),
            vol.Optional(
                "max_points_per_statistic",
                default=DEFAULT_STATISTICS_POINTS,
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=1, max=MAX_STATISTICS_POINTS),
            ),
        }
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Query Home Assistant's supported statistics API."""
        arguments = self.parameters(tool_input.tool_args)
        statistic_ids = _validated_exposed_entity_ids(
            hass,
            llm_context,
            arguments["statistic_ids"],
            maximum=MAX_STATISTIC_IDS,
        )
        days = arguments["days"]
        period = arguments["period"]
        _validate_statistics_range(period, days)
        end_time = _parse_end_time(arguments.get("end_time"))
        start_time = end_time - timedelta(days=days)
        raw_result = await get_instance(hass).async_add_executor_job(
            recorder_statistics.statistics_during_period,
            hass,
            start_time,
            end_time,
            set(statistic_ids),
            period,
            None,
            set(arguments["types"]),
        )
        maximum = arguments["max_points_per_statistic"]
        statistics = {
            statistic_id: [
                _json_safe(row)
                for row in _sample(raw_result.get(statistic_id, []), maximum)
            ]
            for statistic_id in statistic_ids
        }
        return {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "period": period,
            "types": arguments["types"],
            "statistics": statistics,
        }


class GetEnergySummaryTool(llm.Tool):
    """Return statistics for exposed entities configured in Energy Dashboard."""

    name = "GetEnergySummary"
    description = (
        "Get read-only statistics for exposed entity statistic IDs configured in "
        "Home Assistant's Energy Dashboard. Use this for energy production, "
        "consumption, import, export, gas, water, or device-energy questions."
    )
    parameters = vol.Schema(
        {
            vol.Optional("days", default=DEFAULT_ENERGY_DAYS): vol.All(
                vol.Coerce(int),
                vol.Range(min=1, max=MAX_STATISTICS_DAYS),
            ),
            vol.Optional("end_time"): cv.string,
            vol.Optional("period", default="day"): vol.In(
                ("hour", "day", "week", "month")
            ),
            vol.Optional(
                "max_points_per_statistic",
                default=DEFAULT_ENERGY_POINTS,
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=1, max=MAX_ENERGY_POINTS),
            ),
        }
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Read the Energy Dashboard configuration and query its safe IDs."""
        arguments = self.parameters(tool_input.tool_args)
        manager = await energy.async_get_manager(hass)
        configuration = manager.data
        if not configuration:
            return {
                "configured": False,
                "message": "Home Assistant's Energy Dashboard is not configured.",
            }

        paths_by_id = _energy_statistic_paths(configuration)
        exposed_ids = [
            statistic_id
            for statistic_id in sorted(paths_by_id)
            if _is_exposed_entity_id(hass, llm_context, statistic_id)
        ][:_MAX_ENERGY_STATISTIC_IDS]
        if not exposed_ids:
            return {
                "configured": True,
                "message": (
                    "No Energy Dashboard entity statistic IDs are exposed to "
                    "this assistant."
                ),
                "statistics": {},
            }

        days = arguments["days"]
        period = arguments["period"]
        _validate_statistics_range(period, days)
        end_time = _parse_end_time(arguments.get("end_time"))
        start_time = end_time - timedelta(days=days)
        raw_result = await get_instance(hass).async_add_executor_job(
            recorder_statistics.statistics_during_period,
            hass,
            start_time,
            end_time,
            set(exposed_ids),
            period,
            None,
            {"change", "state", "sum"},
        )
        maximum = arguments["max_points_per_statistic"]
        return {
            "configured": True,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "period": period,
            "configured_sources": [
                {
                    "statistic_id": statistic_id,
                    "roles": sorted(paths_by_id[statistic_id]),
                }
                for statistic_id in exposed_ids
            ],
            "statistics": {
                statistic_id: [
                    _json_safe(row)
                    for row in _sample(raw_result.get(statistic_id, []), maximum)
                ]
                for statistic_id in exposed_ids
            },
        }


def _get_history(
    hass: HomeAssistant,
    start_time: datetime,
    end_time: datetime,
    entity_ids: list[str],
    significant_changes_only: bool,
) -> Mapping[str, Sequence[State | Mapping[str, Any]]]:
    """Run one recorder history query in its executor thread."""
    return recorder_history.get_significant_states(
        hass=hass,
        start_time=start_time,
        end_time=end_time,
        entity_ids=entity_ids,
        include_start_time_state=True,
        significant_changes_only=significant_changes_only,
        minimal_response=True,
        no_attributes=True,
    )


def _validated_exposed_entity_ids(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    values: Sequence[str],
    *,
    maximum: int,
) -> list[str]:
    entity_ids = list(dict.fromkeys(values))
    if not entity_ids or len(entity_ids) > maximum:
        raise HomeAssistantError(f"Provide between 1 and {maximum} entity IDs")
    unavailable = [
        entity_id
        for entity_id in entity_ids
        if not _is_exposed_entity_id(hass, llm_context, entity_id)
    ]
    if unavailable:
        raise HomeAssistantError(
            "These entities are missing or not exposed to this assistant: "
            + ", ".join(unavailable)
        )
    return entity_ids


def _is_exposed_entity_id(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    entity_id: str,
) -> bool:
    return bool(
        valid_entity_id(entity_id)
        and hass.states.get(entity_id) is not None
        and llm_context.assistant
        and async_should_expose(hass, llm_context.assistant, entity_id)
    )


def _parse_end_time(value: object) -> datetime:
    if value in (None, ""):
        return dt_util.utcnow()
    if not isinstance(value, str) or (parsed := dt_util.parse_datetime(value)) is None:
        raise HomeAssistantError("end_time must be an ISO 8601 date and time")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return dt_util.as_utc(parsed)


def _validate_statistics_range(period: str, days: int) -> None:
    maximum = {
        "5minute": 7,
        "hour": 90,
        "day": MAX_STATISTICS_DAYS,
        "week": MAX_STATISTICS_DAYS,
        "month": MAX_STATISTICS_DAYS,
        "year": MAX_STATISTICS_DAYS,
    }[period]
    if days > maximum:
        raise HomeAssistantError(
            f"The {period} period supports at most {maximum} requested days"
        )


def _sample(values: Sequence[Any], maximum: int) -> list[Any]:
    """Evenly sample a sequence while preserving its first and last points."""
    values = list(values)
    if len(values) <= maximum:
        return values
    if maximum == 1:
        return [values[-1]]
    indexes = {
        round(index * (len(values) - 1) / (maximum - 1)) for index in range(maximum)
    }
    return [values[index] for index in sorted(indexes)]


def _state_to_dict(value: State | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, State):
        return {
            "entity_id": value.entity_id,
            "state": value.state,
            "last_changed": value.last_changed.isoformat(),
            "last_updated": value.last_updated.isoformat(),
        }
    return dict(_json_safe(value))


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _energy_statistic_paths(configuration: Any) -> dict[str, set[str]]:
    """Find entity statistic IDs without returning the raw Energy config."""
    result: dict[str, set[str]] = {}

    def visit(value: Any, path: tuple[str, ...]) -> None:
        if isinstance(value, str):
            if valid_entity_id(value):
                result.setdefault(value, set()).add(".".join(path) or "energy")
            return
        if isinstance(value, Mapping):
            for key, item in value.items():
                visit(item, (*path, str(key)))
            return
        if isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                visit(item, (*path, str(index)))

    visit(configuration, ())
    return result
