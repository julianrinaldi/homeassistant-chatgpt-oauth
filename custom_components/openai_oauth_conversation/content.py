"""Multimodal content and attachment helpers for ChatGPT OAuth."""
from __future__ import annotations

import base64
import mimetypes
from functools import partial
from pathlib import Path
from typing import Any

import aiohttp
from yarl import URL

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    MAX_ATTACHMENT_BYTES,
    MAX_ATTACHMENTS_TOTAL_BYTES,
    MAX_IMAGE_ATTACHMENTS,
    MAX_REDIRECTS,
    MAX_REMOTE_IMAGE_BYTES,
)
from .exceptions import (
    BackendUnavailableError,
    RequestTimeoutError,
    RequestValidationError,
)


def text_part(text: str) -> dict[str, str]:
    """Build an input-text content part."""
    return {"type": "input_text", "text": text}


def image_url_part(url: str) -> dict[str, str]:
    """Build an input-image content part."""
    return {"type": "input_image", "image_url": url}


def image_bytes_part(
    data: bytes,
    mime_type: str | None = None,
) -> dict[str, str]:
    """Build a bounded inline base64 input-image content part."""
    if not data:
        raise RequestValidationError("The supplied image is empty")
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise RequestValidationError("The supplied image must be 50 MB or smaller")

    detected = detect_image_mime_type(data)
    if detected is None:
        raise RequestValidationError(
            "The supplied attachment does not contain a supported image"
        )
    declared = normalize_mime_type(mime_type)
    if declared is not None and declared != detected:
        raise RequestValidationError(
            f"The supplied image content is {detected}, not {declared}"
        )

    encoded = base64.b64encode(data).decode("ascii")
    return image_url_part(f"data:{detected};base64,{encoded}")


def file_bytes_part(
    data: bytes,
    filename: str,
    mime_type: str = "application/pdf",
) -> dict[str, str]:
    """Build a bounded inline base64 input-file content part."""
    if not data:
        raise RequestValidationError("The supplied file is empty")
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise RequestValidationError("The supplied file must be 50 MB or smaller")
    normalized = normalize_mime_type(mime_type) or "application/octet-stream"
    encoded = base64.b64encode(data).decode("ascii")
    return {
        "type": "input_file",
        "filename": sanitize_filename(filename),
        "file_data": f"data:{normalized};base64,{encoded}",
    }


