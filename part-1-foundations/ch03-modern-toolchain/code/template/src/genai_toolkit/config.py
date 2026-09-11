"""Application configuration, loaded from the environment and validated on startup.

Why this rather than os.environ: a missing or malformed key fails here, at startup,
with a message naming the exact field — instead of a KeyError deep inside a request
handler at 3am, or the string "None" being sent to an API.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = Field(min_length=10)
    # Default to the most capable model. Cost is a decision you make with
    # measurements (Chapter 9), not a default you inherit.
    model: str = "claude-opus-5"
    # Don't lowball max_tokens: hitting the cap truncates mid-thought and
    # costs you a whole retry. ~16k for non-streaming, more when streaming.
    max_tokens: int = Field(default=16_000, ge=1, le=200_000)
    log_level: str = "INFO"
    request_timeout: float = Field(default=30.0, gt=0)


@lru_cache
def get_settings() -> Settings:
    """Cached so the .env file is read once per process."""
    return Settings()  # type: ignore[call-arg]
