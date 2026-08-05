"""Tests for Assist history conversion."""
from __future__ import annotations

from types import SimpleNamespace

from homeassistant.components import conversation

from custom_components.openai_oauth_conversation.const import (
    CONF_ENABLE_HASS_CONTROL,
)
from custom_components.openai_oauth_conversation.conversation import (
    ChatGPTOAuthConversationEntity,
    _chat_log_input_items,
    _chat_log_instructions,
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

    assert (
        enabled.supported_features
        & conversation.ConversationEntityFeature.CONTROL
    )
    assert not (
        disabled.supported_features
        & conversation.ConversationEntityFeature.CONTROL
    )
