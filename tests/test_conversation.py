"""Tests for Assist history conversion."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from homeassistant.components import conversation
from homeassistant.core import Context
from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser

from custom_components.openai_oauth_conversation.client import ChatGPTOAuthClient
from custom_components.openai_oauth_conversation.const import (
    AI_MEDIA_LLM_API_ID,
    CONF_ENABLE_HASS_CONTROL,
    CONF_ENABLE_SCHEDULED_ACTIONS,
    CONF_ENABLED_LOCAL_SKILLS,
    CONF_SELECTED_SCRIPT_ENTITIES,
    CONF_WEB_SEARCH_MODE,
    DOMAIN,
    EVENT_CONVERSATION_FINISHED,
)
from custom_components.openai_oauth_conversation.conversation import (
    ChatGPTOAuthConversationEntity,
    _apply_web_search_presentation,
    _chat_log_input_items,
    _chat_log_instructions,
    _conversation_finished_event_data,
    _llm_api_selection,
    parse_scheduled_action_confirmation,
)
from custom_components.openai_oauth_conversation.request_context import (
    ResolvedRequestContext,
)
from custom_components.openai_oauth_conversation.responses import (
    ChatGPTTextResponse,
    WebCitation,
)
from custom_components.openai_oauth_conversation.web_search import (
    WEB_SEARCH_AUTO,
    WEB_SEARCH_DISABLED,
)


def test_chat_log_history_is_preserved() -> None:
    """System text is separated while visible turns retain their order."""
    chat_log = SimpleNamespace(
        content=[
            SimpleNamespace(role="system", content="System instructions"),
            SimpleNamespace(role="user", content="First question"),
            SimpleNamespace(role="assistant", content="First answer"),
            SimpleNamespace(role="user", content="Follow-up"),
        ]
    )
    assert _chat_log_instructions(chat_log) == "System instructions"
    input_items = _chat_log_input_items(chat_log)
    assert [item["role"] for item in input_items] == [
        "user",
        "assistant",
        "user",
    ]
    assert input_items[0]["content"] == "First question"
    assert input_items[1]["content"] == "First answer"


def test_scheduled_confirmation_requires_the_exact_whole_raw_message() -> None:
    """Only the reserved standalone phrase produces a trusted action reference."""
    action_id = "01ARZ3NDEKTS"
    for message in (
        f"Confirm scheduled action {action_id}",
        f"confirm scheduled action {action_id.lower()}",
        f"  CONFIRM SCHEDULED ACTION {action_id}!  ",
        f"Confirm scheduled action {action_id}.",
        f"Confirm scheduled action {action_id}?",
    ):
        assert parse_scheduled_action_confirmation(message) == action_id

    for message in (
        f"Please confirm scheduled action {action_id}",
        f"Confirm scheduled action {action_id} now",
        f"Confirm scheduled action: {action_id}",
        f"Confirm  scheduled action {action_id}",
        f"Confirm scheduled action {action_id}!!",
        "Confirm scheduled action 01ARZ3NDEKT",
        "Confirm scheduled action 01ARZ3NDEKTI",
        f"{action_id}",
    ):
        assert parse_scheduled_action_confirmation(message) is None


async def test_missing_local_skill_uses_no_tools_and_disables_web_search(hass) -> None:
    """A missing selected pack reaches the real client only in safe mode."""
    user = MockUser(is_owner=True).add_to_hass(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=14,
        data={
            CONF_ENABLE_HASS_CONTROL: True,
            CONF_ENABLE_SCHEDULED_ACTIONS: True,
            CONF_ENABLED_LOCAL_SKILLS: ["missing-private-pack"],
            CONF_WEB_SEARCH_MODE: WEB_SEARCH_AUTO,
        },
    )
    entry.add_to_hass(hass)
    client = ChatGPTOAuthClient(hass, entry)
    response = ChatGPTTextResponse(
        text="Safe response",
        raw_text="Safe response",
        raw_events=[],
    )
    client.async_create_response = AsyncMock(return_value=response)
    client.async_create_tool_response = AsyncMock()
    entry.runtime_data = client

    entity = ChatGPTOAuthConversationEntity(entry)
    entity.hass = hass
    entity.entity_id = "conversation.chatgpt_oauth"
    user_input = conversation.ConversationInput(
        text="Check my home",
        context=Context(user_id=user.id),
        conversation_id="safe-mode-conversation",
        device_id=None,
        satellite_id=None,
        language="en",
        agent_id=entity.entity_id,
    )
    chat_log = conversation.ChatLog(
        hass,
        "safe-mode-conversation",
        content=[
            conversation.SystemContent(""),
            conversation.UserContent(user_input.text),
        ],
    )

    result = await entity._async_handle_message(user_input, chat_log)

    assert result.response.speech["plain"]["speech"] == "Safe response"
    client.async_create_tool_response.assert_not_awaited()
    call = client.async_create_response.await_args.kwargs
    assert call["web_search"].mode == WEB_SEARCH_DISABLED
    assert "Safe mode is active" in call["instructions"]
    assert chat_log.llm_api is None or not chat_log.llm_api.tools


def test_control_feature_follows_entry_setting() -> None:
    """The Assist agent only advertises entity control when enabled."""
    enabled = ChatGPTOAuthConversationEntity(
        SimpleNamespace(
            entry_id="enabled",
            title="Enabled",
            data={CONF_ENABLE_HASS_CONTROL: True},
        )
    )
    disabled = ChatGPTOAuthConversationEntity(
        SimpleNamespace(
            entry_id="disabled",
            title="Disabled",
            data={CONF_ENABLE_HASS_CONTROL: False},
        )
    )

    assert enabled.supported_features & conversation.ConversationEntityFeature.CONTROL
    assert not (
        disabled.supported_features & conversation.ConversationEntityFeature.CONTROL
    )

    selected_script = ChatGPTOAuthConversationEntity(
        SimpleNamespace(
            entry_id="selected-script",
            title="Selected script",
            data={
                CONF_ENABLE_HASS_CONTROL: False,
                CONF_SELECTED_SCRIPT_ENTITIES: ["script.movie_night"],
            },
        )
    )
    assert (
        selected_script.supported_features
        & conversation.ConversationEntityFeature.CONTROL
    )


def test_ai_task_camera_tools_use_a_separate_privacy_setting() -> None:
    """AI media delegation is independent of general entity control."""
    assert _llm_api_selection(
        SimpleNamespace(
            enable_home_assistant_control=True,
            enable_ai_media_tools=True,
            enable_history_tools=False,
        )
    ) == ["assist", AI_MEDIA_LLM_API_ID]
    assert (
        _llm_api_selection(
            SimpleNamespace(
                enable_home_assistant_control=False,
                enable_ai_media_tools=True,
                enable_history_tools=False,
            )
        )
        == AI_MEDIA_LLM_API_ID
    )
    assert (
        _llm_api_selection(
            SimpleNamespace(
                enable_home_assistant_control=True,
                enable_ai_media_tools=False,
                enable_history_tools=False,
            )
        )
        == "assist"
    )
    assert (
        _llm_api_selection(
            SimpleNamespace(
                enable_home_assistant_control=False,
                enable_ai_media_tools=False,
                enable_history_tools=False,
            )
        )
        is None
    )
    settings = SimpleNamespace(
        enable_home_assistant_control=True,
        enable_ai_media_tools=True,
        enable_history_tools=False,
    )
    assert _llm_api_selection(settings, scoped=True) is None
    assert (
        _llm_api_selection(
            settings,
            allow_immediate_home_actions=False,
        )
        == AI_MEDIA_LLM_API_ID
    )


def test_voice_response_uses_clean_speech_and_separate_source_card() -> None:
    """Assist can speak naturally while its UI retains clickable sources."""

    class Response:
        speech: str | None = None
        card: tuple[str, str] | None = None

        def async_set_speech(self, text: str) -> None:
            self.speech = text

        def async_set_card(self, title: str, content: str) -> None:
            self.card = (title, content)

    response = Response()
    result = ChatGPTTextResponse(
        text="It will rain this evening.",
        raw_text="It will rain this evening.",
        raw_events=[],
        citations=[
            WebCitation(
                url="https://example.com/weather",
                title="Weather source",
                start_index=0,
                end_index=27,
            )
        ],
    )
    conversation_result = SimpleNamespace(response=response)

    _apply_web_search_presentation(
        conversation_result,
        result,
        include_sources=False,
    )

    assert response.speech == "It will rain this evening."
    assert response.card is not None
    assert response.card[0] == "Web search sources"
    assert "Sources:" in response.card[1]


def test_visible_sources_do_not_create_a_duplicate_card() -> None:
    """The opt-in cited response remains the only presentation surface."""

    class Response:
        speech: str | None = None
        card: tuple[str, str] | None = None

        def async_set_speech(self, text: str) -> None:
            self.speech = text

        def async_set_card(self, title: str, content: str) -> None:
            self.card = (title, content)

    response = Response()
    result = ChatGPTTextResponse(
        text="Cited answer.\n\nSources:\n1. Example",
        raw_text="Cited answer.",
        raw_events=[],
        citations=[WebCitation(url="https://example.com", title="Example")],
    )

    _apply_web_search_presentation(
        SimpleNamespace(response=response),
        result,
        include_sources=True,
    )

    assert response.speech == result.text
    assert response.card is None


def test_generated_image_is_presented_in_an_assist_card() -> None:
    """Generated image URLs remain visual instead of entering spoken metadata."""

    class Response:
        speech: str | None = None
        card: tuple[str, str] | None = None

        def async_set_speech(self, text: str) -> None:
            self.speech = text

        def async_set_card(self, title: str, content: str) -> None:
            self.card = (title, content)

    response = Response()
    result = ChatGPTTextResponse(
        text="I created the image.",
        raw_text="I created the image.",
        raw_events=[],
        generated_images=[{"url": "/api/ai_task/generated.png?authSig=signed"}],
    )

    _apply_web_search_presentation(
        SimpleNamespace(response=response),
        result,
        include_sources=False,
    )

    assert response.speech == "I created the image."
    assert response.card is not None
    assert response.card[0] == "Generated image"
    assert (
        "![Generated image](/api/ai_task/generated.png?authSig=signed)"
        in (response.card[1])
    )


def test_conversation_finished_event_is_metadata_only() -> None:
    """Completion diagnostics never contain prompts, answers, or tool arguments."""
    result = ChatGPTTextResponse(
        text="Sensitive assistant answer",
        raw_text="Sensitive assistant answer",
        raw_events=[{"request": "Sensitive prompt"}],
        tool_names=["HassTurnOff", "web_search"],
        tool_call_count=2,
    )
    event_data = _conversation_finished_event_data(
        agent_entity_id="conversation.chatgpt_oauth",
        conversation_id="conversation-123",
        settings=SimpleNamespace(
            model="gpt-5.6-terra",
            reasoning_effort="medium",
        ),
        duration_ms=850,
        result=result,
        continued_listening=True,
        error_type=None,
        request_context=ResolvedRequestContext(
            satellite_device_id="satellite-device-id",
            area_id="kitchen-area-id",
        ),
    )

    assert EVENT_CONVERSATION_FINISHED == "chatgpt_oauth.conversation_finished"
    assert set(event_data) == {
        "agent_entity_id",
        "conversation_id",
        "model",
        "thinking_level",
        "duration_ms",
        "tool_names",
        "tool_call_count",
        "web_search_used",
        "continued_listening",
        "success",
        "error_type",
        "satellite_device_id",
        "area_id",
    }
    assert event_data["success"] is True
    assert event_data["tool_names"] == ["HassTurnOff", "web_search"]
    serialized = str(event_data)
    assert "Sensitive prompt" not in serialized
    assert "Sensitive assistant answer" not in serialized
