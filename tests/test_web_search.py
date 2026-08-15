"""Tests for OpenAI web-search options and tool declarations."""

from __future__ import annotations

from types import MethodType, SimpleNamespace

import pytest

from custom_components.openai_oauth_conversation.client import ChatGPTOAuthClient
from custom_components.openai_oauth_conversation.const import (
    CONF_WEB_SEARCH_INCLUDE_SOURCES,
    CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION,
)
from custom_components.openai_oauth_conversation.exceptions import (
    RequestValidationError,
)
from custom_components.openai_oauth_conversation.web_search import (
    WEB_SEARCH_REQUIRED,
    WebSearchOptions,
    approximate_home_assistant_location,
    build_web_search_tool,
    normalize_allowed_domains,
    normalize_web_search_context_size,
    normalize_web_search_mode,
    precise_home_assistant_location,
    web_search_instructions,
)


def test_web_search_tool_uses_supported_controls() -> None:
    """The current hosted tool receives context, live, domain, and location hints."""
    hass = SimpleNamespace(
        config=SimpleNamespace(country="us", time_zone="America/New_York")
    )
    options = WebSearchOptions(
        mode=WEB_SEARCH_REQUIRED,
        context_size="high",
        live_access=False,
        use_home_assistant_location=True,
        allowed_domains=("openai.com", "home-assistant.io"),
    )
    assert build_web_search_tool(options, hass) == {
        "type": "web_search",
        "search_context_size": "high",
        "external_web_access": False,
        "filters": {
            "allowed_domains": ["openai.com", "home-assistant.io"],
        },
        "user_location": {
            "type": "approximate",
            "country": "US",
            "timezone": "America/New_York",
        },
    }


def test_preview_fallback_omits_unsupported_controls() -> None:
    """The legacy preview tool never receives filters or cache-only controls."""
    hass = SimpleNamespace(config=SimpleNamespace(country=None, time_zone=None))
    options = WebSearchOptions(
        mode=WEB_SEARCH_REQUIRED,
        context_size="medium",
        live_access=False,
        allowed_domains=("openai.com",),
    )
    assert build_web_search_tool(
        options,
        hass,
        tool_type="web_search_preview",
    ) == {
        "type": "web_search_preview",
        "search_context_size": "medium",
    }


def test_web_search_normalization_and_domain_validation() -> None:
    """Public settings accept documented values and clean domain-only filters."""
    assert normalize_web_search_mode("always", default="disabled") == "required"
    assert normalize_web_search_context_size("HIGH", default="medium") == "high"
    assert normalize_allowed_domains(
        ["https://OpenAI.com/", "home-assistant.io", "openai.com"]
    ) == ("openai.com", "home-assistant.io")
    with pytest.raises(ValueError, match="must not contain a path"):
        normalize_allowed_domains(["https://example.com/path"])
    with pytest.raises(ValueError, match="Invalid allowed"):
        normalize_allowed_domains(["https://user@example.com"])
    with pytest.raises(ValueError, match="Invalid allowed"):
        normalize_allowed_domains(["example.com:443"])
    with pytest.raises(ValueError, match="Invalid allowed"):
        normalize_allowed_domains(["*.example.com"])


def test_approximate_location_never_exposes_coordinates() -> None:
    """Only country and time zone leave Home Assistant as location hints."""
    hass = SimpleNamespace(
        config=SimpleNamespace(
            country="US",
            time_zone="America/New_York",
            latitude=40.7,
            longitude=-74.0,
            location_name="Home",
        )
    )
    assert approximate_home_assistant_location(hass) == {
        "type": "approximate",
        "country": "US",
        "timezone": "America/New_York",
    }


