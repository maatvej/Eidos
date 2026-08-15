# filename: app/api/v1/endpoints/transcription.py
"""FastAPI router managing transcription job lifecycle, upload ingestion, status polling,
inline editing, bulk speaker renames, audio file serving, and multi-format exports
with Django Auth & Permission enforcement.
"""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from asgiref.sync import sync_to_async
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.logging import logger
from app.core.profiler import profile_async, profile_sync
from app.core.security import (
    DjangoUserSchema,
    RequirePermission,
    get_current_django_user,
)
from app.db.models import Transcription
from app.domain.entities import JobStatus, TranscriptionJobEntity
from app.domain.exceptions import JobNotFoundError
from app.repository.job_repository import JobRepository
from app.schemas.account import SpeakerRenameRequest
from app.services.export_service import ExportService
from app.workers.tasks import process_transcription_job, startup


router = APIRouter(prefix="/transcription", tags=["Transcription Management"])
export_service = ExportService()


async def _run_local_background_job(job_id_str: str) -> None:
    """Helper function executing background pipeline tasks locally."""
    ctx: dict[str, Any] = {}
    await startup(ctx)
    await process_transcription_job(ctx, job_id_str)


@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(RequirePermission("db.add_transcriptionjob"))],
)
@profile_async(name="transcription_upload_endpoint", subfolder="transcription")
async def upload_audio_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: DjangoUserSchema = Depends(get_current_django_user),
) -> dict[str, Any]:
    """Handles audio upload, persists initial entity using Django ORM, and routes task to background execution.

    Requires Django Permission: 'db.add_transcriptionjob'
    """
    job_id = uuid4()
    safe_filename = file.filename or "uploaded_audio.wav"
    target_path = settings.STORAGE_DIR / f"{job_id}_{safe_filename}"

    # Asynchronously stream upload in chunks directly to disk to prevent RAM spikes and high latency
    @profile_sync(name="audio_upload_chunking_stream", subfolder="transcription")
    def _write_file_stream() -> None:
        with open(target_path, "wb") as buffer:
            while True:
                chunk = file.file.read(settings.UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                buffer.write(chunk)

    try:
        await asyncio.to_thread(_write_file_stream)
    finally:
        await file.close()

    job_entity = TranscriptionJobEntity(
        id=job_id,
        filename=safe_filename,
        file_path=str(target_path),
        status=JobStatus.PENDING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    repo = JobRepository()
    await repo.create(job_entity)

    # Also persist to Transcription ORM model for user history
    now_utc = datetime.now(UTC)
    timestamp_str = now_utc.strftime("%d.%m.%Y %H:%M")
    initial_title = f"Расшифровка: {safe_filename} ({timestamp_str})"

    await sync_to_async(Transcription.objects.create)(
        id=job_id,
        user_id=current_user.id,
        title=initial_title,
        original_filename=safe_filename,
        file_path=str(target_path),
        audio_url=f"/api/v1/account/transcriptions/{job_id}/audio",
        status="pending",
        created_at=now_utc,
    )

    background_tasks.add_task(_run_local_background_job, str(job_id))
    logger.info(
        f"User '{current_user.username}' enqueued job {job_id} in local background task runner."
    )

    return {
        "job_id": str(job_id),
        "status": "QUEUED_LOCAL",
        "created_by": current_user.username,
    }


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: UUID,
    current_user: DjangoUserSchema = Depends(get_current_django_user),
) -> TranscriptionJobEntity:
    """Polls job status, progress percentage, current step, and result."""
    repo = JobRepository()
    try:
        return await repo.get_by_id(job_id)
    except JobNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found."
        )


