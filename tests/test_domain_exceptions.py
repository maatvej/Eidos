# filename: tests/test_domain_exceptions.py
"""Unit tests for domain exception hierarchy (app/domain/exceptions.py)."""

from app.domain.exceptions import (
    AudioProcessingError,
    DomainError,
    ExportGenerationError,
    JobNotFoundError,
    LLMServiceError,
    ModelInferenceError,
    SummarizationError,
)


def test_domain_exceptions_properties() -> None:
    """Validates instantiation, inheritance, code, and message formatting for domain exceptions."""
    base_err = DomainError("Base error message", code="BASE_ERR")
    assert base_err.message == "Base error message"
    assert base_err.code == "BASE_ERR"
    assert str(base_err) == "Base error message"

    audio_err = AudioProcessingError("Audio failed")
    assert isinstance(audio_err, DomainError)
    assert audio_err.code == "AUDIO_PROCESSING_FAILED"
    assert audio_err.message == "Audio failed"

    model_err = ModelInferenceError("Inference failed")
    assert model_err.code == "MODEL_INFERENCE_FAILED"

    job_err = JobNotFoundError("abc-123")
    assert job_err.code == "JOB_NOT_FOUND"
    assert "abc-123" in job_err.message

    export_err = ExportGenerationError("PDF", "Template corrupt")
    assert export_err.code == "EXPORT_FAILED"
    assert "PDF" in export_err.message
    assert "Template corrupt" in export_err.message

    summary_err = SummarizationError("Summary failed")
    assert summary_err.code == "SUMMARIZATION_FAILED"

    llm_err = LLMServiceError("API timeout")
    assert llm_err.code == "LLM_SERVICE_ERROR"
