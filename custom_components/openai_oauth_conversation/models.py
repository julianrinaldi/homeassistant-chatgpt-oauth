"""Model capability catalog for ChatGPT OAuth."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .const import DEFAULT_MODEL


@dataclass(frozen=True, slots=True)
class ModelProfile:
    """Capabilities and defaults for one hosted Codex model."""

    slug: str
    display_name: str
    reasoning_efforts: tuple[str, ...]
    default_reasoning_effort: str
    responses_lite: bool
    supports_images: bool = True
    supports_files: bool = True
    supports_tools: bool = True
    supports_structured_output: bool = True
    supports_web_search: bool = True


MODEL_PROFILES: Final[dict[str, ModelProfile]] = {
    "gpt-5.6-sol": ModelProfile(
        slug="gpt-5.6-sol",
        display_name="GPT-5.6 Sol",
        reasoning_efforts=("low", "medium", "high", "xhigh", "max", "ultra"),
        default_reasoning_effort="low",
        responses_lite=True,
    ),
    "gpt-5.6-terra": ModelProfile(
        slug="gpt-5.6-terra",
        display_name="GPT-5.6 Terra",
        reasoning_efforts=("low", "medium", "high", "xhigh", "max", "ultra"),
        default_reasoning_effort="medium",
        responses_lite=True,
    ),
    "gpt-5.6-luna": ModelProfile(
        slug="gpt-5.6-luna",
        display_name="GPT-5.6 Luna",
        reasoning_efforts=("low", "medium", "high", "xhigh", "max"),
        default_reasoning_effort="medium",
        responses_lite=True,
    ),
    "gpt-5.5": ModelProfile(
        slug="gpt-5.5",
        display_name="GPT-5.5",
        reasoning_efforts=("low", "medium", "high", "xhigh"),
        default_reasoning_effort="medium",
        responses_lite=False,
    ),
}

MODEL_ALIASES: Final = {
    "gpt-5.6": "gpt-5.6-sol",
}

REASONING_EFFORT_LABELS: Final = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "xhigh": "Extra high",
    "max": "Max",
    "ultra": "Ultra",
}

REASONING_EFFORT_DESCRIPTIONS: Final = {
    "low": "Fast responses with lighter reasoning",
    "medium": "Balanced speed and reasoning depth",
    "high": "Greater reasoning depth for complex tasks",
    "xhigh": "Extra-high reasoning depth for difficult tasks",
    "max": "Maximum model reasoning depth",
    "ultra": (
        "Maximum model reasoning; automatic Codex delegation is unavailable "
        "in Home Assistant"
    ),
}

REASONING_EFFORT_ALIASES: Final = {
    "light": "low",
    "extra high": "xhigh",
    "extra-high": "xhigh",
    "extra_high": "xhigh",
    "maximum": "max",
}

SUPPORTED_MODELS: Final = tuple(MODEL_PROFILES)
RESPONSES_LITE_MODELS: Final = frozenset(
    slug for slug, profile in MODEL_PROFILES.items() if profile.responses_lite
)
ALL_REASONING_EFFORTS: Final = tuple(
    dict.fromkeys(
        effort
        for profile in MODEL_PROFILES.values()
        for effort in profile.reasoning_efforts
    )
)


def normalize_model(value: object) -> str:
    """Return a canonical supported model slug."""
    if not isinstance(value, str) or not value.strip():
        return DEFAULT_MODEL
    model = value.strip().lower()
    return MODEL_ALIASES.get(model, model)


def get_model_profile(value: object) -> ModelProfile:
    """Return the profile for a supported model."""
    model = normalize_model(value)
    try:
        return MODEL_PROFILES[model]
    except KeyError as err:
        raise ValueError(
            f"Unsupported model {model!r}. Available models: "
            f"{', '.join(SUPPORTED_MODELS)}"
        ) from err


def reasoning_efforts_for_model(model: object) -> tuple[str, ...]:
    """Return the selectable thinking levels for a model."""
    return get_model_profile(model).reasoning_efforts


def default_reasoning_effort(model: object) -> str:
    """Return the catalog default thinking level for a model."""
    return get_model_profile(model).default_reasoning_effort


def normalize_reasoning_effort(model: object, value: object) -> str:
    """Return a valid thinking level for a model, falling back to its default."""
    profile = get_model_profile(model)
    if isinstance(value, str):
        effort = value.strip().lower()
        effort = REASONING_EFFORT_ALIASES.get(effort, effort)
        if effort in profile.reasoning_efforts:
            return effort
    return profile.default_reasoning_effort


def validate_reasoning_effort(model: object, value: object) -> str:
    """Return a valid thinking level or raise ValueError."""
    profile = get_model_profile(model)
    if not isinstance(value, str):
        raise ValueError("Thinking level must be a string")
    effort = REASONING_EFFORT_ALIASES.get(value.strip().lower(), value.strip().lower())
    if effort not in profile.reasoning_efforts:
        raise ValueError(
            f"Thinking level {effort!r} is not available for {profile.slug}. "
            f"Available levels: {', '.join(profile.reasoning_efforts)}"
        )
    return effort


def reasoning_effort_for_request(model: object, value: object) -> str:
    """Return the value sent in Responses reasoning.effort."""
    effort = normalize_reasoning_effort(model, value)
    # Codex implements Ultra as Max model reasoning plus client-side task
    # delegation. Home Assistant does not provide Codex's subagent runtime.
    return "max" if effort == "ultra" else effort


# Backward-compatible aliases retained for downstream forks and older tests.
GPT_56_MODELS: Final = tuple(
    slug for slug in SUPPORTED_MODELS if slug.startswith("gpt-5.6-")
)
MODEL_REASONING_EFFORTS: Final = {
    slug: profile.reasoning_efforts for slug, profile in MODEL_PROFILES.items()
}
MODEL_DEFAULT_REASONING_EFFORT: Final = {
    slug: profile.default_reasoning_effort
    for slug, profile in MODEL_PROFILES.items()
}
MODEL_REASONING_EFFORT = MODEL_DEFAULT_REASONING_EFFORT
GENERIC_REASONING_EFFORTS: Final = ("low", "medium", "high", "xhigh")
