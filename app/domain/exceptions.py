# filename: app/domain/exceptions.py
"""Custom domain exceptions for clean exception handling across all software layers."""


class DomainError(Exception):
    """Base exception class for all domain-level exceptions."""

    def __init__(self, message: str, code: str = "DOMAIN_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class AudioProcessingError(DomainError):
    """Raised when FFmpeg audio normalization or VAD fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="AUDIO_PROCESSING_FAILED")


class ModelInferenceError(DomainError):
    """Raised when Whisper or PyAnnote ML pipelines encounter execution failures."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="MODEL_INFERENCE_FAILED")


class JobNotFoundError(DomainError):
    """Raised when a requested transcription job UUID does not exist."""

    def __init__(self, job_id: str) -> None:
        super().__init__(f"Transcription job '{job_id}' was not found.", code="JOB_NOT_FOUND")


class ExportGenerationError(DomainError):
    """Raised when multi-format export fails (PDF, DOCX, SRT, VTT)."""

    def __init__(self, format_type: str, details: str) -> None:
        super().__init__(f"Failed to render {format_type} export: {details}", code="EXPORT_FAILED")


class SummarizationError(DomainError):
    """Raised when transcript summarization or post-processing fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="SUMMARIZATION_FAILED")


class LLMServiceError(DomainError):
    """Raised when external LLM service communication fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="LLM_SERVICE_ERROR")
