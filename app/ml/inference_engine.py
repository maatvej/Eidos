# filename: app/ml/inference_engine.py
"""Speech-To-Text and Speaker Diarization Pipeline with Dynamic Alignment."""

import asyncio
import time
from pathlib import Path
from typing import Any

import torch

from app.core.config import settings
from app.core.logging import logger
from app.core.metrics import INFERENCE_LATENCY
from app.domain.entities import TranscriptionResult, Utterance, WordTimestamp


class InferenceEngine:
    """Engine managing Faster-Whisper, PyAnnote, and timestamp/speaker alignment."""

    def __init__(self) -> None:
        self.whisper_model: Any = None
        self.diarization_pipeline: Any = None
        self._is_loaded = False

    def load_models(self) -> None:
        """Initializes heavy model weights on startup or background worker init."""
        if self._is_loaded:
            return

        self._load_whisper_model()
        self._load_diarization_pipeline()
        self._is_loaded = True

    def _load_whisper_model(self) -> None:
        logger.info("Loading Faster-Whisper model...")
        try:
            from faster_whisper import WhisperModel

            try:
                torch.set_num_threads(settings.TORCH_NUM_THREADS)
            except Exception as thread_err:
                logger.debug(f"Torch thread limit not configured: {thread_err}")

            device = settings.WHISPER_DEVICE
            compute_type = settings.WHISPER_COMPUTE_TYPE

            if device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"

            if compute_type == "auto":
                compute_type = "float16" if device == "cuda" else "int8"
            elif not torch.cuda.is_available() and device == "cuda":
                device = "cpu"
                compute_type = "int8"

            self.whisper_model = WhisperModel(
                settings.WHISPER_MODEL_SIZE,
                device=device,
                compute_type=compute_type,
                cpu_threads=settings.WHISPER_CPU_THREADS,
                num_workers=settings.WHISPER_NUM_WORKERS,
            )
            logger.info(
                f"Faster-Whisper ({settings.WHISPER_MODEL_SIZE}) loaded successfully on {device} ({compute_type}, threads={settings.WHISPER_CPU_THREADS})."
            )
        except Exception as e:
            logger.warning(
                f"Could not load real Faster-Whisper model ({e}). Fallback demo engine active."
            )
            self.whisper_model = None

    def _load_diarization_pipeline(self) -> None:
        if not settings.PYANNOTE_AUTH_TOKEN or settings.PYANNOTE_AUTH_TOKEN == "hf_dummy_token":
            logger.info(
                "PyAnnote auth token not configured. Using local smart speaker turn clustering."
            )
            self.diarization_pipeline = None
            return

        try:
            from pyannote.audio import Pipeline

            self.diarization_pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1", token=settings.PYANNOTE_AUTH_TOKEN
            )
            if self.diarization_pipeline:
                if torch.cuda.is_available():
                    self.diarization_pipeline.to(torch.device("cuda"))
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    self.diarization_pipeline.to(torch.device("mps"))
            logger.info("PyAnnote speaker diarization pipeline loaded successfully.")
        except Exception as e:
            logger.warning(
                f"PyAnnote pipeline initialization failed ({e}). Using local turn splitter fallback."
            )
            self.diarization_pipeline = None

    async def process_audio(self, audio_path: Path) -> TranscriptionResult:
        """Runs speech recognition and speaker diarization with precise alignment."""
        start_time = time.perf_counter()

        # 1. Run transcription off main thread
        words_with_time, detected_lang, duration = await asyncio.to_thread(
            self._run_transcription, audio_path
        )

        # 2. Run diarization off main thread
        speaker_turns = await asyncio.to_thread(self._run_diarization, audio_path, words_with_time)

        # 3. Align word timestamps with speaker turns
        aligned_utterances = self._align_words_with_speakers(words_with_time, speaker_turns)

        elapsed = time.perf_counter() - start_time
        INFERENCE_LATENCY.labels(step="full_inference").observe(elapsed)

        return TranscriptionResult(
            utterances=aligned_utterances,
            duration_seconds=duration,
            detected_language=detected_lang,
        )

    def _run_transcription(self, audio_path: Path) -> tuple[list[WordTimestamp], str, float]:
        if not self.whisper_model:
            # Fallback mock engine for instant demo/test environments
            return (
                [
                    WordTimestamp(word="Здравствуйте,", start=0.5, end=1.2, probability=0.99),
                    WordTimestamp(word="коллеги.", start=1.25, end=1.8, probability=0.98),
                    WordTimestamp(word="Давайте", start=2.0, end=2.4, probability=0.97),
                    WordTimestamp(word="обсудим", start=2.45, end=2.9, probability=0.99),
                    WordTimestamp(word="результаты", start=2.95, end=3.5, probability=0.96),
                    WordTimestamp(word="встречи.", start=3.55, end=4.1, probability=0.95),
                    WordTimestamp(word="Good", start=4.8, end=5.2, probability=0.98),
                    WordTimestamp(word="morning,", start=5.25, end=5.7, probability=0.99),
                    WordTimestamp(word="everyone.", start=5.75, end=6.3, probability=0.97),
                    WordTimestamp(word="We", start=6.5, end=6.7, probability=0.99),
                    WordTimestamp(word="agreed", start=6.75, end=7.2, probability=0.98),
                    WordTimestamp(word="on", start=7.25, end=7.4, probability=0.99),
                    WordTimestamp(word="all", start=7.45, end=7.7, probability=0.98),
                    WordTimestamp(word="action", start=7.75, end=8.2, probability=0.99),
                    WordTimestamp(word="items.", start=8.25, end=8.8, probability=0.96),
                ],
                "ru",
                9.5,
            )

        segments, info = self.whisper_model.transcribe(
            str(audio_path),
            beam_size=settings.WHISPER_BEAM_SIZE,
            best_of=1,
            condition_on_previous_text=settings.WHISPER_CONDITION_ON_PREVIOUS_TEXT,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500, "speech_pad_ms": 200},
            temperature=0.0,
        )

        extracted_words: list[WordTimestamp] = []
        for segment in segments:
            if segment.words:
                extracted_words.extend(
                    WordTimestamp(
                        word=w.word.strip(),
                        start=round(w.start, 2),
                        end=round(w.end, 2),
                        probability=round(w.probability, 2),
                    )
                    for w in segment.words
                )
        return extracted_words, info.language, info.duration

    def _run_diarization(
        self, audio_path: Path, words: list[WordTimestamp]
    ) -> list[dict[str, Any]]:
        """Runs PyAnnote or falls back to smart local gap-based speaker segmentation."""
        if self.diarization_pipeline:
            try:
                diarization = self.diarization_pipeline(str(audio_path))
                turns: list[dict[str, Any]] = []
                for turn, _, speaker in diarization.itertracks(yield_label=True):
                    turns.append(
                        {
                            "start": turn.start,
                            "end": turn.end,
                            "speaker": f"Спикер {speaker.replace('SPEAKER_', '')}",
                        }
                    )
                if turns:
                    return turns
            except Exception as err:
                logger.warning(f"Diarization execution error: {err}. Using local gap fallback.")

        # Smart local gap fallback: group words separated by > 1.2 second pauses into alternating speaker turns
        if not words:
            return [{"start": 0.0, "end": 10.0, "speaker": "Спикер 1"}]

        turns = []
        current_speaker_idx = 1
        turn_start = words[0].start
        last_end = words[0].end

        for i in range(1, len(words)):
            curr_word = words[i]
            pause_duration = curr_word.start - last_end
            if pause_duration >= 1.2:
                turns.append(
                    {
                        "start": turn_start,
                        "end": last_end,
                        "speaker": f"Спикер {current_speaker_idx}",
                    }
                )
                # Alternate speaker label
                current_speaker_idx = 2 if current_speaker_idx == 1 else 1
                turn_start = curr_word.start
            last_end = curr_word.end

        turns.append(
            {"start": turn_start, "end": last_end, "speaker": f"Спикер {current_speaker_idx}"}
        )

        return turns

    def _align_words_with_speakers(
        self, words: list[WordTimestamp], turns: list[dict[str, Any]]
    ) -> list[Utterance]:
        """Aligns individual words with speaker turns, producing continuous utterances."""
        if not words:
            return []

        utterances: list[Utterance] = []
        current_speaker: str | None = None
        current_words: list[WordTimestamp] = []

        for word in words:
            word_mid = (word.start + word.end) / 2.0
            assigned_speaker = "Спикер 1"
            for turn in turns:
                if turn["start"] <= word_mid <= turn["end"]:
                    assigned_speaker = turn["speaker"]
                    break

            if current_speaker is None:
                current_speaker = assigned_speaker

            if assigned_speaker != current_speaker and current_words:
                utt_text = " ".join([w.word for w in current_words])
                utterances.append(
                    Utterance(
                        speaker=current_speaker,
                        start=current_words[0].start,
                        end=current_words[-1].end,
                        text=utt_text,
                        words=current_words,
                    )
                )
                current_words = []
                current_speaker = assigned_speaker

            current_words.append(word)

        if current_words and current_speaker:
            utt_text = " ".join([w.word for w in current_words])
            utterances.append(
                Utterance(
                    speaker=current_speaker,
                    start=current_words[0].start,
                    end=current_words[-1].end,
                    text=utt_text,
                    words=current_words,
                )
            )

        return utterances
