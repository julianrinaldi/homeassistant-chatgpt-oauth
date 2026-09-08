"""Regression tests for AI Task schemas and clean Core installations."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from homeassistant.helpers import llm, selector
import pytest
import voluptuous as vol

from custom_components.openai_oauth_conversation import openapi_compat
from custom_components.openai_oauth_conversation.client import (
    _format_tool,
    build_turn_payload,
    serialize_request_payload,
)
from custom_components.openai_oauth_conversation.exceptions import StructuredOutputError
from custom_components.openai_oauth_conversation.schema import (
    format_structured_output,
    parse_and_validate_structured_text,
    structured_output_format,
)

PACKAGE = "custom_components.openai_oauth_conversation"
ROOT = Path(__file__).resolve().parents[1]


def test_no_direct_legacy_converter_imports() -> None:
    """No runtime module may require the converter removed from modern Core."""
    for path in (ROOT / "custom_components" / "openai_oauth_conversation").rglob(
        "*.py"
    ):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] != "voluptuous_openapi", path
            elif isinstance(node, ast.Import):
                assert all(
                    item.name.split(".")[0] != "voluptuous_openapi"
                    for item in node.names
                ), path


def test_runtime_imports_in_fresh_process() -> None:
    """Import the entire integration without pytest's already imported modules."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import importlib, pathlib; "
            f"package = {PACKAGE!r}; "
            "importlib.import_module(package); "
            "[importlib.import_module(package + '.' + path.stem) "
            "for path in pathlib.Path(package.replace('.', '/')).glob('*.py') "
            "if path.stem != '__init__']",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_modern_core_does_not_need_legacy_package() -> None:
    """The modern CI environment deliberately removes the legacy dependency."""
    if not hasattr(llm, "to_openapi"):
        pytest.skip("Older Core itself requires voluptuous-openapi")
    assert importlib.util.find_spec("voluptuous_openapi") is None


@pytest.mark.parametrize("with_api", [False, True])
def test_real_core_structured_output_conversion(with_api: bool) -> None:
    """Exercise real Core selectors, not a mocked schema converter."""
    structure = vol.Schema(
        {
            vol.Required("summary"): selector.TextSelector(),
            vol.Optional("count"): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=10, mode="box")
            ),
        }
    )
    api = (
        SimpleNamespace(custom_serializer=llm.selector_serializer) if with_api else None
    )
    converted = format_structured_output(structure, api)
    assert converted["type"] == "object"
    assert converted["additionalProperties"] is False
    assert set(converted["required"]) == {"summary", "count"}
    assert converted["properties"]["summary"]["type"] == "string"
    assert "null" in converted["properties"]["count"]["type"]
    json.dumps(converted, allow_nan=False)


@pytest.mark.parametrize(
    "model", ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5"]
)
def test_tool_and_structured_task_payloads_are_serializable(model: str) -> None:
    """Both request paths use the same real Core schema conversion."""
    structure = vol.Schema({vol.Required("answer"): selector.TextSelector()})
    tool = SimpleNamespace(
        name="TestTool", description="Test tool", parameters=structure
    )
    formatted_tool = _format_tool(tool, llm.selector_serializer)
    output_format = structured_output_format("Test data", structure, None)
    payload, _ = build_turn_payload(
        model=model,
        instructions="Answer the request.",
        input_items=[{"role": "user", "content": "Hello"}],
        tools=[formatted_tool],
        text_format=output_format,
    )
    assert json.loads(serialize_request_payload(payload)) == payload


def test_structured_output_normalizes_foreign_sentinel(monkeypatch) -> None:
    """The data path gets the same sentinel protection as Assist tools."""
    active = object()
    foreign = object()

    def converter(_schema, *, custom_serializer=None):
        assert custom_serializer(object()) is active
        return {"type": "object", "properties": {"answer": {"type": "string"}}}

    monkeypatch.setattr(llm, "to_openapi", converter, raising=False)
    monkeypatch.setattr(llm, "UNSUPPORTED", active, raising=False)
    monkeypatch.setattr(
        openapi_compat,
        "_known_unsupported_sentinels",
        lambda _active: (active, foreign),
    )
    api = SimpleNamespace(custom_serializer=lambda _value: foreign)
    assert format_structured_output(vol.Schema({}), api)["type"] == "object"


def test_structured_output_rejects_non_json_schema(monkeypatch) -> None:
    """Invalid converter output cannot reach request serialization."""
    monkeypatch.setattr(
        llm,
        "to_openapi",
        lambda *_args, **_kwargs: {"properties": {"bad": object()}},
        raising=False,
    )
    with pytest.raises(StructuredOutputError, match="Could not convert"):
        format_structured_output(vol.Schema({}), None)


def test_optional_null_response_still_validates() -> None:
    """Keep strict-output optional-null handling unchanged."""
    structure = vol.Schema({vol.Required("answer"): str, vol.Optional("count"): int})
    result = parse_and_validate_structured_text(
        '{"answer":"Done","count":null}', structure
    )
    assert result == {"answer": "Done"}
