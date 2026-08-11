"""Response models and parsers for ChatGPT OAuth."""
from __future__ import annotations

import base64
import binascii
import json
import struct
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from homeassistant.helpers import llm

from .exceptions import ResponseParseError
from .web_search import markdown_escape, safe_web_url


@dataclass(frozen=True, slots=True)
class WebCitation:
    """One URL citation attached to generated text."""

    url: str
    title: str
    start_index: int | None = None
    end_index: int | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-serializable citation metadata."""
        return {
            "url": self.url,
            "title": self.title,
            "start_index": self.start_index,
            "end_index": self.end_index,
        }


@dataclass(frozen=True, slots=True)
class WebSearchAction:
    """One hosted web-search action taken by the model."""

    call_id: str | None
    action: str
    query: str | None = None
    queries: tuple[str, ...] = ()
    url: str | None = None
    pattern: str | None = None
    sources: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-serializable search metadata."""
        return {
            "call_id": self.call_id,
            "action": self.action,
            "query": self.query,
            "queries": list(self.queries),
            "url": self.url,
            "pattern": self.pattern,
            "sources": list(self.sources),
        }


@dataclass(frozen=True, slots=True)
class WebSource:
    """One unique source cited or consulted by web search."""

    url: str
    title: str

    def as_dict(self) -> dict[str, str]:
        """Return JSON-serializable source metadata."""
        return {"url": self.url, "title": self.title}


@dataclass(slots=True)
class ChatGPTTextResponse:
    """Collected text response from the hosted backend."""

    text: str
    raw_events: list[dict[str, Any]]
    citations: list[WebCitation] = field(default_factory=list)
    searches: list[WebSearchAction] = field(default_factory=list)
    raw_text: str | None = None

    @property
    def sources(self) -> list[WebSource]:
        """Return unique cited and consulted web sources."""
        return web_sources(self.citations, self.searches)


@dataclass(slots=True)
class ChatGPTDataResponse:
    """Plain or structured data returned by the hosted backend."""

    data: Any
    text: str
    raw_events: list[dict[str, Any]]
    citations: list[WebCitation] = field(default_factory=list)
    searches: list[WebSearchAction] = field(default_factory=list)

    @property
    def sources(self) -> list[WebSource]:
        """Return unique cited and consulted web sources."""
        return web_sources(self.citations, self.searches)


@dataclass(slots=True)
class ChatGPTImageResponse:
    """Generated image returned by the hosted image tool."""

    image_data: bytes
    mime_type: str
    width: int | None = None
    height: int | None = None
    model: str | None = None
    revised_prompt: str | None = None


@dataclass(slots=True)
class ChatGPTTurn:
    """One Responses turn, optionally containing function or web-search calls."""

    text: str
    function_calls: list[llm.ToolInput]
    raw_events: list[dict[str, Any]]
    citations: list[WebCitation] = field(default_factory=list)
    searches: list[WebSearchAction] = field(default_factory=list)


