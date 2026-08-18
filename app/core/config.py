# filename: app/core/config.py
"""Application configuration with lightweight Local-Dev, Offline Air-Gapped, and Production controls."""

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Core application settings with strict offline and local-only ML execution controls."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "Eidos Voice Intelligence"
    API_V1_STR: str = "/api/v1"

    # Operational Mode Flags
    DEV_MODE: bool = True
    USE_REDIS: bool = False

    # Storage (Local relative directory fallback)
    STORAGE_DIR: Path = Path("./local_storage")
    MODELS_DIR: Path = Path("./models")

    # Database (Default to local SQLite file for zero-dependency execution)
    DATABASE_URL: str = "sqlite+aiosqlite:///./dev_app.db"

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # Local & Air-Gapped Model Execution Policies
    LOCAL_MODELS_ONLY: bool = True
    ALLOW_MODEL_DOWNLOADS: bool = True
    ALLOW_EXTERNAL_API_CALLS: bool = False

    # Whisper Speech Recognition Settings
    WHISPER_MODEL_SIZE: str = "large-v3-turbo"
    WHISPER_FALLBACK_MODEL_SIZE: str = "medium"
    WHISPER_DOWNLOAD_ROOT: str | None = None
    WHISPER_LOCAL_FILES_ONLY: bool = False
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    WHISPER_CPU_THREADS: int = 4
    WHISPER_NUM_WORKERS: int = 1
    WHISPER_BEAM_SIZE: int = 5
    WHISPER_BEST_OF: int = 5
    WHISPER_PATIENCE: float = 1.0
    WHISPER_REPETITION_PENALTY: float = 1.05
    WHISPER_NO_REPEAT_NGRAM_SIZE: int = 3
    WHISPER_CONDITION_ON_PREVIOUS_TEXT: bool = False
    WHISPER_INITIAL_PROMPT: str = (
        "Стенограмма деловой встречи, совещания, презентации. "
        "Используйте корректную пунктуацию, заглавные буквы, разделение предложений и терминологию."
    )
    WHISPER_VAD_MIN_SILENCE_MS: int = 400
    WHISPER_VAD_SPEECH_PAD_MS: int = 300

    # Audio Preprocessing Enhancements
    AUDIO_NORMALIZE_LOUDNESS: bool = True
    AUDIO_NOISE_REDUCTION: bool = True
    AUDIO_BANDPASS_FILTER: bool = True
    FFMPEG_THREADS: int = 2
    UPLOAD_CHUNK_SIZE: int = 1024 * 1024

    # Speaker Diarization Settings
    PYANNOTE_AUTH_TOKEN: str = "hf_dummy_token"
    PYANNOTE_LOCAL_MODEL_PATH: str | None = None
    DIARIZATION_MIN_SPEAKERS: int | None = None
    DIARIZATION_MAX_SPEAKERS: int | None = None
    VOICE_SIMILARITY_THRESHOLD: float = 0.75
    VOICE_EMBEDDING_DIM: int = 32

    # LLM & Conversation Intelligence Settings (Defaulting to Local Ollama/Offline NLP Engine)
    LLM_API_KEY: str = "local-key"
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_MODEL_NAME: str = "llama3"
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 4096
    TORCH_NUM_THREADS: int = 4

    # Comprehensive Profiling & Performance Diagnostics
    PROFILING_ENABLED: bool = False

    # Frontend Dist Directory for React SPA
    FRONTEND_DIST_DIR: Path = Path("./frontend/dist")
    PROFILING_OUTPUT_DIR: Path = Path("./profiles")
    PROFILING_SORT_BY: str = "cumulative"
    PROFILING_RESTRICTION_LIMIT: int = 30
    PROFILING_SLOW_THRESHOLD_MS: float = 0.0
    PROFILING_EXCLUDE_PATHS: list[str] = [
        "/static",
        "/django-static",
        "/django_static",
        "/assets",
        "/frontend",
        "/health",
        "/favicon.ico",
        "/robots.txt",
        "/openapi.json",
        "/api/v1/openapi.json",
        "/docs",
        "/redoc",
        "/api/v1/events",
        "/sse",
    ]


def configure_offline_environment(app_settings: Settings) -> None:
    """Configures global process environment variables for offline and telemetry-free ML execution.

    Args:
        app_settings: Instance of application Settings.

    Returns:
        None

    Example:
        >>> configure_offline_environment(settings)
    """
    app_settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    app_settings.PROFILING_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    app_settings.MODELS_DIR.mkdir(parents=True, exist_ok=True)

    if not app_settings.ALLOW_MODEL_DOWNLOADS or app_settings.WHISPER_LOCAL_FILES_ONLY:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        os.environ.setdefault("HF_DATASETS_OFFLINE", "1")

    # Always disable telemetry and tracking
    os.environ.setdefault("DISABLE_TELEMETRY", "1")
    os.environ.setdefault("DO_NOT_TRACK", "1")
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")


settings = Settings()
configure_offline_environment(settings)
