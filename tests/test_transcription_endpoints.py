# filename: tests/test_transcription_endpoints.py
"""Integration tests for Transcription endpoints (app/api/v1/endpoints/transcription.py)."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from httpx import AsyncClient

from app.api.v1.endpoints.transcription import export_transcript
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
    # 1. Missing job lookup -> 404
    missing_id = uuid4()
    resp_missing_job = await client.get(f"/api/v1/transcription/jobs/{missing_id}/audio")
    assert resp_missing_job.status_code == 404

    # 2. Create temp audio file and valid job
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

    # Fetch existing audio file
    resp = await client.get(f"/api/v1/transcription/jobs/{job_id}/audio")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"

    # 3. File missing on disk
    audio_file.unlink()
    resp_missing_file = await client.get(f"/api/v1/transcription/jobs/{job_id}/audio")
    assert resp_missing_file.status_code == 404
    assert "Audio file not found on disk" in resp_missing_file.json()["detail"]


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

    # 3. Missing both body and params -> 400 Bad Request
    resp_missing_args = await client.post(
        f"/api/v1/transcription/jobs/{job_with_res.id}/speaker-rename"
    )
    assert resp_missing_args.status_code == 400


@pytest.mark.asyncio
async def test_bulk_rename_speaker_success_json_and_query(client: AsyncClient, test_user) -> None:
    """Validates successful bulk speaker renaming with JSON payload and query params with ORM sync."""
    from asgiref.sync import sync_to_async

    from app.db.models import Transcription, TranscriptionStatus

    job_id = uuid4()
    job = TranscriptionJobEntity(
        id=job_id,
        filename="meeting.wav",
        file_path="/tmp/meeting.wav",
        status=JobStatus.COMPLETED,
        result=TranscriptionResult(
            utterances=[
                Utterance(speaker="SPEAKER_00", start=0.0, end=1.5, text="Hello everyone!"),
                Utterance(speaker="SPEAKER_01", start=1.6, end=3.0, text="Welcome!"),
            ],
            duration_seconds=3.0,
        ),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repo = JobRepository()
    await repo.create(job)

    # Also create linked Transcription ORM record
    trans_orm = await sync_to_async(Transcription.objects.create)(
        id=job_id,
        user=test_user,
        title="meeting.wav",
        original_filename="meeting.wav",
        file_path="/tmp/meeting.wav",
        status=TranscriptionStatus.COMPLETED,
        duration_seconds=3.0,
        transcription_text="SPEAKER_00: Hello everyone!\n\nSPEAKER_01: Welcome!",
    )

    # 1. Rename SPEAKER_00 to "Alice" via JSON payload
    resp_json = await client.post(
        f"/api/v1/transcription/jobs/{job_id}/speaker-rename",
        json={"old_speaker_label": "SPEAKER_00", "new_speaker_name": "Alice"},
    )
    assert resp_json.status_code == 200
    data = resp_json.json()
    assert data["result"]["utterances"][0]["speaker"] == "Alice"
    assert data["result"]["utterances"][1]["speaker"] == "SPEAKER_01"

    # Verify ORM model updated
    updated_trans = await sync_to_async(Transcription.objects.get)(id=job_id)
    assert "Alice: Hello everyone!" in updated_trans.transcription_text

    # 2. Rename SPEAKER_01 to "Bob" via query params
    resp_query = await client.post(
        f"/api/v1/transcription/jobs/{job_id}/speaker-rename",
        params={"old_speaker_label": "SPEAKER_01", "new_speaker_name": "Bob"},
    )
    assert resp_query.status_code == 200
    data_query = resp_query.json()
    assert data_query["result"]["utterances"][1]["speaker"] == "Bob"

    updated_trans2 = await sync_to_async(Transcription.objects.get)(id=job_id)
    assert "Bob: Welcome!" in updated_trans2.transcription_text


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
async def test_export_transcript_errors() -> None:
    """Validates 400 errors when job has no results or unsupported export format is requested."""
    job_id = uuid4()
    job_no_result = TranscriptionJobEntity(
        id=job_id,
        filename="pending.wav",
        file_path="/tmp/pending.wav",
        status=JobStatus.PENDING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repo = JobRepository()
    await repo.create(job_no_result)

    # 1. Export job without result -> raises HTTPException 400
    with pytest.raises(HTTPException) as exc_no_result:
        await export_transcript(job_id=job_id, export_format="txt")
    assert exc_no_result.value.status_code == 400
    assert "not ready for document export" in exc_no_result.value.detail

    # 2. Export with unsupported format -> raises HTTPException 400
    job_with_result = TranscriptionJobEntity(
        id=uuid4(),
        filename="ready.wav",
        file_path="/tmp/ready.wav",
        status=JobStatus.COMPLETED,
        result=TranscriptionResult(
            utterances=[Utterance(speaker="S1", start=0.0, end=1.0, text="Done")]
        ),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await repo.create(job_with_result)

    with pytest.raises(HTTPException) as exc_unsupported:
        await export_transcript(job_id=job_with_result.id, export_format="invalid_format")  # type: ignore[arg-type]
    assert exc_unsupported.value.status_code == 400
    assert "Unsupported export format" in exc_unsupported.value.detail


@pytest.mark.asyncio
async def test_run_local_background_job_helper() -> None:
    """Validates local background runner helper function."""
    from app.api.v1.endpoints.transcription import _run_local_background_job

    job_id_str = str(uuid4())
    with (
        patch("app.api.v1.endpoints.transcription.startup", new_callable=AsyncMock) as mock_start,
        patch(
            "app.api.v1.endpoints.transcription.process_transcription_job", new_callable=AsyncMock
        ) as mock_proc,
    ):
        await _run_local_background_job(job_id_str)
        mock_start.assert_called_once()
        mock_proc.assert_called_once()


@pytest.mark.asyncio
async def test_upload_audio_file_streaming_success(client: AsyncClient) -> None:
    """Validates streaming file upload endpoint, entity persistence, and background task enqueuing."""
    file_content = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00"
    files = {"file": ("test_stream.wav", file_content, "audio/wav")}

    with patch(
        "app.api.v1.endpoints.transcription._run_local_background_job", new_callable=AsyncMock
    ):
        resp = await client.post("/api/v1/transcription/upload", files=files)
        assert resp.status_code == 202
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "QUEUED_LOCAL"
        assert data["created_by"] == "test_admin"
