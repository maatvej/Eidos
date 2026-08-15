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
from app.repository.job_repository import JobRepository, VoiceProfileRepository
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


def test_format_speaker_transcription_helpers() -> None:
    """Validates format_speaker_transcription with various speech patterns and edge cases."""
    from app.repository.job_repository import format_speaker_transcription

    # 1. Empty utterances list
    assert format_speaker_transcription([]) == ""

    # 2. Utterances with blank text
    blank_utt = [
        Utterance(speaker="Alice", start=0.0, end=1.0, text="   "),
        Utterance(speaker="Bob", start=1.0, end=2.0, text=""),
    ]
    assert format_speaker_transcription(blank_utt) == ""

    # 3. Utterances without speaker name
    no_speaker_utt = [
        Utterance(speaker="", start=0.0, end=1.0, text="Unattributed sentence."),
        Utterance(speaker="   ", start=1.0, end=2.0, text="Second unattributed sentence."),
    ]
    assert (
        format_speaker_transcription(no_speaker_utt)
        == "Unattributed sentence.\n\nSecond unattributed sentence."
    )

    # 4. Normal speaker blocks
    multi_speaker_utt = [
        Utterance(speaker="Спикер 1", start=0.0, end=1.0, text="Привет!"),
        Utterance(speaker="Спикер 2", start=1.0, end=2.0, text="Добрый день!"),
    ]
    assert (
        format_speaker_transcription(multi_speaker_utt)
        == "Спикер 1: Привет!\n\nСпикер 2: Добрый день!"
    )


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


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_voice_profile_repository_lifecycle(test_user) -> None:
    """Validates VoiceProfileRepository CRUD lifecycle, running average embedding update, and deletion."""
    repo = VoiceProfileRepository()

    # 1. Create new profile
    emb1 = [1.0] + [0.0] * 31
    profile = await repo.save_or_update_voice_profile(
        user_id=test_user.pk,
        name="Алексей Смирнов",
        embedding=emb1,
    )
    assert profile.name == "Алексей Смирнов"
    assert profile.samples_count == 1
    assert len(profile.embedding) == 32

    # 2. Retrieve by user
    user_profiles = await repo.get_user_voice_profiles(test_user.pk)
    assert len(user_profiles) >= 1
    assert any(p.id == profile.id for p in user_profiles)

    # 3. Retrieve by ID
    fetched = await repo.get_voice_profile_by_id(profile.id, test_user.pk)
    assert fetched is not None
    assert fetched.name == "Алексей Смирнов"

    # Non-existent or other user ID -> None
    assert await repo.get_voice_profile_by_id(uuid4(), test_user.pk) is None
    assert await repo.get_voice_profile_by_id(profile.id, 999999) is None

    # 4. Update existing profile with new embedding (running centroid average)
    emb2 = [0.0, 1.0] + [0.0] * 30
    updated = await repo.save_or_update_voice_profile(
        user_id=test_user.pk,
        name="Алексей Смирнов",
        embedding=emb2,
    )
    assert updated.samples_count == 2
    # Combined vector should have non-zero in components 0 and 1
    assert updated.embedding[0] > 0.0
    assert updated.embedding[1] > 0.0

    # 5. Delete profile
    deleted = await repo.delete_voice_profile(profile.id, test_user.pk)
    assert deleted is True
    assert await repo.get_voice_profile_by_id(profile.id, test_user.pk) is None

    # Delete non-existent
    assert await repo.delete_voice_profile(uuid4(), test_user.pk) is False
