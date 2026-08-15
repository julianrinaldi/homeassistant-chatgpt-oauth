"""Typed exceptions for ChatGPT OAuth."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

_TOKEN_PATTERN = re.compile(
    r"(?i)(bearer\s+|access[_ -]?token[\"'=:\s]+|refresh[_ -]?token[\"'=:\s]+)"
    r"[A-Za-z0-9._~+/=-]{16,}"
)


def sanitize_backend_message(value: object, *, limit: int = 500) -> str:
    """Return a concise backend message with obvious credentials redacted."""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                decoded = json.loads(stripped)
            except json.JSONDecodeError:
                pass
            else:
                return sanitize_backend_message(decoded, limit=limit)
    if isinstance(value, dict):
        for key in ("detail", "message", "error_description"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                value = candidate
                break
        else:
            error = value.get("error")
            if isinstance(error, dict):
                return sanitize_backend_message(error, limit=limit)
            value = json.dumps(value, default=str)
    text = str(value or "Unknown backend error").replace("\x00", " ").strip()
    text = _TOKEN_PATTERN.sub(lambda match: f"{match.group(1)}[redacted]", text)
    return text[:limit]


@dataclass(slots=True)
class ChatGPTOAuthError(Exception):
    """Base exception for the hosted ChatGPT OAuth backend."""

    message: str
    status_code: int | None = None
    request_id: str | None = None

    def __str__(self) -> str:
        suffix = f" (request ID: {self.request_id})" if self.request_id else ""
        return f"{self.message}{suffix}"


class AuthenticationError(ChatGPTOAuthError):
    """OAuth credentials are missing, expired, or rejected."""


class RateLimitError(ChatGPTOAuthError):
    """The signed-in ChatGPT account has reached a service limit."""


class BackendUnavailableError(ChatGPTOAuthError):
    """The hosted service is temporarily unavailable."""


class RequestTimeoutError(ChatGPTOAuthError):
    """The hosted service did not finish within the allowed time."""


class RequestValidationError(ChatGPTOAuthError):
    """The request is invalid or unsupported by the selected model."""


class ResponseParseError(ChatGPTOAuthError):
    """The hosted service returned an incomplete or malformed response."""


class StructuredOutputError(ChatGPTOAuthError):
    """Structured output could not be produced or validated."""


def exception_from_http_response(
    status: int,
    body: object,
    *,
    request_id: str | None = None,
    operation: str = "request",
) -> ChatGPTOAuthError:
    """Classify an HTTP failure into a stable integration exception."""
    detail = sanitize_backend_message(body)
    message = f"ChatGPT OAuth {operation} failed ({status}): {detail}"
    kwargs: dict[str, Any] = {
        "message": message,
        "status_code": status,
        "request_id": request_id,
    }
    if status in {401, 403}:
        return AuthenticationError(**kwargs)
    if status == 429:
        return RateLimitError(**kwargs)
    if status in {408, 425, 502, 503, 504} or status >= 500:
        return BackendUnavailableError(**kwargs)
    if 400 <= status < 500:
        return RequestValidationError(**kwargs)
    return ChatGPTOAuthError(**kwargs)
