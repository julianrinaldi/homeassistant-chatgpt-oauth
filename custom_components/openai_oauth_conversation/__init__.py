"""ChatGPT OAuth integration for Home Assistant."""
from __future__ import annotations

from typing import Any, NoReturn

import voluptuous as vol

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
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.typing import ConfigType

from .client import ChatGPTOAuthClient
from .const import (
    CONF_ENABLE_HASS_CONTROL,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_REASONING_EFFORT,
    DEFAULT_ENABLE_HASS_CONTROL,
    DEFAULT_MODEL,
    DEFAULT_PROMPT,
    DOMAIN,
    INTEGRATION_NAME,
    INTEGRATION_VERSION,
    LEGACY_OUTPUT_LIMIT_KEY,
    LOGGER,
    MAX_ATTACHMENTS_TOTAL_BYTES,
    MAX_IMAGE_ATTACHMENTS,
    SERVICE_ANALYZE_IMAGE,
    SERVICE_GENERATE_CONTENT,
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
from .models import (
    ALL_REASONING_EFFORTS,
    get_model_profile,
    normalize_model,
    normalize_reasoning_effort,
)

PLATFORMS: tuple[Platform, ...] = (Platform.CONVERSATION, Platform.AI_TASK)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register integration actions."""

    async def generate_content(call: ServiceCall) -> ServiceResponse:
        entry = _get_entry(hass, call.data["config_entry"])
        client = _get_client(entry)
        model, reasoning_effort = _resolve_call_settings(client, call)
        instructions = entry.data.get(CONF_PROMPT, DEFAULT_PROMPT)
        try:
            result = await client.async_create_response(
                model=model,
                reasoning_effort=reasoning_effort,
                instructions=instructions,
                content=[text_part(call.data[CONF_PROMPT])],
            )
        except ChatGPTOAuthError as err:
            _raise_home_assistant_error(err)
        return {"text": result.text}

    async def analyze_image(call: ServiceCall) -> ServiceResponse:
        entry = _get_entry(hass, call.data["config_entry"])
        client = _get_client(entry)
        model, reasoning_effort = _resolve_call_settings(client, call)

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
            )
        except ChatGPTOAuthError as err:
            _raise_home_assistant_error(err)
        return {"response_text": result.text, "text": result.text}

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
                vol.Optional(CONF_MODEL): _model_validator,
                vol.Optional(CONF_REASONING_EFFORT): _reasoning_validator,
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
                vol.Optional(CONF_MODEL): _model_validator,
                vol.Optional(CONF_REASONING_EFFORT): _reasoning_validator,
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
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate pre-v1 entries without changing their stable domain or IDs."""
    if entry.version > 6:
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
    data.setdefault(CONF_ENABLE_HASS_CONTROL, DEFAULT_ENABLE_HASS_CONTROL)
    data.pop(LEGACY_OUTPUT_LIMIT_KEY, None)

    if entry.version < 6 or data != dict(entry.data):
        hass.config_entries.async_update_entry(entry, data=data, version=6)
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
    LOGGER.info(
        "Loaded %s v%s with %s, thinking level %s, and %s transport",
        INTEGRATION_NAME,
        INTEGRATION_VERSION,
        profile.slug,
        client.reasoning_effort,
        "Responses Lite" if profile.responses_lite else "Responses",
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload one config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data = None
    return unloaded
