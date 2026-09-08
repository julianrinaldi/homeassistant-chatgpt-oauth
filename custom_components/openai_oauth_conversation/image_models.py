"""Image-tool models, kept separate from conversation/reasoning models."""

from __future__ import annotations

from typing import Final

IMAGE_MODELS: Final[dict[str, str]] = {
    "gpt-image-2": "GPT Image 2",
    "gpt-image-2.5": "GPT Image 2.5",
}
SUPPORTED_IMAGE_MODELS: Final = tuple(IMAGE_MODELS)


def validate_image_model(value: object) -> str:
    """Return an explicit image-tool model, never a text model or fallback."""
    if not isinstance(value, str):
        raise ValueError("Image generation model must be a string")
    model = value.strip().lower()
    if model not in IMAGE_MODELS:
        raise ValueError(
            f"Unsupported image generation model {model!r}. Available models: "
            f"{', '.join(SUPPORTED_IMAGE_MODELS)}"
        )
    return model


# These two API-only choices were briefly offered by v1.10.0. Only persisted
# account settings are upgraded; explicit request overrides remain strict.
LEGACY_API_IMAGE_MODELS: Final = frozenset(
    {"gpt-image-2.5-flare", "gpt-image-2.5-sunburst"}
)


def migrate_legacy_image_model(value: object) -> object:
    """Upgrade the v1.10.0 account choices to the unified OAuth identifier."""
    if isinstance(value, str) and value.strip().lower() in LEGACY_API_IMAGE_MODELS:
        return "gpt-image-2.5"
    return value
