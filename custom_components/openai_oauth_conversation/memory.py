"""Conversation-history selection and optional summarization."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
from typing import TYPE_CHECKING, Any

from homeassistant.components import conversation
from homeassistant.exceptions import HomeAssistantError

from .const import (
    LOGGER,
    MAX_MEMORY_SUMMARY_CACHE_ENTRIES,
    MAX_MEMORY_SUMMARY_CHARACTERS,
    MAX_MEMORY_SUMMARY_SOURCE_CHARACTERS,
    MEMORY_MODE_CURRENT_TURN,
    MEMORY_MODE_FULL,
    MEMORY_MODE_RECENT,
    MEMORY_MODE_SUMMARIZED,
)
from .content import text_part
from .exceptions import ChatGPTOAuthError
from .models import get_model_profile
from .profiles import AssistantProfileSettings
from .web_search import WebSearchOptions, combine_instructions

if TYPE_CHECKING:
    from .client import ChatGPTOAuthClient

SUMMARY_INSTRUCTIONS = (
    "Create a compact memory summary of the earlier conversation. Preserve only "
    "facts explicitly stated by the user or confirmed by tool results, including "
    "names, preferences, Home Assistant entity IDs, decisions, unresolved "
    "questions, and commitments. Do not add assumptions. Do not answer the latest "
    "request. Use concise plain text without headings or preamble."
)


@dataclass(frozen=True, slots=True)
class PreparedConversationMemory:
    """Conversation input selected for one request."""

    input_items: list[dict[str, Any]]
    earlier_context: str | None = None
    retained_turns: int = 0
    omitted_turns: int = 0
    used_model_summary: bool = False


@dataclass(frozen=True, slots=True)
class _CachedSummary:
    digest: str
    text: str


class ConversationMemoryManager:
    """Prepare bounded conversation context and cache older-turn summaries."""

    def __init__(self) -> None:
        self._summary_cache: OrderedDict[str, _CachedSummary] = OrderedDict()

    async def async_prepare(
        self,
        *,
        chat_log: conversation.ChatLog,
        client: ChatGPTOAuthClient,
        settings: AssistantProfileSettings,
        conversation_id: str | None,
    ) -> PreparedConversationMemory:
        """Return request input matching the profile's memory policy."""
        input_items = chat_log_input_items(chat_log)
        turns = _group_turns(input_items)
        if not turns:
            raise HomeAssistantError(
                "The Assist chat log does not contain a user message"
            )

        if settings.memory_mode == MEMORY_MODE_CURRENT_TURN:
            selected = _trim_turns_to_budget(
                turns[-1:],
                settings.memory_max_characters,
            )
            return _prepared(selected, len(turns))

        total_characters = _turns_character_count(turns)
        if settings.memory_mode == MEMORY_MODE_FULL:
            selected = _trim_turns_to_budget(
                turns,
                settings.memory_max_characters,
            )
            return _prepared(selected, len(turns))

        recent_turns = turns[-settings.memory_max_turns :]
        if settings.memory_mode == MEMORY_MODE_RECENT:
            selected = _trim_turns_to_budget(
                recent_turns,
                settings.memory_max_characters,
            )
            return _prepared(selected, len(turns))

        if settings.memory_mode != MEMORY_MODE_SUMMARIZED:
            # Settings are normalized before reaching this point. Keep a safe
            # fallback in case a manually edited config entry bypasses that.
            selected = _trim_turns_to_budget(
                recent_turns,
                settings.memory_max_characters,
            )
            return _prepared(selected, len(turns))

        if (
            len(turns) <= settings.memory_max_turns
            and total_characters <= settings.memory_max_characters
        ):
            return _prepared(turns, len(turns))

        # Reserve most of the configured budget for verbatim recent turns and
        # use the remainder for a compact, explicitly-labelled earlier context.
        recent_budget = max(1_000, int(settings.memory_max_characters * 0.75))
        selected = _trim_turns_to_budget(recent_turns, recent_budget)
        retained_count = len(selected)
        omitted_count = max(0, len(turns) - retained_count)
        if omitted_count == 0:
            return _prepared(selected, len(turns))

        older_turns = turns[: len(turns) - retained_count]
        summary_budget = min(
            MAX_MEMORY_SUMMARY_CHARACTERS,
            max(500, settings.memory_max_characters - _turns_character_count(selected)),
        )
        earlier_context, used_model_summary = await self._async_get_summary(
            client=client,
            settings=settings,
            conversation_id=conversation_id,
            turns=older_turns,
            max_characters=summary_budget,
        )
        return PreparedConversationMemory(
            input_items=_flatten_turns(selected),
            earlier_context=earlier_context,
            retained_turns=retained_count,
            omitted_turns=omitted_count,
            used_model_summary=used_model_summary,
        )

    async def _async_get_summary(
        self,
        *,
        client: ChatGPTOAuthClient,
        settings: AssistantProfileSettings,
        conversation_id: str | None,
        turns: list[list[dict[str, Any]]],
        max_characters: int,
    ) -> tuple[str, bool]:
        transcript = _transcript(turns)
        if len(transcript) > MAX_MEMORY_SUMMARY_SOURCE_CHARACTERS:
            transcript = transcript[-MAX_MEMORY_SUMMARY_SOURCE_CHARACTERS:]
            transcript = "[Earlier content omitted]\n" + transcript

        digest = hashlib.sha256(transcript.encode("utf-8")).hexdigest()
        cache_key = f"{conversation_id or 'anonymous'}:{settings.profile_id}"
        cached = self._summary_cache.get(cache_key)
        if cached is not None and cached.digest == digest:
            self._summary_cache.move_to_end(cache_key)
            return cached.text[:max_characters], True

        profile = get_model_profile(settings.model)
        summary_effort = (
            "low" if "low" in profile.reasoning_efforts else profile.default_effort
        )
        try:
            result = await client.async_create_response(
                model=settings.model,
                reasoning_effort=summary_effort,
                instructions=(
                    f"{SUMMARY_INSTRUCTIONS} Keep the result under "
                    f"{max_characters} characters."
                ),
                content=[text_part(transcript)],
                web_search=WebSearchOptions(),
            )
            summary = (result.raw_text or result.text).strip()
        except ChatGPTOAuthError as err:
            # A failed memory optimization must never break the actual Assist
            # request. Use a bounded verbatim excerpt and avoid logging content.
            LOGGER.debug(
                "Conversation-memory summarization failed with %s; using an excerpt",
                type(err).__name__,
            )
            return _fallback_excerpt(transcript, max_characters), False

        if not summary:
            return _fallback_excerpt(transcript, max_characters), False
        summary = summary[:max_characters].rstrip()
        self._summary_cache[cache_key] = _CachedSummary(digest=digest, text=summary)
        self._summary_cache.move_to_end(cache_key)
        while len(self._summary_cache) > MAX_MEMORY_SUMMARY_CACHE_ENTRIES:
            self._summary_cache.popitem(last=False)
        return summary, True


