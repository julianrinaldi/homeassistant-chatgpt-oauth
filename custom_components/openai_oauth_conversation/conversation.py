"""Conversation agent for ChatGPT OAuth."""
from __future__ import annotations

from typing import Any, Literal

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .client import ChatGPTOAuthClient
from .const import (
    CONF_ENABLE_HASS_CONTROL,
    DEFAULT_ENABLE_HASS_CONTROL,
    DOMAIN,
)
from .exceptions import ChatGPTOAuthError

LLM_HASS_API = "assist"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ChatGPT OAuth conversation entity."""
    async_add_entities([ChatGPTOAuthConversationEntity(config_entry)])


class ChatGPTOAuthConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
):
    """Home Assistant Assist agent backed by ChatGPT OAuth."""

    _attr_supports_streaming = False

    def __init__(self, entry: ConfigEntry) -> None:
        self.entry = entry
        self._control_enabled = bool(
            entry.data.get(
                CONF_ENABLE_HASS_CONTROL,
                DEFAULT_ENABLE_HASS_CONTROL,
            )
        )
        self._attr_supported_features = (
            conversation.ConversationEntityFeature.CONTROL
            if self._control_enabled
            else conversation.ConversationEntityFeature(0)
        )
        # Preserve the original unique ID and existing conversation entity ID.
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.title

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return all languages supported by the selected model."""
        return MATCH_ALL

    @property
    def _client(self) -> ChatGPTOAuthClient:
        client = self.entry.runtime_data
        if not isinstance(client, ChatGPTOAuthClient):
            raise HomeAssistantError("The ChatGPT OAuth integration is not loaded")
        return client

    async def async_added_to_hass(self) -> None:
        """Register this entity as the config entry's conversation agent."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister the conversation agent."""
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Handle one Assist request and preserve its conversation history."""
        client = self._client
        try:
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                LLM_HASS_API if self._control_enabled else None,
                client.system_prompt,
                user_input.extra_system_prompt,
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        instructions = _chat_log_instructions(chat_log) or client.system_prompt
        input_items = _chat_log_input_items(chat_log)
        try:
            if chat_log.llm_api:
                result = await client.async_create_tool_response(
                    model=client.model,
                    reasoning_effort=client.reasoning_effort,
                    instructions=instructions,
                    input_items=input_items,
                    llm_api=chat_log.llm_api,
                )
            else:
                result = await client.async_create_response(
                    model=client.model,
                    reasoning_effort=client.reasoning_effort,
                    instructions=instructions,
                    input_items=input_items,
                )
        except ChatGPTOAuthError as err:
            raise HomeAssistantError(str(err)) from err

        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(
                agent_id=user_input.agent_id,
                content=result.text,
            )
        )
        return conversation.async_get_result_from_chat_log(user_input, chat_log)


# Backward-compatible class name for downstream imports.
OpenAIOAuthConversationEntity = ChatGPTOAuthConversationEntity


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
    """Convert visible Home Assistant chat history to Responses input items."""
    input_items: list[dict[str, Any]] = []
    for item in chat_log.content:
        role = getattr(item, "role", None)
        role_value = getattr(role, "value", role)
        content = getattr(item, "content", None)
        if not isinstance(content, str) or not content.strip():
            continue
        if role_value not in {"user", "assistant"}:
            continue
        input_items.append(
            {
                "type": "message",
                "role": role_value,
                "content": content,
            }
        )

    if not input_items or input_items[-1].get("role") != "user":
        raise HomeAssistantError("The Assist chat log does not contain a user message")
    return input_items
