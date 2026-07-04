"""Application settings loaded from environment variables.

All configuration lives in the ``.env`` file at the project root.
``pydantic-settings`` reads it automatically — no manual parsing needed.

To add a new setting:
    1. Add the variable to ``.env``           →  MY_SETTING="value"
    2. Add a field here with the same name    →  MY_SETTING: str = "default"
    3. Use it anywhere:  ``from backend.config.settings import settings``
                         ``print(settings.MY_SETTING)``
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the AI CCTV Surveillance Platform."""

    # ── Application ───────────────────────────────────────────────
    PROJECT_NAME: str = "AI CCTV Surveillance API"
    VERSION: str = "1.0.0"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # ── Database ──────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./data/surveillance.db"

    # ── ML / Inference ────────────────────────────────────────────
    VIOLENCE_THRESHOLD: float = 0.5
    DEVICE: str = "auto"                    # "auto", "cuda", or "cpu"

    # ── Alert System ──────────────────────────────────────────────
    EMAIL_SENDER: str = ""
    EMAIL_PASSWORD: str = ""
    EMAIL_RECEIVER: str = ""                # defaults to EMAIL_SENDER
    TELEGRAM_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    ALERT_COOLDOWN_SECONDS: int = 30        # min seconds between alerts
    ALERTS_ENABLED: bool = True

    # ── Storage ───────────────────────────────────────────────────
    MAX_UPLOAD_MB: int = 500                # max upload file size
    CLIP_DURATION_SECONDS: float = 5.0      # evidence clip length
    ENABLE_AUTO_CLEANUP: bool = True        # run retention policy
    RETENTION_DAYS: int = 30                # days to keep evidence
    MAX_STORAGE_GB: int = 50                # emergency cap on storage directory

    # ── Authentication (Phase 11) ─────────────────────────────────
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480           # 8 hours

    # ── ML Models ─────────────────────────────────────────────────
    # If using custom models dir, set it here. We default to None to use built-in.
    MODEL_PATH: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def email_receiver(self) -> str:
        """Fall back to sender address if no separate receiver is set."""
        return self.EMAIL_RECEIVER or self.EMAIL_SENDER

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024


settings = Settings()
