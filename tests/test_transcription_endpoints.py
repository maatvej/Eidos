# filename: tests/test_transcription_endpoints.py
"""Integration tests for Transcription endpoints (app/api/v1/endpoints/transcription.py)."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.domain.entities import (
    ConversationAnalysis,
    JobStatus,
    TranscriptionJobEntity,
    TranscriptionResult,
    Utterance,
)
from app.repository.job_repository import JobRepository


@pytest.fixture
def completed_job_with_result() -> TranscriptionJobEntity:
    job_id = uuid4()
    result = TranscriptionResult(
        utterances=[
            Utterance(speaker="SPEAKER_00", start=0.0, end=2.0, text="Привет всем."),
            Utterance(speaker="SPEAKER_01", start=2.5, end=4.0, text="Добрый день."),
        ],
        duration_seconds=10.0,
        detected_language="ru",
        analysis=ConversationAnalysis(
            executive_summary="Краткая выжимка встречи.",
            key_decisions=["Принято решение А."],
            action_items=[],
        ),
    )
    return TranscriptionJobEntity(
        id=job_id,
        filename="meeting.wav",
        file_path="/tmp/test_meeting.wav",
        status=JobStatus.COMPLETED,
        progress_percentage=100.0,
        current_step="Completed",
        result=result,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_get_job_status_success_and_not_found(
    client: AsyncClient, completed_job_with_result
) -> None:
    """Validates status polling endpoint for existing and missing jobs."""
    repo = JobRepository()
    await repo.create(completed_job_with_result)

    # Success
    resp = await client.get(f"/api/v1/transcription/jobs/{completed_job_with_result.id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "COMPLETED"

    # Not found
    random_id = uuid4()
    resp_404 = await client.get(f"/api/v1/transcription/jobs/{random_id}")
    assert resp_404.status_code == 404


@pytest.mark.asyncio
async def test_get_job_audio_serving(client: AsyncClient, tmp_path: Path) -> None:
    """Validates audio file serving, MIME detection, and missing file error handling."""
    # Create temp audio file
    audio_file = tmp_path / "test_audio.mp3"
    audio_file.write_bytes(b"FAKE_MP3_DATA")

    job_id = uuid4()
    job = TranscriptionJobEntity(
        id=job_id,
        filename="test_audio.mp3",
        file_path=str(audio_file),
        status=JobStatus.COMPLETED,
        progress_percentage=100.0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repo = JobRepository()
    await repo.create(job)

    # 1. Fetch existing audio file
    resp = await client.get(f"/api/v1/transcription/jobs/{job_id}/audio")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"

    # 2. File missing on disk
    audio_file.unlink()
    resp_missing_file = await client.get(f"/api/v1/transcription/jobs/{job_id}/audio")
    assert resp_missing_file.status_code == 404
    assert "not found on disk" in resp_missing_file.json()["detail"]


@pytest.mark.asyncio
async def test_cancel_job(client: AsyncClient) -> None:
    """Validates canceling active/pending job and error when canceling completed job."""
    job_id = uuid4()
    pending_job = TranscriptionJobEntity(
        id=job_id,
        filename="cancel_test.wav",
        file_path="/tmp/cancel.wav",
        status=JobStatus.TRANSCRIBING,
        progress_percentage=45.0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repo = JobRepository()
    await repo.create(pending_job)

    # Cancel pending job
    resp = await client.post(f"/api/v1/transcription/jobs/{job_id}/cancel")
    assert resp.status_code == 200
    assert "recorded successfully" in resp.json()["message"]

    # Verify status in DB
    updated = await repo.get_by_id(job_id)
    assert updated.status == JobStatus.CANCELLED

    # Attempt to cancel again -> 400 Bad Request
    resp_again = await client.post(f"/api/v1/transcription/jobs/{job_id}/cancel")
    assert resp_again.status_code == 400


@pytest.mark.asyncio
async def test_bulk_rename_speaker_errors(client: AsyncClient) -> None:
    """Validates speaker rename error paths (no results or unknown speaker label)."""
    job_id = uuid4()
    no_result_job = TranscriptionJobEntity(
        id=job_id,
        filename="no_res.wav",
        file_path="/tmp/no_res.wav",
        status=JobStatus.PREPROCESSING,
        progress_percentage=15.0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repo = JobRepository()
    await repo.create(no_result_job)

    # 1. Job without result -> 400 Bad Request
    resp_no_res = await client.post(
        f"/api/v1/transcription/jobs/{job_id}/speaker-rename",
        params={"old_speaker_label": "SPEAKER_00", "new_speaker_name": "Bob"},
    )
    assert resp_no_res.status_code == 400

    # 2. Unknown speaker label -> 404 Not Found
    job_with_res = TranscriptionJobEntity(
        id=uuid4(),
        filename="res.wav",
        file_path="/tmp/res.wav",
        status=JobStatus.COMPLETED,
        result=TranscriptionResult(
            utterances=[Utterance(speaker="SPEAKER_01", start=0.0, end=1.0, text="Hi")]
        ),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await repo.create(job_with_res)

    resp_unknown_speaker = await client.post(
        f"/api/v1/transcription/jobs/{job_with_res.id}/speaker-rename",
        params={"old_speaker_label": "NON_EXISTENT_SPEAKER", "new_speaker_name": "Bob"},
    )
    assert resp_unknown_speaker.status_code == 404


@pytest.mark.asyncio
async def test_export_transcript_all_formats(
    client: AsyncClient, completed_job_with_result
) -> None:
    """Validates exporting transcript in txt, json, srt, vtt, pdf, and docx formats."""
    repo = JobRepository()
    await repo.create(completed_job_with_result)
    job_id = completed_job_with_result.id

    formats = ["txt", "json", "srt", "vtt", "pdf", "docx"]
    for fmt in formats:
        resp = await client.get(
            f"/api/v1/transcription/jobs/{job_id}/export", params={"export_format": fmt}
        )
        assert resp.status_code == 200, f"Failed for format {fmt}"
        assert len(resp.content) > 0


@pytest.mark.asyncio
async def test_run_local_background_job_helper() -> None:
    """Validates local background runner helper function."""
    from app.api.v1.endpoints.transcription import _run_local_background_job

    job_id_str = str(uuid4())
    with patch("app.api.v1.endpoints.transcription.startup", new_callable=AsyncMock) as mock_start:
        with patch(
            "app.api.v1.endpoints.transcription.process_transcription_job", new_callable=AsyncMock
        ) as mock_proc:
            await _run_local_background_job(job_id_str)
            mock_start.assert_called_once()
            mock_proc.assert_called_once()
