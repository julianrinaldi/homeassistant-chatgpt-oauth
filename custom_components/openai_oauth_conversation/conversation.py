"""Conversation agents for ChatGPT OAuth."""

from __future__ import annotations

import re
import time
from typing import Any, Literal

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .client import ChatGPTOAuthClient
from .const import (
    DOMAIN,
    EVENT_CONVERSATION_FINISHED,
    HISTORY_LLM_API_ID,
    SUBENTRY_TYPE_ASSISTANT,
)
from .exceptions import ChatGPTOAuthError
from .memory import (
    ConversationMemoryManager,
    chat_log_input_items,
    combine_memory_instructions,
)
from .profiles import AssistantProfileSettings, resolve_assistant_profile
from .request_context import (
    ResolvedRequestContext,
    async_resolve_request_context,
    combine_request_context,
)

LLM_HASS_API = "assist"
TOOL_SAFETY_INSTRUCTIONS = (
    "Use the fewest Home Assistant and web-search tools needed. Stop calling tools "
    "as soon as the request is satisfied. Do not repeat an action with identical "
    "arguments, alternate between tools that return no new information, or retry a "
    "failing device action more than once."
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the default and additional ChatGPT OAuth assistants."""
    async_add_entities([ChatGPTOAuthConversationEntity(config_entry)])
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_ASSISTANT:
            continue
        async_add_entities(
            [ChatGPTOAuthConversationEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class ChatGPTOAuthConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
):
    """Home Assistant Assist agent backed by one ChatGPT OAuth profile."""

    _attr_supports_streaming = False

    def __init__(
        self,
        entry: ConfigEntry,
        subentry: ConfigSubentry | None = None,
    ) -> None:
        self.entry = entry
        self.subentry = subentry
        self._memory_manager = ConversationMemoryManager()
        settings = self._settings
        self._attr_supported_features = (
            conversation.ConversationEntityFeature.CONTROL
            if settings.enable_home_assistant_control
            else conversation.ConversationEntityFeature(0)
        )
        # Preserve the original default unique ID and existing entity ID. New
        # profiles use their stable Home Assistant config-subentry identifier.
        self._attr_unique_id = (
            entry.entry_id
            if subentry is None
            else f"{entry.entry_id}_{subentry.subentry_id}"
        )
        self._attr_name = settings.title

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return all languages supported by the selected model."""
        return MATCH_ALL

    @property
    def _settings(self) -> AssistantProfileSettings:
        return resolve_assistant_profile(self.entry, self.subentry)

    @property
    def _client(self) -> ChatGPTOAuthClient:
        client = self.entry.runtime_data
        if not isinstance(client, ChatGPTOAuthClient):
            raise HomeAssistantError("The ChatGPT OAuth integration is not loaded")
        return client

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose non-sensitive profile behavior for troubleshooting."""
        settings = self._settings
        return {
            "profile_id": settings.profile_id,
            "model": settings.model,
            "thinking_level": settings.reasoning_effort,
            "home_assistant_control": settings.enable_home_assistant_control,
            "history_tools": settings.enable_history_tools,
            "user_context": settings.include_user_context,
            "satellite_room_context": settings.include_satellite_room_context,
            "room_entities": settings.include_room_entities,
            "max_tool_calls_per_turn": settings.max_tool_calls,
            "max_total_tool_time": settings.max_tool_time,
            "web_search_mode": settings.web_search.mode,
            "memory_mode": settings.memory_mode,
            "memory_max_turns": settings.memory_max_turns,
            "memory_max_characters": settings.memory_max_characters,
        }

    async def async_added_to_hass(self) -> None:
        """Register this entity as a conversation agent."""
        await super().async_added_to_hass()
        if self.subentry is None:
            conversation.async_set_agent(self.hass, self.entry, self)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister the conversation agent."""
        if self.subentry is None:
            conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Handle one Assist request using this profile's tools and memory."""
        client = self._client
        settings = self._settings
        started = time.monotonic()
        request_context = ResolvedRequestContext()
        result = None
        conversation_result = None
        error_type: str | None = None
        try:
            request_context = await async_resolve_request_context(
                self.hass,
                user_input,
                settings,
            )
            try:
                await chat_log.async_provide_llm_data(
                    user_input.as_llm_context(DOMAIN),
                    _llm_api_selection(settings),
                    settings.prompt,
                    user_input.extra_system_prompt,
                )
            except conversation.ConverseError as err:
                error_type = _event_error_type(err)
                conversation_result = err.as_conversation_result()
                return conversation_result

            instructions = _chat_log_instructions(chat_log) or settings.prompt
            prepared = await self._memory_manager.async_prepare(
                chat_log=chat_log,
                client=client,
                settings=settings,
                conversation_id=(
                    user_input.conversation_id
                    or getattr(chat_log, "conversation_id", None)
                ),
            )
            instructions = combine_memory_instructions(instructions, prepared)
            instructions = combine_request_context(instructions, request_context)
            if chat_log.llm_api:
                instructions = f"{instructions.rstrip()}\n\n{TOOL_SAFETY_INSTRUCTIONS}"
                result = await client.async_create_tool_response(
                    model=settings.model,
                    reasoning_effort=settings.reasoning_effort,
                    instructions=instructions,
                    input_items=prepared.input_items,
                    llm_api=chat_log.llm_api,
                    web_search=settings.web_search,
                    max_tool_calls=settings.max_tool_calls,
                    max_tool_time=settings.max_tool_time,
                )
            else:
                result = await client.async_create_response(
                    model=settings.model,
                    reasoning_effort=settings.reasoning_effort,
                    instructions=instructions,
                    input_items=prepared.input_items,
                    web_search=settings.web_search,
                )

            error_type = result.tool_error_type
            chat_log.async_add_assistant_content_without_tools(
                conversation.AssistantContent(
                    agent_id=user_input.agent_id,
                    content=result.raw_text or result.text,
                )
            )
            conversation_result = conversation.async_get_result_from_chat_log(
                user_input,
                chat_log,
            )
            _apply_web_search_presentation(
                conversation_result,
                result,
                include_sources=settings.web_search.include_sources,
            )
            return conversation_result
        except ChatGPTOAuthError as err:
            error_type = _event_error_type(err)
            raise HomeAssistantError(str(err)) from err
        except Exception as err:
            error_type = error_type or _event_error_type(err)
            raise
        finally:
            self.hass.bus.async_fire(
                EVENT_CONVERSATION_FINISHED,
                _conversation_finished_event_data(
                    agent_entity_id=self.entity_id,
                    conversation_id=(
                        getattr(conversation_result, "conversation_id", None)
                        or user_input.conversation_id
                        or getattr(chat_log, "conversation_id", None)
                    ),
                    settings=settings,
                    duration_ms=round((time.monotonic() - started) * 1000),
                    result=result,
                    continued_listening=bool(
                        getattr(conversation_result, "continue_conversation", False)
                    ),
                    error_type=error_type,
                    request_context=request_context,
                ),
            )


# Backward-compatible class name for downstream imports.
OpenAIOAuthConversationEntity = ChatGPTOAuthConversationEntity


def _llm_api_selection(
    settings: AssistantProfileSettings,
) -> str | list[str] | None:
    """Return the Home Assistant LLM APIs enabled for one profile."""
    api_ids: list[str] = []
    if settings.enable_home_assistant_control:
        api_ids.append(LLM_HASS_API)
    if settings.enable_history_tools:
        api_ids.append(HISTORY_LLM_API_ID)
    if not api_ids:
        return None
    if len(api_ids) == 1:
        return api_ids[0]
    return api_ids


def _apply_web_search_presentation(
    conversation_result: conversation.ConversationResult,
    result: Any,
    *,
    include_sources: bool,
) -> None:
    """Keep Assist speech natural while preserving clickable source details."""
    conversation_result.response.async_set_speech(result.text)
    if not include_sources and (result.citations or result.searches):
        conversation_result.response.async_set_card(
            "Web search sources",
            result.cited_text,
        )


def _chat_log_instructions(chat_log: conversation.ChatLog) -> str:
    """Collect Home Assistant system and developer instructions."""
    instructions: list[str] = []
    for item in chat_log.content:
        role = getattr(item, "role", None)
        role_value = getattr(role, "value", role)
        content = getattr(item, "content", None)
        if (
            role_value in {"system", "developer"}
            and isinstance(content, str)
            and content.strip()
        ):
            instructions.append(content.strip())
    return "\n\n".join(instructions)


def _chat_log_input_items(
    chat_log: conversation.ChatLog,
) -> list[dict[str, Any]]:
    """Backward-compatible wrapper for downstream imports and tests."""
    return chat_log_input_items(chat_log)


def _event_error_type(error: BaseException) -> str:
    """Return a stable event-safe error category without exception text."""
    name = type(error).__name__
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _conversation_finished_event_data(
    *,
    agent_entity_id: str | None,
    conversation_id: str | None,
    settings: AssistantProfileSettings,
    duration_ms: int,
    result: Any,
    continued_listening: bool,
    error_type: str | None,
    request_context: ResolvedRequestContext,
) -> dict[str, Any]:
    """Build a stable event payload that deliberately excludes conversation data."""
    return {
        "agent_entity_id": agent_entity_id,
        "conversation_id": conversation_id,
        "model": settings.model,
        "thinking_level": settings.reasoning_effort,
        "duration_ms": duration_ms,
        "tool_names": result.tool_names if result is not None else [],
        "tool_call_count": result.tool_call_count if result is not None else 0,
        "web_search_used": bool(
            result is not None and (result.searches or result.citations)
        ),
        "continued_listening": continued_listening,
        "success": error_type is None,
        "error_type": error_type,
        "satellite_device_id": request_context.satellite_device_id,
        "area_id": request_context.area_id,
    }
