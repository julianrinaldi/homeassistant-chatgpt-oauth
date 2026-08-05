"""Tests for native Home Assistant AI Task metadata."""
from __future__ import annotations

from homeassistant.components import ai_task
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openai_oauth_conversation.ai_task import (
    ChatGPTOAuthTaskEntity,
    SUPPORTED_FEATURES,
)
from custom_components.openai_oauth_conversation.const import DOMAIN


def test_ai_task_keeps_stable_unique_id() -> None:
    """The public rename cannot break existing AI Task automations."""
    entry = MockConfigEntry(domain=DOMAIN, title="ChatGPT OAuth", data={})
    entity = ChatGPTOAuthTaskEntity(entry)
    assert entity.unique_id == f"{entry.entry_id}_image_generation"
    assert entity.name == "ChatGPT OAuth AI Task"
    assert SUPPORTED_FEATURES & ai_task.AITaskEntityFeature.GENERATE_DATA
    assert SUPPORTED_FEATURES & ai_task.AITaskEntityFeature.GENERATE_IMAGE
    assert SUPPORTED_FEATURES & ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
