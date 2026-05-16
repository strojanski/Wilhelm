"""LLM service using the OpenAI client.

Using the OpenAI SDK keeps this compatible with any OpenAI-compatible server:
  * vLLM running Gemma locally
  * Google's Gemini/Gemma OpenAI-compatible endpoint
  * OpenAI itself
  * Ollama, LM Studio, llama.cpp server, etc.

Only the base_url, api_key and model name change between them.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import AsyncOpenAI

from app.config import Settings
from app.services.system_prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


# The system prompt enforces the exact JSON template we want back.
# Gemma (and most modern instruction-tuned models) follows this reliably
# when the schema is described clearly and we ask for JSON only.
# SYSTEM_PROMPT = """You are a structured-data extraction assistant.

# You will receive a user's free-form text, optionally accompanied by:
#   - an image,
#   - extracted text from a PDF document,
#   - extra metadata fields.

# Your job is to analyze ALL of that input together and return a SINGLE JSON
# object that exactly matches this schema:

# {
#   "summary":    string,              // 1-3 sentence overall summary
#   "category":   string,              // single best-fit category
#   "tags":       string[],            // 3-8 short tags / keywords
#   "entities":   string[],            // named entities (people, orgs, places, products)
#   "key_points": string[],            // 3-6 bulleted key takeaways
#   "sentiment":  "positive" | "negative" | "neutral" | "mixed",
#   "confidence": number               // your confidence 0.0 - 1.0
# }

# Rules:
#   1. Output ONLY the JSON object. No prose before or after. No markdown fences.
#   2. Use double quotes. Every field is required.
#   3. If a field has no content, use an empty array [] or "unknown".
#   4. Keep strings concise; do not invent facts not supported by the input.
# """

class TestLLMService:
    """Call a real LLM to make a poem to verify the integration is working end-to-end."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        )
        self._model = settings.llm_model

    async def make_poem(self, topic: str) -> str:
        messages = [
            {"role": "system", "content": "You are a poet."},
            {"role": "user", "content": f"Write a short poem about {topic}."},
        ]

        completion = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.7,
            max_tokens=100,
        )

        poem = completion.choices[0].message.content or ""
        return poem.strip()

class LLMService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        )
        self._model = settings.llm_model

    async def analyze(
        self,
        user_text: str,
        pdf_text: str | None = None,
        image_data_url: str | None = None,
        audio_data_url: str | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> str:
        """Send everything to the LLM and return the model's Markdown text."""
        user_content: list[dict[str, Any]] = []

        # Build the textual prompt block first, but append image BEFORE text
        # when sending multimodal content — Gemma best practice.
        prompt_body = self._build_user_text_block(user_text, pdf_text, extra_fields)

        # Multimodal order: image, then audio, then text (Gemma best practice)
        if image_data_url:
            user_content.append({"type": "image_url", "image_url": {"url": image_data_url}})

        if audio_data_url:
            user_content.append({"type": "audio_url", "audio_url": {"url": audio_data_url}})

        # Then the text block
        user_content.append({"type": "text", "text": prompt_body})

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        logger.info("Calling LLM model=%s", self._model)
        # NOTE: we avoid response_format=json_object because not every
        # OpenAI-compatible server (notably some vLLM + Gemma combos) supports
        # it. The system prompt reliably enforces JSON instead.
        completion = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.2,
            max_tokens=10480,
        )

        raw = (completion.choices[0].message.content or "").strip()
        logger.debug("Raw LLM output: %s", raw)
        return raw

    @staticmethod
    def _build_user_text_block(
        user_text: str,
        pdf_text: str | None,
        extra_fields: dict[str, Any] | None,
    ) -> str:
        parts = ["=== USER TEXT ===", user_text.strip() or "(empty)"]

        if extra_fields:
            parts.append("\n=== EXTRA FIELDS ===")
            parts.append(json.dumps(extra_fields, ensure_ascii=False, indent=2))

        if pdf_text:
            parts.append("\n=== PDF CONTENT ===")
            parts.append(pdf_text.strip())

        parts.append(
            "\n=== TASK ===\n"
            "Analyze everything above (including the attached image if present) "
            "and return the completed Markdown medical report as specified. "
            "Fill every section with clinically useful detail, prefer a complete "
            "report over a terse summary, and keep the template structure exactly "
            "as provided."
        )
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# JSON extraction: tolerant of stray prose or markdown fences.
# ---------------------------------------------------------------------------


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json_object(raw: str) -> dict[str, Any]:
    """Best-effort: pull the first JSON object out of the model's reply."""
    # Try plain parse first.
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try stripped markdown fence.
    m = _JSON_FENCE_RE.search(raw)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Try first "{ ... }" by bracket balancing.
    start = raw.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(raw[start:], start=start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    chunk = raw[start : i + 1]
                    try:
                        return json.loads(chunk)
                    except json.JSONDecodeError:
                        break

    raise ValueError(
        "LLM did not return parseable JSON. Raw output:\n" + raw
    )
