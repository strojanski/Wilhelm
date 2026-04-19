"""FastAPI entrypoint.

Endpoints:
  GET  /health
  POST /analyze      multipart form: text, optional image, optional pdf, other fields
  POST /transcribe   multipart form: audio file, optional language
"""

from __future__ import annotations

import io
import json
import logging
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import Settings, get_settings
from app.schemas import HealthResponse, TranscribeResponse
from app.services.llm_service import LLMService, TestLLMService
from app.services.stt_service import STTService
from app.utils.file_processing import encode_image_to_data_url, extract_pdf_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gemma-api")

app = FastAPI(
    title="Gemma Multimodal Analyzer",
    description=(
        "Accepts text + optional image + optional PDF + metadata, "
        "calls an OpenAI-compatible LLM (e.g. Gemma on vLLM, or Google's "
        "Gemini/Gemma OpenAI-compatible endpoint), and returns a structured "
        "template response. Also exposes a speech-to-text endpoint."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Dependency wiring
# ---------------------------------------------------------------------------


def get_llm_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LLMService:
    return LLMService(settings)


def get_test_llm_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> TestLLMService:
    return TestLLMService(settings)


def get_stt_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> STTService:
    return STTService(settings)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get(
    "/test_llm_poem",
    summary="Test LLM poem generation",
    description=(
        "Calls the configured LLM with a small poetry prompt to verify that "
        "the OpenAI-compatible connection, model selection, and response flow "
        "are working end to end."
    ),
)
async def test_llm_poem(
    llm: Annotated[TestLLMService, Depends(get_test_llm_service)],
) -> str:
    """Return a short poem from the configured LLM for connectivity checks."""
    poem = await llm.make_poem("the beauty of nature")
    return poem

@app.get("/health", response_model=HealthResponse)
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(
        status="ok",
        llm_model=settings.llm_model,
        stt_model=settings.stt_model,
    )


# ---------------------------------------------------------------------------
# Analyze: text + image + pdf + extra fields -> markdown response
# ---------------------------------------------------------------------------


@app.post("/analyze", response_class=PlainTextResponse)
async def analyze(
    settings: Annotated[Settings, Depends(get_settings)],
    llm: Annotated[LLMService, Depends(get_llm_service)],
    text: Annotated[str, Form(description="Primary user text / prompt.")],
    image: Annotated[UploadFile | str | None, File(description="Optional image.")] = None,
    pdf: Annotated[UploadFile | str | None, File(description="Optional PDF document.")] = None,
    category: Annotated[str | None, Form(description="Optional category hint.")] = None,
    user_id: Annotated[str | None, Form(description="Optional user id.")] = None,
    metadata_json: Annotated[
        str | None,
        Form(description='Optional JSON string with extra fields, e.g. \'{"foo": "bar"}\''),
    ] = None,
) -> str:
    max_bytes = settings.max_upload_mb * 1024 * 1024

    # ---- Image ----
    image_data_url: str | None = None
    if isinstance(image, UploadFile) and image.filename:
        img_bytes = await _read_with_limit(image, max_bytes, "image")
        try:
            image_data_url = encode_image_to_data_url(
                img_bytes,
                content_type=image.content_type or "image/png",
            )
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    elif isinstance(image, str) and image.strip():
        # Allow passing an image as a data URL string directly (for testing or non-file inputs)
        image_data_url = image.strip()

    # ---- PDF ----
    pdf_text: str | None = None
    if isinstance(pdf, UploadFile) and pdf.filename:
        pdf_bytes = await _read_with_limit(pdf, max_bytes, "pdf")
        if (pdf.content_type or "").lower() not in (
            "application/pdf",
            "application/x-pdf",
            "",  # some clients omit it
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Expected a PDF, got content-type '{pdf.content_type}'",
            )
        try:
            pdf_text = extract_pdf_text(pdf_bytes)
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    elif isinstance(pdf, str):
        # Allow passing PDF text directly as a string (for testing or non-file inputs)
        pdf_text = pdf.strip()

    # ---- Extra fields ----
    extra: dict = {}
    if category:
        extra["category_hint"] = category
    if user_id:
        extra["user_id"] = user_id
    if metadata_json:
        try:
            extra["metadata"] = json.loads(metadata_json)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"metadata_json is not valid JSON: {e}",
            ) from e

    # ---- Call LLM ----
    try:
        result = await llm.analyze(
            user_text=text,
            pdf_text=pdf_text,
            image_data_url=image_data_url,
            extra_fields=extra or None,
        )
    except Exception as e:
        logger.exception("LLM call failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"LLM call failed: {e}",
        ) from e

    return result


# ---------------------------------------------------------------------------
# Transcribe: audio -> text (OpenAI-compatible Whisper endpoint)
# ---------------------------------------------------------------------------


@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    settings: Annotated[Settings, Depends(get_settings)],
    stt: Annotated[STTService, Depends(get_stt_service)],
    audio: Annotated[UploadFile, File(description="Audio file (wav, mp3, m4a, ogg, etc.)")],
    language: Annotated[str | None, Form(description="Optional ISO-639-1 language hint")] = None,
) -> TranscribeResponse:
    max_bytes = settings.max_upload_mb * 1024 * 1024
    audio_bytes = await _read_with_limit(audio, max_bytes, "audio")

    try:
        return await stt.transcribe(
            audio_file=io.BytesIO(audio_bytes),
            filename=audio.filename or "audio.wav",
            language=language,
        )
    except Exception as e:
        logger.exception("STT call failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Transcription failed: {e}"
        ) from e


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _read_with_limit(upload: UploadFile, max_bytes: int, label: str) -> bytes:
    data = await upload.read()
    if len(data) > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"{label} file too large: {len(data)} bytes (max {max_bytes}).",
        )
    if not data:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Empty {label} upload."
        )
    return data


# ---------------------------------------------------------------------------
# Generic exception -> JSON
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def _unhandled_exc(_, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": str(exc)},
    )