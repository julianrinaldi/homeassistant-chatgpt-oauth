"""Tests for Assist history conversion."""

from __future__ import annotations

from types import SimpleNamespace

from homeassistant.components import conversation

from custom_components.openai_oauth_conversation.const import (
    CONF_ENABLE_HASS_CONTROL,
    EVENT_CONVERSATION_FINISHED,
)
from custom_components.openai_oauth_conversation.conversation import (
    ChatGPTOAuthConversationEntity,
    _apply_web_search_presentation,
    _chat_log_input_items,
    _chat_log_instructions,
    _conversation_finished_event_data,
)
from custom_components.openai_oauth_conversation.request_context import (
    ResolvedRequestContext,
)
from custom_components.openai_oauth_conversation.responses import (
    ChatGPTTextResponse,
    WebCitation,
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
