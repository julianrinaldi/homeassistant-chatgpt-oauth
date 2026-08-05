"""Tests for OAuth parsing and refresh serialization."""
from __future__ import annotations

import asyncio
import base64
import json
from types import SimpleNamespace

import pytest

from custom_components.openai_oauth_conversation import auth as auth_module
from custom_components.openai_oauth_conversation.auth import (
    OAuthTokenManager,
    _token_data_from_payload,
    compute_code_challenge,
    extract_account_id,
    generate_code_verifier,
    parse_authorization_input,
)
from custom_components.openai_oauth_conversation.const import (
    CONF_ACCESS_TOKEN,
    CONF_EXPIRES,
    CONF_REFRESH_TOKEN,
)
from custom_components.openai_oauth_conversation.exceptions import (
    AuthenticationError,
    ResponseParseError,
)


def _jwt(payload: dict) -> str:
    encoded = (
        base64.urlsafe_b64encode(json.dumps(payload).encode())
        .decode()
        .rstrip("=")
    )
    return f"header.{encoded}.signature"


def test_callback_and_jwt_parsing() -> None:
    """The manual OAuth callback and account routing claim are normalized."""
    code, state = parse_authorization_input(
        "http://localhost:1455/auth/callback?code=abc&state=xyz"
    )
    assert (code, state) == ("abc", "xyz")
    token = _jwt(
        {
            "https://api.openai.com/auth": {
                "chatgpt_account_id": "account-123"
            }
        }
    )
    assert extract_account_id(token) == "account-123"
    assert compute_code_challenge("verifier") == compute_code_challenge("verifier")


def test_pkce_verifier_bounds() -> None:
    """PKCE verifiers stay within the RFC 7636 length range."""
    assert len(generate_code_verifier(43)) == 43
    assert len(generate_code_verifier(128)) == 128
    with pytest.raises(ValueError, match="between 43 and 128"):
        generate_code_verifier(42)
    with pytest.raises(ValueError, match="between 43 and 128"):
        generate_code_verifier(129)


def test_token_response_requires_positive_expiry() -> None:
    """Immediately expired token responses are rejected during setup."""
    with pytest.raises(ResponseParseError, match="positive expiry"):
        _token_data_from_payload(
            {
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_in": 0,
            }
        )


@pytest.mark.asyncio
async def test_concurrent_expired_tokens_refresh_once(monkeypatch) -> None:
    """Concurrent image/data requests cannot race token refresh."""
    entry = SimpleNamespace(
        data={
            CONF_ACCESS_TOKEN: "expired",
            CONF_REFRESH_TOKEN: "refresh",
            CONF_EXPIRES: 0,
        },
        title="Account",
    )
    hass = SimpleNamespace()
    manager = OAuthTokenManager(hass, entry, session=SimpleNamespace())
    refreshes = 0

    async def fake_refresh() -> str:
        nonlocal refreshes
        refreshes += 1
        await asyncio.sleep(0)
        entry.data = {
            **entry.data,
            CONF_ACCESS_TOKEN: "fresh",
            CONF_EXPIRES: auth_module.now_ms() + 3_600_000,
        }
        return "fresh"

    monkeypatch.setattr(manager, "_async_refresh_token", fake_refresh)
    first, second = await asyncio.gather(
        manager.async_get_access_token(),
        manager.async_get_access_token(),
    )
    assert (first, second) == ("fresh", "fresh")
    assert refreshes == 1


@pytest.mark.asyncio
async def test_rejected_refresh_starts_reauthentication(monkeypatch) -> None:
    """A revoked refresh token starts Home Assistant's reauth flow."""

    class RejectedResponse:
        status = 401
        headers: dict[str, str] = {}

        async def __aenter__(self):
            await asyncio.sleep(0)
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            await asyncio.sleep(0)
            return False

        async def text(self) -> str:
            await asyncio.sleep(0)
            return '{"error":{"message":"invalid refresh token"}}'

    class RejectedSession:
        def post(self, *args, **kwargs):
            return RejectedResponse()

    entry = SimpleNamespace(
        data={
            CONF_ACCESS_TOKEN: "expired",
            CONF_REFRESH_TOKEN: "revoked",
            CONF_EXPIRES: 0,
        },
        title="Account",
    )
    manager = OAuthTokenManager(SimpleNamespace(), entry, session=RejectedSession())
    started = False

    async def start_reauth() -> None:
        nonlocal started
        started = True

    monkeypatch.setattr(manager, "async_start_reauth", start_reauth)
    with pytest.raises(AuthenticationError, match="invalid refresh token"):
        await manager.async_get_access_token()
    assert started
