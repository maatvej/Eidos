# filename: tests/test_events_endpoint.py
"""Integration tests for Server-Sent Events (SSE) progress streaming (app/api/v1/endpoints/events.py)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.domain.entities import JobStatus, TranscriptionJobEntity
from app.domain.exceptions import JobNotFoundError


@pytest.mark.asyncio
async def test_stream_job_progress_completed_job(client: AsyncClient) -> None:
    """Validates SSE stream emitting progress frame and terminating on completed status."""
    job_id = uuid4()
    mock_job = TranscriptionJobEntity(
        id=job_id,
        filename="test.wav",
        file_path="/tmp/test.wav",
        status=JobStatus.COMPLETED,
        progress_percentage=100.0,
        current_step="Completed",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with patch("app.api.v1.endpoints.events.JobRepository") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_job)
        mock_repo_cls.return_value = mock_repo

        response = await client.get(f"/api/v1/events/sse/{job_id}")
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        content = response.text
        assert "event: progress" in content
        assert "event: complete" in content
        assert str(job_id) in content


@pytest.mark.asyncio
async def test_stream_job_progress_in_progress_then_complete(client: AsyncClient) -> None:
    """Validates SSE stream iterating through in-progress state before completing."""
    job_id = uuid4()
    job_step1 = TranscriptionJobEntity(
        id=job_id,
        filename="test.wav",
        file_path="/tmp/test.wav",
        status=JobStatus.TRANSCRIBING,
        progress_percentage=50.0,
        current_step="Transcribing audio",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    job_step2 = TranscriptionJobEntity(
        id=job_id,
        filename="test.wav",
        file_path="/tmp/test.wav",
        status=JobStatus.COMPLETED,
        progress_percentage=100.0,
        current_step="Completed",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with (
        patch("app.api.v1.endpoints.events.JobRepository") as mock_repo_cls,
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(side_effect=[job_step1, job_step2])
        mock_repo_cls.return_value = mock_repo

        response = await client.get(f"/api/v1/events/sse/{job_id}")
        assert response.status_code == 200
        content = response.text
        assert "event: progress" in content
        assert "event: complete" in content
        mock_sleep.assert_called_once_with(0.5)


@pytest.mark.asyncio
async def test_stream_job_progress_client_disconnected(client: AsyncClient) -> None:
    """Validates SSE stream termination when client disconnects."""
    job_id = uuid4()

    with patch("starlette.requests.Request.is_disconnected", new_callable=AsyncMock) as mock_disc:
        mock_disc.return_value = True

        response = await client.get(f"/api/v1/events/sse/{job_id}")
        assert response.status_code == 200
        assert response.text == ""


@pytest.mark.asyncio
async def test_stream_job_progress_error_handling(client: AsyncClient) -> None:
    """Validates SSE stream emitting error frame when job lookup raises exception."""
    job_id = uuid4()

    with patch("app.api.v1.endpoints.events.JobRepository") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(side_effect=JobNotFoundError(str(job_id)))
        mock_repo_cls.return_value = mock_repo

        response = await client.get(f"/api/v1/events/sse/{job_id}")
        assert response.status_code == 200
        assert "event: error" in response.text
        assert "JobNotFoundError" in response.text or "not found" in response.text
