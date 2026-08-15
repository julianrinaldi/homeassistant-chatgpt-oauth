"""ChatGPT OAuth integration for Home Assistant."""

from __future__ import annotations

from typing import Any, NoReturn

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import llm, selector
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from .client import ChatGPTOAuthClient
from .const import (
    CONF_ENABLE_HASS_CONTROL,
    CONF_ENABLE_HISTORY_TOOLS,
    CONF_INCLUDE_ROOM_ENTITIES,
    CONF_INCLUDE_SATELLITE_ROOM_CONTEXT,
    CONF_INCLUDE_USER_CONTEXT,
    CONF_MAX_TOOL_CALLS,
    CONF_MAX_TOOL_TIME,
    CONF_MEMORY_MAX_CHARACTERS,
    CONF_MEMORY_MAX_TURNS,
    CONF_MEMORY_MODE,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_REASONING_EFFORT,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_INCLUDE_SOURCES,
    CONF_WEB_SEARCH_LIVE_ACCESS,
    CONF_WEB_SEARCH_MODE,
    CONF_WEB_SEARCH_USE_HASS_LOCATION,
    CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION,
    DEFAULT_ENABLE_HASS_CONTROL,
    DEFAULT_ENABLE_HISTORY_TOOLS,
    DEFAULT_INCLUDE_ROOM_ENTITIES,
    DEFAULT_INCLUDE_SATELLITE_ROOM_CONTEXT,
    DEFAULT_INCLUDE_USER_CONTEXT,
    DEFAULT_MAX_TOOL_CALLS,
    DEFAULT_MAX_TOOL_TIME,
    DEFAULT_MEMORY_MAX_CHARACTERS,
    DEFAULT_MEMORY_MAX_TURNS,
    DEFAULT_MEMORY_MODE,
    DEFAULT_MODEL,
    DEFAULT_PROMPT,
    DEFAULT_WEB_SEARCH_CONTEXT_SIZE,
    DEFAULT_WEB_SEARCH_INCLUDE_SOURCES,
    DEFAULT_WEB_SEARCH_LIVE_ACCESS,
    DEFAULT_WEB_SEARCH_MODE,
    DEFAULT_WEB_SEARCH_USE_HASS_LOCATION,
    DEFAULT_WEB_SEARCH_USE_HASS_PRECISE_LOCATION,
    DOMAIN,
    INTEGRATION_NAME,
    INTEGRATION_VERSION,
    LEGACY_OUTPUT_LIMIT_KEY,
    LOGGER,
    MAX_ATTACHMENTS_TOTAL_BYTES,
    MAX_IMAGE_ATTACHMENTS,
    MIGRATED_MEMORY_MAX_CHARACTERS,
    MIGRATED_MEMORY_MODE,
    SERVICE_ANALYZE_IMAGE,
    SERVICE_GENERATE_CONTENT,
    SERVICE_WEB_SEARCH,
)
from .content import (
    image_part_from_entity,
    image_part_from_local_file,
    image_part_from_url,
    inline_content_size,
    text_part,
)
from .exceptions import (
    AuthenticationError,
    BackendUnavailableError,
    ChatGPTOAuthError,
    RateLimitError,
    RequestTimeoutError,
    RequestValidationError,
    StructuredOutputError,
)
from .history_tools import create_history_api
from .models import (
    ALL_REASONING_EFFORTS,
    get_model_profile,
    normalize_model,
    normalize_reasoning_effort,
)
from .profiles import (
    assistant_profiles_fingerprint,
    normalize_max_tool_calls,
    normalize_max_tool_time,
    normalize_memory_max_characters,
    normalize_memory_max_turns,
    normalize_memory_mode,
)
from .responses import ChatGPTTextResponse
from .web_search import (
    WEB_SEARCH_AUTO,
    WEB_SEARCH_DISABLED,
    WEB_SEARCH_REQUIRED,
    WebSearchOptions,
    normalize_web_search_context_size,
    normalize_web_search_mode,
)

