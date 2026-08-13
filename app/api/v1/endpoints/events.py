# filename: app/api/v1/endpoints/events.py
"""Server-Sent Events (SSE) router providing lightweight progress streaming to clients."""

import asyncio
import json
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.logging import logger
from app.db.session import AsyncSessionLocal
from app.domain.entities import JobStatus
from app.repository.job_repository import JobRepository

router = APIRouter(prefix="/events", tags=["Real-Time Progress Events"])


@router.get("/sse/{job_id}")
async def stream_job_progress(job_id: UUID, request: Request) -> StreamingResponse:
    """Streams real-time job execution updates using Server-Sent Events (SSE)."""

    async def event_generator() -> AsyncGenerator[str, None]:
        last_progress = -1.0

        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                logger.info(f"SSE client disconnected for job: {job_id}")
                break

            try:
                # Open a fresh AsyncSession on each tick to bypass SQLAlchemy session caching
                async with AsyncSessionLocal() as session:
                    repo = JobRepository(session)
                    job = await repo.get_by_id(job_id)

                    # Emit frame if progress percentage or step message changed
                    if job.progress_percentage != last_progress:
                        last_progress = job.progress_percentage
                        data_payload = json.dumps(
                            {
                                "job_id": str(job.id),
                                "status": job.status.value,
                                "progress": job.progress_percentage,
                                "step": job.current_step,
                                "error": job.error_message,
                            }
                        )
                        yield f"event: progress\ndata: {data_payload}\n\n"

                    # Terminate stream on completion, cancellation, or failure
                    if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                        complete_payload = json.dumps({"status": job.status.value})
                        yield f"event: complete\ndata: {complete_payload}\n\n"
                        break

            except Exception as err:
                error_payload = json.dumps({"error": str(err)})
                yield f"event: error\ndata: {error_payload}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
