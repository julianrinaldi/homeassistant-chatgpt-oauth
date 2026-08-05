"""Tests for safe backend error messages."""
from __future__ import annotations

from custom_components.openai_oauth_conversation.exceptions import (
    sanitize_backend_message,
)


def test_json_error_body_is_unwrapped_and_redacted() -> None:
    """JSON error bodies expose only the useful message and redact credentials."""
    message = sanitize_backend_message(
        '{"detail":"Unsupported request; bearer abcdefghijklmnopqrstuvwxyz123456"}'
    )
    assert message == "Unsupported request; bearer [redacted]"
    assert "detail" not in message
