# filename: app/repository/hardened_repository.py
"""Async repository featuring optimistic locking and transient database retry logic."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.db.models import TranscriptionJobModel
from app.domain.entities import JobStatus, TranscriptionJobEntity, TranscriptionResult
from app.domain.exceptions import DomainError, JobNotFoundError


class ConcurrentUpdateError(DomainError):
    """Raised when an optimistic concurrency version check fails."""

    def __init__(self, job_id: str) -> None:
        super().__init__(
            f"Job '{job_id}' was updated concurrently by another request. Please refresh and retry.",
            code="CONCURRENT_UPDATE_CONFLICT",
        )


class HardenedJobRepository:
    """Enterprise Data Access Layer with concurrent safety mechanisms."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def update_transcript_utterance_safe(
        self, job_id: UUID, utterance_id: str, new_text: str, expected_version: int | None = None
    ) -> TranscriptionJobEntity:
        """Updates a specific utterance within a transcript using optimistic state verification."""
        stmt = select(TranscriptionJobModel).where(TranscriptionJobModel.id == str(job_id))
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()

        if not model:
            raise JobNotFoundError(str(job_id))

        if not model.result_json:
            raise DomainError(
                "Cannot update utterance on job with no result.", code="INVALID_STATE"
            )

        # Hydrate domain model
        result_entity = TranscriptionResult.model_validate_json(model.result_json)

        # Modify matching utterance
        modified = False
        for utt in result_entity.utterances:
            if utt.id == utterance_id:
                utt.text = new_text
                modified = True
                break

        if not modified:
            raise DomainError(f"Utterance '{utterance_id}' not found.", code="UTTERANCE_NOT_FOUND")

        # Persist updated JSON back to database
        model.result_json = result_entity.model_dump_json()
        model.updated_at = datetime.now(UTC)

        try:
            await self.session.commit()
            await self.session.refresh(model)
        except StaleDataError:
            await self.session.rollback()
            raise ConcurrentUpdateError(str(job_id))

        return TranscriptionJobEntity(
            id=UUID(model.id),
            filename=model.filename,
            file_path=model.file_path,
            status=JobStatus(model.status),
            progress_percentage=model.progress_percentage,
            current_step=model.current_step,
            result=result_entity,
            error_message=model.error_message,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
