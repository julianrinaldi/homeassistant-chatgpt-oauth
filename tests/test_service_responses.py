"""Tests for compact integration action responses."""

from __future__ import annotations

from custom_components.openai_oauth_conversation import _text_response_data
from custom_components.openai_oauth_conversation.responses import (
    ChatGPTTextResponse,
    WebCitation,
    WebSearchAction,
)


def test_search_response_does_not_repeat_identical_answer_or_sources() -> None:
    """The common no-inline-citation result contains the answer only once."""
    answer = "The latest stable release is Home Assistant 2026.8.2."
    response = _text_response_data(
        ChatGPTTextResponse(
            text=answer,
            raw_text=answer,
            raw_events=[],
            searches=[
                WebSearchAction(
                    call_id="ws_1",
                    action="search",
                    query="latest Home Assistant release",
                    sources=(
                        "https://www.home-assistant.io/blog/2026/08/05/release-20268/",
                    ),
                )
            ],
        ),
        compact=True,
    )

    assert response["text"] == answer
    assert "raw_text" not in response
    assert "cited_text" not in response
    assert response["sources"] == [
        {
            "url": "https://www.home-assistant.io/blog/2026/08/05/release-20268/",
            "title": "www.home-assistant.io",
        }
    ]
    assert response["searches"] == [
        {
            "call_id": "ws_1",
            "action": "search",
            "query": "latest Home Assistant release",
            "queries": [],
            "url": None,
            "pattern": None,
        }
    ]


def test_search_response_keeps_a_genuinely_distinct_cited_variant() -> None:
    """Clickable cited text remains available when it adds information."""
    answer = "The current answer."
    response = _text_response_data(
        ChatGPTTextResponse(
            text=answer,
            raw_text=answer,
            raw_events=[],
            citations=[
                WebCitation(
                    url="https://example.com/current",
                    title="Current source",
                    start_index=0,
                    end_index=len(answer),
                )
            ],
        ),
        compact=True,
    )

    assert response["text"] == answer
    assert "raw_text" not in response
    assert "cited_text" in response
    assert "https://example.com/current" in response["cited_text"]


def test_other_actions_keep_their_legacy_text_fields() -> None:
    """Generate-content and analyze-image response compatibility is unchanged."""
    answer = "A generated answer."
    response = _text_response_data(
        ChatGPTTextResponse(
            text=answer,
            raw_text=answer,
            raw_events=[],
        )
    )

    assert response["text"] == answer
    assert response["raw_text"] == answer
    assert response["cited_text"] == answer
