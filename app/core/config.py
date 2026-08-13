# filename: app/core/config.py
"""Application configuration with lightweight Local-Dev and Production controls."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "Eidos Voice Intelligence"
    API_V1_STR: str = "/api/v1"

    # Operational Mode Flags
    DEV_MODE: bool = True
    USE_REDIS: bool = False

    # Storage (Local relative directory fallback)
    STORAGE_DIR: Path = Path("./local_storage")

    # Database (Default to local SQLite file for zero-dependency execution)
    DATABASE_URL: str = "sqlite+aiosqlite:///./dev_app.db"

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # ML Models & Device Overrides
    WHISPER_MODEL_SIZE: str = "small"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    PYANNOTE_AUTH_TOKEN: str = "hf_dummy_token"
    LLM_API_KEY: str = "mock-key"
    LLM_MODEL_NAME: str = "gpt-4o"


settings = Settings()
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
