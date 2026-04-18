"""Speech-to-Text service using the OpenAI-compatible audio transcriptions API.

Works with OpenAI Whisper, vLLM serving Whisper, faster-whisper server,
Deepgram's OpenAI-compat endpoint, etc.
"""

from __future__ import annotations

import logging
from typing import BinaryIO

from openai import AsyncOpenAI

from app.config import Settings
from app.schemas import TranscribeResponse

logger = logging.getLogger(__name__)


class STTService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(
            base_url=settings.stt_base_url,
            api_key=settings.stt_api_key,
        )
        self._model = settings.stt_model

    async def transcribe(
        self,
        audio_file: BinaryIO,
        filename: str,
        language: str | None = None,
    ) -> TranscribeResponse:
        logger.info("Transcribing %s with model=%s", filename, self._model)

        kwargs: dict = {
            "model": self._model,
            "file": (filename, audio_file),
            "response_format": "verbose_json",
        }
        if language:
            kwargs["language"] = language

        result = await self._client.audio.transcriptions.create(**kwargs)

        # verbose_json returns an object with .text, .language, .duration
        # (Some backends only return .text; handle both.)
        text = getattr(result, "text", "") or ""
        lang = getattr(result, "language", None)
        duration = getattr(result, "duration", None)

        return TranscribeResponse(
            text=text,
            language=lang,
            duration_seconds=float(duration) if duration is not None else None,
            model=self._model,
        )
