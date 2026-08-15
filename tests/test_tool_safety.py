"""Tests for bounded Home Assistant tool loops."""

from __future__ import annotations

from homeassistant.helpers import llm

from custom_components.openai_oauth_conversation.tool_safety import ToolSafetyTracker


def _call(tool_name: str, **arguments: object) -> llm.ToolInput:
    return llm.ToolInput(tool_name=tool_name, tool_args=arguments)


def test_repeated_successful_call_is_stopped() -> None:
    """An already-completed identical action is never executed twice."""
    tracker = ToolSafetyTracker(max_calls=10, max_time=60)
    call = _call("HassTurnOn", entity_id="light.kitchen")

    assert tracker.before_call(call) is None
    assert tracker.record(call, {"success": True}, duration=0.1, failed=False) is None

    stop = tracker.before_call(call)
    assert stop is not None
    assert stop.error_type == "repeated_identical_tool_call"
    assert "already completed" in stop.message


def test_repeated_failures_for_same_entity_are_stopped() -> None:
    """Two failures against one target produce a specific explanation."""
    tracker = ToolSafetyTracker(max_calls=10, max_time=60)
    first = _call("HassTurnOn", entity_id="light.kitchen")
    second = _call("HassSetPosition", entity_id="light.kitchen", position=50)

    assert (
        tracker.record(
            first,
            {"error": "ServiceValidationError"},
            duration=0.1,
            failed=True,
        )
        is None
    )
    stop = tracker.record(
        second,
        {"error": "ServiceValidationError"},
        duration=0.1,
        failed=True,
    )

    assert stop is not None
    assert stop.error_type == "repeated_entity_failure"
    assert stop.message == (
        "I could not complete that because the same device action failed repeatedly."
    )


def test_repeated_camera_failures_are_treated_as_one_target() -> None:
    """Different questions cannot hide repeated failures for one camera."""
    tracker = ToolSafetyTracker(max_calls=10, max_time=60)
    first = _call(
        "AnalyzeCamera",
        camera_name="Front Door Camera",
        question="Who is there?",
    )
    second = _call(
        "AnalyzeCamera",
        camera_name="Front Door Camera",
        question="What is happening?",
    )

    assert (
        tracker.record(first, {"error": "SnapshotError"}, duration=1, failed=True)
        is None
    )
    stop = tracker.record(
        second,
        {"error": "SnapshotError"},
        duration=1,
        failed=True,
    )

    assert stop is not None
    assert stop.error_type == "repeated_entity_failure"


def test_configured_call_and_time_limits_are_enforced() -> None:
    """Tool safety reports which configured budget was exhausted."""
    tracker = ToolSafetyTracker(max_calls=1, max_time=10)
    first = _call("GetLiveContext")
    tracker.record(first, {"state": "on"}, duration=10, failed=False)

    time_stop = tracker.before_call(_call("HassTurnOff", name="Kitchen"))
    assert time_stop is not None
    assert time_stop.error_type == "tool_call_limit"

    tracker = ToolSafetyTracker(max_calls=10, max_time=10)
    tracker.record(first, {"state": "on"}, duration=10, failed=False)
    time_stop = tracker.before_call(_call("HassTurnOff", name="Kitchen"))
    assert time_stop is not None
    assert time_stop.error_type == "tool_time_limit"


def test_alternating_calls_with_unchanged_results_are_stopped() -> None:
    """Different arguments cannot hide an A-B-A-B no-progress loop."""
    tracker = ToolSafetyTracker(max_calls=10, max_time=60)
    calls_and_results = (
        (_call("GetState", name="Kitchen one"), {"state": "unknown"}),
        (_call("FindEntity", name="Window one"), {"matches": []}),
        (_call("GetState", name="Kitchen two"), {"state": "unknown"}),
        (_call("FindEntity", name="Window two"), {"matches": []}),
    )

    stop = None
    for call, result in calls_and_results:
        assert tracker.before_call(call) is None
        stop = tracker.record(call, result, duration=0.1, failed=False)

    assert stop is not None
    assert stop.error_type == "alternating_tool_loop"
    assert "without returning new information" in stop.message


def test_generated_image_metadata_is_retained_without_bytes() -> None:
    """The outer Assist response can display an AI Task image safely."""
    tracker = ToolSafetyTracker(max_calls=5, max_time=60)
    tracker.record(
        _call("GenerateImage", instructions="Draw a cat"),
        {
            "created": True,
            "generated_image": {
                "url": "/api/ai_task/cat.png?authSig=signed",
                "media_source_id": "media-source://ai_task/cat.png",
                "mime_type": "image/png",
                "image_data": b"not-retained",
            },
        },
        duration=1,
        failed=False,
    )

    assert tracker.generated_images == [
        {
            "url": "/api/ai_task/cat.png?authSig=signed",
            "media_source_id": "media-source://ai_task/cat.png",
            "mime_type": "image/png",
        }
    ]
