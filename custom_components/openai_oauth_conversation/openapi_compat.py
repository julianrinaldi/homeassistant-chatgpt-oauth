"""OpenAPI conversion compatibility for Home Assistant LLM tools."""

from __future__ import annotations

from collections.abc import Callable
import importlib
import json
from typing import Any

from homeassistant.helpers import llm

from .exceptions import RequestValidationError


def _resolve_converter() -> Callable[..., dict[str, Any]]:
    """Return the OpenAPI converter exported by the running Core."""
    converter = getattr(llm, "to_openapi", None) or getattr(llm, "convert", None)
    if not callable(converter):
        raise RequestValidationError(
            "Home Assistant does not expose a compatible OpenAPI schema converter"
        )
    return converter


def _known_unsupported_sentinels(
    active_unsupported: Any,
) -> tuple[Any, ...]:
    """Return every importable converter's unsupported sentinel."""
    sentinels = [active_unsupported]
    for module_name in ("voluptuous_openapi", "probatio"):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        sentinel = getattr(module, "UNSUPPORTED", None)
        if sentinel is not None and all(sentinel is not known for known in sentinels):
            sentinels.append(sentinel)
    return tuple(sentinels)


def _normalize_custom_serializer(
    custom_serializer: Callable[[Any], Any] | None,
) -> Callable[[Any], Any] | None:
    """Translate foreign unsupported sentinels to Core's sentinel."""
    if custom_serializer is None:
        return None

    active_unsupported = getattr(llm, "UNSUPPORTED", None)
    if active_unsupported is None:
        return custom_serializer
    unsupported_sentinels = _known_unsupported_sentinels(active_unsupported)

    def _serialize(value: Any) -> Any:
        result = custom_serializer(value)
        if any(result is sentinel for sentinel in unsupported_sentinels):
            return active_unsupported
        return result

    return _serialize


def convert_tool_parameters(
    parameters: Any,
    custom_serializer: Callable[[Any], Any] | None,
    *,
    tool_name: str,
) -> dict[str, Any]:
    """Convert and verify one Home Assistant tool parameter schema."""
    converter = _resolve_converter()
    try:
        converted = converter(
            parameters,
            custom_serializer=_normalize_custom_serializer(custom_serializer),
        )
        if not isinstance(converted, dict):
            raise TypeError(
                "the Home Assistant converter did not return an object schema"
            )
        json.dumps(
            converted,
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as err:
        raise RequestValidationError(
            f"Could not convert Home Assistant tool schema for {tool_name}: {err}"
        ) from err
    return converted
