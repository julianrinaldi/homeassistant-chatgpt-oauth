"""Tests for AI Task, camera-analysis, and image-generation LLM tools."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant.components.ai_task.const import AITaskEntityFeature
from homeassistant.core import Context
from homeassistant.helpers import llm

from custom_components.openai_oauth_conversation import async_setup
from custom_components.openai_oauth_conversation.const import (
    AI_MEDIA_LLM_API_ID,
    DOMAIN,
)
from custom_components.openai_oauth_conversation.media_tools import (
    AIMediaAPI,
    AnalyzeCameraTool,
    GenerateImageTool,
    RunAITaskTool,
    _accessible_visual_sources,
    _EntityChoice,
)


def _context() -> llm.LLMContext:
    return llm.LLMContext(
        platform=DOMAIN,
        context=Context(),
        language="en",
        assistant="conversation",
        device_id=None,
    )


async def test_media_api_exposes_supported_tools_without_internal_ids(hass) -> None:
    """The model receives human labels and only tools backed by capabilities."""
    provider = _EntityChoice(
        entity_id="ai_task.chatgpt_oauth_ai_task",
        name="ChatGPT OAuth AI Task",
        supported_features=int(
            AITaskEntityFeature.GENERATE_DATA
            | AITaskEntityFeature.SUPPORT_ATTACHMENTS
            | AITaskEntityFeature.GENERATE_IMAGE
        ),
    )
    camera = _EntityChoice(
        entity_id="camera.front_door",
        name="Front Door Camera",
    )
    image = _EntityChoice(
        entity_id="image.last_doorbell_event",
        name="Last Doorbell Event",
    )
    api = AIMediaAPI(hass=hass, id="test_media", name="Test media")

    with (
        patch(
            "custom_components.openai_oauth_conversation.media_tools."
            "_accessible_ai_tasks",
            AsyncMock(return_value=[provider]),
        ),
        patch(
            "custom_components.openai_oauth_conversation.media_tools."
            "_accessible_visual_sources",
            AsyncMock(return_value=[camera, image]),
        ),
    ):
        instance = await api.async_get_api_instance(_context())

    assert [tool.name for tool in instance.tools] == [
        "RunAITask",
        "AnalyzeCamera",
        "GenerateImage",
    ]
    assert "ChatGPT OAuth AI Task" in instance.api_prompt
    assert "Front Door Camera" in instance.api_prompt
    assert provider.entity_id not in instance.api_prompt
    assert camera.entity_id not in instance.api_prompt


async def test_media_api_is_registered_with_home_assistant(hass) -> None:
    """Integration setup makes its AI media API available to conversation."""
    assert await async_setup(hass, {})
    assert AI_MEDIA_LLM_API_ID in {api.id for api in llm.async_get_apis(hass)}


async def test_run_ai_task_uses_attachment_capability_without_recursive_tools(
    hass,
) -> None:
    """Multimodal delegation selects a capable provider and no nested LLM API."""
    provider = _EntityChoice(
        entity_id="ai_task.chatgpt_oauth_ai_task",
        name="ChatGPT OAuth AI Task",
        supported_features=int(
            AITaskEntityFeature.GENERATE_DATA | AITaskEntityFeature.SUPPORT_ATTACHMENTS
        ),
    )
    attachment = {
        "media_content_id": "media-source://image/image.latest_event",
        "media_content_type": "image/jpeg",
    }
    resolve_provider = AsyncMock(return_value=provider)
    generate = AsyncMock(return_value=SimpleNamespace(data={"summary": "Clear"}))

    with (
        patch(
            "custom_components.openai_oauth_conversation.media_tools._resolve_ai_task",
            resolve_provider,
        ),
        patch(
            "custom_components.openai_oauth_conversation.media_tools."
            "_resolve_attachments",
            AsyncMock(return_value=[attachment]),
        ),
        patch(
            "custom_components.openai_oauth_conversation.media_tools."
            "ha_ai_task.async_generate_data",
            generate,
        ),
    ):
        result = await RunAITaskTool().async_call(
            hass,
            llm.ToolInput(
                tool_name="RunAITask",
                tool_args={
                    "instructions": "Summarize the image",
                    "image_names": ["Latest Event"],
                },
            ),
            _context(),
        )

    assert result["result"] == {"summary": "Clear"}
    assert resolve_provider.await_args.kwargs["required_features"] == (
        AITaskEntityFeature.GENERATE_DATA | AITaskEntityFeature.SUPPORT_ATTACHMENTS
    )
    assert generate.await_args.kwargs["attachments"] == [attachment]
    assert generate.await_args.kwargs["llm_api"] is None


async def test_camera_analysis_delegates_snapshot_to_ai_task(hass) -> None:
    """AnalyzeCamera sends one current exposed camera attachment to AI Task."""
    provider = _EntityChoice(
        entity_id="ai_task.chatgpt_oauth_ai_task",
        name="ChatGPT OAuth AI Task",
        supported_features=int(
            AITaskEntityFeature.GENERATE_DATA | AITaskEntityFeature.SUPPORT_ATTACHMENTS
        ),
    )
    camera = _EntityChoice(
        entity_id="camera.front_door",
        name="Front Door Camera",
    )
    generate = AsyncMock(
        return_value=SimpleNamespace(data="A delivery person is holding a package.")
    )

    with (
        patch(
            "custom_components.openai_oauth_conversation.media_tools._resolve_ai_task",
            AsyncMock(return_value=provider),
        ),
        patch(
            "custom_components.openai_oauth_conversation.media_tools."
            "_resolve_visual_source",
            AsyncMock(return_value=camera),
        ),
        patch(
            "custom_components.openai_oauth_conversation.media_tools."
            "ha_ai_task.async_generate_data",
            generate,
        ),
    ):
        result = await AnalyzeCameraTool().async_call(
            hass,
            llm.ToolInput(
                tool_name="AnalyzeCamera",
                tool_args={
                    "camera_name": "Front Door Camera",
                    "question": "What is happening?",
                },
            ),
            _context(),
        )

    assert result["camera"] == "Front Door Camera"
    assert result["analysis"] == "A delivery person is holding a package."
    kwargs = generate.await_args.kwargs
    assert kwargs["entity_id"] == provider.entity_id
    assert kwargs["llm_api"] is None
    assert kwargs["attachments"] == [
        {
            "media_content_id": "media-source://camera/camera.front_door",
            "media_content_type": "image/jpeg",
        }
    ]


async def test_image_generation_returns_displayable_local_artifact(hass) -> None:
    """GenerateImage delegates references and returns no image bytes to the model."""
    provider = _EntityChoice(
        entity_id="ai_task.chatgpt_oauth_ai_task",
        name="ChatGPT OAuth AI Task",
        supported_features=int(
            AITaskEntityFeature.GENERATE_IMAGE | AITaskEntityFeature.SUPPORT_ATTACHMENTS
        ),
    )
    references = [
        {
            "media_content_id": "media-source://camera/camera.front_door",
            "media_content_type": "image/jpeg",
        }
    ]
    generate = AsyncMock(
        return_value={
            "url": "/api/ai_task/generated.png?authSig=signed",
            "media_source_id": "media-source://ai_task/generated_images/generated.png",
            "mime_type": "image/png",
            "width": 1024,
            "height": 1024,
            "image_data": b"must-not-leak",
        }
    )

    with (
        patch(
            "custom_components.openai_oauth_conversation.media_tools._resolve_ai_task",
            AsyncMock(return_value=provider),
        ),
        patch(
            "custom_components.openai_oauth_conversation.media_tools."
            "_resolve_attachments",
            AsyncMock(return_value=references),
        ),
        patch(
            "custom_components.openai_oauth_conversation.media_tools."
            "ha_ai_task.async_generate_image",
            generate,
        ),
    ):
        result = await GenerateImageTool().async_call(
            hass,
            llm.ToolInput(
                tool_name="GenerateImage",
                tool_args={
                    "instructions": "Make this look like a watercolor painting",
                    "reference_image_names": ["Front Door Camera"],
                },
            ),
            _context(),
        )

    assert result["created"] is True
    assert result["generated_image"]["url"].startswith("/api/ai_task/")
    assert "image_data" not in result["generated_image"]
    assert generate.await_args.kwargs["attachments"] == references


async def test_camera_list_requires_assist_exposure(hass) -> None:
    """An unexposed camera can never be selected by the media tools."""
    hass.states.async_set(
        "camera.front_door",
        "streaming",
        {"friendly_name": "Front Door Camera"},
    )
    hass.states.async_set(
        "camera.nursery",
        "streaming",
        {"friendly_name": "Nursery Camera"},
    )

    with patch(
        "custom_components.openai_oauth_conversation.media_tools.async_should_expose",
        side_effect=lambda _hass, _assistant, entity_id: (
            entity_id == "camera.front_door"
        ),
    ):
        sources = await _accessible_visual_sources(hass, _context())

    assert [source.name for source in sources] == ["Front Door Camera"]