PLATFORMS: tuple[Platform, ...] = (Platform.CONVERSATION, Platform.AI_TASK)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PER_CALL_WEB_SEARCH_MODES = (
    "configured",
    WEB_SEARCH_DISABLED,
    WEB_SEARCH_AUTO,
    WEB_SEARCH_REQUIRED,
)


def _model_validator(value: object) -> str:
    try:
        return get_model_profile(value).slug
    except ValueError as err:
        raise vol.Invalid(str(err)) from err


def _reasoning_validator(value: object) -> str:
    if not isinstance(value, str):
        raise vol.Invalid("Thinking level must be a string")
    effort = value.strip().lower()
    if effort not in ALL_REASONING_EFFORTS:
        raise vol.Invalid(
            "Supported thinking levels are: " + ", ".join(ALL_REASONING_EFFORTS)
        )
    return effort


def _web_search_mode_validator(value: object) -> str:
    if not isinstance(value, str):
        raise vol.Invalid("Web-search mode must be a string")
    mode = value.strip().lower()
    if mode not in PER_CALL_WEB_SEARCH_MODES:
        raise vol.Invalid(
            "Supported web-search modes are: " + ", ".join(PER_CALL_WEB_SEARCH_MODES)
        )
    return mode


def _web_search_context_validator(value: object) -> str:
    try:
        return normalize_web_search_context_size(
            value,
            default=DEFAULT_WEB_SEARCH_CONTEXT_SIZE,
        )
    except ValueError as err:
        raise vol.Invalid(str(err)) from err


def _get_entry(hass: HomeAssistant, entry_id: str) -> ConfigEntry:
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError(f"Invalid ChatGPT OAuth config entry: {entry_id}")
    return entry


def _get_client(entry: ConfigEntry) -> ChatGPTOAuthClient:
    client = entry.runtime_data
    if not isinstance(client, ChatGPTOAuthClient):
        raise HomeAssistantError(
            "The selected ChatGPT OAuth config entry is not loaded"
        )
    return client


def _resolve_call_settings(
    client: ChatGPTOAuthClient,
    call: ServiceCall,
) -> tuple[str, str]:
    try:
        model = client.resolve_model(call.data.get(CONF_MODEL))
        reasoning_effort = client.resolve_reasoning_effort(
            model,
            call.data.get(CONF_REASONING_EFFORT),
        )
    except ValueError as err:
        raise ServiceValidationError(str(err)) from err
    return model, reasoning_effort


def _resolve_call_web_search(
    client: ChatGPTOAuthClient,
    call: ServiceCall,
    *,
    force_required: bool = False,
) -> WebSearchOptions:
    mode: object | None = call.data.get(CONF_WEB_SEARCH_MODE)
    if mode in (None, "configured"):
        mode = None
    if force_required:
        mode = WEB_SEARCH_REQUIRED
    try:
        return client.resolve_web_search_options(
            mode=mode,
            context_size=call.data.get(CONF_WEB_SEARCH_CONTEXT_SIZE),
            include_sources=call.data.get(CONF_WEB_SEARCH_INCLUDE_SOURCES),
            live_access=call.data.get(CONF_WEB_SEARCH_LIVE_ACCESS),
            use_home_assistant_location=call.data.get(
                CONF_WEB_SEARCH_USE_HASS_LOCATION
            ),
            use_home_assistant_precise_location=call.data.get(
                CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION
            ),
            allowed_domains=call.data.get("allowed_domains"),
        )
    except ValueError as err:
        raise ServiceValidationError(str(err)) from err


def _text_response_data(result: ChatGPTTextResponse) -> ServiceResponse:
    """Return stable, serializable text and web-source metadata."""
    return {
        "text": result.text,
        "raw_text": result.raw_text or result.text,
        "cited_text": result.cited_text,
        "citations": [citation.as_dict() for citation in result.citations],
        "sources": [source.as_dict() for source in result.sources],
        "searches": [search.as_dict() for search in result.searches],
    }