def response_output_items(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Return Responses output items present in one SSE event."""
    items: list[dict[str, Any]] = []
    direct_item = event.get("item")
    if isinstance(direct_item, dict):
        items.append(direct_item)

    response = event.get("response")
    if isinstance(response, dict):
        output = response.get("output")
        if isinstance(output, list):
            items.extend(item for item in output if isinstance(item, dict))

    output = event.get("output")
    if isinstance(output, list):
        items.extend(item for item in output if isinstance(item, dict))
    return items


def text_from_output_items(items: list[dict[str, Any]]) -> str:
    """Extract final text from completed Responses message items."""
    chunks: list[str] = []
    for item in items:
        if item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") not in {"output_text", "text"}:
                continue
            part_text = part.get("text")
            if isinstance(part_text, str):
                chunks.append(part_text)
    return "".join(chunks).strip()


def _annotation_payload(annotation: dict[str, Any]) -> dict[str, Any]:
    nested = annotation.get("url_citation")
    return nested if isinstance(nested, dict) else annotation


def url_citation_from_annotation(annotation: object) -> WebCitation | None:
    """Convert one Responses URL annotation to stable citation metadata."""
    if not isinstance(annotation, dict):
        return None
    if annotation.get("type") != "url_citation" and not isinstance(
        annotation.get("url_citation"), dict
    ):
        return None

    payload = _annotation_payload(annotation)
    url = safe_web_url(payload.get("url"))
    if url is None:
        return None
    title_value = payload.get("title")
    title = (
        title_value.strip()
        if isinstance(title_value, str) and title_value.strip()
        else (urlsplit(url).hostname or url)
    )
    start = payload.get("start_index")
    end = payload.get("end_index")
    return WebCitation(
        url=url,
        title=title,
        start_index=start if isinstance(start, int) else None,
        end_index=end if isinstance(end, int) else None,
    )


def url_citations_from_output_items(
    items: list[dict[str, Any]],
) -> list[WebCitation]:
    """Extract URL citations from completed Responses message items."""
    citations: list[WebCitation] = []
    for item in items:
        if item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            annotations = part.get("annotations")
            if not isinstance(annotations, list):
                continue
            for annotation in annotations:
                citation = url_citation_from_annotation(annotation)
                if citation is not None:
                    citations.append(citation)
    return dedupe_citations(citations)


def web_search_actions_from_output_items(
    items: list[dict[str, Any]],
) -> list[WebSearchAction]:
    """Extract hosted web-search actions and consulted source URLs."""
    actions: list[WebSearchAction] = []
    for item in items:
        if item.get("type") != "web_search_call":
            continue
        action = item.get("action")
        if not isinstance(action, dict):
            continue
        action_type = action.get("type")
        if not isinstance(action_type, str) or not action_type:
            continue
        query = action.get("query")
        queries_value = action.get("queries")
        queries = (
            tuple(
                value.strip()
                for value in queries_value
                if isinstance(value, str) and value.strip()
            )
            if isinstance(queries_value, list)
            else ()
        )
        sources_value = action.get("sources")
        sources: list[str] = []
        if isinstance(sources_value, list):
            for source in sources_value:
                source_url = safe_web_url(
                    source.get("url") if isinstance(source, dict) else source
                )
                if source_url and source_url not in sources:
                    sources.append(source_url)
        action_url = safe_web_url(action.get("url"))
        pattern = action.get("pattern")
        call_id_value = item.get("id") or item.get("call_id")
        actions.append(
            WebSearchAction(
                call_id=str(call_id_value) if call_id_value is not None else None,
                action=action_type,
                query=(
                    query.strip()
                    if isinstance(query, str) and query.strip()
                    else None
                ),
                queries=queries,
                url=action_url,
                pattern=(
                    pattern.strip()
                    if isinstance(pattern, str) and pattern.strip()
                    else None
                ),
                sources=tuple(sources),
            )
        )
    return dedupe_searches(actions)


def dedupe_citations(citations: list[WebCitation]) -> list[WebCitation]:
    """Remove duplicate URL/range citations while preserving order."""
    result: list[WebCitation] = []
    seen: set[tuple[str, int | None, int | None]] = set()
    for citation in citations:
        key = (citation.url, citation.start_index, citation.end_index)
        if key in seen:
            continue
        seen.add(key)
        result.append(citation)
    return result


def dedupe_searches(searches: list[WebSearchAction]) -> list[WebSearchAction]:
    """Remove duplicate streamed search-call items while preserving order."""
    result: list[WebSearchAction] = []
    seen: set[tuple[Any, ...]] = set()
    for search in searches:
        key = (
            search.call_id,
            search.action,
            search.query,
            search.queries,
            search.url,
            search.pattern,
            search.sources,
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(search)
    return result


def web_sources(
    citations: list[WebCitation],
    searches: list[WebSearchAction],
) -> list[WebSource]:
    """Return unique cited and consulted sources with the best available title."""
    result: list[WebSource] = []
    seen: set[str] = set()
    for citation in citations:
        if citation.url in seen:
            continue
        seen.add(citation.url)
        result.append(WebSource(url=citation.url, title=citation.title))
    for search in searches:
        candidates = list(search.sources)
        if search.url:
            candidates.append(search.url)
        for url in candidates:
            if url in seen:
                continue
            seen.add(url)
            result.append(WebSource(url=url, title=urlsplit(url).hostname or url))
    return result


def render_text_with_web_citations(
    text: str,
    citations: list[WebCitation],
    searches: list[WebSearchAction] | None = None,
) -> str:
    """Render citations as clickable Markdown and append a source list."""
    unique_sources = web_sources(citations, searches or [])
    if not unique_sources:
        return text.strip()

    source_number = {
        source.url: index for index, source in enumerate(unique_sources, 1)
    }
    rendered = text
    insertions: dict[int, list[int]] = {}
    for citation in citations:
        end = citation.end_index
        if end is None or end < 0 or end > len(text):
            continue
        number = source_number[citation.url]
        numbers = insertions.setdefault(end, [])
        if number not in numbers:
            numbers.append(number)
    for index, numbers in sorted(insertions.items(), reverse=True):
        markers = "".join(
            f" [{number}](<{unique_sources[number - 1].url}>)" for number in numbers
        )
        rendered = rendered[:index] + markers + rendered[index:]

    source_lines = ["", "Sources:"]
    for index, source in enumerate(unique_sources, 1):
        source_lines.append(
            f"{index}. [{markdown_escape(source.title)}](<{source.url}>)"
        )
    return rendered.strip() + "\n" + "\n".join(source_lines)


def response_error_message(event: dict[str, Any]) -> str:
    """Extract the most useful error text from a Responses event."""
    response = event.get("response")
    if isinstance(response, dict):
        error = response.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"]
        incomplete = response.get("incomplete_details")
        if isinstance(incomplete, dict) and incomplete.get("reason"):
            return str(incomplete["reason"])

    error = event.get("error")
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"]
    if isinstance(event.get("message"), str):
        return event["message"]
    return json.dumps(event, default=str)[:500]


def parse_tool_arguments(arguments: Any) -> dict[str, Any]:
    """Parse a function-call argument payload."""
    if arguments in (None, ""):
        return {}
    if isinstance(arguments, dict):
        return arguments
    if not isinstance(arguments, str):
        raise ResponseParseError(
            "ChatGPT returned function-call arguments in an unsupported format"
        )
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError as err:
        raise ResponseParseError(
            "ChatGPT returned invalid JSON function-call arguments"
        ) from err
    if not isinstance(parsed, dict):
        raise ResponseParseError(
            "ChatGPT returned function-call arguments that were not an object"
        )
    return parsed


def extract_function_call(item: dict[str, Any]) -> llm.ToolInput | None:
    """Convert one Responses function-call item to Home Assistant input."""
    if item.get("type") != "function_call":
        return None
    name = item.get("name")
    if not isinstance(name, str) or not name:
        return None
    call_id = item.get("call_id") or item.get("id")
    if call_id is None:
        return None
    return llm.ToolInput(
        id=str(call_id),
        tool_name=name,
        tool_args=parse_tool_arguments(item.get("arguments")),
    )


def image_items_from_event(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Return completed image-generation items from one event."""
    return [
        item
        for item in response_output_items(event)
        if item.get("type") == "image_generation_call"
    ]


def mime_type_from_output_format(output_format: Any) -> str:
    """Map a hosted image output format to a MIME type."""
    if not isinstance(output_format, str) or not output_format:
        return "image/png"
    normalized = output_format.lower().lstrip(".")
    if normalized == "jpg":
        normalized = "jpeg"
    if normalized not in {"png", "jpeg", "webp"}:
        return "image/png"
    return f"image/{normalized}"


def parse_reported_size(size: Any) -> tuple[int | None, int | None]:
    """Parse image dimensions returned as ``WIDTHxHEIGHT`` or an object."""
    if isinstance(size, Mapping):
        width_value = size.get("width")
        height_value = size.get("height")
    elif isinstance(size, str):
        try:
            width_value, height_value = size.lower().split("x", 1)
        except ValueError:
            return None, None
    else:
        return None, None

    try:
        width = int(width_value)
        height = int(height_value)
    except (TypeError, ValueError):
        return None, None
    if width <= 0 or height <= 0:
        return None, None
    return width, height


def png_dimensions(image_data: bytes) -> tuple[int | None, int | None]:
    """Read PNG dimensions without adding an image-library dependency."""
    if (
        len(image_data) >= 24
        and image_data[:8] == b"\x89PNG\r\n\x1a\n"
        and image_data[12:16] == b"IHDR"
    ):
        width, height = struct.unpack(">II", image_data[16:24])
        return width, height
    return None, None


def _validate_image_data(image_data: bytes, mime_type: str) -> None:
    """Reject an empty or malformed image result before returning it to HA."""
    signatures = {
        "image/png": image_data.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": image_data.startswith(b"\xff\xd8\xff"),
        "image/webp": (
            len(image_data) >= 12
            and image_data.startswith(b"RIFF")
            and image_data[8:12] == b"WEBP"
        ),
    }
    if not signatures.get(mime_type, False):
        raise ResponseParseError(
            f"ChatGPT image generation returned invalid {mime_type} data"
        )


def decode_image_item(item: dict[str, Any]) -> ChatGPTImageResponse | None:
    """Decode one completed image-generation output item."""
    result = item.get("result")
    if not isinstance(result, str) or not result:
        return None
    try:
        image_data = base64.b64decode(result, validate=True)
    except (binascii.Error, ValueError) as err:
        raise ResponseParseError(
            "ChatGPT image generation returned invalid base64 image data"
        ) from err
    if not image_data:
        raise ResponseParseError("ChatGPT image generation returned an empty image")

    mime_type = mime_type_from_output_format(item.get("output_format"))
    _validate_image_data(image_data, mime_type)

    width, height = parse_reported_size(item.get("size"))
    if width is None or height is None:
        width, height = png_dimensions(image_data)

    model = item.get("model")
    if not isinstance(model, str):
        model = None
    revised_prompt = item.get("revised_prompt")
    if not isinstance(revised_prompt, str):
        revised_prompt = None

    return ChatGPTImageResponse(
        image_data=image_data,
        mime_type=mime_type,
        width=width,
        height=height,
        model=model,
        revised_prompt=revised_prompt,
    )
