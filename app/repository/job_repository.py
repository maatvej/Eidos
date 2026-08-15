# filename: app/repository/job_repository.py
"""Async database repository implementation using Django ORM for transcription jobs and history tracking."""

from datetime import UTC, datetime
from uuid import UUID

from asgiref.sync import sync_to_async

from app.core.logging import logger
from app.core.profiler import profile_async, profile_sync
from app.db.models import Transcription, TranscriptionJob, VoiceProfile
from app.domain.entities import (
    JobStatus,
    TranscriptionJobEntity,
    TranscriptionResult,
    Utterance,
    VoiceProfileEntity,
)
from app.domain.exceptions import JobNotFoundError
from app.ml.inference_engine import InferenceEngine


@profile_sync(name="format_speaker_transcription", subfolder="repository")
def format_speaker_transcription(utterances: list[Utterance]) -> str:
    """Formats a list of utterances into a structured speaker-separated transcript text.

    Args:
        utterances: Sequence of speech utterance domain entities.

    Returns:
        Structured multiline transcript string formatted with speaker names and speech turns.

    Example:
        >>> format_speaker_transcription(
        ...     [
        ...         Utterance(speaker="Спикер 1", start=0.0, end=2.0, text="Привет всем!"),
        ...         Utterance(speaker="Спикер 2", start=2.1, end=4.0, text="Добрый день!"),
        ...     ]
        ... )
        'Спикер 1: Привет всем!\\n\\nСпикер 2: Добрый день!'
    """
    if not utterances:
        return ""

    formatted_blocks: list[str] = []
    for utt in utterances:
        clean_text = utt.text.strip()
        if not clean_text:
            continue
        if utt.speaker and utt.speaker.strip():
            formatted_blocks.append(f"{utt.speaker.strip()}: {clean_text}")
        else:
            formatted_blocks.append(clean_text)

    return "\n\n".join(formatted_blocks)


class JobRepository:
    """Async repository interfacing with Django ORM for job persistence and user history sync."""

    def __init__(self, session=None) -> None:
        self.session = session

    @profile_async(name="repo_job_create", subfolder="repository")
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

    @profile_async(name="repo_job_get_by_id", subfolder="repository")
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

    @profile_async(name="repo_job_update_progress", subfolder="repository")
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
                formatted_text = format_speaker_transcription(result.utterances)
                trans_model.transcription_text = formatted_text
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
            logger.debug(f"Transcription record {job_id} does not exist for sync.")
        except Exception as err:
            logger.warning(f"Error syncing user transcription record {job_id}: {err}")


class VoiceProfileRepository:
    """Async repository managing user speaker voice profiles and embedding centroids."""

    def __init__(self, session=None) -> None:
        self.session = session

    @profile_async(name="repo_voice_get_profiles", subfolder="repository")
    async def get_user_voice_profiles(self, user_id: int) -> list[VoiceProfileEntity]:
        """Retrieves all voice profiles belonging to a specific user.

        Args:
            user_id: Target user identifier.

        Returns:
            List of domain voice profile entities.

        Example:
            >>> profiles = await repo.get_user_voice_profiles(user_id=1)
        """

        @sync_to_async(thread_sensitive=True)
        def _fetch_profiles() -> list[VoiceProfile]:
            return list(VoiceProfile.objects.filter(user_id=user_id).order_by("-updated_at"))

        models = await _fetch_profiles()
        return [
            VoiceProfileEntity(
                id=m.id,
                user_id=m.user_id,
                name=m.name,
                embedding=m.embedding or [],
                samples_count=m.samples_count,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in models
        ]

    @profile_async(name="repo_voice_get_profile_by_id", subfolder="repository")
    async def get_voice_profile_by_id(
        self, profile_id: UUID, user_id: int
    ) -> VoiceProfileEntity | None:
        """Retrieves a single voice profile by its ID and user ownership.

        Args:
            profile_id: Unique UUID of the voice profile.
            user_id: ID of the owning user.

        Returns:
            VoiceProfileEntity if found, otherwise None.

        Example:
            >>> profile = await repo.get_voice_profile_by_id(uuid4(), 1)
        """
        try:
            model = await sync_to_async(VoiceProfile.objects.get)(id=profile_id, user_id=user_id)
            return VoiceProfileEntity(
                id=model.id,
                user_id=model.user_id,
                name=model.name,
                embedding=model.embedding or [],
                samples_count=model.samples_count,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
        except VoiceProfile.DoesNotExist:
            return None

    @profile_async(name="repo_voice_save_profile", subfolder="repository")
    async def save_or_update_voice_profile(
        self,
        user_id: int,
        name: str,
        embedding: list[float],
    ) -> VoiceProfileEntity:
        """Persists a new voice profile or updates an existing one using running average centroids.

        Args:
            user_id: User identifier owning this speaker profile.
            name: Human-readable speaker name or alias.
            embedding: Extracted normalized acoustic feature vector.

        Returns:
            Persisted VoiceProfileEntity domain model.

        Example:
            >>> profile = await repo.save_or_update_voice_profile(1, "Alice", [0.1, 0.2])
        """
        clean_name = name.strip()

        @sync_to_async(thread_sensitive=True)
        def _persist() -> VoiceProfileEntity:
            try:
                model = VoiceProfile.objects.get(user_id=user_id, name=clean_name)
                # Running centroid update
                updated_emb = InferenceEngine.update_profile_embedding(
                    existing_embedding=model.embedding or [],
                    new_embedding=embedding,
                    samples_count=model.samples_count,
                )
                model.embedding = updated_emb
                model.samples_count += 1
                model.updated_at = datetime.now(UTC)
                model.save()
            except VoiceProfile.DoesNotExist:
                model = VoiceProfile.objects.create(
                    user_id=user_id,
                    name=clean_name,
                    embedding=embedding,
                    samples_count=1,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )

            return VoiceProfileEntity(
                id=model.id,
                user_id=model.user_id,
                name=model.name,
                embedding=model.embedding or [],
                samples_count=model.samples_count,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )

        return await _persist()

    @profile_async(name="repo_voice_delete_profile", subfolder="repository")
    async def delete_voice_profile(self, profile_id: UUID, user_id: int) -> bool:
        """Deletes a voice profile if it exists and belongs to the specified user.

        Args:
            profile_id: Unique UUID of the profile to delete.
            user_id: Identifier of the authenticated user.

        Returns:
            True if deleted successfully, False if not found.

        Example:
            >>> deleted = await repo.delete_voice_profile(uuid4(), 1)
        """

        @sync_to_async(thread_sensitive=True)
        def _delete() -> bool:
            try:
                model = VoiceProfile.objects.get(id=profile_id, user_id=user_id)
                model.delete()
                return True
            except VoiceProfile.DoesNotExist:
                return False

        return await _delete()
