# filename: app/workers/tasks.py
"""Background task workers executing end-to-end processing pipelines."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from asgiref.sync import sync_to_async

from app.core.logging import logger
from app.core.metrics import ACTIVE_JOBS, PROCESSED_AUDIO_SECONDS
from app.core.profiler import profile_worker_task
from app.db.models import Transcription
from app.db.session import AsyncSessionLocal
from app.domain.entities import JobStatus, VoiceProfileEntity
from app.ml.audio_processor import FFmpegAudioProcessor
from app.ml.inference_engine import InferenceEngine
from app.ml.llm_processor import LLMIntelligenceEngine
from app.repository.job_repository import JobRepository, VoiceProfileRepository


# Global model instance within worker process lifecycle
inference_engine = InferenceEngine()


async def startup(ctx: dict) -> None:
    """Worker startup lifecycle hook."""
    logger.info("Initializing background worker ML engines...")
    inference_engine.load_models()
    ctx["ffmpeg"] = FFmpegAudioProcessor()
    ctx["llm"] = LLMIntelligenceEngine()


@profile_worker_task(name="background_transcription_worker_pipeline", subfolder="workers")
async def process_transcription_job(ctx: dict, job_id_str: str) -> None:
    """Async task orchestrator executing ingestion, VAD, Whisper, Diarization, and LLM extraction."""
    job_id = UUID(job_id_str)
    ffmpeg: FFmpegAudioProcessor = ctx.get("ffmpeg") or FFmpegAudioProcessor()
    llm: LLMIntelligenceEngine = ctx.get("llm") or LLMIntelligenceEngine()

    ACTIVE_JOBS.labels(status="processing").inc()
    async with AsyncSessionLocal() as session:
        repo = JobRepository(session)
        voice_repo = VoiceProfileRepository(session)
        job = await repo.get_by_id(job_id)

        try:
            # Retrieve associated user voice profiles from DB memory
            user_profiles: list[VoiceProfileEntity] = []
            try:
                trans_record = await sync_to_async(Transcription.objects.get)(id=job_id)
                if trans_record and trans_record.user_id:
                    user_profiles = await voice_repo.get_user_voice_profiles(trans_record.user_id)
                    logger.info(
                        f"Loaded {len(user_profiles)} saved voice profiles for user {trans_record.user_id}."
                    )
            except Exception as user_fetch_err:
                logger.debug(f"User voice profile lookup skipped ({user_fetch_err}).")

            # 1. Preprocessing
            await repo.update_progress(
                job_id, JobStatus.PREPROCESSING, 15.0, "Нормализация аудио и VAD"
            )
            normalized_path = Path(f"{job.file_path}_16k.wav")
            try:
                await ffmpeg.normalize_and_vad(Path(job.file_path), normalized_path)
                audio_to_process = normalized_path
            except Exception as ffmpeg_err:
                logger.warning(f"FFmpeg normalization skipped ({ffmpeg_err}). Using raw file.")
                audio_to_process = Path(job.file_path)

            # 2. Speech Recognition & Diarization with Voice Memory Matching
            await repo.update_progress(
                job_id,
                JobStatus.TRANSCRIBING,
                45.0,
                "Распознавание речи и диаризация спикеров",
            )
            transcription_result = await inference_engine.process_audio(
                audio_to_process, voice_profiles=user_profiles
            )

            # 3. LLM Post-processing
            await repo.update_progress(
                job_id,
                JobStatus.POST_PROCESSING,
                85.0,
                "Генерация краткой выжимки и задач",
            )
            full_text = " ".join([u.text for u in transcription_result.utterances])
            analysis = await llm.extract_intelligence(
                full_text, language=transcription_result.detected_language
            )
            analysis.timestamp = datetime.now(UTC).strftime("%d.%m.%Y %H:%M")
            transcription_result.analysis = analysis

            # 4. Completion
            await repo.update_progress(
                job_id,
                JobStatus.COMPLETED,
                100.0,
                "Завершено",
                result=transcription_result,
            )
            PROCESSED_AUDIO_SECONDS.inc(transcription_result.duration_seconds)
            logger.info(f"Successfully finished processing transcription job {job_id}")

            # Cleanup temporary normalized WAV file if created
            if normalized_path.exists() and normalized_path != Path(job.file_path):
                normalized_path.unlink()

        except Exception as err:
            logger.error(f"Error executing job {job_id}: {err!s}", exc_info=True)
            await repo.update_progress(
                job_id, JobStatus.FAILED, 0.0, "Ошибка обработки", error_message=str(err)
            )
        finally:
            ACTIVE_JOBS.labels(status="processing").dec()


class WorkerSettings:
    functions = [process_transcription_job]
    on_startup = startup
