# filename: tests/test_api.py
"""Integration test suite validating REST endpoints, Django auth bridge, and ORM operations."""

from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.domain.entities import (
    JobStatus,
    TranscriptionJobEntity,
    TranscriptionResult,
    Utterance,
)
from app.repository.job_repository import JobRepository


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """Validates root health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["architecture"] == "django-fastapi-hybrid"


@pytest.mark.asyncio
async def test_auth_me_endpoint(client: AsyncClient) -> None:
    """Validates Django authentication bridge user profile endpoint."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "test_admin"
    assert data["is_superuser"] is True


@pytest.mark.asyncio
async def test_audio_upload_endpoint(client: AsyncClient) -> None:
    """Validates audio file ingestion with Django permission enforcement."""
    file_content = b"RIFF....WAVEfmt ....data...."
    files = {"file": ("test_meeting.wav", file_content, "audio/wav")}

    with patch("app.api.v1.endpoints.transcription.process_transcription_job") as mock_job:
        mock_job.return_value = None
        response = await client.post("/api/v1/transcription/upload", files=files)
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "QUEUED_LOCAL"
        assert data["created_by"] == "test_admin"


@pytest.mark.asyncio
async def test_speaker_rename_endpoint(client: AsyncClient) -> None:
    """Validates async speaker rename operation using Django ORM repository."""
    job_id = uuid4()
    repo = JobRepository()

    result = TranscriptionResult(
        utterances=[Utterance(speaker="SPEAKER_00", start=0.0, end=1.5, text="Welcome everyone.")]
    )
    job = TranscriptionJobEntity(
        id=job_id,
        filename="test.wav",
        file_path="/tmp/test.wav",
        status=JobStatus.COMPLETED,
        progress_percentage=100.0,
        result=result,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await repo.create(job)

    response = await client.post(
        f"/api/v1/transcription/jobs/{job_id}/speaker-rename",
        params={"old_speaker_label": "SPEAKER_00", "new_speaker_name": "Alice"},
    )
    assert response.status_code == 200
    updated_data = response.json()
    assert updated_data["result"]["utterances"][0]["speaker"] == "Alice"


@pytest.mark.asyncio
async def test_root_ui_authenticated(client: AsyncClient) -> None:
    """Validates that authenticated user can access the UI at root path."""
    response = await client.get("/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_spa_deep_routes_authenticated(client: AsyncClient) -> None:
    """Validates that authenticated user can access all deep SPA routes."""
    test_routes = [
        "/dashboard",
        "/studio",
        f"/jobs/{uuid4()}",
        f"/transcriptions/{uuid4()}",
        "/account",
        "/account/history",
        "/account/profile",
        "/account/security",
    ]
    for route in test_routes:
        response = await client.get(route)
        assert response.status_code == 200
        assert "Eidos" in response.text


@pytest.mark.asyncio
async def test_root_ui_unauthenticated(client: AsyncClient) -> None:
    """Validates that unauthenticated user is redirected to Django Allauth login."""
    from app.main import app

    app.dependency_overrides.clear()
    try:
        response = await client.get("/", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/accounts/login/"

        # Test deep link redirect preserves query and path
        deep_job_path = f"/jobs/{uuid4()}"
        resp_deep = await client.get(deep_job_path, follow_redirects=False)
        assert resp_deep.status_code == 302
        assert resp_deep.headers["location"] == f"/accounts/login/?next={deep_job_path}"
    finally:
        pass
