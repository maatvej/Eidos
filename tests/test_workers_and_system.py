# filename: tests/test_workers_and_system.py
"""Integration and unit tests for Workers (app/workers/tasks.py), ASGI Dispatcher (app/asgi.py), DB session, and Logging."""

import logging
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.asgi import UnifiedASGIApplication
from app.core.logging import JSONFormatter, setup_logging
from app.db.models import Transcription, TranscriptionJob
from app.db.session import get_db_session
from app.domain.entities import (
    ConversationAnalysis,
    JobStatus,
    TranscriptionJobEntity,
    TranscriptionResult,
    Utterance,
)
from app.repository.job_repository import JobRepository
from app.workers.tasks import WorkerSettings, process_transcription_job, startup


@pytest.mark.asyncio
async def test_worker_startup_hook() -> None:
    """Validates worker startup lifecycle hook initializing engines in context."""
    ctx: dict = {}
    with patch("app.workers.tasks.inference_engine.load_models") as mock_load:
        await startup(ctx)
        mock_load.assert_called_once()
        assert "ffmpeg" in ctx
        assert "llm" in ctx


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_process_transcription_job_success_and_cleanup(tmp_path: Path) -> None:
    """Validates full worker pipeline execution and temporary file cleanup."""
    audio_file = tmp_path / "job_audio.wav"
    audio_file.write_bytes(b"RIFF....WAVE")

    # Create temporary normalized wav file to trigger cleanup branch
    normalized_file = Path(f"{audio_file}_16k.wav")
    normalized_file.write_bytes(b"RIFF_NORMALIZED_16K")

    job_id = uuid4()
    job_entity = TranscriptionJobEntity(
        id=job_id,
        filename="job_audio.wav",
        file_path=str(audio_file),
        status=JobStatus.PENDING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repo = JobRepository()
    await repo.create(job_entity)

    # Mock FFmpeg, InferenceEngine, and LLM
    mock_ffmpeg = AsyncMock()
    mock_ffmpeg.normalize_and_vad.return_value = normalized_file

    mock_result = TranscriptionResult(
        utterances=[Utterance(speaker="SPEAKER_00", start=0.0, end=1.0, text="Привет")],
        duration_seconds=2.0,
        detected_language="ru",
    )
    mock_analysis = ConversationAnalysis(
        title="Тест встречи",
        executive_summary="Все прошло отлично.",
        key_decisions=[],
        action_items=[],
    )

    mock_llm = AsyncMock()
    mock_llm.extract_intelligence.return_value = mock_analysis

    ctx = {"ffmpeg": mock_ffmpeg, "llm": mock_llm}

    with patch(
        "app.workers.tasks.inference_engine.process_audio", new_callable=AsyncMock
    ) as mock_process:
        mock_process.return_value = mock_result

        await process_transcription_job(ctx, str(job_id))

        updated_job = await repo.get_by_id(job_id)
        assert updated_job.status == JobStatus.COMPLETED
        assert updated_job.progress_percentage == 100.0
        # Verify temporary normalized file was deleted
        assert not normalized_file.exists()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_process_transcription_job_error_handling() -> None:
    """Validates worker failure handling when job execution raises exception."""
    job_id = uuid4()
    job_entity = TranscriptionJobEntity(
        id=job_id,
        filename="err.wav",
        file_path="/tmp/err.wav",
        status=JobStatus.PENDING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repo = JobRepository()
    await repo.create(job_entity)

    mock_ffmpeg = AsyncMock()
    mock_ffmpeg.normalize_and_vad.side_effect = RuntimeError("Fatal normalization error")

    ctx = {"ffmpeg": mock_ffmpeg}

    with patch(
        "app.workers.tasks.inference_engine.process_audio", new_callable=AsyncMock
    ) as mock_process:
        mock_process.side_effect = RuntimeError("Fatal ML error")

        await process_transcription_job(ctx, str(job_id))

        updated_job = await repo.get_by_id(job_id)
        assert updated_job.status == JobStatus.FAILED
        assert updated_job.error_message is not None
        assert "Fatal" in updated_job.error_message


def test_worker_settings_class() -> None:
    """Validates Arq WorkerSettings class attributes."""
    assert process_transcription_job in WorkerSettings.functions
    assert WorkerSettings.on_startup == startup


@pytest.mark.asyncio
async def test_unified_asgi_application() -> None:
    """Validates UnifiedASGIApplication routing HTTP requests to Django or FastAPI based on URI prefix."""
    django_app = AsyncMock()
    fastapi_app = AsyncMock()
    mock_receive = AsyncMock()
    mock_send = AsyncMock()

    dispatcher = UnifiedASGIApplication(django_app=django_app, fastapi_app=fastapi_app)

    # 1. Admin path -> django_app
    scope_admin = {"type": "http", "path": "/admin/login"}
    await dispatcher(scope_admin, mock_receive, mock_send)
    django_app.assert_called_once_with(scope_admin, mock_receive, mock_send)

    # 2. Accounts path -> django_app
    scope_acc = {"type": "http", "path": "/accounts/login/"}
    await dispatcher(scope_acc, mock_receive, mock_send)
    assert django_app.call_count == 2

    # 3. REST API path -> fastapi_app
    scope_api = {"type": "http", "path": "/api/v1/transcription/upload"}
    await dispatcher(scope_api, mock_receive, mock_send)
    fastapi_app.assert_called_once_with(scope_api, mock_receive, mock_send)


@pytest.mark.asyncio
async def test_get_db_session_generator() -> None:
    """Validates AsyncSession context generator."""
    session_gen = get_db_session()
    session = await anext(session_gen)
    assert session is not None
    await session_gen.aclose()


def test_models_str_representation() -> None:
    """Validates __str__ methods on ORM models."""
    t = Transcription(title="Встреча A", status="completed")
    assert str(t) == "Встреча A (completed)"

    tj = TranscriptionJob(filename="test.wav", status="PROCESSING")
    assert str(tj) == "test.wav (PROCESSING)"


def test_json_formatter_logging() -> None:
    """Validates JSON log formatting with extra attributes and exception info."""
    formatter = JSONFormatter()

    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    record.extra = {"user_id": 42}

    output = formatter.format(record)
    assert '"message": "Test message"' in output
    assert '"user_id": 42' in output

    # Exception formatting
    try:
        raise ValueError("Log exception test")
    except ValueError:
        import sys

        record_exc = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=20,
            msg="Error occurred",
            args=(),
            exc_info=sys.exc_info(),
        )
        out_exc = formatter.format(record_exc)
        assert '"exception":' in out_exc
        assert "ValueError: Log exception test" in out_exc

    # setup_logging call test
    logger_inst = setup_logging()
    assert logger_inst.name == "conversation_ai"
