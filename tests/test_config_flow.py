"""Tests for the public setup flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from yarl import URL

from homeassistant import config_entries, data_entry_flow

from custom_components.openai_oauth_conversation.auth import OAuthTokenData
from custom_components.openai_oauth_conversation.const import (
    CONF_ENABLE_HASS_CONTROL,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_REASONING_EFFORT,
    DOMAIN,
)


async def test_full_user_flow(hass) -> None:
    """Setup links model-specific thinking selection to OAuth validation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Primary account",
            CONF_ENABLE_HASS_CONTROL: False,
            CONF_MODEL: "gpt-5.6-luna",
            CONF_PROMPT: "Be helpful.",
        },
    )
    assert result["step_id"] == "reasoning"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_REASONING_EFFORT: "max"},
    )
    assert result["step_id"] == "auth_manual"
    authorize_url = result["description_placeholders"]["authorize_url"]
    state = URL(authorize_url).query["state"]

    token_data = OAuthTokenData(
        access_token="access-token",
        refresh_token="refresh-token",
        expires_ms=4_000_000_000_000,
        account_id="account-123",
    )
    with (
        patch(
            "custom_components.openai_oauth_conversation.config_flow."
            "async_exchange_authorization_code",
            AsyncMock(return_value=token_data),
        ),
        patch(
            "custom_components.openai_oauth_conversation.config_flow."
            "ChatGPTOAuthClient.async_test_connection",
            AsyncMock(return_value=None),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "callback_url": (
                    "http://localhost:1455/auth/callback?code=code&state=" + state
                )
            },
        )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Primary account"
    assert result["data"][CONF_ENABLE_HASS_CONTROL] is False
    assert result["data"][CONF_MODEL] == "gpt-5.6-luna"
    assert result["data"][CONF_REASONING_EFFORT] == "max"
