"""OAuth helpers and token lifecycle management for ChatGPT OAuth."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import secrets
import time
from typing import Any, Protocol
from urllib.parse import parse_qs

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from yarl import URL

from .const import (
    AUTHORIZE_URL,
    CLIENT_ID,
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_ID,
    CONF_EXPIRES,
    CONF_REFRESH_TOKEN,
    OAUTH_REQUEST_TIMEOUT,
    ORIGINATOR,
    REDIRECT_URI,
    SCOPE,
    TOKEN_REFRESH_MARGIN_MS,
    TOKEN_URL,
)
from .exceptions import (
    AuthenticationError,
    BackendUnavailableError,
    ResponseParseError,
    exception_from_http_response,
)


class ConfigEntryLike(Protocol):
    """Minimal config-entry interface needed by the OAuth client."""

    data: Mapping[str, Any]
    title: str


@dataclass(frozen=True, slots=True)
class OAuthTokenData:
    """Normalized token response data."""

    access_token: str
    refresh_token: str
    expires_ms: int
    account_id: str | None = None

    def as_config_data(self) -> dict[str, Any]:
        """Return the token fields stored in a Home Assistant config entry."""
        data: dict[str, Any] = {
            CONF_ACCESS_TOKEN: self.access_token,
            CONF_REFRESH_TOKEN: self.refresh_token,
            CONF_EXPIRES: self.expires_ms,
        }
        if self.account_id:
            data[CONF_ACCOUNT_ID] = self.account_id
        return data


def now_ms() -> int:
    """Return the current Unix time in milliseconds."""
    return int(time.time() * 1000)


def _expires_ms(value: Any) -> int:
    """Return a safe millisecond expiry value from persisted config data."""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def generate_code_verifier(length: int = 128) -> str:
    """Create an RFC 7636 PKCE verifier."""
    if not 43 <= length <= 128:
        raise ValueError("PKCE verifier length must be between 43 and 128 characters")
    return secrets.token_urlsafe(96)[:length]


def compute_code_challenge(code_verifier: str) -> str:
    """Create an RFC 7636 S256 PKCE challenge."""
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def build_authorize_url(*, code_verifier: str, state: str) -> str:
    """Build the ChatGPT OAuth authorization URL."""
    return str(
        URL(AUTHORIZE_URL).with_query(
            {
                "response_type": "code",
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "scope": SCOPE,
                "code_challenge": compute_code_challenge(code_verifier),
                "code_challenge_method": "S256",
                "state": state,
                "id_token_add_organizations": "true",
                "codex_cli_simplified_flow": "true",
                "originator": ORIGINATOR,
            }
        )
    )


def parse_authorization_input(value: str) -> tuple[str | None, str | None]:
    """Extract an OAuth code and state from a callback URL or pasted code."""
    value = value.strip()
    if not value:
        return None, None

    try:
        url = URL(value)
    except (TypeError, ValueError):
        url = None
    if url is not None and url.query.get("code"):
        return url.query.get("code"), url.query.get("state")

    if "code=" in value:
        params = parse_qs(value)
        return (params.get("code") or [None])[0], (params.get("state") or [None])[0]

    if "#" in value:
        code, state = value.split("#", 1)
        return code or None, state or None

    return value, None


def decode_jwt_payload(token: Any) -> dict[str, Any]:
    """Decode a JWT payload without validating its signature."""
    if not isinstance(token, str) or not token:
        return {}
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def extract_account_id(token: Any) -> str | None:
    """Extract the ChatGPT account ID from an OAuth JWT when available."""
    payload = decode_jwt_payload(token)
    auth_claim = payload.get("https://api.openai.com/auth")
    if not isinstance(auth_claim, dict):
        auth_claim = {}
    for value in (
        auth_claim.get("chatgpt_account_id"),
        payload.get("chatgpt_account_id"),
        payload.get("account_id"),
    ):
        if isinstance(value, str) and value:
            return value
    return None


def _token_data_from_payload(
    payload: Mapping[str, Any],
    *,
    fallback_refresh_token: str | None = None,
) -> OAuthTokenData:
    access = payload.get("access_token")
    refresh = payload.get("refresh_token") or fallback_refresh_token
    expires_in = payload.get("expires_in")
    if not isinstance(access, str) or not access:
        raise ResponseParseError("OAuth response did not include an access token")
    if not isinstance(refresh, str) or not refresh:
        raise ResponseParseError("OAuth response did not include a refresh token")
    try:
        expires_seconds = int(expires_in)
    except (TypeError, ValueError) as err:
        raise ResponseParseError(
            "OAuth response did not include a valid expiry"
        ) from err
    if expires_seconds <= 0:
        raise ResponseParseError("OAuth response did not include a positive expiry")
    account_id = extract_account_id(payload.get("id_token")) or extract_account_id(
        access
    )
    return OAuthTokenData(
        access_token=access,
        refresh_token=refresh,
        expires_ms=now_ms() + expires_seconds * 1000,
        account_id=account_id,
    )


async def async_exchange_authorization_code(
    session: aiohttp.ClientSession,
    *,
    code: str,
    code_verifier: str,
) -> OAuthTokenData:
    """Exchange an OAuth authorization code for access and refresh tokens."""
    try:
        async with session.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "code": code,
                "code_verifier": code_verifier,
                "redirect_uri": REDIRECT_URI,
            },
            timeout=aiohttp.ClientTimeout(total=OAUTH_REQUEST_TIMEOUT),
        ) as response:
            text = await response.text()
            request_id = response.headers.get("x-request-id")
            if response.status >= 400:
                raise exception_from_http_response(
                    response.status,
                    text,
                    request_id=request_id,
                    operation="OAuth token exchange",
                )
    except TimeoutError as err:
        raise BackendUnavailableError("OAuth token exchange timed out") from err
    except aiohttp.ClientError as err:
        raise BackendUnavailableError(
            f"Could not connect to the OAuth service: {err}"
        ) from err

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as err:
        raise ResponseParseError("OAuth service returned invalid JSON") from err
    if not isinstance(payload, dict):
        raise ResponseParseError("OAuth service returned an invalid response")
    return _token_data_from_payload(payload)


class OAuthTokenManager:
    """Serialize token refreshes and persist rotated credentials safely."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntryLike,
        *,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._session = session or async_get_clientsession(hass)
        self._refresh_lock = asyncio.Lock()

    async def async_get_access_token(
        self,
        *,
        force_refresh: bool = False,
        invalid_access_token: str | None = None,
    ) -> str:
        """Return a valid access token, refreshing it once when necessary.

        When a request received HTTP 401, ``invalid_access_token`` prevents
        concurrent callers from refreshing again after another task has already
        installed a replacement token.
        """
        access = self._entry.data.get(CONF_ACCESS_TOKEN)
        expires = _expires_ms(self._entry.data.get(CONF_EXPIRES))
        if (
            isinstance(access, str)
            and access
            and expires > now_ms() + TOKEN_REFRESH_MARGIN_MS
            and (not force_refresh or access != invalid_access_token)
        ):
            return access

        async with self._refresh_lock:
            # Another task may have completed the refresh while this caller waited.
            access = self._entry.data.get(CONF_ACCESS_TOKEN)
            expires = _expires_ms(self._entry.data.get(CONF_EXPIRES))
            if (
                isinstance(access, str)
                and access
                and expires > now_ms() + TOKEN_REFRESH_MARGIN_MS
                and (not force_refresh or access != invalid_access_token)
            ):
                return access
            return await self._async_refresh_token()

    async def _async_refresh_token(self) -> str:
        refresh = self._entry.data.get(CONF_REFRESH_TOKEN)
        if not isinstance(refresh, str) or not refresh:
            raise AuthenticationError(
                "ChatGPT OAuth credentials are incomplete; "
                "reauthenticate the integration"
            )

        try:
            async with self._session.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                    "client_id": CLIENT_ID,
                },
                timeout=aiohttp.ClientTimeout(total=OAUTH_REQUEST_TIMEOUT),
            ) as response:
                text = await response.text()
                request_id = response.headers.get("x-request-id")
                if response.status >= 400:
                    error = exception_from_http_response(
                        response.status,
                        text,
                        request_id=request_id,
                        operation="OAuth refresh",
                    )
                    if isinstance(error, AuthenticationError):
                        await self.async_start_reauth()
                    raise error
        except TimeoutError as err:
            raise BackendUnavailableError("OAuth refresh timed out") from err
        except aiohttp.ClientError as err:
            raise BackendUnavailableError(
                f"Could not connect to the OAuth service: {err}"
            ) from err

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as err:
            raise ResponseParseError("OAuth refresh returned invalid JSON") from err
        if not isinstance(payload, dict):
            raise ResponseParseError("OAuth refresh returned an invalid response")

        token_data = _token_data_from_payload(payload, fallback_refresh_token=refresh)
        self._persist_token_data(token_data)
        return token_data.access_token

    def _persist_token_data(self, token_data: OAuthTokenData) -> None:
        """Persist a refreshed token when backed by a real ConfigEntry."""
        if not isinstance(self._entry, ConfigEntry):
            return
        new_data = dict(self._entry.data)
        new_data.update(token_data.as_config_data())
        self._hass.config_entries.async_update_entry(self._entry, data=new_data)

    async def async_start_reauth(self) -> None:
        """Start Home Assistant's reauthentication flow when possible."""
        if isinstance(self._entry, ConfigEntry):
            self._entry.async_start_reauth(self._hass)


async def async_token_manager_for_entry(
    hass: HomeAssistant,
    entry: ConfigEntryLike,
) -> OAuthTokenManager:
    """Compatibility helper used by tests and downstream forks."""
    return OAuthTokenManager(hass, entry)
