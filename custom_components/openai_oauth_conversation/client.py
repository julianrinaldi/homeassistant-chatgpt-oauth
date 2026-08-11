"""Async client for the hosted ChatGPT/Codex OAuth Responses backend."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import aiohttp
import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.json import json_dumps

from .auth import ConfigEntryLike, OAuthTokenManager, extract_account_id
from .const import (
    CODEX_CLIENT_VERSION,
    CODEX_RESPONSES_URL,
    CODEX_USER_AGENT,
    CONF_ACCOUNT_ID,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_REASONING_EFFORT,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_LIVE_ACCESS,
    CONF_WEB_SEARCH_MODE,
    CONF_WEB_SEARCH_USE_HASS_LOCATION,
    DEFAULT_MODEL,
    DEFAULT_PROMPT,
    DEFAULT_WEB_SEARCH_CONTEXT_SIZE,
    DEFAULT_WEB_SEARCH_LIVE_ACCESS,
    DEFAULT_WEB_SEARCH_MODE,
    DEFAULT_WEB_SEARCH_USE_HASS_LOCATION,
    IMAGE_REQUEST_TIMEOUT,
    LEGACY_OUTPUT_LIMIT_KEY,
    LOGGER,
    MAX_TOOL_ITERATIONS,
    ORIGINATOR,
    TEXT_REQUEST_TIMEOUT,
)
from .content import text_part
from .exceptions import (
    AuthenticationError,
    BackendUnavailableError,
    ChatGPTOAuthError,
    RateLimitError,
    RequestTimeoutError,
    RequestValidationError,
    ResponseParseError,
    exception_from_http_response,
    sanitize_backend_message,
)
from .models import (
    get_model_profile,
    normalize_model,
    normalize_reasoning_effort,
    reasoning_effort_for_request,
    validate_reasoning_effort,
)
from .responses import (
    ChatGPTDataResponse,
    ChatGPTImageResponse,
    ChatGPTTextResponse,
    ChatGPTTurn,
    decode_image_item,
    dedupe_citations,
    dedupe_searches,
    extract_function_call,
    image_items_from_event,
    render_text_with_web_citations,
    response_error_message,
    response_output_items,
    text_from_output_items,
    url_citation_from_annotation,
    url_citations_from_output_items,
    web_search_actions_from_output_items,
)
from .schema import (
    fallback_json_instructions,
    is_structured_output_error,
    parse_and_validate_structured_text,
    structured_output_format,
)
from .sse import iter_sse_json
from .web_search import (
    WEB_SEARCH_TOOL_TYPES,
    WebSearchOptions,
    build_web_search_tool,
    combine_instructions,
    normalize_allowed_domains,
    normalize_web_search_context_size,
    normalize_web_search_mode,
    web_search_instructions,
)


def serialize_request_payload(payload: dict[str, Any]) -> bytes:
    """Serialize a request as guaranteed ASCII JSON bytes.

    Home Assistant customizes aiohttp's ``json=`` serializer. Multimegabyte
    base64 attachments are therefore serialized explicitly and sent through
    ``data=`` so no raw binary can enter the shared serializer.
    """
    if _contains_key(payload, LEGACY_OUTPUT_LIMIT_KEY):
        raise RequestValidationError(
            "Refusing to send an obsolete output-token limit to ChatGPT"
        )
    try:
        body = json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError) as err:
        raise RequestValidationError(
            f"Could not serialize the ChatGPT request: {err}"
        ) from err
    if not body.isascii():  # pragma: no cover - ensure_ascii invariant
        raise RequestValidationError(
            "ChatGPT request serialization unexpectedly produced binary data"
        )
    return body


def _contains_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


def build_request_headers(
    token: str,
    entry: ConfigEntryLike,
    *,
    responses_lite: bool = False,
) -> dict[str, str]:
    """Build authenticated headers for the hosted backend."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "originator": ORIGINATOR,
        "version": CODEX_CLIENT_VERSION,
        "User-Agent": CODEX_USER_AGENT,
    }
    if responses_lite:
        headers["X-OpenAI-Internal-Codex-Responses-Lite"] = "true"

    account_id = entry.data.get(CONF_ACCOUNT_ID) or extract_account_id(token)
    if isinstance(account_id, str) and account_id:
        headers["ChatGPT-Account-ID"] = account_id
    return headers


