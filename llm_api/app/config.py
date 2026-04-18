"""Application configuration loaded from environment variables / .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM (OpenAI-compatible) ------------------------------------------------
    llm_base_url: str = "http://localhost:8000/v1"
    llm_api_key: str = "EMPTY"
    llm_model: str = "google/gemma-3-27b-it"

    # Speech-to-Text (OpenAI-compatible) -------------------------------------
    stt_base_url: str = "https://api.openai.com/v1"
    stt_api_key: str = "EMPTY"
    stt_model: str = "whisper-1"

    # App -------------------------------------------------------------------
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    log_level: str = "info"
    max_upload_mb: int = 25

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Cache settings so the .env file is only parsed once per process."""
    return Settings()
