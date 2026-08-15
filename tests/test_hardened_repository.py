# filename: tests/test_hardened_repository.py
"""Unit tests for HardenedJobRepository (app/repository/hardened_repository.py)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm.exc import StaleDataError

from app.db.models import TranscriptionJobModel
from app.domain.entities import TranscriptionResult, Utterance
from app.domain.exceptions import DomainError, JobNotFoundError
from app.repository.hardened_repository import (
    ConcurrentUpdateError,
    HardenedJobRepository,
)


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


def test_concurrent_update_error_properties() -> None:
    """Validates ConcurrentUpdateError exception properties."""
    err = ConcurrentUpdateError("job-123")
    assert err.code == "CONCURRENT_UPDATE_CONFLICT"
    assert "job-123" in str(err)


@pytest.mark.asyncio
async def test_update_transcript_utterance_safe_success(mock_session: AsyncMock) -> None:
    """Validates successful utterance modification and persistence."""
    job_id = uuid4()
    utt = Utterance(speaker="SPEAKER_00", start=0.0, end=1.0, text="Initial text")
    result = TranscriptionResult(utterances=[utt], duration_seconds=1.0)

    model = TranscriptionJobModel(
        id=str(job_id),
        filename="test.wav",
        file_path="/tmp/test.wav",
        status="COMPLETED",
        progress_percentage=100.0,
        current_step="Completed",
        result_json=result.model_dump_json(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_scalar = MagicMock()
    mock_scalar.scalar_one_or_none.return_value = model
    mock_session.execute.return_value = mock_scalar

    with patch("app.repository.hardened_repository.select"):
        repo = HardenedJobRepository(session=mock_session)
        updated_job = await repo.update_transcript_utterance_safe(
            job_id=job_id,
            utterance_id=utt.id,
            new_text="Updated text",
        )

        assert updated_job.result is not None
        assert updated_job.result.utterances[0].text == "Updated text"
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once_with(model)


@pytest.mark.asyncio
async def test_update_transcript_utterance_safe_errors(mock_session: AsyncMock) -> None:
    """Validates error scenarios: job not found, job with no result, utterance not found, and stale data error."""
    job_id = uuid4()
    repo = HardenedJobRepository(session=mock_session)

    with patch("app.repository.hardened_repository.select"):
        # 1. Job not found
        mock_scalar_none = MagicMock()
        mock_scalar_none.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_scalar_none

        with pytest.raises(JobNotFoundError):
            await repo.update_transcript_utterance_safe(job_id, "u-1", "text")

        # 2. Job with no result_json
        model_no_res = TranscriptionJobModel(
            id=str(job_id),
            filename="test.wav",
            file_path="/tmp/test.wav",
            status="PENDING",
            progress_percentage=0.0,
            result_json=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_scalar_no_res = MagicMock()
        mock_scalar_no_res.scalar_one_or_none.return_value = model_no_res
        mock_session.execute.return_value = mock_scalar_no_res

        with pytest.raises(DomainError) as exc_no_res:
            await repo.update_transcript_utterance_safe(job_id, "u-1", "text")
        assert exc_no_res.value.code == "INVALID_STATE"

        # 3. Utterance ID not found in result
        utt = Utterance(speaker="S1", start=0.0, end=1.0, text="Hi")
        result = TranscriptionResult(utterances=[utt])
        model_with_res = TranscriptionJobModel(
            id=str(job_id),
            filename="test.wav",
            file_path="/tmp/test.wav",
            status="COMPLETED",
            progress_percentage=100.0,
            result_json=result.model_dump_json(),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_scalar_with_res = MagicMock()
        mock_scalar_with_res.scalar_one_or_none.return_value = model_with_res
        mock_session.execute.return_value = mock_scalar_with_res

        with pytest.raises(DomainError) as exc_no_utt:
            await repo.update_transcript_utterance_safe(job_id, "non-existent-utt-id", "text")
        assert exc_no_utt.value.code == "UTTERANCE_NOT_FOUND"

        # 4. StaleDataError -> ConcurrentUpdateError
        mock_session.commit.side_effect = StaleDataError(
            "Row was modified by another transaction"
        )
        with pytest.raises(ConcurrentUpdateError) as exc_stale:
            await repo.update_transcript_utterance_safe(job_id, utt.id, "new text")
        assert exc_stale.value.code == "CONCURRENT_UPDATE_CONFLICT"
        mock_session.rollback.assert_called_once()
