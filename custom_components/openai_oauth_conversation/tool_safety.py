"""Bounded Home Assistant tool execution and no-progress detection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any

from homeassistant.helpers import llm


@dataclass(frozen=True, slots=True)
class ToolSafetyStop:
    """A user-facing reason to end the tool loop safely."""

    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class _ToolRecord:
    tool_name: str
    signature: str
    result_digest: str
    target: str | None
    failed: bool


@dataclass(slots=True)
class ToolSafetyTracker:
    """Track one turn's tool budget and detect calls that make no progress."""

    max_calls: int
    max_time: float
    call_count: int = 0
    tool_time: float = 0.0
    _tool_names: list[str] = field(default_factory=list)
    _records: list[_ToolRecord] = field(default_factory=list)
    _generated_images: list[dict[str, Any]] = field(default_factory=list)

    @property
    def tool_names(self) -> list[str]:
        """Return unique tool names in first-use order."""
        return list(self._tool_names)

    @property
    def successful_call_count(self) -> int:
        """Return completed calls that did not report a failure."""
        return sum(not record.failed for record in self._records)

    @property
    def generated_images(self) -> list[dict[str, Any]]:
        """Return safe generated-image metadata reported by AI Task tools."""
        return [dict(image) for image in self._generated_images]

    @property
    def remaining_time(self) -> float:
        """Return remaining aggregate tool execution time in seconds."""
        return max(0.0, self.max_time - self.tool_time)

    def before_call(self, call: llm.ToolInput) -> ToolSafetyStop | None:
        """Reject a call that exceeds a limit or repeats completed work."""
        if self.call_count >= self.max_calls:
            return ToolSafetyStop(
                "tool_call_limit",
                "I could not complete that because the configured Home Assistant "
                "tool-call limit was reached.",
            )
        if self.remaining_time <= 0:
            return self.time_limit_stop()

        signature = _call_signature(call)
        matching = [record for record in self._records if record.signature == signature]
        if matching and any(not record.failed for record in matching):
            return ToolSafetyStop(
                "repeated_identical_tool_call",
                "I stopped because the same Home Assistant action was requested "
                "repeatedly after it had already completed.",
            )
        if len(matching) >= 2:
            return ToolSafetyStop(
                "repeated_identical_tool_call",
                "I could not complete that because the same Home Assistant action "
                "kept repeating without making progress.",
            )

        target = _call_target(call)
        if (
            target
            and sum(
                record.failed and record.target == target for record in self._records
            )
            >= 2
        ):
            return ToolSafetyStop(
                "repeated_entity_failure",
                "I could not complete that because the same device action failed "
                "repeatedly.",
            )
        return None

    def record(
        self,
        call: llm.ToolInput,
        result: Any,
        *,
        duration: float,
        failed: bool,
    ) -> ToolSafetyStop | None:
        """Record one executed call and return a no-progress stop if detected."""
        self.call_count += 1
        self.tool_time += max(0.0, duration)
        if call.tool_name not in self._tool_names:
            self._tool_names.append(call.tool_name)
        record = _ToolRecord(
            tool_name=call.tool_name,
            signature=_call_signature(call),
            result_digest=_result_digest(result),
            target=_call_target(call),
            failed=failed or _result_reports_failure(result),
        )
        self._records.append(record)
        if isinstance(result, Mapping) and isinstance(
            generated_image := result.get("generated_image"),
            Mapping,
        ):
            url = generated_image.get("url")
            if isinstance(url, str) and url:
                self._generated_images.append(
                    {
                        key: value
                        for key in (
                            "url",
                            "media_source_id",
                            "mime_type",
                            "width",
                            "height",
                            "model",
                            "revised_prompt",
                        )
                        if (value := generated_image.get(key)) is not None
                    }
                )

        if (
            record.failed
            and record.target
            and sum(
                previous.failed and previous.target == record.target
                for previous in self._records
            )
            >= 2
        ):
            return ToolSafetyStop(
                "repeated_entity_failure",
                "I could not complete that because the same device action failed "
                "repeatedly.",
            )

        if len(self._records) >= 4:
            first, second, third, fourth = self._records[-4:]
            if (
                first.tool_name == third.tool_name
                and second.tool_name == fourth.tool_name
                and first.tool_name != second.tool_name
                and first.result_digest == third.result_digest
                and second.result_digest == fourth.result_digest
            ):
                return ToolSafetyStop(
                    "alternating_tool_loop",
                    "I could not complete that because Home Assistant tools kept "
                    "alternating without returning new information.",
                )
        return None

    @staticmethod
    def time_limit_stop() -> ToolSafetyStop:
        """Return the consistent aggregate-time limit response."""
        return ToolSafetyStop(
            "tool_time_limit",
            "I could not complete that because Home Assistant tools took longer "
            "than the configured time limit.",
        )


def _call_signature(call: llm.ToolInput) -> str:
    return f"{call.tool_name}:{_canonical_json(call.tool_args)}"


def _call_target(call: llm.ToolInput) -> str | None:
    """Return an ephemeral target fingerprint used only for loop detection."""
    targets: list[tuple[str, str]] = []

    def collect(value: Any, key: str = "") -> None:
        if isinstance(value, Mapping):
            for child_key, child in value.items():
                collect(child, str(child_key).casefold())
            return
        if isinstance(value, (list, tuple, set)):
            for child in value:
                collect(child, key)
            return
        if key in {
            "ai_task_name",
            "camera_name",
            "entity_id",
            "device_id",
            "area_id",
            "floor_id",
            "image_names",
            "reference_image_names",
            "target",
            "name",
        } or key.endswith("_entity"):
            targets.append((key, str(value)))

    collect(call.tool_args)
    if not targets:
        return None
    payload = _canonical_json(sorted(targets))
    return hashlib.sha256(payload.encode()).hexdigest()


def _result_digest(result: Any) -> str:
    return hashlib.sha256(_canonical_json(result).encode()).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _result_reports_failure(result: Any) -> bool:
    if not isinstance(result, Mapping):
        return False
    if result.get("success") is False:
        return True
    return any(key in result for key in ("error", "error_text", "exception"))