def _raise_home_assistant_error(error: ChatGPTOAuthError) -> NoReturn:
    """Translate stable client exceptions to useful Home Assistant errors."""
    if isinstance(error, (RequestValidationError, StructuredOutputError)):
        raise ServiceValidationError(str(error)) from error
    if isinstance(error, AuthenticationError):
        raise HomeAssistantError(
            f"{error}. Reauthenticate the ChatGPT OAuth integration."
        ) from error
    if isinstance(error, RateLimitError):
        raise HomeAssistantError(
            f"{error}. Check the usage limits of the signed-in ChatGPT account."
        ) from error
    if isinstance(error, RequestTimeoutError):
        raise HomeAssistantError(str(error)) from error
    if isinstance(error, BackendUnavailableError):
        raise HomeAssistantError(str(error)) from error
    raise HomeAssistantError(str(error)) from error


def _shared_text_fields() -> dict[vol.Marker, Any]:
    """Return common service fields for model, reasoning, and web search."""
    return {
        vol.Optional(CONF_MODEL): _model_validator,
        vol.Optional(CONF_REASONING_EFFORT): _reasoning_validator,
        vol.Optional(CONF_WEB_SEARCH_MODE): _web_search_mode_validator,
        vol.Optional(CONF_WEB_SEARCH_CONTEXT_SIZE): _web_search_context_validator,
        vol.Optional(CONF_WEB_SEARCH_INCLUDE_SOURCES): cv.boolean,
        vol.Optional(CONF_WEB_SEARCH_LIVE_ACCESS): cv.boolean,
        vol.Optional(CONF_WEB_SEARCH_USE_HASS_LOCATION): cv.boolean,
        vol.Optional(CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION): cv.boolean,
    }


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register integration actions and the read-only history LLM API."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if "history_api_unregister" not in domain_data:
        domain_data["history_api_unregister"] = llm.async_register_api(
            hass,
            create_history_api(hass),
        )

    async def generate_content(call: ServiceCall) -> ServiceResponse:
        entry = _get_entry(hass, call.data["config_entry"])
        client = _get_client(entry)
        model, reasoning_effort = _resolve_call_settings(client, call)
        web_search = _resolve_call_web_search(client, call)
        instructions = entry.data.get(CONF_PROMPT, DEFAULT_PROMPT)
        try:
            result = await client.async_create_response(
                model=model,
                reasoning_effort=reasoning_effort,
                instructions=instructions,
                content=[text_part(call.data[CONF_PROMPT])],
                web_search=web_search,
            )
        except ChatGPTOAuthError as err:
            _raise_home_assistant_error(err)
        return _text_response_data(result)

    async def analyze_image(call: ServiceCall) -> ServiceResponse:
        entry = _get_entry(hass, call.data["config_entry"])
        client = _get_client(entry)
        model, reasoning_effort = _resolve_call_settings(client, call)
        web_search = _resolve_call_web_search(client, call)

        image_files = call.data.get("image_file", []) or []
        image_urls = call.data.get("image_url", []) or []
        entity_ids = call.data.get(CONF_ENTITY_ID, []) or []
        image_count = len(image_files) + len(image_urls) + len(entity_ids)
        if image_count == 0:
            raise ServiceValidationError(
                "Provide at least one image file, image URL, camera, or image entity"
            )
        if image_count > MAX_IMAGE_ATTACHMENTS:
            raise ServiceValidationError(
                f"Analyze image accepts at most {MAX_IMAGE_ATTACHMENTS} images"
            )

        try:
            content: list[dict[str, Any]] = [text_part(call.data[CONF_PROMPT])]
            image_parts: list[dict[str, str]] = []
            for path in image_files:
                image_parts.append(await image_part_from_local_file(hass, path))
            for url in image_urls:
                image_parts.append(await image_part_from_url(hass, url))
            for entity_id in entity_ids:
                image_parts.append(await image_part_from_entity(hass, entity_id))
            if sum(inline_content_size(part) for part in image_parts) > (
                MAX_ATTACHMENTS_TOTAL_BYTES
            ):
                raise RequestValidationError(
                    "Analyze-image attachments must total 50 MB or less"
                )
            content.extend(image_parts)

            instructions = call.data.get("system_prompt") or entry.data.get(
                CONF_PROMPT,
                DEFAULT_PROMPT,
            )
            result = await client.async_create_response(
                model=model,
                reasoning_effort=reasoning_effort,
                instructions=instructions,
                content=content,
                web_search=web_search,
            )
        except ChatGPTOAuthError as err:
            _raise_home_assistant_error(err)
        response = _text_response_data(result)
        response["response_text"] = result.text
        return response

    async def web_search(call: ServiceCall) -> ServiceResponse:
        entry = _get_entry(hass, call.data["config_entry"])
        client = _get_client(entry)
        model, reasoning_effort = _resolve_call_settings(client, call)
        search_options = _resolve_call_web_search(
            client,
            call,
            force_required=True,
        )
        instructions = call.data.get("system_prompt") or entry.data.get(
            CONF_PROMPT,
            DEFAULT_PROMPT,
        )
        try:
            result = await client.async_create_response(
                model=model,
                reasoning_effort=reasoning_effort,
                instructions=instructions,
                content=[text_part(call.data["query"])],
                web_search=search_options,
            )
        except ChatGPTOAuthError as err:
            _raise_home_assistant_error(err)
        response = _text_response_data(result)
        response.update(
            {
                "model": model,
                "reasoning_effort": reasoning_effort,
                "search_context_size": search_options.context_size,
                "include_sources_in_text": search_options.include_sources,
                "live_access": search_options.live_access,
            }
        )
        return response

    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_CONTENT,
        generate_content,
        schema=vol.Schema(
            {
                vol.Required("config_entry"): selector.ConfigEntrySelector(
                    {"integration": DOMAIN}
                ),
                vol.Required(CONF_PROMPT): cv.string,
                **_shared_text_fields(),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ANALYZE_IMAGE,
        analyze_image,
        schema=vol.Schema(
            {
                vol.Required("config_entry"): selector.ConfigEntrySelector(
                    {"integration": DOMAIN}
                ),
                vol.Required(CONF_PROMPT): cv.string,
                vol.Optional("system_prompt"): cv.string,
                **_shared_text_fields(),
                vol.Optional("image_url", default=[]): vol.All(
                    cv.ensure_list,
                    [cv.string],
                ),
                vol.Optional("image_file", default=[]): vol.All(
                    cv.ensure_list,
                    [cv.string],
                ),
                vol.Optional(CONF_ENTITY_ID, default=[]): cv.entity_ids,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_WEB_SEARCH,
        web_search,
        schema=vol.Schema(
            {
                vol.Required("config_entry"): selector.ConfigEntrySelector(
                    {"integration": DOMAIN}
                ),
                vol.Required("query"): cv.string,
                vol.Optional("system_prompt"): cv.string,
                vol.Optional(CONF_MODEL): _model_validator,
                vol.Optional(CONF_REASONING_EFFORT): _reasoning_validator,
                vol.Optional(
                    CONF_WEB_SEARCH_CONTEXT_SIZE
                ): _web_search_context_validator,
                vol.Optional(CONF_WEB_SEARCH_INCLUDE_SOURCES): cv.boolean,
                vol.Optional(CONF_WEB_SEARCH_LIVE_ACCESS): cv.boolean,
                vol.Optional(CONF_WEB_SEARCH_USE_HASS_LOCATION): cv.boolean,
                vol.Optional(CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION): cv.boolean,
                vol.Optional("allowed_domains", default=[]): vol.All(
                    cv.ensure_list,
                    [cv.string],
                ),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate earlier entries without changing their stable domain or IDs."""
    if entry.version > 11:
        LOGGER.error(
            "Cannot migrate config entry %s from future version %s",
            entry.entry_id,
            entry.version,
        )
        return False

    data = dict(entry.data)
    model = normalize_model(data.get(CONF_MODEL, DEFAULT_MODEL))
    try:
        get_model_profile(model)
    except ValueError:
        LOGGER.warning(
            "Config entry %s used unsupported model %s; resetting to %s",
            entry.entry_id,
            model,
            DEFAULT_MODEL,
        )
        model = DEFAULT_MODEL
    data[CONF_MODEL] = model
    data[CONF_REASONING_EFFORT] = normalize_reasoning_effort(
        model,
        data.get(CONF_REASONING_EFFORT),
    )
    data.setdefault(CONF_PROMPT, DEFAULT_PROMPT)

    control = data.get(CONF_ENABLE_HASS_CONTROL)
    data[CONF_ENABLE_HASS_CONTROL] = (
        control if isinstance(control, bool) else DEFAULT_ENABLE_HASS_CONTROL
    )
    history_tools = data.get(CONF_ENABLE_HISTORY_TOOLS)
    data[CONF_ENABLE_HISTORY_TOOLS] = (
        history_tools
        if isinstance(history_tools, bool)
        else DEFAULT_ENABLE_HISTORY_TOOLS
    )

    for key, default in (
        (CONF_INCLUDE_USER_CONTEXT, DEFAULT_INCLUDE_USER_CONTEXT),
        (
            CONF_INCLUDE_SATELLITE_ROOM_CONTEXT,
            DEFAULT_INCLUDE_SATELLITE_ROOM_CONTEXT,
        ),
        (CONF_INCLUDE_ROOM_ENTITIES, DEFAULT_INCLUDE_ROOM_ENTITIES),
    ):
        value = data.get(key)
        data[key] = value if isinstance(value, bool) else default

    try:
        data[CONF_MAX_TOOL_CALLS] = normalize_max_tool_calls(
            data.get(CONF_MAX_TOOL_CALLS),
            default=DEFAULT_MAX_TOOL_CALLS,
        )
    except ValueError:
        LOGGER.warning(
            "Config entry %s used an invalid tool-call limit; resetting to %s",
            entry.entry_id,
            DEFAULT_MAX_TOOL_CALLS,
        )
        data[CONF_MAX_TOOL_CALLS] = DEFAULT_MAX_TOOL_CALLS
    try:
        data[CONF_MAX_TOOL_TIME] = normalize_max_tool_time(
            data.get(CONF_MAX_TOOL_TIME),
            default=DEFAULT_MAX_TOOL_TIME,
        )
    except ValueError:
        LOGGER.warning(
            "Config entry %s used an invalid tool-time limit; resetting to %s",
            entry.entry_id,
            DEFAULT_MAX_TOOL_TIME,
        )
        data[CONF_MAX_TOOL_TIME] = DEFAULT_MAX_TOOL_TIME

    try:
        data[CONF_WEB_SEARCH_MODE] = normalize_web_search_mode(
            data.get(CONF_WEB_SEARCH_MODE),
            default=DEFAULT_WEB_SEARCH_MODE,
        )
    except ValueError:
        LOGGER.warning(
            "Config entry %s used an invalid web-search mode; disabling search",
            entry.entry_id,
        )
        data[CONF_WEB_SEARCH_MODE] = DEFAULT_WEB_SEARCH_MODE
    try:
        data[CONF_WEB_SEARCH_CONTEXT_SIZE] = normalize_web_search_context_size(
            data.get(CONF_WEB_SEARCH_CONTEXT_SIZE),
            default=DEFAULT_WEB_SEARCH_CONTEXT_SIZE,
        )
    except ValueError:
        LOGGER.warning(
            "Config entry %s used an invalid web-search context size; resetting to %s",
            entry.entry_id,
            DEFAULT_WEB_SEARCH_CONTEXT_SIZE,
        )
        data[CONF_WEB_SEARCH_CONTEXT_SIZE] = DEFAULT_WEB_SEARCH_CONTEXT_SIZE

    for key, default in (
        (CONF_WEB_SEARCH_INCLUDE_SOURCES, DEFAULT_WEB_SEARCH_INCLUDE_SOURCES),
        (CONF_WEB_SEARCH_LIVE_ACCESS, DEFAULT_WEB_SEARCH_LIVE_ACCESS),
        (
            CONF_WEB_SEARCH_USE_HASS_LOCATION,
            DEFAULT_WEB_SEARCH_USE_HASS_LOCATION,
        ),
        (
            CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION,
            DEFAULT_WEB_SEARCH_USE_HASS_PRECISE_LOCATION,
        ),
    ):
        value = data.get(key)
        data[key] = value if isinstance(value, bool) else default

    # Before v1.3.0 the full visible chat log was sent on every turn. Preserve
    # that behavior for existing entries while placing a generous safety limit
    # on unbounded conversations. New entries use the more efficient defaults.
    memory_mode_default = (
        MIGRATED_MEMORY_MODE if entry.version < 9 else DEFAULT_MEMORY_MODE
    )
    memory_characters_default = (
        MIGRATED_MEMORY_MAX_CHARACTERS
        if entry.version < 9
        else DEFAULT_MEMORY_MAX_CHARACTERS
    )
    try:
        data[CONF_MEMORY_MODE] = normalize_memory_mode(
            data.get(CONF_MEMORY_MODE),
            default=memory_mode_default,
        )
    except ValueError:
        LOGGER.warning(
            "Config entry %s used an invalid conversation-memory mode; resetting to %s",
            entry.entry_id,
            memory_mode_default,
        )
        data[CONF_MEMORY_MODE] = memory_mode_default
    try:
        data[CONF_MEMORY_MAX_TURNS] = normalize_memory_max_turns(
            data.get(CONF_MEMORY_MAX_TURNS),
            default=DEFAULT_MEMORY_MAX_TURNS,
        )
    except ValueError:
        LOGGER.warning(
            "Config entry %s used an invalid conversation-memory turn limit; "
            "resetting to %s",
            entry.entry_id,
            DEFAULT_MEMORY_MAX_TURNS,
        )
        data[CONF_MEMORY_MAX_TURNS] = DEFAULT_MEMORY_MAX_TURNS
    try:
        data[CONF_MEMORY_MAX_CHARACTERS] = normalize_memory_max_characters(
            data.get(CONF_MEMORY_MAX_CHARACTERS),
            default=memory_characters_default,
        )
    except ValueError:
        LOGGER.warning(
            "Config entry %s used an invalid conversation-memory character limit; "
            "resetting to %s",
            entry.entry_id,
            memory_characters_default,
        )
        data[CONF_MEMORY_MAX_CHARACTERS] = memory_characters_default

    data.pop(LEGACY_OUTPUT_LIMIT_KEY, None)

    if entry.version < 11 or data != dict(entry.data):
        hass.config_entries.async_update_entry(entry, data=data, version=11)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one ChatGPT OAuth config entry."""
    client = ChatGPTOAuthClient(hass, entry)
    try:
        await client.token_manager.async_get_access_token()
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except BackendUnavailableError as err:
        raise ConfigEntryNotReady(str(err)) from err
    except ChatGPTOAuthError as err:
        raise ConfigEntryNotReady(str(err)) from err

    entry.runtime_data = client
    profile = get_model_profile(client.model)
    web_search = client.web_search_options
    text_transport = (
        "Responses for web-search requests; Responses Lite otherwise"
        if profile.responses_lite and web_search.enabled
        else ("Responses Lite" if profile.responses_lite else "Responses")
    )
    LOGGER.info(
        "Loaded %s v%s with %s, thinking level %s, %s, and web search %s",
        INTEGRATION_NAME,
        INTEGRATION_VERSION,
        profile.slug,
        client.reasoning_effort,
        text_transport,
        web_search.mode,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    profile_fingerprint = assistant_profiles_fingerprint(entry)

    async def _async_profile_settings_updated(
        updated_hass: HomeAssistant,
        updated_entry: ConfigEntry,
    ) -> None:
        """Reload only when an assistant profile changes.

        OAuth refreshes update credentials in the same config entry. Those updates must
        not tear down active conversation agents, so the listener compares only resolved
        profile settings and config subentries.
        """
        nonlocal profile_fingerprint
        new_fingerprint = assistant_profiles_fingerprint(updated_entry)
        if new_fingerprint == profile_fingerprint:
            return
        profile_fingerprint = new_fingerprint
        await updated_hass.config_entries.async_reload(updated_entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_async_profile_settings_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload one config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data = None
    return unloaded