def combine_memory_instructions(
    instructions: str | None,
    prepared: PreparedConversationMemory,
) -> str | None:
    """Add older-conversation context without altering visible recent turns."""
    if not prepared.earlier_context:
        return instructions
    label = (
        "Conversation memory summary from earlier turns"
        if prepared.used_model_summary
        else "Conversation excerpt from earlier turns"
    )
    return combine_instructions(
        instructions,
        f"{label}:\n{prepared.earlier_context}",
    )


def chat_log_input_items(
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


def _group_turns(
    input_items: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    turns: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for item in input_items:
        if item.get("role") == "user":
            if current:
                turns.append(current)
            current = [item]
        elif current:
            current.append(item)
    if current:
        turns.append(current)
    return turns


def _trim_turns_to_budget(
    turns: list[list[dict[str, Any]]],
    max_characters: int,
) -> list[list[dict[str, Any]]]:
    selected: list[list[dict[str, Any]]] = []
    used = 0
    for turn in reversed(turns):
        cost = _turn_character_count(turn)
        if selected and used + cost > max_characters:
            break
        selected.append(turn)
        used += cost
        # Always retain the current user turn, even when one unusually long
        # utterance exceeds the configured soft budget.
        if used >= max_characters:
            break
    selected.reverse()
    return selected


def _prepared(
    selected: list[list[dict[str, Any]]],
    total_turns: int,
) -> PreparedConversationMemory:
    return PreparedConversationMemory(
        input_items=_flatten_turns(selected),
        retained_turns=len(selected),
        omitted_turns=max(0, total_turns - len(selected)),
    )


def _flatten_turns(
    turns: list[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    return [dict(item) for turn in turns for item in turn]


def _turn_character_count(turn: list[dict[str, Any]]) -> int:
    return sum(len(str(item.get("content", ""))) for item in turn)


def _turns_character_count(turns: list[list[dict[str, Any]]]) -> int:
    return sum(_turn_character_count(turn) for turn in turns)


def _transcript(turns: list[list[dict[str, Any]]]) -> str:
    lines: list[str] = []
    for item in _flatten_turns(turns):
        role = "User" if item.get("role") == "user" else "Assistant"
        lines.append(f"{role}: {item.get('content', '')}")
    return "\n".join(lines)


def _fallback_excerpt(transcript: str, max_characters: int) -> str:
    excerpt = transcript[-max_characters:]
    if len(excerpt) < len(transcript):
        excerpt = "…" + excerpt.lstrip()
    return excerpt
