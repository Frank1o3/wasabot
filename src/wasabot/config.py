"""
Configuration management using pydantic-settings.

🐍 PYTHON NATIVE: Uses pydantic-settings for env var management instead of manual os.getenv()
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # WhatsApp Business API
    wa_access_token: str = ""
    wa_phone_number_id: str = ""
    wa_verify_token: str = ""

    # Groq AI Configuration
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    groq_whisper_model: str = "whisper-large-v3-turbo"

    # Environment
    environment: str = "development"
    port: int = 8888
    host: str = "0.0.0.0"

    # Database path (relative to project root)
    database_path: str = "data/wasabot.db"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() == "production"

    @property
    def absolute_db_path(self) -> Path:
        """Get absolute path to database file."""
        # 🐍 PYTHON NATIVE: Resolve relative to project root
        project_root = Path(__file__).parent.parent.parent
        return project_root / self.database_path

    @property
    def whatsapp_base_url(self) -> str:
        """WhatsApp Cloud API base URL."""
        return "https://graph.facebook.com/v21.0"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    🐍 PYTHON NATIVE: lru_cache ensures singleton pattern without global variables
    """
    return Settings()
