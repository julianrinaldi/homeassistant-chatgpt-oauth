"""Structured-output conversion and validation for ChatGPT OAuth."""

from __future__ import annotations

import json
from typing import Any

from homeassistant.helpers import llm
from homeassistant.util import slugify
import voluptuous as vol
from voluptuous_openapi import convert

from .exceptions import ChatGPTOAuthError, StructuredOutputError

_SCHEMA_ANNOTATION_KEYS = {
    "$schema",
    "default",
    "deprecated",
    "example",
    "examples",
    "externalDocs",
    "readOnly",
    "writeOnly",
    "xml",
}


def _schema_allows_null(schema: dict[str, Any]) -> bool:
    schema_type = schema.get("type")
    if schema_type == "null":
        return True
    if isinstance(schema_type, list) and "null" in schema_type:
        return True
    if schema.get("nullable") is True:
        return True
    enum = schema.get("enum")
    if isinstance(enum, list) and None in enum:
        return True
    for keyword in ("anyOf", "oneOf"):
        choices = schema.get(keyword)
        if isinstance(choices, list) and any(
            isinstance(choice, dict) and _schema_allows_null(choice)
            for choice in choices
        ):
            return True
    return False


def _make_schema_nullable(schema: dict[str, Any]) -> None:
    if _schema_allows_null(schema):
        schema.pop("nullable", None)
        return

    schema_type = schema.get("type")
    if isinstance(schema_type, str):
        schema["type"] = [schema_type, "null"]
    elif isinstance(schema_type, list):
        schema["type"] = [*schema_type, "null"]
    elif isinstance(schema.get("anyOf"), list):
        schema["anyOf"].append({"type": "null"})
    else:
        original = dict(schema)
        schema.clear()
        schema["anyOf"] = [original, {"type": "null"}]

    enum = schema.get("enum")
    if isinstance(enum, list) and None not in enum:
        enum.append(None)
    schema.pop("nullable", None)


def _adjust_structured_output_schema(schema: dict[str, Any]) -> None:
    """Make a converted Home Assistant schema strict-output compatible."""
    for key in _SCHEMA_ANNOTATION_KEYS:
        schema.pop(key, None)

    if schema.pop("nullable", False):
        _make_schema_nullable(schema)

    if "oneOf" in schema and "anyOf" not in schema:
        schema["anyOf"] = schema.pop("oneOf")

    for keyword in ("anyOf", "allOf"):
        choices = schema.get(keyword)
        if isinstance(choices, list):
            for choice in choices:
                if isinstance(choice, dict):
                    _adjust_structured_output_schema(choice)

    for definitions_key in ("$defs", "definitions"):
        definitions = schema.get(definitions_key)
        if isinstance(definitions, dict):
            for definition in definitions.values():
                if isinstance(definition, dict):
                    _adjust_structured_output_schema(definition)

    schema_type = schema.get("type")
    type_names = (
        set(schema_type)
        if isinstance(schema_type, list)
        else {schema_type}
        if isinstance(schema_type, str)
        else set()
    )

    properties = schema.get("properties")
    if "object" in type_names or isinstance(properties, dict):
        schema.setdefault("type", "object")
        schema["additionalProperties"] = False
        if isinstance(properties, dict):
            required_names = schema.get("required")
            originally_required = (
                set(required_names) if isinstance(required_names, list) else set()
            )
            for property_name, property_schema in properties.items():
                if not isinstance(property_schema, dict):
                    continue
                _adjust_structured_output_schema(property_schema)
                if property_name not in originally_required:
                    _make_schema_nullable(property_schema)
            schema["required"] = list(properties)

    items = schema.get("items")
    if ("array" in type_names or items is not None) and isinstance(items, dict):
        _adjust_structured_output_schema(items)


def format_structured_output(
    structure: vol.Schema,
    llm_api: llm.APIInstance | None,
) -> dict[str, Any]:
    """Convert and normalize a Home Assistant output structure."""
    try:
        converted = convert(
            structure,
            custom_serializer=(
                llm_api.custom_serializer if llm_api else llm.selector_serializer
            ),
        )
    except Exception as err:  # Selector conversion is supplied by Home Assistant.
        raise StructuredOutputError(
            f"Could not convert the Home Assistant data structure: {err}"
        ) from err

    if not isinstance(converted, dict):
        raise StructuredOutputError(
            "Home Assistant data structure did not convert to a JSON schema"
        )
    _adjust_structured_output_schema(converted)
    return converted