def _message_item_for_lite(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    if "role" in normalized and "content" in normalized:
        normalized.setdefault("type", "message")
    return normalized


def build_turn_payload(
    *,
    model: str,
    instructions: str | None,
    input_items: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
    parallel_tool_calls: bool | None = None,
    text_format: dict[str, Any] | None = None,
    reasoning_effort: str | None = None,
    include: list[str] | None = None,
) -> tuple[dict[str, Any], bool]:
    """Build a normal Responses or GPT-5.6 Responses Lite request.

    Native hosted tools such as OpenAI web search require the full Responses
    transport. Function-only turns retain Responses Lite for compatible models.
    """
    profile = get_model_profile(model)
    configured_effort = normalize_reasoning_effort(
        profile.slug,
        reasoning_effort,
    )
    request_effort = reasoning_effort_for_request(
        profile.slug,
        configured_effort,
    )
    active_tools = list(tools or [])
    has_web_search = any(
        tool.get("type") in WEB_SEARCH_TOOL_TYPES for tool in active_tools
    )
    use_responses_lite = profile.responses_lite and not has_web_search

    if use_responses_lite:
        lite_input: list[dict[str, Any]] = [
            {
                "type": "additional_tools",
                "role": "developer",
                "tools": active_tools,
            }
        ]
        if instructions:
            lite_input.append(
                {
                    "type": "message",
                    "role": "developer",
                    "content": [text_part(instructions)],
                }
            )
        lite_input.extend(_message_item_for_lite(item) for item in input_items)

        payload: dict[str, Any] = {
            "model": profile.slug,
            "input": lite_input,
            "tool_choice": tool_choice or "auto",
            "parallel_tool_calls": False,
            "reasoning": {
                "effort": request_effort,
                "context": "all_turns",
            },
            "include": ["reasoning.encrypted_content"],
            "text": {"verbosity": "low"},
            "stream": True,
            "store": False,
        }
        if include:
            payload["include"] = list(
                dict.fromkeys([*payload["include"], *include])
            )
        if text_format is not None:
            payload["text"]["format"] = text_format
        return payload, True

    payload = {
        "model": profile.slug,
        "input": input_items,
        "reasoning": {"effort": request_effort},
        "stream": True,
        "store": False,
    }
    if instructions:
        payload["instructions"] = instructions
    if text_format is not None:
        payload["text"] = {"format": text_format}
    if active_tools:
        payload["tools"] = active_tools
        payload["tool_choice"] = tool_choice or "auto"
        if parallel_tool_calls is not None:
            payload["parallel_tool_calls"] = parallel_tool_calls
    if include:
        payload["include"] = list(dict.fromkeys(include))
    return payload, False


def _format_tool(
    tool: llm.Tool,
    custom_serializer: Callable[[Any], Any] | None,
) -> dict[str, Any]:
    return {
        "type": "function",
        "name": tool.name,
        "description": tool.description,
        "parameters": convert(
            tool.parameters,
            custom_serializer=custom_serializer,
        ),
        "strict": False,
    }


def _event_exception(event: dict[str, Any], *, operation: str) -> ChatGPTOAuthError:
    detail = sanitize_backend_message(response_error_message(event))
    lowered = detail.lower()
    message = f"ChatGPT {operation} failed: {detail}"
    if "rate limit" in lowered or "usage limit" in lowered:
        return RateLimitError(message)
    if "unauthorized" in lowered or "authentication" in lowered:
        return AuthenticationError(message)
    return ResponseParseError(message)


def _validate_required_web_search(
    options: WebSearchOptions | None,
    *,
    citations: list[Any],
    searches: list[Any],
) -> None:
    """Reject a required-search response that contains no search evidence."""
    if options is not None and options.required and not (citations or searches):
        raise ResponseParseError(
            "ChatGPT did not perform the required OpenAI web search"
        )


class ChatGPTOAuthClient:
    """Per-config-entry client and runtime state."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntryLike,
        *,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.session = session or async_get_clientsession(hass)
        self.token_manager = OAuthTokenManager(
            hass,
            entry,
            session=self.session,
        )

    @property
    def model(self) -> str:
        """Return the configured canonical model."""
        return normalize_model(self.entry.data.get(CONF_MODEL, DEFAULT_MODEL))

    @property
    def reasoning_effort(self) -> str:
        """Return the configured model-compatible thinking level."""
        return normalize_reasoning_effort(
            self.model,
            self.entry.data.get(CONF_REASONING_EFFORT),
        )

    @property
    def system_prompt(self) -> str:
        """Return the configured system prompt."""
        value = self.entry.data.get(CONF_PROMPT, DEFAULT_PROMPT)
        return value if isinstance(value, str) and value.strip() else DEFAULT_PROMPT

    @property
    def web_search_options(self) -> WebSearchOptions:
        """Return the configured OpenAI web-search behavior."""
        return self.resolve_web_search_options()

    def resolve_model(self, value: object | None = None) -> str:
        """Resolve and validate a configured or per-request model."""
        return get_model_profile(value if value is not None else self.model).slug

    def resolve_reasoning_effort(
        self,
        model: str,
        value: object | None = None,
    ) -> str:
        """Resolve and validate a configured or per-request thinking level."""
        if value is None:
            return normalize_reasoning_effort(model, self.reasoning_effort)
        return validate_reasoning_effort(model, value)

    def resolve_web_search_options(
        self,
        *,
        mode: object | None = None,
        context_size: object | None = None,
        live_access: object | None = None,
        use_home_assistant_location: object | None = None,
        allowed_domains: object | None = None,
    ) -> WebSearchOptions:
        """Resolve configured and per-request OpenAI web-search options."""
        configured_mode = normalize_web_search_mode(
            self.entry.data.get(CONF_WEB_SEARCH_MODE),
            default=DEFAULT_WEB_SEARCH_MODE,
        )
        resolved_mode = normalize_web_search_mode(
            mode,
            default=configured_mode,
        )
        configured_context_size = normalize_web_search_context_size(
            self.entry.data.get(CONF_WEB_SEARCH_CONTEXT_SIZE),
            default=DEFAULT_WEB_SEARCH_CONTEXT_SIZE,
        )
        resolved_context_size = normalize_web_search_context_size(
            context_size,
            default=configured_context_size,
        )
        resolved_live_access = (
            bool(self.entry.data.get(
                CONF_WEB_SEARCH_LIVE_ACCESS,
                DEFAULT_WEB_SEARCH_LIVE_ACCESS,
            ))
            if live_access is None
            else bool(live_access)
        )
        resolved_location = (
            bool(self.entry.data.get(
                CONF_WEB_SEARCH_USE_HASS_LOCATION,
                DEFAULT_WEB_SEARCH_USE_HASS_LOCATION,
            ))
            if use_home_assistant_location is None
            else bool(use_home_assistant_location)
        )
        return WebSearchOptions(
            mode=resolved_mode,
            context_size=resolved_context_size,
            live_access=resolved_live_access,
            use_home_assistant_location=resolved_location,
            allowed_domains=normalize_allowed_domains(allowed_domains),
        )

    @asynccontextmanager
    async def _async_response(
        self,
        payload: dict[str, Any],
        *,
        responses_lite: bool,
        timeout_seconds: int,
        operation: str,
    ) -> AsyncIterator[aiohttp.ClientResponse]:
        """POST a request, retrying one rejected access token after refresh."""
        body = await self.hass.async_add_executor_job(
            serialize_request_payload,
            payload,
        )
        invalid_token: str | None = None

        for attempt in range(2):
            token = await self.token_manager.async_get_access_token(
                force_refresh=attempt > 0,
                invalid_access_token=invalid_token,
            )
            try:
                response = await self.session.post(
                    CODEX_RESPONSES_URL,
                    data=body,
                    headers=build_request_headers(
                        token,
                        self.entry,
                        responses_lite=responses_lite,
                    ),
                    timeout=aiohttp.ClientTimeout(total=timeout_seconds),
                )
            except TimeoutError as err:
                raise RequestTimeoutError(
                    f"ChatGPT {operation} timed out after {timeout_seconds} seconds"
                ) from err
            except aiohttp.ClientError as err:
                raise BackendUnavailableError(
                    f"Could not connect to ChatGPT for {operation}: {err}"
                ) from err

            if response.status == 401 and attempt == 0:
                invalid_token = token
                await response.read()
                response.release()
                continue

            if response.status >= 400:
                text = await response.text()
                request_id = (
                    response.headers.get("x-request-id")
                    or response.headers.get("request-id")
                )
                response.release()
                error = exception_from_http_response(
                    response.status,
                    text,
                    request_id=request_id,
                    operation=operation,
                )
                if isinstance(error, AuthenticationError):
                    await self.token_manager.async_start_reauth()
                raise error

            try:
                yield response
            finally:
                response.release()
            return

        await self.token_manager.async_start_reauth()
        raise AuthenticationError(
            "ChatGPT rejected the refreshed OAuth access token; "
            "reauthenticate the integration"
        )

    async def async_test_connection(self) -> None:
        """Validate credentials, model access, and streamed response handling."""
        result = await self.async_create_response(
            model=self.model,
            reasoning_effort=self.reasoning_effort,
            instructions="Reply with exactly: ok",
            content=[text_part("ok")],
        )
        if result.text.strip().lower() != "ok":
            LOGGER.debug("Connection test returned an unexpected response")

    async def _async_create_turn(
        self,
        *,
        model: str,
        instructions: str | None,
        input_items: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
        text_format: dict[str, Any] | None = None,
        reasoning_effort: str | None = None,
        web_search: WebSearchOptions | None = None,
    ) -> ChatGPTTurn:
        """Run one streamed Responses turn with optional native web search."""
        model = self.resolve_model(model)
        profile = get_model_profile(model)
        reasoning_effort = self.resolve_reasoning_effort(model, reasoning_effort)
        search_options = web_search or WebSearchOptions()
        active_tools = list(tools or [])
        include: list[str] = []
        active_instructions = instructions

        if search_options.enabled:
            if not profile.supports_web_search:
                raise RequestValidationError(
                    f"OpenAI web search is not available for {model}"
                )
            active_tools.append(build_web_search_tool(search_options, self.hass))
            active_instructions = combine_instructions(
                instructions,
                web_search_instructions(search_options),
            )
            include.append("web_search_call.action.sources")
            if search_options.required:
                tool_choice = "required"
            elif tool_choice is None:
                tool_choice = "auto"

        payload, responses_lite = build_turn_payload(
            model=model,
            instructions=active_instructions,
            input_items=input_items,
            tools=active_tools or None,
            tool_choice=tool_choice,
            parallel_tool_calls=parallel_tool_calls,
            text_format=text_format,
            reasoning_effort=reasoning_effort,
            include=include or None,
        )

        retried_without_parallel = False
        retried_without_sources = False
        retried_preview = False
        removed_search_fields: set[str] = set()
        while True:
            LOGGER.debug(
                "Submitting %s request for %s at thinking level %s with fields %s",
                "Responses Lite" if responses_lite else "Responses",
                model,
                reasoning_effort,
                sorted(payload),
            )
            try:
                return await self._async_collect_turn(
                    payload,
                    responses_lite=responses_lite,
                )
            except RequestValidationError as err:
                message = str(err).lower()
                unsupported = any(
                    marker in message
                    for marker in (
                        "unsupported",
                        "unknown parameter",
                        "unrecognized",
                        "not supported",
                        "invalid value",
                    )
                )

                if (
                    not responses_lite
                    and not retried_without_parallel
                    and "parallel_tool_calls" in payload
                    and "parallel_tool_calls" in message
                    and unsupported
                ):
                    payload.pop("parallel_tool_calls", None)
                    retried_without_parallel = True
                    continue

                if (
                    not retried_without_sources
                    and "web_search_call.action.sources"
                    in payload.get("include", [])
                    and unsupported
                    and (
                        "web_search_call.action.sources" in message
                        or "include" in message
                    )
                ):
                    payload["include"] = [
                        item
                        for item in payload["include"]
                        if item != "web_search_call.action.sources"
                    ]
                    if not payload["include"]:
                        payload.pop("include", None)
                    retried_without_sources = True
                    continue

                tools_payload = payload.get("tools")
                web_tools = (
                    [
                        tool
                        for tool in tools_payload
                        if isinstance(tool, dict)
                        and tool.get("type") in WEB_SEARCH_TOOL_TYPES
                    ]
                    if isinstance(tools_payload, list)
                    else []
                )
                optional_fields = (
                    "external_web_access",
                    "filters",
                    "user_location",
                    "search_context_size",
                )
                removed_field = False
                for field_name in optional_fields:
                    if (
                        field_name not in removed_search_fields
                        and field_name in message
                        and unsupported
                        and any(field_name in tool for tool in web_tools)
                    ):
                        if (
                            field_name == "external_web_access"
                            and not search_options.live_access
                        ):
                            raise RequestValidationError(
                                "The hosted backend rejected cache/index-only "
                                "web search; refusing to enable live access"
                            ) from err
                        if (
                            field_name == "filters"
                            and search_options.allowed_domains
                        ):
                            raise RequestValidationError(
                                "The hosted backend rejected the web-search "
                                "domain allowlist; refusing an unrestricted search"
                            ) from err
                        for tool in web_tools:
                            tool.pop(field_name, None)
                        removed_search_fields.add(field_name)
                        removed_field = True
                        break
                if removed_field:
                    continue

                current_tools = [
                    tool
                    for tool in web_tools
                    if tool.get("type") != "web_search_preview"
                ]
                if (
                    current_tools
                    and not retried_preview
                    and unsupported
                    and (
                        "web_search" in message
                        or "hosted tool" in message
                        or "tools" in message
                    )
                ):
                    if not search_options.live_access:
                        raise RequestValidationError(
                            "The hosted backend does not support the current "
                            "cache/index-only web-search request, and the legacy "
                            "preview tool would enable live access"
                        ) from err
                    if search_options.allowed_domains:
                        raise RequestValidationError(
                            "The hosted backend does not support the current "
                            "domain-filtered web-search request, and the legacy "
                            "preview tool does not enforce domain allowlists"
                        ) from err
                    for tool in current_tools:
                        tool["type"] = "web_search_preview"
                        tool.pop("external_web_access", None)
                        tool.pop("filters", None)
                    retried_preview = True
                    continue
                raise

    async def _async_collect_turn(
        self,
        payload: dict[str, Any],
        *,
        responses_lite: bool,
    ) -> ChatGPTTurn:
        chunks: list[str] = []
        calls: list[llm.ToolInput] = []
        call_ids: set[str] = set()
        citations = []
        searches = []
        events: list[dict[str, Any]] = []

        try:
            async with self._async_response(
                payload,
                responses_lite=responses_lite,
                timeout_seconds=TEXT_REQUEST_TIMEOUT,
                operation="response request",
            ) as response:
                async for _event_name, data in iter_sse_json(response):
                    events.append(data)
                    event_type = data.get("type")
                    if event_type == "response.output_text.delta":
                        chunks.append(str(data.get("delta") or ""))
                    elif event_type == "response.output_text.done" and not chunks:
                        chunks.append(str(data.get("text") or ""))
                    elif event_type == "response.output_text.annotation.added":
                        citation = url_citation_from_annotation(
                            data.get("annotation")
                        )
                        if citation is not None:
                            citations.append(citation)

                    if event_type in {
                        "response.output_item.done",
                        "response.completed",
                    }:
                        output_items = response_output_items(data)
                        citations.extend(url_citations_from_output_items(output_items))
                        searches.extend(
                            web_search_actions_from_output_items(output_items)
                        )
                        for item in output_items:
                            call = extract_function_call(item)
                            if call is None or call.id in call_ids:
                                continue
                            calls.append(call)
                            call_ids.add(call.id)
                        if not chunks:
                            completed_text = text_from_output_items(output_items)
                            if completed_text:
                                chunks.append(completed_text)

                    if event_type in {
                        "response.failed",
                        "response.incomplete",
                        "error",
                    }:
                        raise _event_exception(data, operation="response")
        except TimeoutError as err:
            raise RequestTimeoutError(
                "ChatGPT response stream timed out after "
                f"{TEXT_REQUEST_TIMEOUT} seconds"
            ) from err
        except aiohttp.ClientError as err:
            raise BackendUnavailableError(
                f"ChatGPT response stream ended unexpectedly: {err}"
            ) from err

        return ChatGPTTurn(
            text="".join(chunks).strip(),
            function_calls=calls,
            raw_events=events,
            citations=dedupe_citations(citations),
            searches=dedupe_searches(searches),
        )

    async def async_create_response(
        self,
        *,
        model: str,
        instructions: str | None,
        content: list[dict[str, Any]] | None = None,
        input_items: list[dict[str, Any]] | None = None,
        text_format: dict[str, Any] | None = None,
        reasoning_effort: str | None = None,
        web_search: WebSearchOptions | None = None,
    ) -> ChatGPTTextResponse:
        """Create a text response without Home Assistant tools."""
        if input_items is None:
            if content is None:
                raise RequestValidationError("Missing user content for a response")
            input_items = [
                {"type": "message", "role": "user", "content": content}
            ]
        else:
            input_items = [dict(item) for item in input_items]

        turn = await self._async_create_turn(
            model=model,
            instructions=instructions,
            input_items=input_items,
            text_format=text_format,
            reasoning_effort=reasoning_effort,
            web_search=web_search,
        )
        if not turn.text:
            raise ResponseParseError("ChatGPT returned an empty text response")
        _validate_required_web_search(
            web_search,
            citations=turn.citations,
            searches=turn.searches,
        )
        rendered_text = render_text_with_web_citations(
            turn.text,
            turn.citations,
            turn.searches,
        )
        return ChatGPTTextResponse(
            text=rendered_text,
            raw_text=turn.text,
            raw_events=turn.raw_events,
            citations=turn.citations,
            searches=turn.searches,
        )

    async def async_create_image_response(
        self,
        *,
        model: str,
        content: list[dict[str, Any]],
        reasoning_effort: str | None = None,
    ) -> ChatGPTImageResponse:
        """Generate or edit one image with the hosted image tool."""
        model = self.resolve_model(model)
        reasoning_effort = self.resolve_reasoning_effort(model, reasoning_effort)
        request_effort = reasoning_effort_for_request(model, reasoning_effort)
        is_edit = any(part.get("type") == "input_image" for part in content)
        instructions = (
            "Use the image generation tool to generate exactly one PNG image for "
            "the user's request. Do not use any other tool."
        )
        if is_edit:
            instructions += (
                " Treat the input images as edit or reference images and preserve "
                "details the user asks to retain."
            )

        # Image generation uses the full Responses request shape, including for
        # models whose text path uses Responses Lite, because the hosted image
        # tool expects the full transport.
        payload: dict[str, Any] = {
            "model": model,
            "instructions": instructions,
            "input": [{"type": "message", "role": "user", "content": content}],
            "reasoning": {"effort": request_effort},
            "tools": [
                {
                    "type": "image_generation",
                    "output_format": "png",
                    "size": "auto",
                    "quality": "auto",
                    "background": "auto",
                    "partial_images": 0,
                }
            ],
            "tool_choice": {"type": "image_generation"},
            "parallel_tool_calls": False,
            "stream": True,
            "store": False,
        }
        last_status: str | None = None
        try:
            async with self._async_response(
                payload,
                responses_lite=False,
                timeout_seconds=IMAGE_REQUEST_TIMEOUT,
                operation="image generation",
            ) as response:
                async for _event_name, data in iter_sse_json(response):
                    event_type = data.get("type")
                    if event_type in {
                        "response.failed",
                        "response.incomplete",
                        "error",
                    }:
                        raise _event_exception(data, operation="image generation")
                    for item in image_items_from_event(data):
                        status = item.get("status")
                        if isinstance(status, str):
                            last_status = status
                        image = decode_image_item(item)
                        if image is not None:
                            return image
        except TimeoutError as err:
            raise RequestTimeoutError(
                f"ChatGPT image stream timed out after {IMAGE_REQUEST_TIMEOUT} seconds"
            ) from err
        except aiohttp.ClientError as err:
            raise BackendUnavailableError(
                f"ChatGPT image stream ended unexpectedly: {err}"
            ) from err

        if last_status:
            raise ResponseParseError(
                "ChatGPT response ended without an image result; "
                f"last image status was {last_status}"
            )
        raise ResponseParseError(
            "ChatGPT response ended without an image generation result"
        )

    async def async_create_data_response(
        self,
        *,
        model: str,
        instructions: str,
        content: list[dict[str, Any]],
        structure_name: str,
        structure: vol.Schema | None,
        llm_api: llm.APIInstance | None = None,
        reasoning_effort: str | None = None,
        web_search: WebSearchOptions | None = None,
    ) -> ChatGPTDataResponse:
        """Generate plain text or schema-validated data for an AI Task."""
        tools = (
            [_format_tool(tool, llm_api.custom_serializer) for tool in llm_api.tools]
            if llm_api and llm_api.tools
            else []
        )
        input_items: list[dict[str, Any]] = [
            {"type": "message", "role": "user", "content": content}
        ]
        all_events: list[dict[str, Any]] = []
        all_citations = []
        all_searches = []
        text_format = (
            structured_output_format(structure_name, structure, llm_api)
            if structure is not None
            else None
        )
        active_instructions = instructions
        fallback_used = False

        for _iteration in range(MAX_TOOL_ITERATIONS):
            try:
                turn = await self._async_create_turn(
                    model=model,
                    instructions=active_instructions,
                    input_items=input_items,
                    tools=tools,
                    tool_choice="auto" if tools else None,
                    parallel_tool_calls=False if tools else None,
                    text_format=text_format,
                    reasoning_effort=reasoning_effort,
                    web_search=web_search,
                )
            except ChatGPTOAuthError as err:
                if (
                    structure is not None
                    and text_format is not None
                    and not fallback_used
                    and is_structured_output_error(err)
                ):
                    active_instructions = fallback_json_instructions(
                        instructions,
                        text_format,
                    )
                    text_format = None
                    fallback_used = True
                    continue
                raise

            all_events.extend(turn.raw_events)
            all_citations.extend(turn.citations)
            all_searches.extend(turn.searches)
            if turn.function_calls:
                if llm_api is None:
                    raise ResponseParseError(
                        "ChatGPT requested a Home Assistant tool, but no "
                        "LLM API was configured"
                    )
                await self._async_append_tool_results(
                    input_items,
                    turn.function_calls,
                    llm_api,
                )
                continue

            if not turn.text:
                raise ResponseParseError(
                    "ChatGPT returned an empty AI Task data response"
                )

            if structure is None:
                citations = dedupe_citations(all_citations)
                searches = dedupe_searches(all_searches)
                _validate_required_web_search(
                    web_search,
                    citations=citations,
                    searches=searches,
                )
                rendered_text = render_text_with_web_citations(
                    turn.text,
                    citations,
                    searches,
                )
                return ChatGPTDataResponse(
                    data=rendered_text,
                    text=turn.text,
                    raw_events=all_events,
                    citations=citations,
                    searches=searches,
                )

            try:
                data = parse_and_validate_structured_text(turn.text, structure)
            except ChatGPTOAuthError:
                if text_format is not None and not fallback_used:
                    active_instructions = fallback_json_instructions(
                        instructions,
                        text_format,
                    )
                    text_format = None
                    fallback_used = True
                    continue
                raise

            citations = dedupe_citations(all_citations)
            searches = dedupe_searches(all_searches)
            _validate_required_web_search(
                web_search,
                citations=citations,
                searches=searches,
            )
            return ChatGPTDataResponse(
                data=data,
                text=turn.text,
                raw_events=all_events,
                citations=citations,
                searches=searches,
            )

        raise ResponseParseError(
            "ChatGPT exceeded the maximum number of Home Assistant tool iterations"
        )

    async def async_create_tool_response(
        self,
        *,
        model: str,
        instructions: str,
        llm_api: llm.APIInstance,
        user_text: str | None = None,
        content: list[dict[str, Any]] | None = None,
        input_items: list[dict[str, Any]] | None = None,
        text_format: dict[str, Any] | None = None,
        reasoning_effort: str | None = None,
        web_search: WebSearchOptions | None = None,
    ) -> ChatGPTTextResponse:
        """Create a conversation response with Home Assistant tools enabled."""
        tools = [
            _format_tool(tool, llm_api.custom_serializer) for tool in llm_api.tools
        ]
        if input_items is None:
            if content is None:
                if user_text is None:
                    raise RequestValidationError(
                        "Missing user content for a tool-enabled response"
                    )
                content = [text_part(user_text)]
            input_items = [
                {"type": "message", "role": "user", "content": content}
            ]
        else:
            input_items = [dict(item) for item in input_items]

        all_events: list[dict[str, Any]] = []
        all_citations = []
        all_searches = []

        for _iteration in range(MAX_TOOL_ITERATIONS):
            turn = await self._async_create_turn(
                model=model,
                instructions=instructions,
                input_items=input_items,
                tools=tools,
                tool_choice="auto",
                parallel_tool_calls=False,
                text_format=text_format,
                reasoning_effort=reasoning_effort,
                web_search=web_search,
            )
            all_events.extend(turn.raw_events)
            all_citations.extend(turn.citations)
            all_searches.extend(turn.searches)
            if not turn.function_calls:
                if not turn.text:
                    raise ResponseParseError("ChatGPT returned an empty response")
                citations = dedupe_citations(all_citations)
                searches = dedupe_searches(all_searches)
                _validate_required_web_search(
                    web_search,
                    citations=citations,
                    searches=searches,
                )
                return ChatGPTTextResponse(
                    text=render_text_with_web_citations(
                        turn.text,
                        citations,
                        searches,
                    ),
                    raw_text=turn.text,
                    raw_events=all_events,
                    citations=citations,
                    searches=searches,
                )
            await self._async_append_tool_results(
                input_items,
                turn.function_calls,
                llm_api,
            )

        raise ResponseParseError(
            "ChatGPT exceeded the maximum number of Home Assistant tool iterations"
        )

    async def _async_append_tool_results(
        self,
        input_items: list[dict[str, Any]],
        calls: list[llm.ToolInput],
        llm_api: llm.APIInstance,
    ) -> None:
        """Execute Home Assistant tools and append their results to input."""
        for call in calls:
            input_items.append(
                {
                    "type": "function_call",
                    "name": call.tool_name,
                    "arguments": json_dumps(call.tool_args),
                    "call_id": call.id,
                }
            )
            try:
                result = await llm_api.async_call_tool(call)
            except Exception as err:  # Tool failures are reported back to the model.
                result = {"error": type(err).__name__, "error_text": str(err)}
            input_items.append(
                {
                    "type": "function_call_output",
                    "call_id": call.id,
                    "output": json_dumps(result),
                }
            )
