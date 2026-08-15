"""Tests for multimodal attachment handling."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.openai_oauth_conversation import content as content_module
from custom_components.openai_oauth_conversation.content import (
    read_data_attachments,
    read_image_attachments,
)
from custom_components.openai_oauth_conversation.exceptions import (
    RequestValidationError,
)


def _attachment(path, mime_type: str):
    return SimpleNamespace(path=path, mime_type=mime_type)


def test_exactly_ten_image_attachments_are_accepted(tmp_path) -> None:
    """Image generation accepts the documented ten-image boundary."""
    attachments = []
    for index in range(10):
        path = tmp_path / f"image-{index}.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\nsource")
        attachments.append(_attachment(path, "image/png"))

    content = read_image_attachments(attachments)
    assert len(content) == 10
    assert all(part["type"] == "input_image" for part in content)
    assert all(
        part["image_url"].startswith("data:image/png;base64,") for part in content
    )


def test_eleven_image_attachments_are_rejected(tmp_path) -> None:
    """The public maximum is enforced before reading the files."""
    attachments = [
        _attachment(tmp_path / f"missing-{index}.png", "image/png")
        for index in range(11)
    ]
    with pytest.raises(RequestValidationError, match="at most 10"):
        read_image_attachments(attachments)


def test_image_generation_rejects_non_image_attachment(tmp_path) -> None:
    """PDFs are valid for data tasks but never for image generation."""
    path = tmp_path / "document.pdf"
    path.write_bytes(b"%PDF-1.7\n")
    with pytest.raises(RequestValidationError, match="only image"):
        read_image_attachments([_attachment(path, "application/pdf")])


def test_data_generation_accepts_images_and_pdfs(tmp_path) -> None:
    """Data generation retains multimodal image and PDF support."""
    image = tmp_path / "photo.jpg"
    image.write_bytes(b"\xff\xd8\xff\xe0image")
    document = tmp_path / "report.pdf"
    document.write_bytes(b"%PDF-1.7\nreport")

    content = read_data_attachments(
        [
            _attachment(image, "image/jpeg; charset=binary"),
            _attachment(document, "application/pdf"),
        ]
    )
    assert [part["type"] for part in content] == ["input_image", "input_file"]
    assert content[1]["filename"] == "report.pdf"


def test_combined_attachment_limit_is_enforced(tmp_path, monkeypatch) -> None:
    """Combined raw attachment bytes are bounded independently of base64 growth."""
    monkeypatch.setattr(content_module, "MAX_ATTACHMENTS_TOTAL_BYTES", 10)
    first = tmp_path / "one.png"
    second = tmp_path / "two.png"
    first.write_bytes(b"\x89PNG\r\n\x1a\n1")
    second.write_bytes(b"\x89PNG\r\n\x1a\n2")

    with pytest.raises(RequestValidationError, match="total"):
        read_image_attachments(
            [
                _attachment(first, "image/png"),
                _attachment(second, "image/png"),
            ]
        )


def test_image_signature_must_match_declared_mime_type(tmp_path) -> None:
    """File content, rather than only an extension or MIME label, is verified."""
    path = tmp_path / "not-really-jpeg.jpg"
    path.write_bytes(b"\x89PNG\r\n\x1a\npayload")

    with pytest.raises(RequestValidationError, match="not image/jpeg"):
        read_image_attachments([_attachment(path, "image/jpeg")])


def test_data_generation_rejects_fake_pdf(tmp_path) -> None:
    """A PDF MIME label cannot be used to send arbitrary bytes."""
    path = tmp_path / "fake.pdf"
    path.write_bytes(b"not a pdf")

    with pytest.raises(RequestValidationError, match="valid image and PDF"):
        read_data_attachments([_attachment(path, "application/pdf")])
