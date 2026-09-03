from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    AI_SERVICE_PORT: int = 8001
    AI_SERVICE_HOST: str = "0.0.0.0"

    DATABASE_URL: str = "postgresql://medibook:password123@db:5432/medibook_db"
    BACKEND_API_URL: str = "http://backend:8000/api"

    GROQ_API_KEY: str = ""
    GROQ_API_KEYS: str = ""  # Comma-separated list for multi-key round-robin
    GROQ_MODEL: str = "openai/gpt-oss-120b"

    GOOGLE_CALENDAR_CREDENTIALS_PATH: str = "google-calendar-credentials.json"
    GOOGLE_CALENDAR_API_KEY: str = ""
    GOOGLE_CALENDAR_SECRET: str = ""
    GOOGLE_CALENDAR_ID: str = ""

    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    FRONTEND_URL: str = "http://localhost:3000"

    N8N_URL: str = "http://n8n:5678"
    N8N_WEBHOOK_URL: str = "http://n8n:5678/webhook/medibook-reminder"

    CONVERSATION_MAX_HISTORY: int = 20

    ALLOWED_ORIGINS: str = (
        "http://localhost:3000,http://localhost:3001,http://localhost:5173,"
        "http://127.0.0.1:3000,http://127.0.0.1:5173"
    )

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def backend_base(self) -> str:
        return self.BACKEND_API_URL.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