def structured_output_format(
    structure_name: str,
    structure: vol.Schema,
    llm_api: llm.APIInstance | None,
) -> dict[str, Any]:
    """Build a Responses strict JSON-schema text format."""
    name = slugify(structure_name)[:64] or "ai_task_result"
    return {
        "type": "json_schema",
        "name": name,
        "schema": format_structured_output(structure, llm_api),
        "strict": True,
    }


def is_structured_output_error(error: ChatGPTOAuthError) -> bool:
    """Return whether the backend rejected native structured output."""
    message = str(error).lower()
    markers = (
        "json_schema",
        "json schema",
        "structured output",
        "response_format",
        "text.format",
        "text format",
        "invalid schema",
        "unsupported parameter: text",
        "unknown parameter: text",
    )
    return any(marker in message for marker in markers)


def fallback_json_instructions(
    instructions: str,
    output_format: dict[str, Any],
) -> str:
    """Ask for schema-shaped JSON when native text.format is unavailable."""
    schema_text = json.dumps(
        output_format["schema"],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        f"{instructions}\n\n"
        "Return only one valid JSON value matching the following JSON Schema. "
        "Do not use Markdown fences, explanatory prose, or comments.\n"
        f"JSON Schema: {schema_text}"
    )


def _parse_structured_text(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline >= 0:
            stripped = stripped[first_newline + 1 :]
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3].rstrip()

    starts = [index for token in ("{", "[") if (index := stripped.find(token)) >= 0]
    if not starts:
        raise StructuredOutputError("Structured AI Task response was not valid JSON")
    start = min(starts)
    try:
        value, end = json.JSONDecoder().raw_decode(stripped[start:])
    except json.JSONDecodeError as err:
        raise StructuredOutputError(
            f"Structured AI Task response was not valid JSON: {err}"
        ) from err
    if stripped[start + end :].strip():
        raise StructuredOutputError(
            "Structured AI Task response contained text after the JSON value"
        )
    return value


def _is_optional_schema_key(key: Any) -> bool:
    optional_type = getattr(vol, "Optional", None)
    return optional_type is not None and isinstance(key, optional_type)


def _drop_optional_nulls(value: Any, schema: Any) -> tuple[Any, bool]:
    """Remove strict-output null placeholders for optional voluptuous fields."""
    schema_value = getattr(schema, "schema", schema)

    if isinstance(value, dict) and isinstance(schema_value, dict):
        cleaned = dict(value)
        changed = False
        for schema_key, child_schema in schema_value.items():
            value_key = getattr(schema_key, "schema", schema_key)
            try:
                present = value_key in cleaned
            except TypeError:
                continue
            if not present:
                continue
            if _is_optional_schema_key(schema_key) and cleaned[value_key] is None:
                del cleaned[value_key]
                changed = True
                continue

            child_value, child_changed = _drop_optional_nulls(
                cleaned[value_key], child_schema
            )
            if child_changed:
                cleaned[value_key] = child_value
                changed = True
        return (cleaned, True) if changed else (value, False)

    if (
        isinstance(value, list)
        and isinstance(schema_value, list)
        and len(schema_value) == 1
    ):
        cleaned_items: list[Any] = []
        changed = False
        for item in value:
            cleaned_item, item_changed = _drop_optional_nulls(item, schema_value[0])
            cleaned_items.append(cleaned_item)
            changed |= item_changed
        return (cleaned_items, True) if changed else (value, False)

    return value, False


def parse_and_validate_structured_text(
    text: str,
    structure: vol.Schema,
) -> Any:
    """Parse generated JSON and validate it with Home Assistant's schema."""
    value = _parse_structured_text(text)
    try:
        return structure(value)
    except vol.Invalid as first_error:
        cleaned_value, changed = _drop_optional_nulls(value, structure)
        if changed:
            try:
                return structure(cleaned_value)
            except vol.Invalid as err:
                validation_error = err
        else:
            validation_error = first_error

        raise StructuredOutputError(
            f"Generated data did not match the requested structure: {validation_error}"
        ) from validation_error
