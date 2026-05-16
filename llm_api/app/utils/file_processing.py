"""Helpers for processing uploaded files (PDF text extraction, image encoding)."""

import base64
import io
import logging
from typing import Literal

from PIL import Image
from pypdf import PdfReader

logger = logging.getLogger(__name__)

ImageFormat = Literal["jpeg", "png", "webp", "gif"]
_ALLOWED_IMAGE_MIMES = {
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


def extract_pdf_text(pdf_bytes: bytes, max_chars: int = 30_000) -> str:
    """Extract plain text from a PDF byte string.

    Truncates at max_chars to keep prompts bounded.
    """
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception as e:
        logger.exception("Failed to parse PDF")
        raise ValueError(f"Could not parse PDF: {e}") from e

    parts: list[str] = []
    total = 0
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            logger.warning("Failed to extract text from page %d", i)
            continue
        if not text.strip():
            continue
        parts.append(f"[Page {i + 1}]\n{text}")
        total += len(text)
        if total >= max_chars:
            parts.append(f"\n...[truncated after page {i + 1}]...")
            break

    result = "\n\n".join(parts).strip()
    if not result:
        return "(No extractable text found in PDF.)"
    return result[:max_chars]


def encode_image_to_data_url(
    image_bytes: bytes,
    content_type: str,
    max_dimension: int = 1536,
) -> str:
    """Encode image bytes into a data URL for an OpenAI-style vision request.

    Downscales overly large images to keep request size reasonable.
    """
    img_format = _ALLOWED_IMAGE_MIMES.get(content_type.lower())
    if img_format is None:
        raise ValueError(
            f"Unsupported image type '{content_type}'. "
            f"Supported: {list(_ALLOWED_IMAGE_MIMES.keys())}"
        )

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    except Exception as e:
        raise ValueError(f"Could not open image: {e}") from e

    # Downscale if needed.
    if max(img.size) > max_dimension:
        img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        # Convert to RGB for JPEG if it has an alpha channel
        if img_format == "jpeg" and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(buf, format=img_format.upper())
        image_bytes = buf.getvalue()

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/{img_format};base64,{b64}"


def encode_file_to_data_url(file_bytes: bytes, content_type: str) -> str:
    """Encode arbitrary file bytes (audio, etc.) into a data URL.

    Does no transformation; caller should ensure size limits are respected.
    """
    if not content_type:
        raise ValueError("Content type required to encode file to data URL")
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{content_type};base64,{b64}"
