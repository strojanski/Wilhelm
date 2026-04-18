"""Pydantic models for API requests and responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AnalyzeResponse(BaseModel):
    """Standardized, templated response from the LLM."""

    summary: str = Field(..., description="One-paragraph summary of the input.")
    category: str = Field(..., description="Single best-fit category label.")
    tags: list[str] = Field(default_factory=list, description="Relevant tags/keywords.")
    entities: list[str] = Field(
        default_factory=list,
        description="Named entities found (people, places, orgs, products).",
    )
    key_points: list[str] = Field(
        default_factory=list, description="Bulleted list of key takeaways."
    )
    sentiment: str = Field(
        ..., description="One of: positive, negative, neutral, mixed."
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Model's self-reported confidence 0-1."
    )
    raw_model_output: str | None = Field(
        None,
        description="Raw model JSON string, for debugging. Null in production.",
    )


class TranscribeResponse(BaseModel):
    """Response from the speech-to-text endpoint."""

    text: str
    language: str | None = None
    duration_seconds: float | None = None
    model: str


class HealthResponse(BaseModel):
    status: str
    llm_model: str
    stt_model: str


class ErrorResponse(BaseModel):
    error: str
    detail: Any | None = None
