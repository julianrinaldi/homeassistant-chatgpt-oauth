"""Config flow for ChatGPT OAuth."""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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
    CONF_MODEL,
    CONF_PROMPT,
    CONF_REASONING_EFFORT,
    DEFAULT_ENABLE_HASS_CONTROL,
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DEFAULT_PROMPT,
    DOMAIN,
    LEGACY_OUTPUT_LIMIT_KEY,
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
    normalize_model,
    normalize_reasoning_effort,
    reasoning_efforts_for_model,
    validate_reasoning_effort,
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


class ChatGPTOAuthConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure ChatGPT OAuth."""

    VERSION = 6

    _oauth_input: dict[str, Any]
    _reconfigure_input: dict[str, Any]
    _oauth_state: str
    _code_verifier: str
    _authorize_url: str

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Collect the entry name, model, and system prompt."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                model = get_model_profile(user_input.get(CONF_MODEL)).slug
            except ValueError:
                errors["base"] = "unsupported_model"
            else:
                self._oauth_input = {
                    "name": str(user_input.get("name") or DEFAULT_NAME).strip()
                    or DEFAULT_NAME,
                    CONF_ENABLE_HASS_CONTROL: bool(
                        user_input.get(
                            CONF_ENABLE_HASS_CONTROL,
                            DEFAULT_ENABLE_HASS_CONTROL,
                        )
                    ),
                    CONF_MODEL: model,
                    CONF_PROMPT: str(
                        user_input.get(CONF_PROMPT) or DEFAULT_PROMPT
                    ).strip(),
                }
                return await self.async_step_reasoning()

        schema = vol.Schema(
            {
                vol.Optional("name", default=DEFAULT_NAME): str,
                vol.Required(CONF_MODEL, default=DEFAULT_MODEL): _model_schema(
                    DEFAULT_MODEL
                ),
                vol.Optional(
                    CONF_ENABLE_HASS_CONTROL,
                    default=DEFAULT_ENABLE_HASS_CONTROL,
                ): bool,
                vol.Optional(CONF_PROMPT, default=DEFAULT_PROMPT): _prompt_selector(),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
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

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_REASONING_EFFORT,
                    default=default_effort,
                ): _reasoning_schema(model)
            }
        )
        return self.async_show_form(
            step_id="reasoning",
            data_schema=schema,
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
            data_schema=vol.Schema(
                {vol.Required("callback_url"): str}
            ),
            errors=errors,
            description_placeholders={"authorize_url": self._authorize_url},
        )

    async def _async_finish_oauth(
        self,
        token_data: OAuthTokenData,
    ) -> ConfigFlowResult:
        """Validate the authenticated backend and create or update an entry."""
        model = normalize_model(self._oauth_input.get(CONF_MODEL, DEFAULT_MODEL))
        reasoning_effort = normalize_reasoning_effort(
            model,
            self._oauth_input.get(CONF_REASONING_EFFORT),
        )
        data = {
            **token_data.as_config_data(),
            CONF_ENABLE_HASS_CONTROL: bool(
                self._oauth_input.get(
                    CONF_ENABLE_HASS_CONTROL,
                    DEFAULT_ENABLE_HASS_CONTROL,
                )
            ),
            CONF_MODEL: model,
            CONF_REASONING_EFFORT: reasoning_effort,
            CONF_PROMPT: self._oauth_input.get(CONF_PROMPT, DEFAULT_PROMPT),
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
            # Preserve the user's title and non-auth settings gathered from the
            # existing entry while replacing credentials atomically.
            new_data = dict(entry.data)
            new_data.update(data)
            return self.async_update_reload_and_abort(
                entry,
                data_updates=new_data,
                reason="reauth_successful",
            )

        unique_id = token_data.account_id or hashlib.sha256(
            token_data.refresh_token.encode("utf-8")
        ).hexdigest()[:32]
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
        """Update the entry name, model, and system prompt."""
        entry = self._get_reconfigure_entry()
        current_model = normalize_model(entry.data.get(CONF_MODEL, DEFAULT_MODEL))
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                model = get_model_profile(
                    user_input.get(CONF_MODEL, current_model)
                ).slug
            except ValueError:
                errors["base"] = "unsupported_model"
            else:
                self._reconfigure_input = {
                    "name": str(user_input.get("name") or entry.title).strip()
                    or entry.title,
                    CONF_ENABLE_HASS_CONTROL: bool(
                        user_input.get(
                            CONF_ENABLE_HASS_CONTROL,
                            entry.data.get(
                                CONF_ENABLE_HASS_CONTROL,
                                DEFAULT_ENABLE_HASS_CONTROL,
                            ),
                        )
                    ),
                    CONF_MODEL: model,
                    CONF_PROMPT: str(
                        user_input.get(
                            CONF_PROMPT,
                            entry.data.get(CONF_PROMPT, DEFAULT_PROMPT),
                        )
                    ).strip(),
                }
                return await self.async_step_reconfigure_reasoning()

        schema = vol.Schema(
            {
                vol.Optional("name", default=entry.title): str,
                vol.Required(CONF_MODEL, default=current_model): _model_schema(
                    current_model
                ),
                vol.Optional(
                    CONF_ENABLE_HASS_CONTROL,
                    default=entry.data.get(
                        CONF_ENABLE_HASS_CONTROL,
                        DEFAULT_ENABLE_HASS_CONTROL,
                    ),
                ): bool,
                vol.Optional(
                    CONF_PROMPT,
                    default=entry.data.get(CONF_PROMPT, DEFAULT_PROMPT),
                ): _prompt_selector(),
            }
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
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
                        CONF_ENABLE_HASS_CONTROL: self._reconfigure_input[
                            CONF_ENABLE_HASS_CONTROL
                        ],
                        CONF_MODEL: model,
                        CONF_PROMPT: self._reconfigure_input[CONF_PROMPT],
                        CONF_REASONING_EFFORT: effort,
                    }
                )
                new_data.pop(LEGACY_OUTPUT_LIMIT_KEY, None)
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=new_data,
                    title=self._reconfigure_input["name"],
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_REASONING_EFFORT,
                    default=current_effort,
                ): _reasoning_schema(model)
            }
        )
        return self.async_show_form(
            step_id="reconfigure_reasoning",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "model": get_model_profile(model).display_name,
            },
        )

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Reauthenticate while retaining the entry's model and prompt."""
        entry = self._get_reauth_entry()
        model = normalize_model(entry_data.get(CONF_MODEL, DEFAULT_MODEL))
        self._oauth_input = {
            "name": entry.title,
            CONF_ENABLE_HASS_CONTROL: bool(
                entry_data.get(
                    CONF_ENABLE_HASS_CONTROL,
                    DEFAULT_ENABLE_HASS_CONTROL,
                )
            ),
            CONF_MODEL: model,
            CONF_REASONING_EFFORT: normalize_reasoning_effort(
                model,
                entry_data.get(CONF_REASONING_EFFORT),
            ),
            CONF_PROMPT: entry_data.get(CONF_PROMPT, DEFAULT_PROMPT),
        }
        return await self.async_step_auth_manual()


# Preserve the class name Home Assistant may reference in older traces/tests.
OpenAIOAuthConfigFlow = ChatGPTOAuthConfigFlow
