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
    WHISPER_MODEL_SIZE: str = "large-v3-turbo"
    WHISPER_FALLBACK_MODEL_SIZE: str = "medium"
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
    DIARIZATION_MIN_SPEAKERS: int | None = None
    DIARIZATION_MAX_SPEAKERS: int | None = None
    VOICE_SIMILARITY_THRESHOLD: float = 0.75
    VOICE_EMBEDDING_DIM: int = 32

    # LLM & Conversation Intelligence Settings
    LLM_API_KEY: str = "mock-key"
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL_NAME: str = "gpt-4o"
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


settings = Settings()
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
settings.PROFILING_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
