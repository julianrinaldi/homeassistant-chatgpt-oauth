"""Config and assistant-profile flows for ChatGPT OAuth."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import secrets
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .auth import (
    OAuthTokenData,
    async_exchange_authorization_code,
    build_authorize_url,
    generate_code_verifier,
    parse_authorization_input,
)
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
    DEFAULT_MEMORY_MAX_CHARACTERS,
    DEFAULT_MEMORY_MAX_TURNS,
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DOMAIN,
    LEGACY_OUTPUT_LIMIT_KEY,
    MAX_MEMORY_MAX_CHARACTERS,
    MAX_MEMORY_MAX_TURNS,
    MAX_TOOL_CALLS,
    MAX_TOOL_TIME,
    MEMORY_MODE_CURRENT_TURN,
    MEMORY_MODE_FULL,
    MEMORY_MODE_RECENT,
    MEMORY_MODE_SUMMARIZED,
    MIN_MEMORY_MAX_CHARACTERS,
    MIN_MEMORY_MAX_TURNS,
    MIN_TOOL_CALLS,
    MIN_TOOL_TIME,
    SUBENTRY_TYPE_ASSISTANT,
)
from .exceptions import (
    AuthenticationError,
    BackendUnavailableError,
    ChatGPTOAuthError,
    RateLimitError,
    RequestTimeoutError,
    RequestValidationError,
)
from .models import (
    MODEL_PROFILES,
    REASONING_EFFORT_LABELS,
    get_model_profile,
    normalize_reasoning_effort,
    reasoning_efforts_for_model,
    validate_reasoning_effort,
)
from .profiles import profile_data_defaults, profile_data_from_input
from .web_search import (
    WEB_SEARCH_AUTO,
    WEB_SEARCH_CONTEXT_HIGH,
    WEB_SEARCH_CONTEXT_LOW,
    WEB_SEARCH_CONTEXT_MEDIUM,
    WEB_SEARCH_DISABLED,
    WEB_SEARCH_REQUIRED,
)


@dataclass(slots=True)
class _TemporaryEntry:
    """Minimal config-entry representation used for setup validation."""

    data: dict[str, Any]
    title: str


def _model_schema(default: str) -> vol.In:
    choices = {
        profile.slug: profile.display_name for profile in MODEL_PROFILES.values()
    }
    if default not in choices:
        default = DEFAULT_MODEL
    return vol.In(choices)


def _reasoning_schema(model: str) -> vol.In:
    return vol.In(
        {
            effort: REASONING_EFFORT_LABELS.get(effort, effort.title())
            for effort in reasoning_efforts_for_model(model)
        }
    )


def _web_search_mode_schema() -> vol.In:
    return vol.In(
        {
            WEB_SEARCH_DISABLED: "Disabled",
            WEB_SEARCH_AUTO: "Automatic",
            WEB_SEARCH_REQUIRED: "Required",
        }
    )


def _web_search_context_schema() -> vol.In:
    return vol.In(
        {
            WEB_SEARCH_CONTEXT_LOW: "Low",
            WEB_SEARCH_CONTEXT_MEDIUM: "Medium",
            WEB_SEARCH_CONTEXT_HIGH: "High",
        }
    )


def _memory_mode_schema() -> vol.In:
    return vol.In(
        {
            MEMORY_MODE_CURRENT_TURN: "Current message only",
            MEMORY_MODE_RECENT: "Recent conversation",
            MEMORY_MODE_SUMMARIZED: "Recent conversation plus summary",
            MEMORY_MODE_FULL: "Full conversation up to the size limit",
        }
    )


def _prompt_selector() -> selector.TextSelector:
    return selector.TextSelector({"multiline": True})


def _flow_error(error: ChatGPTOAuthError) -> str:
    if isinstance(error, AuthenticationError):
        return "invalid_auth"
    if isinstance(error, RateLimitError):
        return "rate_limited"
    if isinstance(error, (BackendUnavailableError, RequestTimeoutError)):
        return "cannot_connect"
    if isinstance(error, RequestValidationError):
        return "invalid_response"
    return "unknown"


def _profile_schema(
    defaults: Mapping[str, Any],
    *,
    name_default: str,
) -> vol.Schema:
    """Build one account or assistant-profile settings form."""
    return vol.Schema(
        {
            vol.Optional("name", default=name_default): str,
            vol.Required(CONF_MODEL, default=defaults[CONF_MODEL]): _model_schema(
                defaults[CONF_MODEL]
            ),
            vol.Optional(
                CONF_ENABLE_HASS_CONTROL,
                default=defaults[CONF_ENABLE_HASS_CONTROL],
            ): bool,
            vol.Optional(
                CONF_ENABLE_HISTORY_TOOLS,
                default=defaults[CONF_ENABLE_HISTORY_TOOLS],
            ): bool,
            vol.Optional(
                CONF_INCLUDE_USER_CONTEXT,
                default=defaults[CONF_INCLUDE_USER_CONTEXT],
            ): bool,
            vol.Optional(
                CONF_INCLUDE_SATELLITE_ROOM_CONTEXT,
                default=defaults[CONF_INCLUDE_SATELLITE_ROOM_CONTEXT],
            ): bool,
            vol.Optional(
                CONF_INCLUDE_ROOM_ENTITIES,
                default=defaults[CONF_INCLUDE_ROOM_ENTITIES],
            ): bool,
            vol.Required(
                CONF_MAX_TOOL_CALLS,
                default=defaults[CONF_MAX_TOOL_CALLS],
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_TOOL_CALLS,
                    max=MAX_TOOL_CALLS,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_MAX_TOOL_TIME,
                default=defaults[CONF_MAX_TOOL_TIME],
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_TOOL_TIME,
                    max=MAX_TOOL_TIME,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="seconds",
                )
            ),
            vol.Required(
                CONF_MEMORY_MODE,
                default=defaults[CONF_MEMORY_MODE],
            ): _memory_mode_schema(),
            vol.Required(
                CONF_MEMORY_MAX_TURNS,
                default=defaults[CONF_MEMORY_MAX_TURNS],
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_MEMORY_MAX_TURNS,
                    max=MAX_MEMORY_MAX_TURNS,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_MEMORY_MAX_CHARACTERS,
                default=defaults[CONF_MEMORY_MAX_CHARACTERS],
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_MEMORY_MAX_CHARACTERS,
                    max=MAX_MEMORY_MAX_CHARACTERS,
                    step=1000,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="characters",
                )
            ),
            vol.Required(
                CONF_WEB_SEARCH_MODE,
                default=defaults[CONF_WEB_SEARCH_MODE],
            ): _web_search_mode_schema(),
            vol.Required(
                CONF_WEB_SEARCH_CONTEXT_SIZE,
                default=defaults[CONF_WEB_SEARCH_CONTEXT_SIZE],
            ): _web_search_context_schema(),
            vol.Optional(
                CONF_WEB_SEARCH_INCLUDE_SOURCES,
                default=defaults[CONF_WEB_SEARCH_INCLUDE_SOURCES],
            ): bool,
            vol.Optional(
                CONF_WEB_SEARCH_LIVE_ACCESS,
                default=defaults[CONF_WEB_SEARCH_LIVE_ACCESS],
            ): bool,
            vol.Optional(
                CONF_WEB_SEARCH_USE_HASS_LOCATION,
                default=defaults[CONF_WEB_SEARCH_USE_HASS_LOCATION],
            ): bool,
            vol.Optional(
                CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION,
                default=defaults[CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION],
            ): bool,
            vol.Optional(
                CONF_PROMPT,
                default=defaults[CONF_PROMPT],
            ): _prompt_selector(),
        }
    )


def _parse_profile_form(
    user_input: Mapping[str, Any],
    *,
    defaults: Mapping[str, Any],
    fallback_name: str,
) -> tuple[str, dict[str, Any]]:
    """Normalize one profile form and its title."""
    model = get_model_profile(user_input.get(CONF_MODEL, defaults[CONF_MODEL])).slug
    normalized_input = dict(user_input)
    normalized_input[CONF_MODEL] = model
    data = profile_data_from_input(normalized_input, defaults=defaults)
    name = str(user_input.get("name") or fallback_name).strip() or fallback_name
    return name, data


class ChatGPTOAuthConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure a ChatGPT OAuth account and its default assistant."""

    VERSION = 11

    _oauth_input: dict[str, Any]
    _reconfigure_input: dict[str, Any]
    _oauth_state: str
    _code_verifier: str
    _authorize_url: str

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls,
        config_entry: ConfigEntry,
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return additional configurations sharing this OAuth account."""
        return {SUBENTRY_TYPE_ASSISTANT: AssistantProfileSubentryFlow}

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Collect default assistant behavior before OAuth authentication."""
        defaults = profile_data_defaults()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                name, data = _parse_profile_form(
                    user_input,
                    defaults=defaults,
                    fallback_name=DEFAULT_NAME,
                )
            except (ValueError, vol.Invalid):
                errors["base"] = "unsupported_profile_settings"
            else:
                self._oauth_input = {"name": name, **data}
                return await self.async_step_reasoning()

        return self.async_show_form(
            step_id="user",
            data_schema=_profile_schema(defaults, name_default=DEFAULT_NAME),
            errors=errors,
        )

    async def async_step_reasoning(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Collect a thinking level compatible with the selected model."""
        model = self._oauth_input[CONF_MODEL]
        default_effort = normalize_reasoning_effort(
            model,
            self._oauth_input.get(CONF_REASONING_EFFORT),
        )
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                effort = validate_reasoning_effort(
                    model,
                    user_input.get(CONF_REASONING_EFFORT),
                )
            except ValueError:
                errors["base"] = "unsupported_reasoning"
            else:
                self._oauth_input[CONF_REASONING_EFFORT] = effort
                return await self.async_step_auth_manual()

        return self.async_show_form(
            step_id="reasoning",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_REASONING_EFFORT,
                        default=default_effort,
                    ): _reasoning_schema(model)
                }
            ),
            errors=errors,
            description_placeholders={
                "model": get_model_profile(model).display_name,
            },
        )

    async def async_step_auth_manual(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Complete OAuth using a browser and pasted localhost callback URL."""
        if not hasattr(self, "_authorize_url"):
            self._code_verifier = generate_code_verifier()
            self._oauth_state = secrets.token_urlsafe(24)
            self._authorize_url = build_authorize_url(
                code_verifier=self._code_verifier,
                state=self._oauth_state,
            )

        errors: dict[str, str] = {}
        if user_input is not None:
            code, returned_state = parse_authorization_input(
                str(user_input.get("callback_url") or "")
            )
            if not code:
                errors["base"] = "missing_code"
            elif returned_state and returned_state != self._oauth_state:
                errors["base"] = "state_mismatch"
            else:
                try:
                    token_data = await async_exchange_authorization_code(
                        async_get_clientsession(self.hass),
                        code=code,
                        code_verifier=self._code_verifier,
                    )
                    return await self._async_finish_oauth(token_data)
                except ChatGPTOAuthError as err:
                    errors["base"] = _flow_error(err)

        return self.async_show_form(
            step_id="auth_manual",
            data_schema=vol.Schema({vol.Required("callback_url"): str}),
            errors=errors,
            description_placeholders={"authorize_url": self._authorize_url},
        )

    async def _async_finish_oauth(
        self,
        token_data: OAuthTokenData,
    ) -> ConfigFlowResult:
        """Validate the authenticated backend and create or update an entry."""
        model = self._oauth_input[CONF_MODEL]
        data = {
            **token_data.as_config_data(),
            **{key: value for key, value in self._oauth_input.items() if key != "name"},
            CONF_REASONING_EFFORT: normalize_reasoning_effort(
                model,
                self._oauth_input.get(CONF_REASONING_EFFORT),
            ),
        }
        data.pop(LEGACY_OUTPUT_LIMIT_KEY, None)

        temporary_entry = _TemporaryEntry(
            data=data,
            title=self._oauth_input.get("name", DEFAULT_NAME),
        )
        try:
            await ChatGPTOAuthClient(
                self.hass,
                temporary_entry,
                session=async_get_clientsession(self.hass),
            ).async_test_connection()
        except ChatGPTOAuthError as err:
            return self.async_show_form(
                step_id="auth_manual",
                data_schema=vol.Schema({vol.Required("callback_url"): str}),
                errors={"base": _flow_error(err)},
                description_placeholders={"authorize_url": self._authorize_url},
            )

        if self.context.get("source") == config_entries.SOURCE_REAUTH:
            entry = self._get_reauth_entry()
            new_data = dict(entry.data)
            new_data.update(data)
            result = self.async_update_and_abort(
                entry,
                data=new_data,
                reason="reauth_successful",
            )
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return result

        unique_id = (
            token_data.account_id
            or hashlib.sha256(token_data.refresh_token.encode("utf-8")).hexdigest()[:32]
        )
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=self._oauth_input.get("name", DEFAULT_NAME),
            data=data,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Update the default assistant profile."""
        entry = self._get_reconfigure_entry()
        defaults = profile_data_defaults(entry.data)
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                name, data = _parse_profile_form(
                    user_input,
                    defaults=defaults,
                    fallback_name=entry.title,
                )
            except (ValueError, vol.Invalid):
                errors["base"] = "unsupported_profile_settings"
            else:
                self._reconfigure_input = {"name": name, **data}
                return await self.async_step_reconfigure_reasoning()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_profile_schema(defaults, name_default=entry.title),
            errors=errors,
        )

    async def async_step_reconfigure_reasoning(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Update the model-compatible thinking level."""
        entry = self._get_reconfigure_entry()
        model = self._reconfigure_input[CONF_MODEL]
        current_effort = normalize_reasoning_effort(
            model,
            entry.data.get(CONF_REASONING_EFFORT),
        )
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                effort = validate_reasoning_effort(
                    model,
                    user_input.get(CONF_REASONING_EFFORT),
                )
            except ValueError:
                errors["base"] = "unsupported_reasoning"
            else:
                new_data = dict(entry.data)
                new_data.update(
                    {
                        key: value
                        for key, value in self._reconfigure_input.items()
                        if key != "name"
                    }
                )
                new_data[CONF_REASONING_EFFORT] = effort
                new_data.pop(LEGACY_OUTPUT_LIMIT_KEY, None)
                return self.async_update_and_abort(
                    entry,
                    data=new_data,
                    title=self._reconfigure_input["name"],
                )

        return self.async_show_form(
            step_id="reconfigure_reasoning",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_REASONING_EFFORT,
                        default=current_effort,
                    ): _reasoning_schema(model)
                }
            ),
            errors=errors,
            description_placeholders={
                "model": get_model_profile(model).display_name,
            },
        )

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Reauthenticate while retaining default-profile settings."""
        entry = self._get_reauth_entry()
        defaults = profile_data_defaults(entry_data)
        self._oauth_input = {
            "name": entry.title,
            **defaults,
        }
        return await self.async_step_auth_manual()


class AssistantProfileSubentryFlow(ConfigSubentryFlow):
    """Add and reconfigure assistants that share the parent OAuth account."""

    _profile_input: dict[str, Any]

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        """Add another assistant profile."""
        entry = self._get_entry()
        defaults = profile_data_defaults(entry.data)
        # New profiles start with conservative privacy and memory defaults even
        # when the parent account was migrated from an older full-history entry.
        defaults[CONF_ENABLE_HISTORY_TOOLS] = False
        defaults[CONF_MEMORY_MODE] = MEMORY_MODE_RECENT
        defaults[CONF_MEMORY_MAX_TURNS] = DEFAULT_MEMORY_MAX_TURNS
        defaults[CONF_MEMORY_MAX_CHARACTERS] = DEFAULT_MEMORY_MAX_CHARACTERS
        default_name = "Additional assistant"
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                name, data = _parse_profile_form(
                    user_input,
                    defaults=defaults,
                    fallback_name=default_name,
                )
            except (ValueError, vol.Invalid):
                errors["base"] = "unsupported_profile_settings"
            else:
                self._profile_input = {"name": name, **data}
                return await self.async_step_reasoning()

        return self.async_show_form(
            step_id="user",
            data_schema=_profile_schema(defaults, name_default=default_name),
            errors=errors,
        )

    async def async_step_reasoning(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        """Select a compatible thinking level for a new profile."""
        model = self._profile_input[CONF_MODEL]
        default_effort = normalize_reasoning_effort(
            model,
            self._profile_input.get(CONF_REASONING_EFFORT),
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                effort = validate_reasoning_effort(
                    model,
                    user_input.get(CONF_REASONING_EFFORT),
                )
            except ValueError:
                errors["base"] = "unsupported_reasoning"
            else:
                data = {
                    key: value
                    for key, value in self._profile_input.items()
                    if key != "name"
                }
                data[CONF_REASONING_EFFORT] = effort
                return self.async_create_entry(
                    title=self._profile_input["name"],
                    data=data,
                )

        return self.async_show_form(
            step_id="reasoning",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_REASONING_EFFORT,
                        default=default_effort,
                    ): _reasoning_schema(model)
                }
            ),
            errors=errors,
            description_placeholders={
                "model": get_model_profile(model).display_name,
            },
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        """Update an existing additional assistant profile."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        combined_defaults = dict(entry.data)
        combined_defaults.update(subentry.data)
        defaults = profile_data_defaults(combined_defaults)
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                name, data = _parse_profile_form(
                    user_input,
                    defaults=defaults,
                    fallback_name=subentry.title,
                )
            except (ValueError, vol.Invalid):
                errors["base"] = "unsupported_profile_settings"
            else:
                self._profile_input = {"name": name, **data}
                return await self.async_step_reconfigure_reasoning()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_profile_schema(defaults, name_default=subentry.title),
            errors=errors,
        )

    async def async_step_reconfigure_reasoning(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        """Update an additional profile's thinking level and reload."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        model = self._profile_input[CONF_MODEL]
        current_effort = normalize_reasoning_effort(
            model,
            subentry.data.get(CONF_REASONING_EFFORT),
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                effort = validate_reasoning_effort(
                    model,
                    user_input.get(CONF_REASONING_EFFORT),
                )
            except ValueError:
                errors["base"] = "unsupported_reasoning"
            else:
                data = {
                    key: value
                    for key, value in self._profile_input.items()
                    if key != "name"
                }
                data[CONF_REASONING_EFFORT] = effort
                return self.async_update_and_abort(
                    entry,
                    subentry,
                    title=self._profile_input["name"],
                    data=data,
                )

        return self.async_show_form(
            step_id="reconfigure_reasoning",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_REASONING_EFFORT,
                        default=current_effort,
                    ): _reasoning_schema(model)
                }
            ),
            errors=errors,
            description_placeholders={
                "model": get_model_profile(model).display_name,
            },
        )


# Preserve the class name Home Assistant may reference in older traces/tests.
OpenAIOAuthConfigFlow = ChatGPTOAuthConfigFlow
