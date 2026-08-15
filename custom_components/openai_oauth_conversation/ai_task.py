"""AI Task entity for ChatGPT OAuth data and image generation."""

from __future__ import annotations

from typing import Any, NoReturn

from homeassistant.components import ai_task, conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .client import ChatGPTOAuthClient
from .const import (
    DEFAULT_AI_TASK_SYSTEM_PROMPT,
    INTEGRATION_VERSION,
    MAX_IMAGE_ATTACHMENTS,
)
from .content import read_data_attachments, read_image_attachments, text_part
from .exceptions import (
    ChatGPTOAuthError,
    RequestValidationError,
    StructuredOutputError,
)
from .models import get_model_profile, reasoning_effort_for_request

SUPPORTED_FEATURES = (
    ai_task.AITaskEntityFeature.GENERATE_DATA
    | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
    | ai_task.AITaskEntityFeature.GENERATE_IMAGE
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ChatGPT OAuth AI Task entity."""
    async_add_entities([ChatGPTOAuthTaskEntity(config_entry)])


def _raise_task_error(error: ChatGPTOAuthError) -> NoReturn:
    if isinstance(error, (RequestValidationError, StructuredOutputError)):
        raise ServiceValidationError(str(error)) from error
    raise HomeAssistantError(str(error)) from error


class ChatGPTOAuthTaskEntity(ai_task.AITaskEntity):
    """Generate structured data, text, and images through ChatGPT OAuth."""

    _attr_supported_features = SUPPORTED_FEATURES

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the AI Task entity."""
        super().__init__()
        self.entry = entry
        # Preserve the established unique ID so existing entity IDs and
        # automations remain compatible across upgrades.
        self._attr_unique_id = f"{entry.entry_id}_image_generation"
        self._attr_name = f"{entry.title} AI Task"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose non-sensitive model and transport diagnostics."""
        client = self._client
        profile = get_model_profile(client.model)
        return {
            "integration_version": INTEGRATION_VERSION,
            "configured_model": profile.slug,
            "configured_thinking_level": client.reasoning_effort,
            "request_reasoning_effort": reasoning_effort_for_request(
                profile.slug,
                client.reasoning_effort,
            ),
            "transport": ("responses_lite" if profile.responses_lite else "responses"),
            "maximum_image_attachments": MAX_IMAGE_ATTACHMENTS,
            "web_search_mode": client.web_search_options.mode,
            "web_search_context_size": client.web_search_options.context_size,
            "web_search_includes_sources_in_text": (
                client.web_search_options.include_sources
            ),
            "web_search_live_access": client.web_search_options.live_access,
            "web_search_uses_home_assistant_location": (
                client.web_search_options.use_home_assistant_location
            ),
        }

    @property
    def _client(self) -> ChatGPTOAuthClient:
        client = self.entry.runtime_data
        if not isinstance(client, ChatGPTOAuthClient):
            raise HomeAssistantError("The ChatGPT OAuth integration is not loaded")
        return client

    async def _async_generate_data(
        self,
        task: ai_task.GenDataTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenDataTaskResult:
        """Handle ``ai_task.generate_data``."""
        content: list[dict[str, Any]] = [text_part(task.instructions)]
        if task.attachments:
            try:
                content.extend(
                    await self.hass.async_add_executor_job(
                        read_data_attachments,
                        list(task.attachments),
                    )
                )
            except ChatGPTOAuthError as err:
                _raise_task_error(err)

        client = self._client
        try:
            result = await client.async_create_data_response(
                model=client.model,
                reasoning_effort=client.reasoning_effort,
                instructions=_chat_log_instructions(chat_log),
                content=content,
                structure_name=task.name,
                structure=task.structure,
                llm_api=chat_log.llm_api,
                web_search=client.web_search_options,
            )
        except ChatGPTOAuthError as err:
            _raise_task_error(err)

        return ai_task.GenDataTaskResult(
            conversation_id=chat_log.conversation_id,
            data=result.data,
        )

    async def _async_generate_image(
        self,
        task: ai_task.GenImageTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenImageTaskResult:
        """Handle ``ai_task.generate_image`` with up to ten source images."""
        content: list[dict[str, Any]] = [text_part(task.instructions)]
        if task.attachments:
            try:
                content.extend(
                    await self.hass.async_add_executor_job(
                        read_image_attachments,
                        list(task.attachments),
                    )
                )
            except ChatGPTOAuthError as err:
                _raise_task_error(err)

        client = self._client
        try:
            result = await client.async_create_image_response(
                model=client.model,
                reasoning_effort=client.reasoning_effort,
                content=content,
            )
        except ChatGPTOAuthError as err:
            _raise_task_error(err)

        return ai_task.GenImageTaskResult(
            image_data=result.image_data,
            conversation_id=chat_log.conversation_id,
            mime_type=result.mime_type,
            width=result.width,
            height=result.height,
            model=result.model or client.model,
            revised_prompt=result.revised_prompt,
        )


# Compatibility aliases for v0.x imports and entity-registry migrations.
OpenAIOAuthTaskEntity = ChatGPTOAuthTaskEntity
OpenAIOAuthImageTaskEntity = ChatGPTOAuthTaskEntity


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
    return "\n\n".join(instructions) or DEFAULT_AI_TASK_SYSTEM_PROMPT
