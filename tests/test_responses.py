"""Tests for streamed response parsing helpers."""

from __future__ import annotations

import base64
import struct

from custom_components.openai_oauth_conversation.responses import (
    ChatGPTTextResponse,
    WebCitation,
    decode_image_item,
    image_items_from_event,
    parse_reported_size,
    png_dimensions,
    render_text_with_web_citations,
    response_output_items,
    text_from_output_items,
    url_citation_from_annotation,
    url_citations_from_output_items,
    web_search_actions_from_output_items,
    web_sources,
)


def _png(width: int, height: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + struct.pack(">II", width, height)
        + b"\x08\x06\x00\x00\x00"
    )


def test_completed_text_is_extracted() -> None:
    """Final-only Responses output is supported even without delta events."""
    event = {
        "type": "response.completed",
        "response": {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "Hello"},
                        {"type": "output_text", "text": " world"},
                    ],
                }
            ]
        },
    }
    items = response_output_items(event)
    assert text_from_output_items(items) == "Hello world"


def test_image_result_decoding_and_dimensions() -> None:
    """A final image tool result becomes a native AI Task image result."""
    image_data = _png(1536, 1024)
    item = {
        "type": "image_generation_call",
        "status": "completed",
        "result": base64.b64encode(image_data).decode(),
        "output_format": "png",
        "revised_prompt": "A refined prompt",
        "model": "gpt-image-1",
    }
    result = decode_image_item(item)
    assert result is not None
    assert result.image_data == image_data
    assert result.mime_type == "image/png"
    assert (result.width, result.height) == (1536, 1024)
    assert result.revised_prompt == "A refined prompt"
    assert result.model == "gpt-image-1"
    assert png_dimensions(image_data) == (1536, 1024)


def test_image_items_and_reported_sizes() -> None:
    """Image results are found in direct and completed response events."""
    direct = {"item": {"type": "image_generation_call", "status": "completed"}}
    completed = {
        "response": {
            "output": [{"type": "image_generation_call", "status": "completed"}]
        }
    }
    assert len(image_items_from_event(direct)) == 1
    assert len(image_items_from_event(completed)) == 1
    assert parse_reported_size("1024x1536") == (1024, 1536)
    assert parse_reported_size({"width": 512, "height": 768}) == (512, 768)


def test_web_search_citations_and_sources_are_clickable() -> None:
    """Completed web-search output becomes clickable Markdown and metadata."""
    text = "The Eiffel Tower opened in 1889."
    start = text.index("opened")
    items = [
        {
            "type": "web_search_call",
            "id": "ws_123",
            "status": "completed",
            "action": {
                "type": "search",
                "query": "Eiffel Tower opening date",
                "sources": [
                    {"type": "url", "url": "https://example.com/eiffel"},
                    {"type": "url", "url": "https://example.org/history"},
                ],
            },
        },
        {
            "type": "message",
            "content": [
                {
                    "type": "output_text",
                    "text": text,
                    "annotations": [
                        {
                            "type": "url_citation",
                            "url": "https://example.com/eiffel",
                            "title": "Eiffel Tower history",
                            "start_index": start,
                            "end_index": len(text),
                        }
                    ],
                }
            ],
        },
    ]

    citations = url_citations_from_output_items(items)
    searches = web_search_actions_from_output_items(items)
    sources = web_sources(citations, searches)
    rendered = render_text_with_web_citations(text, citations, searches)

    assert citations[0].title == "Eiffel Tower history"
    assert searches[0].query == "Eiffel Tower opening date"
    assert [source.url for source in sources] == [
        "https://example.com/eiffel",
        "https://example.org/history",
    ]
    assert "The Eiffel Tower opened in 1889." in rendered
    assert "[1](<https://example.com/eiffel>)" in rendered
    assert "[Eiffel Tower history](<https://example.com/eiffel>)" in rendered
    assert "[example.org](<https://example.org/history>)" in rendered


def test_text_response_always_exposes_a_cited_variant() -> None:
    """Clean action text can coexist with an always-available cited answer."""
    raw_text = "A current fact."
    response = ChatGPTTextResponse(
        text=raw_text,
        raw_text=raw_text,
        raw_events=[],
        citations=[
            WebCitation(
                url="https://example.com/fact",
                title="Fact source",
                start_index=0,
                end_index=len(raw_text),
            )
        ],
    )

    assert response.text == raw_text
    assert "Sources:" in response.cited_text
    assert "https://example.com/fact" in response.cited_text


def test_streamed_nested_url_annotation_is_supported() -> None:
    """Streaming annotations may wrap citation fields in ``url_citation``."""
    citation = url_citation_from_annotation(
        {
            "type": "url_citation",
            "url_citation": {
                "url": "https://example.com/current",
                "title": "Current source",
                "start_index": 0,
                "end_index": 7,
            },
        }
    )
    assert citation is not None
    assert citation.url == "https://example.com/current"
    assert citation.end_index == 7


def test_unsafe_citation_url_is_not_rendered() -> None:
    """Credentials and control characters cannot become clickable citations."""
    assert (
        url_citation_from_annotation(
            {
                "type": "url_citation",
                "url": "https://user:password@example.com/private",
                "title": "Unsafe",
            }
        )
        is None
    )
    assert (
        url_citation_from_annotation(
            {
                "type": "url_citation",
                "url": "https://example.com/line\nbreak",
                "title": "Unsafe",
            }
        )
        is None
    )
