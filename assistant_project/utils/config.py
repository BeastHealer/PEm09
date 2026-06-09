"""Application configuration via Pydantic Settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent


class Settings(BaseSettings):
    """Central configuration loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_chat_model: str = Field("gpt-4o-mini", alias="OPENAI_CHAT_MODEL")
    openai_vision_model: str = Field("gpt-4o", alias="OPENAI_VISION_MODEL")
    openai_embedding_model: str = Field(
        "text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL"
    )
    openai_whisper_model: str = Field("whisper-1", alias="OPENAI_WHISPER_MODEL")
    openai_tts_model: str = Field("tts-1", alias="OPENAI_TTS_MODEL")
    openai_tts_voice: str = Field("alloy", alias="OPENAI_TTS_VOICE")

    # Telegram
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")

    # Paths
    data_dir: Path = Field(default_factory=lambda: WORKSPACE_ROOT / "data")
    db_dir: Path = Field(default_factory=lambda: PROJECT_ROOT / "db")
    chroma_dir: Path = Field(default_factory=lambda: PROJECT_ROOT / "db" / "chroma")

    # RAG
    chunk_size: int = Field(400, alias="CHUNK_SIZE", ge=300, le=500)
    chunk_overlap_percent: int = Field(15, alias="CHUNK_OVERLAP_PERCENT", ge=0, le=50)
    rag_top_k: int = Field(4, alias="RAG_TOP_K", ge=1, le=20)
    chroma_collection: str = Field("prompt_knowledge", alias="CHROMA_COLLECTION")

    # Context
    max_context_tokens: int = Field(8000, alias="MAX_CONTEXT_TOKENS", ge=1000)
    max_history_messages: int = Field(30, alias="MAX_HISTORY_MESSAGES", ge=2)

    # Web
    web_host: str = Field("0.0.0.0", alias="WEB_HOST")
    web_port: int = Field(8000, alias="WEB_PORT")
    web_debug: bool = Field(False, alias="WEB_DEBUG")

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        "INFO", alias="LOG_LEVEL"
    )

    @field_validator("data_dir", "db_dir", "chroma_dir", mode="before")
    @classmethod
    def resolve_path(cls, value: str | Path) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = (PROJECT_ROOT / path).resolve()
        return path

    @property
    def context_db_path(self) -> Path:
        return self.db_dir / "context.db"

    @property
    def metadata_path(self) -> Path:
        return self.db_dir / "metadata.json"

    @property
    def chunk_overlap(self) -> int:
        return max(1, int(self.chunk_size * self.chunk_overlap_percent / 100))

    def ensure_dirs(self) -> None:
        """Create required directories if they do not exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return cached settings singleton."""
    cfg = Settings()
    cfg.ensure_dirs()
    return cfg


# Convenience alias for modules that import settings directly.
settings = get_settings()
