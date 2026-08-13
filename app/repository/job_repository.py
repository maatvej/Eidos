# filename: app/repository/job_repository.py
"""Async database repository implementation using Django ORM for transcription jobs and history tracking."""

from datetime import UTC, datetime
from uuid import UUID

from asgiref.sync import sync_to_async

from app.db.models import Transcription, TranscriptionJob
from app.domain.entities import JobStatus, TranscriptionJobEntity, TranscriptionResult
from app.domain.exceptions import JobNotFoundError


class JobRepository:
    """Async repository interfacing with Django ORM for job persistence and user history sync."""

    def __init__(self, session=None) -> None:
        self.session = session

    async def create(self, job: TranscriptionJobEntity) -> TranscriptionJobEntity:
        await TranscriptionJob.objects.acreate(
            id=str(job.id),
            filename=job.filename,
            file_path=job.file_path,
            status=job.status.value,
            progress_percentage=job.progress_percentage,
            current_step=job.current_step,
            result_json=job.result.model_dump_json() if job.result else None,
            error_message=job.error_message,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
        return job

    async def get_by_id(self, job_id: UUID) -> TranscriptionJobEntity:
        try:
            model = await TranscriptionJob.objects.aget(id=str(job_id))
        except TranscriptionJob.DoesNotExist:
            raise JobNotFoundError(str(job_id))

        result_entity = (
            TranscriptionResult.model_validate_json(model.result_json)
            if model.result_json
            else None
        )

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

    async def update_progress(
        self,
        job_id: UUID,
        status: JobStatus,
        progress: float,
        step: str,
        result: TranscriptionResult | None = None,
        error_message: str | None = None,
    ) -> None:
        try:
            model = await TranscriptionJob.objects.aget(id=str(job_id))
        except TranscriptionJob.DoesNotExist:
            raise JobNotFoundError(str(job_id))

        model.status = status.value
        model.progress_percentage = progress
        model.current_step = step
        model.updated_at = datetime.now(UTC)

        if result:
            model.result_json = result.model_dump_json()
        if error_message:
            model.error_message = error_message

        await sync_to_async(model.save)()

        # Synchronize corresponding Transcription ORM model if present
        try:
            trans_model = await sync_to_async(Transcription.objects.get)(id=job_id)
            trans_model.status = status.value.lower()
            trans_model.updated_at = datetime.now(UTC)
            if result:
                full_text = " ".join([u.text for u in result.utterances])
                trans_model.transcription_text = full_text
                trans_model.duration_seconds = result.duration_seconds
                trans_model.language = result.detected_language or trans_model.language

                created_at_str = trans_model.created_at.strftime("%d.%m.%Y %H:%M")
                if result.analysis and result.analysis.title:
                    trans_model.title = f"{result.analysis.title} ({created_at_str})"
                elif not trans_model.title or trans_model.title == trans_model.original_filename:
                    trans_model.title = (
                        f"Расшифровка {trans_model.original_filename} ({created_at_str})"
                    )
            await sync_to_async(trans_model.save)()
        except Transcription.DoesNotExist:
            pass
        except Exception:
            pass