@router.get("/jobs/{job_id}/audio")
async def get_job_audio(
    job_id: UUID,
    current_user: DjangoUserSchema = Depends(get_current_django_user),
) -> FileResponse:
    """Streams uploaded audio file to frontend player."""
    repo = JobRepository()
    try:
        job = await repo.get_by_id(job_id)
    except JobNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found."
        )

    audio_path = Path(job.file_path)
    if not audio_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Audio file not found on disk."
        )

    ext = audio_path.suffix.lower()
    content_types = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
        ".webm": "audio/webm",
    }
    media_type = content_types.get(ext, "application/octet-stream")
    return FileResponse(path=audio_path, media_type=media_type, filename=job.filename)


@router.post(
    "/jobs/{job_id}/cancel",
    dependencies=[Depends(RequirePermission("db.change_transcriptionjob"))],
)
async def cancel_job(
    job_id: UUID,
    current_user: DjangoUserSchema = Depends(get_current_django_user),
) -> dict[str, str]:
    """Signals job cancellation for active or pending processing operations."""
    repo = JobRepository()
    job = await repo.get_by_id(job_id)

    if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job in state '{job.status}'.",
        )

    await repo.update_progress(
        job_id=job_id,
        status=JobStatus.CANCELLED,
        progress=job.progress_percentage,
        step=f"Cancelled by user '{current_user.username}'",
    )
    return {"message": "Job cancellation signal recorded successfully."}


@router.post(
    "/jobs/{job_id}/speaker-rename",
    dependencies=[Depends(RequirePermission("db.change_transcriptionjob"))],
)
async def bulk_rename_speaker(
    job_id: UUID,
    payload: SpeakerRenameRequest | None = None,
    old_speaker_label: str | None = None,
    new_speaker_name: str | None = None,
    current_user: DjangoUserSchema = Depends(get_current_django_user),
) -> TranscriptionJobEntity:
    """Globally renames speaker tags across the entire transcript.

    Supports both JSON body payload and URL query parameters for full interoperability.
    """
    target_old = (payload.old_speaker_label if payload else old_speaker_label) or ""
    target_new = (payload.new_speaker_name if payload else new_speaker_name) or ""

    if not target_old.strip() or not target_new.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both 'old_speaker_label' and 'new_speaker_name' must be provided.",
        )

    repo = JobRepository()
    job = await repo.get_by_id(job_id)

    if not job.result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot rename speakers on a job without completed transcription results.",
        )

    renamed_count = 0
    for utt in job.result.utterances:
        if utt.speaker == target_old:
            utt.speaker = target_new
            renamed_count += 1

    if renamed_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No utterances found matching speaker label '{target_old}'.",
        )

    await repo.update_progress(
        job_id=job_id,
        status=job.status,
        progress=job.progress_percentage,
        step=job.current_step,
        result=job.result,
    )
    return job


@router.get("/jobs/{job_id}/export")
async def export_transcript(
    job_id: UUID,
    export_format: Literal["txt", "srt", "vtt", "json", "pdf", "docx"],
    current_user: DjangoUserSchema = Depends(get_current_django_user),
) -> Response:
    """Generates dynamic multi-format exports (TXT, SRT, VTT, JSON, PDF, DOCX)."""
    repo = JobRepository()
    job = await repo.get_by_id(job_id)

    if not job.result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job results are not ready for document export.",
        )

    filename_base = f"transcript_{job_id}"

    if export_format == "txt":
        txt_data = export_service.to_txt(job.result)
        return Response(
            content=txt_data,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename_base}.txt"},
        )
    if export_format == "json":
        return Response(
            content=job.result.model_dump_json(indent=2),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename_base}.json"},
        )
    if export_format == "srt":
        srt_data = export_service.to_srt(job.result)
        return Response(
            content=srt_data,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename_base}.srt"},
        )
    if export_format == "vtt":
        vtt_data = export_service.to_vtt(job.result)
        return Response(
            content=vtt_data,
            media_type="text/vtt; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename_base}.vtt"},
        )
    if export_format == "pdf":
        pdf_bytes = export_service.to_pdf(job.result)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename_base}.pdf"},
        )
    if export_format == "docx":
        docx_bytes = export_service.to_docx(job.result)
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={filename_base}.docx"},
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported export format."
    )
