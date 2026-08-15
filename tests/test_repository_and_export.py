# filename: tests/test_repository_and_export.py
"""Unit tests for JobRepository (app/repository/job_repository.py) and ExportService (app/services/export_service.py)."""

from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

import pytest
from asgiref.sync import sync_to_async

from app.db.models import Transcription
from app.domain.entities import (
    ActionItem,
    ConversationAnalysis,
    JobStatus,
    TranscriptionJobEntity,
    TranscriptionResult,
    Utterance,
)
from app.domain.exceptions import ExportGenerationError, JobNotFoundError
from app.repository.job_repository import JobRepository
from app.services.export_service import ExportService


@pytest.fixture
def sample_result() -> TranscriptionResult:
    return TranscriptionResult(
        utterances=[
            Utterance(speaker="SPEAKER_00", start=0.0, end=1.5, text="Hello and welcome."),
            Utterance(speaker="SPEAKER_01", start=2.0, end=3.5, text="Thanks for inviting me."),
        ],
        duration_seconds=5.0,
        detected_language="en",
        analysis=ConversationAnalysis(
            title="Project Update Meeting",
            executive_summary="Team reviewed progress.",
            key_decisions=["Deploy to production next Monday."],
            action_items=[ActionItem(task="Run test suite", owner="Alice", priority="HIGH")],
        ),
    )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_job_repository_crud_and_sync(test_user, sample_result: TranscriptionResult) -> None:
    """Validates JobRepository creation, status update, sync with Transcription ORM, and error paths."""
    repo = JobRepository()
    job_id = uuid4()

    job_entity = TranscriptionJobEntity(
        id=job_id,
        filename="test_sync.wav",
        file_path="/tmp/test_sync.wav",
        status=JobStatus.PENDING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # 1. Create Job
    created = await repo.create(job_entity)
    assert created.id == job_id

    # Create associated Transcription ORM object for user
    await sync_to_async(Transcription.objects.create)(
        id=job_id,
        user_id=test_user.pk,
        title="initial_title",
        original_filename="test_sync.wav",
    )

    # 2. Get Job by ID
    fetched = await repo.get_by_id(job_id)
    assert fetched.filename == "test_sync.wav"

    # 3. Update progress with result -> triggers ORM sync
    await repo.update_progress(
        job_id=job_id,
        status=JobStatus.COMPLETED,
        progress=100.0,
        step="Completed",
        result=sample_result,
    )

    updated_job = await repo.get_by_id(job_id)
    assert updated_job.status == JobStatus.COMPLETED
    assert updated_job.result is not None
    assert updated_job.result.duration_seconds == 5.0

    # Verify Transcription ORM model updated
    trans_orm = await sync_to_async(Transcription.objects.get)(id=job_id)
    assert trans_orm.status == "completed"
    assert "Project Update Meeting" in trans_orm.title
    assert "Hello and welcome." in trans_orm.transcription_text

    # 4. Update progress with no analysis title fallback
    result_no_title = TranscriptionResult(
        utterances=[Utterance(speaker="S1", start=0.0, end=1.0, text="Text")],
        duration_seconds=1.0,
        analysis=ConversationAnalysis(
            title="",
            executive_summary="Summary",
            key_decisions=[],
            action_items=[],
        ),
    )
    trans_orm.title = "test_sync.wav"
    await sync_to_async(trans_orm.save)()

    await repo.update_progress(
        job_id=job_id,
        status=JobStatus.COMPLETED,
        progress=100.0,
        step="Completed",
        result=result_no_title,
    )
    trans_orm_updated = await sync_to_async(Transcription.objects.get)(id=job_id)
    assert "Расшифровка test_sync.wav" in trans_orm_updated.title

    # 5. Exception during sync handling (hits line 108-109 in job_repository.py)
    with patch.object(Transcription.objects, "get", side_effect=RuntimeError("ORM sync error")):
        await repo.update_progress(
            job_id=job_id, status=JobStatus.COMPLETED, progress=100.0, step="Done"
        )

    # 6. JobNotFoundError on non-existent job ID
    random_id = uuid4()
    with pytest.raises(JobNotFoundError):
        await repo.get_by_id(random_id)

    with pytest.raises(JobNotFoundError):
        await repo.update_progress(random_id, JobStatus.FAILED, 0.0, "Error")


def test_export_service_formatting_and_renders(sample_result: TranscriptionResult) -> None:
    """Validates ExportService TXT, SRT, VTT, DOCX, and PDF renders."""
    service = ExportService()

    # TXT with analysis
    txt_data = service.to_txt(sample_result)
    assert "MEETING SUMMARY" in txt_data
    assert "Project Update Meeting" in txt_data or "Team reviewed progress." in txt_data
    assert "Hello and welcome." in txt_data

    # TXT without analysis
    result_no_analysis = TranscriptionResult(
        utterances=sample_result.utterances, duration_seconds=5.0
    )
    txt_no_analysis = service.to_txt(result_no_analysis)
    assert "FULL TRANSCRIPT" in txt_no_analysis

    # SRT
    srt_data = service.to_srt(sample_result)
    assert "00:00:00,000 --> 00:00:01,500" in srt_data
    assert "[SPEAKER_00]: Hello and welcome." in srt_data

    # VTT
    vtt_data = service.to_vtt(sample_result)
    assert "WEBVTT" in vtt_data
    assert "<v SPEAKER_00>Hello and welcome." in vtt_data

    # DOCX
    docx_bytes = service.to_docx(sample_result)
    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 0

    # PDF
    pdf_bytes = service.to_pdf(sample_result)
    assert pdf_bytes.startswith(b"%PDF")


def test_export_service_error_handling(sample_result: TranscriptionResult) -> None:
    """Validates ExportGenerationError when docx/pdf generation encounters errors."""
    service = ExportService()

    # DOCX error
    with patch("docx.Document", side_effect=RuntimeError("DOCX library error")):
        with pytest.raises(ExportGenerationError) as exc1:
            service.to_docx(sample_result)
        assert exc1.value.code == "EXPORT_FAILED"
        assert "DOCX" in exc1.value.message

    # PDF error
    with patch(
        "reportlab.platypus.SimpleDocTemplate.build", side_effect=RuntimeError("PDF build error")
    ):
        with pytest.raises(ExportGenerationError) as exc2:
            service.to_pdf(sample_result)
        assert exc2.value.code == "EXPORT_FAILED"
        assert "PDF" in exc2.value.message