def test_precise_location_is_validated_and_added_to_instructions() -> None:
    """Explicit precise sharing adds trusted coordinates as request context."""
    hass = SimpleNamespace(
        config=SimpleNamespace(
            country="us",
            time_zone="America/New_York",
            latitude=40.7128,
            longitude=-74.006,
            location_name="  My\nHome  ",
        )
    )
    assert precise_home_assistant_location(hass) == {
        "latitude": 40.7128,
        "longitude": -74.006,
        "location_name": "My Home",
        "country": "US",
        "timezone": "America/New_York",
    }

    options = WebSearchOptions(
        mode="auto",
        use_home_assistant_precise_location=True,
    )
    instructions = web_search_instructions(options, hass)
    assert '"latitude": 40.7128' in instructions
    assert '"longitude": -74.006' in instructions
    assert '"location_name": "My Home"' in instructions
    assert "Do not repeat the precise coordinates" in instructions
    assert build_web_search_tool(options, hass)["user_location"] == {
        "type": "approximate",
        "country": "US",
        "timezone": "America/New_York",
    }


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (91, 0),
        (0, 181),
        (float("nan"), 0),
        (True, 0),
        (None, None),
    ],
)
def test_invalid_precise_location_is_not_shared(latitude, longitude) -> None:
    """Missing or unsafe coordinates never enter request instructions."""
    hass = SimpleNamespace(
        config=SimpleNamespace(
            country=None,
            time_zone=None,
            latitude=latitude,
            longitude=longitude,
            location_name="Home",
        )
    )
    options = WebSearchOptions(
        mode="auto",
        use_home_assistant_precise_location=True,
    )
    assert precise_home_assistant_location(hass) is None
    assert "precise home-location sharing" not in web_search_instructions(options, hass)


def test_voice_friendly_search_instructions_do_not_request_spoken_sources() -> None:
    """Source annotations remain available without cluttering spoken answers."""
    hidden = web_search_instructions(
        WebSearchOptions(mode="auto", include_sources=False)
    )
    visible = web_search_instructions(
        WebSearchOptions(mode="auto", include_sources=True)
    )

    assert "without adding citation numbers" in hidden
    assert "Sources section" in hidden
    assert "Preserve source citation annotations" in visible


def test_source_display_resolves_from_config_and_per_call_override() -> None:
    """The account default can be overridden for one integration action."""
    client = object.__new__(ChatGPTOAuthClient)
    client.entry = SimpleNamespace(
        data={
            CONF_WEB_SEARCH_INCLUDE_SOURCES: True,
            CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION: True,
        }
    )

    assert client.resolve_web_search_options().include_sources is True
    assert (
        client.resolve_web_search_options().use_home_assistant_precise_location is True
    )
    assert (
        client.resolve_web_search_options(include_sources=False).include_sources
        is False
    )
    assert (
        client.resolve_web_search_options(
            use_home_assistant_precise_location=False
        ).use_home_assistant_precise_location
        is False
    )


def _client_with_rejected_request(message: str) -> ChatGPTOAuthClient:
    client = object.__new__(ChatGPTOAuthClient)
    client.hass = SimpleNamespace(
        config=SimpleNamespace(country="US", time_zone="America/New_York")
    )
    client.entry = SimpleNamespace(
        data={"model": "gpt-5.6-terra", "reasoning_effort": "medium"}
    )

    async def reject(_self, _payload, *, responses_lite):
        del responses_lite
        raise RequestValidationError(message)

    client._async_collect_turn = MethodType(reject, client)
    return client


@pytest.mark.asyncio
async def test_domain_allowlist_is_never_silently_removed() -> None:
    """A compatibility retry must not widen an allowlisted search."""
    client = _client_with_rejected_request("Unsupported parameter: filters")
    with pytest.raises(RequestValidationError, match="refusing an unrestricted"):
        await client._async_create_turn(
            model="gpt-5.6-terra",
            instructions="Search.",
            input_items=[],
            web_search=WebSearchOptions(
                mode=WEB_SEARCH_REQUIRED,
                allowed_domains=("openai.com",),
            ),
        )


@pytest.mark.asyncio
async def test_cache_only_search_is_never_silently_made_live() -> None:
    """A compatibility retry must not remove a cache-only constraint."""
    client = _client_with_rejected_request("Unsupported parameter: external_web_access")
    with pytest.raises(RequestValidationError, match="refusing to enable live"):
        await client._async_create_turn(
            model="gpt-5.6-terra",
            instructions="Search.",
            input_items=[],
            web_search=WebSearchOptions(
                mode=WEB_SEARCH_REQUIRED,
                live_access=False,
            ),
        )