def inline_content_size(part: dict[str, Any]) -> int:
    """Return the decoded byte size of an inline image or file content part."""
    value = part.get("image_url") or part.get("file_data")
    if not isinstance(value, str) or ";base64," not in value:
        return 0
    encoded = value.split(";base64,", 1)[1]
    padding = len(encoded) - len(encoded.rstrip("="))
    return max(0, (len(encoded) * 3) // 4 - padding)


def normalize_mime_type(value: str | None) -> str | None:
    """Normalize a MIME type and remove optional parameters."""
    if not isinstance(value, str):
        return None
    normalized = value.split(";", 1)[0].strip().lower()
    if normalized == "image/jpg":
        return "image/jpeg"
    return normalized or None


def detect_image_mime_type(data: bytes) -> str | None:
    """Return the MIME type of a supported image from its file signature."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if (
        len(data) >= 12
        and data.startswith(b"RIFF")
        and data[8:12] == b"WEBP"
    ):
        return "image/webp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    return None


def _is_pdf(data: bytes) -> bool:
    """Return whether bytes begin with a PDF file signature."""
    return data.startswith(b"%PDF-")


def sanitize_filename(value: object) -> str:
    """Return a safe filename for backend metadata and user-facing errors."""
    name = Path(str(value or "attachment")).name.strip()
    if not name:
        return "attachment"
    return "".join(ch for ch in name if ch.isprintable())[:160] or "attachment"


def _attachment_path(attachment: Any) -> Path:
    path_value = getattr(attachment, "path", None)
    if not path_value:
        raise RequestValidationError(
            "An AI Task attachment did not include a file path"
        )
    return Path(path_value)


def _attachment_mime_type(attachment: Any, path: Path) -> str | None:
    return normalize_mime_type(
        getattr(attachment, "mime_type", None)
        or mimetypes.guess_type(str(path))[0]
    )


def _read_file_bytes(path: Path, *, label: str) -> bytes:
    if not path.is_file():
        raise RequestValidationError(
            f"{label} attachment does not exist: {sanitize_filename(path)}"
        )
    try:
        data = path.read_bytes()
    except OSError as err:
        raise RequestValidationError(
            f"Could not read {label.lower()} attachment "
            f"{sanitize_filename(path)}: {err}"
        ) from err
    if not data:
        raise RequestValidationError(
            f"{label} attachment is empty: {sanitize_filename(path)}"
        )
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise RequestValidationError(
            f"{label} attachment must be 50 MB or smaller: {sanitize_filename(path)}"
        )
    return data


def read_data_attachments(attachments: list[Any]) -> list[dict[str, Any]]:
    """Read image and PDF attachments for ``ai_task.generate_data``."""
    content: list[dict[str, Any]] = []
    total_bytes = 0
    for attachment in attachments:
        path = _attachment_path(attachment)
        data = _read_file_bytes(path, label="AI Task")
        total_bytes += len(data)
        if total_bytes > MAX_ATTACHMENTS_TOTAL_BYTES:
            raise RequestValidationError(
                "AI Task attachments must total 50 MB or less"
            )

        mime_type = _attachment_mime_type(attachment, path)
        detected_image = detect_image_mime_type(data)
        if detected_image is not None:
            declared_image = (
                mime_type if mime_type and mime_type.startswith("image/") else None
            )
            content.append(image_bytes_part(data, declared_image))
        elif _is_pdf(data):
            if mime_type not in {None, "application/pdf", "application/octet-stream"}:
                raise RequestValidationError(
                    "The PDF attachment content does not match its MIME type: "
                    f"{sanitize_filename(path)}"
                )
            content.append(file_bytes_part(data, path.name, "application/pdf"))
        else:
            raise RequestValidationError(
                "Data generation supports only valid image and PDF attachments; "
                f"unsupported attachment: {sanitize_filename(path)}"
            )
    return content


def read_image_attachments(attachments: list[Any]) -> list[dict[str, Any]]:
    """Read up to ten image attachments for generation or editing."""
    if len(attachments) > MAX_IMAGE_ATTACHMENTS:
        raise RequestValidationError(
            f"Image generation supports at most {MAX_IMAGE_ATTACHMENTS} attachments"
        )

    content: list[dict[str, Any]] = []
    total_bytes = 0
    for attachment in attachments:
        path = _attachment_path(attachment)
        mime_type = _attachment_mime_type(attachment, path)
        if mime_type and not mime_type.startswith("image/"):
            raise RequestValidationError(
                "Image generation accepts only image attachments; "
                f"unsupported attachment: {sanitize_filename(path)}"
            )
        data = _read_file_bytes(path, label="Image")
        total_bytes += len(data)
        if total_bytes > MAX_ATTACHMENTS_TOTAL_BYTES:
            raise RequestValidationError(
                "Image-generation attachments must total 50 MB or less"
            )
        content.append(image_bytes_part(data, mime_type))
    return content


async def image_part_from_local_file(
    hass: HomeAssistant,
    raw_path: str,
) -> dict[str, str]:
    """Read an image from an allowed Home Assistant path."""
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path(hass.config.path(raw_path))
    try:
        path = path.resolve(strict=True)
    except OSError as err:
        raise RequestValidationError(
            f"Could not resolve image file {sanitize_filename(raw_path)}: {err}"
        ) from err

    if not hass.config.is_allowed_path(str(path)):
        raise RequestValidationError(
            "The image file is outside Home Assistant's allowed paths: "
            f"{sanitize_filename(path)}"
        )

    data = await hass.async_add_executor_job(
        partial(_read_file_bytes, path, label="Image")
    )
    mime_type = normalize_mime_type(mimetypes.guess_type(str(path))[0])
    if mime_type and not mime_type.startswith("image/"):
        raise RequestValidationError(
            f"The local file is not a recognized image: {sanitize_filename(path)}"
        )
    return image_bytes_part(data, mime_type)


async def _read_bounded_response(
    response: aiohttp.ClientResponse,
    *,
    limit: int,
) -> bytes:
    content_length = response.content_length
    if content_length is not None and content_length > limit:
        raise RequestValidationError(
            f"Remote image is larger than the {limit // (1024 * 1024)} MB limit"
        )
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.content.iter_chunked(64 * 1024):
        size += len(chunk)
        if size > limit:
            raise RequestValidationError(
                f"Remote image is larger than the {limit // (1024 * 1024)} MB limit"
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def image_part_from_url(
    hass: HomeAssistant,
    raw_url: str,
) -> dict[str, str]:
    """Download and validate a remote image before sending it to ChatGPT."""
    try:
        url = URL(raw_url)
    except (TypeError, ValueError) as err:
        raise RequestValidationError("Image URL is invalid") from err
    if url.scheme not in {"http", "https"} or not url.host:
        raise RequestValidationError("Image URL must use HTTP or HTTPS")

    session = async_get_clientsession(hass)
    try:
        async with session.get(
            url,
            allow_redirects=True,
            max_redirects=MAX_REDIRECTS,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            if response.status >= 400:
                raise RequestValidationError(
                    f"Could not download image URL (HTTP {response.status})"
                )
            mime_type = normalize_mime_type(response.headers.get("Content-Type"))
            if not mime_type or not mime_type.startswith("image/"):
                raise RequestValidationError(
                    "Image URL did not return an image content type"
                )
            data = await _read_bounded_response(
                response,
                limit=MAX_REMOTE_IMAGE_BYTES,
            )
    except TimeoutError as err:
        raise RequestTimeoutError("Downloading the image URL timed out") from err
    except aiohttp.TooManyRedirects as err:
        raise RequestValidationError("Image URL redirected too many times") from err
    except aiohttp.ClientError as err:
        raise BackendUnavailableError(
            f"Could not download the image URL: {err}"
        ) from err

    if not data:
        raise RequestValidationError("Image URL returned an empty file")
    return image_bytes_part(data, mime_type)


async def image_part_from_entity(
    hass: HomeAssistant,
    entity_id: str,
) -> dict[str, str]:
    """Read a snapshot from a camera or image entity."""
    domain = entity_id.split(".", 1)[0]
    if domain == "camera":
        from homeassistant.components.camera import async_get_image

        try:
            image = await async_get_image(hass, entity_id, timeout=15)
        except Exception as err:
            raise RequestValidationError(
                f"Could not get an image from {entity_id}: {err}"
            ) from err
        return image_bytes_part(
            image.content,
            normalize_mime_type(image.content_type),
        )

    if domain == "image":
        from homeassistant.components.image import async_get_image

        try:
            image = await async_get_image(hass, entity_id, timeout=15)
        except Exception as err:
            raise RequestValidationError(
                f"Could not get an image from {entity_id}: {err}"
            ) from err
        return image_bytes_part(
            image.content,
            normalize_mime_type(image.content_type),
        )

    raise RequestValidationError(
        f"Unsupported image entity {entity_id}; select a camera or image entity"
    )
