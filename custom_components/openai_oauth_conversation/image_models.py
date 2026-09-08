"""Image-tool models, kept separate from conversation/reasoning models."""

from __future__ import annotations

from typing import Final

IMAGE_MODELS: Final[dict[str, str]] = {
    "gpt-image-2": "GPT Image 2",
    "gpt-image-2.5-flare": "GPT Image 2.5 Flare",
    "gpt-image-2.5-sunburst": "GPT Image 2.5 Sunburst",
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
