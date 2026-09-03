"""Tests for Home Assistant OpenAPI converter compatibility."""

from __future__ import annotations

import json
from types import SimpleNamespace

from homeassistant.helpers import llm
import pytest

from custom_components.openai_oauth_conversation import openapi_compat
from custom_components.openai_oauth_conversation.exceptions import (
    RequestValidationError,
)


def test_uses_core_converter_and_normalizes_foreign_sentinel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A probatio-style converter receives probatio's sentinel."""
    active_unsupported = object()
    foreign_unsupported = object()
    parameter_schema = object()
    converter_used = False

    def active_converter(value, *, custom_serializer=None):
        nonlocal converter_used
        converter_used = True
        assert value is parameter_schema
        assert custom_serializer is not None
        assert custom_serializer(object()) is active_unsupported
        return {"type": "object", "properties": {}}

    def stale_converter(*_args, **_kwargs):
        raise AssertionError("The stale converter must not be used")

    real_import_module = openapi_compat.importlib.import_module

    def fake_import_module(name: str):
        if name == "voluptuous_openapi":
            return SimpleNamespace(UNSUPPORTED=foreign_unsupported)
        if name == "probatio":
            return SimpleNamespace(UNSUPPORTED=active_unsupported)
        return real_import_module(name)

    monkeypatch.setattr(
        llm,
        "to_openapi",
        active_converter,
        raising=False,
    )
    monkeypatch.setattr(
        llm,
        "convert",
        stale_converter,
        raising=False,
    )
    monkeypatch.setattr(
        llm,
        "UNSUPPORTED",
        active_unsupported,
        raising=False,
    )
    monkeypatch.setattr(
        openapi_compat.importlib,
        "import_module",
        fake_import_module,
    )

    converted = openapi_compat.convert_tool_parameters(
        parameter_schema,
        lambda _value: foreign_unsupported,
        tool_name="TestTool",
    )

    assert converter_used is True
    assert converted == {"type": "object", "properties": {}}
    json.dumps(converted)


def test_uses_legacy_core_converter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pre-2026.9 Core continues to use llm.convert."""
    parameter_schema = object()

    def legacy_converter(value, *, custom_serializer=None):
        assert value is parameter_schema
        assert custom_serializer is None
        return {"type": "object", "properties": {}}

    monkeypatch.setattr(llm, "to_openapi", None, raising=False)
    monkeypatch.setattr(
        llm,
        "convert",
        legacy_converter,
        raising=False,
    )
    monkeypatch.setattr(
        llm,
        "UNSUPPORTED",
        object(),
        raising=False,
    )

    converted = openapi_compat.convert_tool_parameters(
        parameter_schema,
        None,
        tool_name="LegacyTool",
    )

    assert converted["type"] == "object"
    json.dumps(converted)


def test_rejects_non_json_converter_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A remaining sentinel fails before the request is sent."""
    unsupported = object()

    def broken_converter(_value, *, custom_serializer=None):
        del custom_serializer
        return {"properties": {"bad": unsupported}}

    monkeypatch.setattr(
        llm,
        "to_openapi",
        broken_converter,
        raising=False,
    )
    monkeypatch.setattr(
        llm,
        "UNSUPPORTED",
        unsupported,
        raising=False,
    )

    with pytest.raises(
        RequestValidationError,
        match="Could not convert Home Assistant tool schema",
    ):
        openapi_compat.convert_tool_parameters(
            object(),
            None,
            tool_name="BrokenTool",
        )
