"""Tests for the model capability catalog."""
from __future__ import annotations

import pytest

from custom_components.openai_oauth_conversation.models import (
    MODEL_PROFILES,
    default_reasoning_effort,
    get_model_profile,
    normalize_model,
    normalize_reasoning_effort,
    reasoning_effort_for_request,
    reasoning_efforts_for_model,
    validate_reasoning_effort,
)


@pytest.mark.parametrize(
    ("model", "levels", "default"),
    [
        (
            "gpt-5.6-sol",
            ("low", "medium", "high", "xhigh", "max", "ultra"),
            "low",
        ),
        (
            "gpt-5.6-terra",
            ("low", "medium", "high", "xhigh", "max", "ultra"),
            "medium",
        ),
        (
            "gpt-5.6-luna",
            ("low", "medium", "high", "xhigh", "max"),
            "medium",
        ),
        ("gpt-5.5", ("low", "medium", "high", "xhigh"), "medium"),
    ],
)
def test_model_catalog(model: str, levels: tuple[str, ...], default: str) -> None:
    """Every public model exposes the expected model-specific levels."""
    profile = get_model_profile(model)
    assert profile.reasoning_efforts == levels
    assert reasoning_efforts_for_model(model) == levels
    assert default_reasoning_effort(model) == default
    assert normalize_reasoning_effort(model, None) == default
    assert profile.supports_web_search is True


def test_all_catalog_levels_validate() -> None:
    """Every catalog combination is accepted and maps correctly on the wire."""
    for model, profile in MODEL_PROFILES.items():
        for level in profile.reasoning_efforts:
            assert validate_reasoning_effort(model, level) == level
            expected = "max" if level == "ultra" else level
            assert reasoning_effort_for_request(model, level) == expected


def test_model_alias_and_reasoning_aliases() -> None:
    """Legacy aliases remain compatible."""
    assert normalize_model(" GPT-5.6 ") == "gpt-5.6-sol"
    assert validate_reasoning_effort("gpt-5.6-sol", "extra high") == "xhigh"
    assert validate_reasoning_effort("gpt-5.6-terra", "maximum") == "max"


def test_incompatible_level_is_rejected() -> None:
    """The selector and runtime share strict model compatibility."""
    with pytest.raises(ValueError, match="not available"):
        validate_reasoning_effort("gpt-5.6-luna", "ultra")
    with pytest.raises(ValueError, match="not available"):
        validate_reasoning_effort("gpt-5.5", "max")
