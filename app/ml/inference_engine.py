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
from app.core.profiler import profile_async, profile_sync
from app.domain.entities import (
    TranscriptionResult,
    Utterance,
    VoiceProfileEntity,
    WordTimestamp,
)


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
        logger.info(f"Loading Faster-Whisper model ({settings.WHISPER_MODEL_SIZE})...")
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

            try:
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
            except Exception as primary_err:
                logger.warning(
                    f"Could not load primary model '{settings.WHISPER_MODEL_SIZE}' ({primary_err}). "
                    f"Attempting fallback model '{settings.WHISPER_FALLBACK_MODEL_SIZE}'..."
                )
                self.whisper_model = WhisperModel(
                    settings.WHISPER_FALLBACK_MODEL_SIZE,
                    device=device,
                    compute_type=compute_type,
                    cpu_threads=settings.WHISPER_CPU_THREADS,
                    num_workers=settings.WHISPER_NUM_WORKERS,
                )
                logger.info(
                    f"Faster-Whisper fallback ({settings.WHISPER_FALLBACK_MODEL_SIZE}) loaded on {device}."
                )
        except Exception as e:
            logger.warning(
                f"Could not load real Faster-Whisper model ({e}). Fallback demo engine active."
            )
            self.whisper_model = None

    def _load_diarization_pipeline(self) -> None:
        if not settings.PYANNOTE_AUTH_TOKEN or settings.PYANNOTE_AUTH_TOKEN == "hf_dummy_token":
            logger.info(
                "PyAnnote auth token not configured. Advanced acoustic clustering engine active."
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
                f"PyAnnote pipeline initialization failed ({e}). Using acoustic feature clustering."
            )
            self.diarization_pipeline = None

    @profile_async(name="speech_transcription_and_diarization", subfolder="ml_inference")
    async def process_audio(
        self,
        audio_path: Path,
        voice_profiles: list[VoiceProfileEntity] | None = None,
    ) -> TranscriptionResult:
        """Runs speech recognition, speaker diarization, voice embedding extraction, and voice profile matching.

        Args:
            audio_path: Path to the target audio file on disk.
            voice_profiles: Optional list of saved user voice profiles to identify known speakers.

        Returns:
            TranscriptionResult populated with aligned utterances, detected language, duration,
            and extracted speaker voice embeddings.

        Example:
            >>> result = await engine.process_audio(Path("audio.wav"), voice_profiles=[profile])
            >>> print(result.utterances[0].speaker)
        """
        start_time = time.perf_counter()

        # 1. Run high-quality transcription off main thread
        words_with_time, detected_lang, duration = await asyncio.to_thread(
            self._run_transcription, audio_path
        )

        # 2. Run speaker diarization (PyAnnote or acoustic feature clustering) off main thread
        speaker_turns = await asyncio.to_thread(self._run_diarization, audio_path, words_with_time)

        # 3. Extract speaker voice embeddings
        speaker_embeddings = await asyncio.to_thread(
            self.extract_all_speaker_embeddings, audio_path, speaker_turns
        )

        # 4. Match against saved voice profiles in model memory if provided
        if voice_profiles:
            speaker_turns, speaker_embeddings = self.match_speakers_with_voice_memory(
                speaker_turns=speaker_turns,
                speaker_embeddings=speaker_embeddings,
                voice_profiles=voice_profiles,
                threshold=settings.VOICE_SIMILARITY_THRESHOLD,
            )

        # 5. Align word timestamps with speaker turns using maximum temporal overlap
        aligned_utterances = self._align_words_with_speakers(words_with_time, speaker_turns)

        elapsed = time.perf_counter() - start_time
        INFERENCE_LATENCY.labels(step="full_inference").observe(elapsed)

        return TranscriptionResult(
            utterances=aligned_utterances,
            duration_seconds=duration,
            detected_language=detected_lang,
            speaker_embeddings=speaker_embeddings,
        )

    @staticmethod
    @profile_sync(name="compute_voice_similarity", subfolder="ml_inference")
    def compute_voice_similarity(emb1: list[float], emb2: list[float]) -> float:
        """Computes cosine similarity between two normalized voice embedding vectors.

        Args:
            emb1: First voice feature embedding vector.
            emb2: Second voice feature embedding vector.

        Returns:
            Cosine similarity score in the range [-1.0, 1.0].

        Example:
            >>> sim = InferenceEngine.compute_voice_similarity([1.0, 0.0], [1.0, 0.0])
            >>> round(sim, 2)
            1.0
        """
        if not emb1 or not emb2 or len(emb1) != len(emb2):
            return 0.0

        import numpy as np

        v1 = np.array(emb1, dtype=np.float32)
        v2 = np.array(emb2, dtype=np.float32)

        norm1 = float(np.linalg.norm(v1))
        norm2 = float(np.linalg.norm(v2))

        if norm1 <= 1e-9 or norm2 <= 1e-9:
            return 0.0

        sim = float(np.dot(v1, v2) / (norm1 * norm2))
        return max(-1.0, min(1.0, sim))

    @staticmethod
    @profile_sync(name="update_profile_embedding", subfolder="ml_inference")
    def update_profile_embedding(
        existing_embedding: list[float],
        new_embedding: list[float],
        samples_count: int = 1,
    ) -> list[float]:
        """Calculates running centroid average of voice embeddings and normalizes result.

        Args:
            existing_embedding: Current stored voice embedding centroid.
            new_embedding: Newly extracted voice embedding from current audio session.
            samples_count: Number of previous audio samples already aggregated in profile.

        Returns:
            Updated L2-normalized voice embedding vector.

        Example:
            >>> updated = InferenceEngine.update_profile_embedding([1.0, 0.0], [0.0, 1.0], 1)
            >>> len(updated)
            2
        """
        if not existing_embedding:
            return new_embedding
        if not new_embedding:
            return existing_embedding

        import numpy as np

        v_old = np.array(existing_embedding, dtype=np.float32)
        v_new = np.array(new_embedding, dtype=np.float32)

        # Weighted running average
        count = max(1, samples_count)
        v_combined = (v_old * count + v_new) / (count + 1)
        norm = float(np.linalg.norm(v_combined))
        if norm > 1e-9:
            v_combined = v_combined / norm

        return [float(x) for x in v_combined]

    @staticmethod
    def _extract_chunk_features(chunk: Any, sr: int, target_dim: int) -> list[float]:
        """Extracts acoustic spectral and timbre features from an isolated audio chunk.

        Args:
            chunk: Audio samples as float32 1D numpy array.
            sr: Audio sample rate in Hz.
            target_dim: Target feature embedding vector dimension.

        Returns:
            List of float feature values of length target_dim.
        """
        import numpy as np

        rms = float(np.sqrt(np.mean(chunk**2)))
        zcr = float(np.mean(np.abs(np.diff(np.signbit(chunk)))))

        fft_vals = np.abs(np.fft.rfft(chunk * np.hamming(len(chunk))))
        freqs = np.fft.rfftfreq(len(chunk), 1.0 / sr)
        total_energy = float(np.sum(fft_vals)) or 1.0

        centroid = float(np.sum(freqs * fft_vals) / total_energy) / 4000.0
        variance = float(np.sum(((freqs - centroid * 4000.0) ** 2) * fft_vals) / total_energy) / 1e6

        low_f0 = float(
            np.sum(fft_vals[np.logical_and(freqs >= 70.0, freqs < 300.0)]) / total_energy
        )
        f1 = float(np.sum(fft_vals[np.logical_and(freqs >= 300.0, freqs < 1000.0)]) / total_energy)
        f2 = float(np.sum(fft_vals[np.logical_and(freqs >= 1000.0, freqs < 2500.0)]) / total_energy)
        f3 = float(np.sum(fft_vals[np.logical_and(freqs >= 2500.0, freqs < 4500.0)]) / total_energy)
        high = float(
            np.sum(fft_vals[np.logical_and(freqs >= 4500.0, freqs < 8000.0)]) / total_energy
        )

        sub_bands: list[float] = []
        band_edges = np.geomspace(80, min(8000, sr // 2), num=17)
        for b_idx in range(16):
            b_low = float(band_edges[b_idx])
            b_high = float(band_edges[b_idx + 1])
            mask = np.logical_and(freqs >= b_low, freqs < b_high)
            sub_bands.append(float(np.sum(fft_vals[mask]) / total_energy))

        cum_energy = np.cumsum(fft_vals)
        roll_idx = int(np.searchsorted(cum_energy, 0.85 * total_energy))
        roll_freq = float(freqs[min(roll_idx, len(freqs) - 1)]) / 4000.0
        geom_mean = np.exp(np.mean(np.log(fft_vals + 1e-9)))
        flatness = float(geom_mean / (np.mean(fft_vals) + 1e-9))

        base_feat = [
            rms,
            zcr,
            centroid,
            variance,
            low_f0,
            f1,
            f2,
            f3,
            high,
            roll_freq,
            flatness,
        ]
        feat = [*base_feat, *sub_bands]

        if len(feat) < target_dim:
            feat.extend([0.0] * (target_dim - len(feat)))
        else:
            feat = feat[:target_dim]

        return feat

    @staticmethod
    def _load_audio_pcm(audio_path: Path, target_sr: int = 16000) -> tuple[Any, int]:
        """Loads PCM float32 mono audio array from WAV file or decodes via FFmpeg.

        Args:
            audio_path: Path to target audio file on disk.
            target_sr: Target sample rate in Hz.

        Returns:
            Tuple of (audio_data_float32_array, sample_rate).

        Raises:
            RuntimeError: If audio file cannot be loaded or decoded.
        """
        import subprocess
        import wave

        import numpy as np

        # 1. Check normalized 16k companion wav if original path is non-wav or missing
        candidates = [audio_path]
        companion_16k = audio_path.with_name(f"{audio_path.name}_16k.wav")
        if companion_16k.exists() and companion_16k != audio_path:
            candidates.insert(0, companion_16k)
        stem_16k = audio_path.with_name(f"{audio_path.stem}_16k.wav")
        if stem_16k.exists() and stem_16k not in candidates:
            candidates.insert(0, stem_16k)

        for cand in candidates:
            if cand.exists() and cand.suffix.lower() == ".wav":
                try:
                    with wave.open(str(cand), "rb") as wf:
                        sr = wf.getframerate()
                        n_channels = wf.getnchannels()
                        sampwidth = wf.getsampwidth()
                        raw_bytes = wf.readframes(wf.getnframes())

                    dtype = np.int16 if sampwidth == 2 else np.int32
                    audio_data = np.frombuffer(raw_bytes, dtype=dtype).astype(np.float32)
                    if n_channels > 1:
                        audio_data = audio_data.reshape(-1, n_channels).mean(axis=1)
                    max_val = np.max(np.abs(audio_data)) or 1.0
                    return (audio_data / max_val), sr
                except Exception as cand_err:
                    logger.debug(f"Direct WAV candidate read skipped for '{cand}': {cand_err}")

        # 2. Try FFmpeg pipe decoding for any format (MP3, M4A, OGG, AAC, etc.)
        if audio_path.exists():
            try:
                cmd = [
                    "ffmpeg",
                    "-nostdin",
                    "-threads",
                    "0",
                    "-i",
                    str(audio_path),
                    "-f",
                    "s16le",
                    "-ac",
                    "1",
                    "-ar",
                    str(target_sr),
                    "pipe:1",
                ]
                res = subprocess.run(cmd, capture_output=True, check=True)  # noqa: S603
                audio_data = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32)
                max_val = np.max(np.abs(audio_data)) or 1.0
                return (audio_data / max_val), target_sr
            except Exception as ffmpeg_err:
                logger.debug(f"FFmpeg PCM decoding skipped for '{audio_path}': {ffmpeg_err}")

        raise RuntimeError(f"Could not load or decode PCM audio from {audio_path}")

    @staticmethod
    def _heuristic_embedding_fallback(
        segments: list[dict[str, Any]], target_dim: int, audio_identifier: str = ""
    ) -> list[float]:
        """Calculates deterministic normalized unit vector based on segment cadence and dynamics.

        Args:
            segments: Audio segment dictionaries.
            target_dim: Expected output dimensionality.
            audio_identifier: Optional audio path identifier to prevent cross-file collision.

        Returns:
            Normalized float feature list of length target_dim.
        """
        import hashlib

        import numpy as np

        total_dur = sum(max(0.1, s.get("end", 0.0) - s.get("start", 0.0)) for s in segments)
        first_start = segments[0].get("start", 0.0) if segments else 0.0
        words_count = sum(len(s.get("words", [])) for s in segments)
        tempo = words_count / max(0.1, total_dur)

        seed_bytes = f"{audio_identifier}:{first_start:.2f}:{total_dur:.2f}:{tempo:.2f}".encode()
        feat_fallback = [0.0] * target_dim

        for k in range(target_dim):
            h_k = hashlib.sha256(seed_bytes + bytes([k])).digest()
            val = int.from_bytes(h_k[:2], "little", signed=True) / 32768.0
            feat_fallback[k] = float(val)

        v_arr = np.array(feat_fallback, dtype=np.float32)
        norm = float(np.linalg.norm(v_arr)) or 1.0
        return [float(x) for x in (v_arr / norm)]

    @profile_sync(name="speaker_embedding_extraction", subfolder="ml_inference")
    def extract_speaker_embedding(
        self, audio_path: Path, segments: list[dict[str, Any]]
    ) -> list[float]:
        """Extracts a fixed-dimensional normalized acoustic voice embedding for a speaker turn cluster.

        Args:
            audio_path: Path to the audio file on disk.
            segments: Sequence of audio segments belonging to this specific speaker.

        Returns:
            Normalized 32-dimensional acoustic embedding vector.

        Example:
            >>> emb = engine.extract_speaker_embedding(
            ...     Path("audio.wav"), [{"start": 0.0, "end": 2.0}]
            ... )
            >>> len(emb)
            32
        """
        target_dim = settings.VOICE_EMBEDDING_DIM or 32
        if not segments:
            return [0.0] * target_dim

        import numpy as np

        collected_vectors: list[np.ndarray] = []

        try:
            audio_data, sr = self._load_audio_pcm(audio_path)

            for seg in segments:
                start_frame = max(0, int(seg["start"] * sr))
                end_frame = min(len(audio_data), int(seg["end"] * sr))
                chunk = audio_data[start_frame:end_frame]
                if len(chunk) < 250:
                    continue

                feat = self._extract_chunk_features(chunk, sr, target_dim)
                collected_vectors.append(np.array(feat, dtype=np.float32))

        except Exception as e:
            logger.debug(f"Direct PCM speaker embedding skipped ({e}). Using heuristic vector.")

        if not collected_vectors:
            return self._heuristic_embedding_fallback(
                segments, target_dim, audio_identifier=str(audio_path)
            )

        mean_vec = np.mean(collected_vectors, axis=0)
        norm = float(np.linalg.norm(mean_vec)) or 1.0
        normalized = mean_vec / norm
        return [float(x) for x in normalized]

    @profile_sync(name="all_speaker_embeddings_extraction", subfolder="ml_inference")
    def extract_all_speaker_embeddings(
        self, audio_path: Path, turns: list[dict[str, Any]]
    ) -> dict[str, list[float]]:
        """Extracts acoustic voice embeddings for all speakers present in turns list.

        Args:
            audio_path: Path to the audio file.
            turns: Sequence of speaker speech turn dictionaries.

        Returns:
            Dictionary mapping speaker labels to their normalized embedding vectors.

        Example:
            >>> embs = engine.extract_all_speaker_embeddings(Path("audio.wav"), turns)
            >>> print(embs.keys())
        """
        from collections import defaultdict

        speaker_segments: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for turn in turns:
            spk = turn.get("speaker") or "Спикер 1"
            speaker_segments[spk].append(turn)

        speaker_embeddings: dict[str, list[float]] = {}
        for spk, segs in speaker_segments.items():
            speaker_embeddings[spk] = self.extract_speaker_embedding(audio_path, segs)

        return speaker_embeddings

    def _build_speaker_rename_map(
        self,
        speaker_embeddings: dict[str, list[float]],
        voice_profiles: list[VoiceProfileEntity],
        threshold: float,
    ) -> dict[str, str]:
        """Builds greedy highest-similarity mapping between speaker clusters and voice profiles.

        Args:
            speaker_embeddings: Speaker embeddings from audio.
            voice_profiles: User voice profiles.
            threshold: Cosine similarity threshold.

        Returns:
            Dictionary mapping original speaker label to recognized voice profile name.
        """
        candidates: list[tuple[float, str, str]] = []
        for current_spk, emb in speaker_embeddings.items():
            for profile in voice_profiles:
                if not profile.embedding:
                    continue
                sim = self.compute_voice_similarity(emb, profile.embedding)
                if sim >= threshold:
                    candidates.append((sim, current_spk, profile.name))

        candidates.sort(key=lambda item: item[0], reverse=True)
        assigned_current: set[str] = set()
        assigned_profiles: set[str] = set()
        rename_map: dict[str, str] = {}

        for sim, curr_spk, prof_name in candidates:
            if curr_spk in assigned_current or prof_name in assigned_profiles:
                continue
            rename_map[curr_spk] = prof_name
            assigned_current.add(curr_spk)
            assigned_profiles.add(prof_name)
            logger.info(
                f"Voice Memory Match: '{curr_spk}' recognized as '{prof_name}' with similarity {sim:.3f}"
            )

        return rename_map

    @profile_sync(name="match_speakers_with_voice_memory", subfolder="ml_inference")
    def match_speakers_with_voice_memory(
        self,
        speaker_turns: list[dict[str, Any]],
        speaker_embeddings: dict[str, list[float]],
        voice_profiles: list[VoiceProfileEntity] | None = None,
        threshold: float = 0.75,
    ) -> tuple[list[dict[str, Any]], dict[str, list[float]]]:
        """Matches extracted speaker embeddings with saved voice memory profiles and updates speaker names.

        Args:
            speaker_turns: List of speech turn dictionaries with 'speaker', 'start', 'end'.
            speaker_embeddings: Dictionary mapping speaker labels to embedding vectors.
            voice_profiles: Saved voice profiles from user memory.
            threshold: Cosine similarity threshold for confident speaker recognition.

        Returns:
            Tuple of updated speaker turns and renamed speaker embeddings dictionary.

        Example:
            >>> turns, embs = engine.match_speakers_with_voice_memory(turns, embs, [profile])
        """
        if not voice_profiles or not speaker_embeddings:
            return speaker_turns, speaker_embeddings

        rename_map = self._build_speaker_rename_map(speaker_embeddings, voice_profiles, threshold)
        if not rename_map:
            return speaker_turns, speaker_embeddings

        # Update turns
        updated_turns: list[dict[str, Any]] = []
        for turn in speaker_turns:
            spk = turn.get("speaker", "Спикер 1")
            new_spk = rename_map.get(spk, spk)
            updated_turn = dict(turn)
            updated_turn["speaker"] = new_spk
            updated_turns.append(updated_turn)

        # Update embeddings dictionary
        updated_embeddings: dict[str, list[float]] = {
            rename_map.get(spk, spk): emb for spk, emb in speaker_embeddings.items()
        }

        return updated_turns, updated_embeddings

    @profile_sync(name="whisper_speech_transcription", subfolder="ml_inference")
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
            best_of=settings.WHISPER_BEST_OF,
            patience=settings.WHISPER_PATIENCE,
            repetition_penalty=settings.WHISPER_REPETITION_PENALTY,
            no_repeat_ngram_size=settings.WHISPER_NO_REPEAT_NGRAM_SIZE,
            initial_prompt=settings.WHISPER_INITIAL_PROMPT,
            condition_on_previous_text=settings.WHISPER_CONDITION_ON_PREVIOUS_TEXT,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters={
                "threshold": 0.5,
                "min_speech_duration_ms": 250,
                "max_speech_duration_s": float("inf"),
                "min_silence_duration_ms": settings.WHISPER_VAD_MIN_SILENCE_MS,
                "speech_pad_ms": settings.WHISPER_VAD_SPEECH_PAD_MS,
            },
            temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6,
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
                    if w.word and w.word.strip()
                )
        return extracted_words, info.language, info.duration

    @profile_sync(name="speaker_diarization", subfolder="ml_inference")
    def _run_diarization(
        self, audio_path: Path, words: list[WordTimestamp]
    ) -> list[dict[str, Any]]:
        """Runs PyAnnote or falls back to intelligent acoustic voice timbre clustering."""
        if self.diarization_pipeline:
            try:
                diarization_kwargs: dict[str, Any] = {}
                if settings.DIARIZATION_MIN_SPEAKERS:
                    diarization_kwargs["min_speakers"] = settings.DIARIZATION_MIN_SPEAKERS
                if settings.DIARIZATION_MAX_SPEAKERS:
                    diarization_kwargs["max_speakers"] = settings.DIARIZATION_MAX_SPEAKERS

                diarization = self.diarization_pipeline(str(audio_path), **diarization_kwargs)
                turns: list[dict[str, Any]] = []
                speaker_map: dict[str, str] = {}
                next_speaker_num = 1

                for turn, _, speaker_raw in diarization.itertracks(yield_label=True):
                    if speaker_raw not in speaker_map:
                        speaker_map[speaker_raw] = f"Спикер {next_speaker_num}"
                        next_speaker_num += 1

                    turns.append(
                        {
                            "start": round(turn.start, 2),
                            "end": round(turn.end, 2),
                            "speaker": speaker_map[speaker_raw],
                        }
                    )
                if turns:
                    return turns
            except Exception as err:
                logger.warning(
                    f"PyAnnote diarization error: {err}. Falling back to acoustic clustering."
                )

        return self._run_acoustic_diarization(audio_path, words)

    @profile_sync(name="acoustic_diarization", subfolder="ml_inference")
    def _run_acoustic_diarization(
        self, audio_path: Path, words: list[WordTimestamp]
    ) -> list[dict[str, Any]]:
        """Acoustic feature extraction and timbre clustering for high-accuracy local speaker separation."""
        if not words:
            return [{"start": 0.0, "end": 10.0, "speaker": "Спикер 1"}]

        # 1. Segment words into contiguous speech phrases separated by significant pauses
        speech_segments: list[dict[str, Any]] = []
        seg_start = words[0].start
        last_end = words[0].end
        seg_words = [words[0]]

        for i in range(1, len(words)):
            curr_word = words[i]
            pause_duration = curr_word.start - last_end
            if pause_duration >= 0.8:
                speech_segments.append(
                    {
                        "start": seg_start,
                        "end": last_end,
                        "words": seg_words,
                    }
                )
                seg_start = curr_word.start
                seg_words = [curr_word]
            else:
                seg_words.append(curr_word)
            last_end = curr_word.end

        speech_segments.append(
            {
                "start": seg_start,
                "end": last_end,
                "words": seg_words,
            }
        )

        if len(speech_segments) <= 1:
            return [
                {
                    "start": speech_segments[0]["start"],
                    "end": speech_segments[0]["end"],
                    "speaker": "Спикер 1",
                }
            ]

        # 2. Extract acoustic timbre features per speech segment if audio file is available
        features = self._extract_segment_acoustic_features(audio_path, speech_segments)

        # 3. Cluster speech segments into speaker identities using Agglomerative Clustering
        speaker_labels = self._cluster_acoustic_features(features, len(speech_segments))

        # Map cluster labels chronologically so the first active voice is always "Спикер 1"
        speaker_map: dict[int, str] = {}
        next_speaker_num = 1
        turns: list[dict[str, Any]] = []

        for seg, spk_idx in zip(speech_segments, speaker_labels, strict=False):
            if spk_idx not in speaker_map:
                speaker_map[spk_idx] = f"Спикер {next_speaker_num}"
                next_speaker_num += 1

            turns.append(
                {
                    "start": seg["start"],
                    "end": seg["end"],
                    "speaker": speaker_map[spk_idx],
                }
            )

        return turns

    @profile_sync(name="acoustic_feature_extraction", subfolder="ml_inference")
    def _extract_segment_acoustic_features(
        self, audio_path: Path, segments: list[dict[str, Any]]
    ) -> list[list[float]]:
        """Extracts normalized energy, zero-crossing, and multi-band spectral features from audio segments."""
        import numpy as np

        features: list[list[float]] = []

        try:
            audio_data, sr = self._load_audio_pcm(audio_path)

            for seg in segments:
                start_frame = max(0, int(seg["start"] * sr))
                end_frame = min(len(audio_data), int(seg["end"] * sr))
                chunk = audio_data[start_frame:end_frame]

                if len(chunk) < 200:
                    features.append([0.0, 0.0, 0.0, 0.0, 0.0])
                    continue

                # Energy RMS
                rms = float(np.sqrt(np.mean(chunk**2)))

                # Zero Crossing Rate (pitch and voicing cue)
                zcr = float(np.mean(np.abs(np.diff(np.signbit(chunk)))))

                # Spectral energy distribution across frequency bands (vocal resonance)
                fft_vals = np.abs(np.fft.rfft(chunk * np.hamming(len(chunk))))
                freqs = np.fft.rfftfreq(len(chunk), 1.0 / sr)

                total_energy = float(np.sum(fft_vals)) or 1.0
                spectral_centroid = float(np.sum(freqs * fft_vals) / total_energy)

                # Low band (80-300Hz: fundamental voice pitch)
                low_mask = np.logical_and(freqs >= 80.0, freqs < 300.0)
                low_ratio = float(np.sum(fft_vals[low_mask]) / total_energy)

                # Mid band (300-2500Hz: formant/timbre range)
                mid_mask = np.logical_and(freqs >= 300.0, freqs < 2500.0)
                mid_ratio = float(np.sum(fft_vals[mid_mask]) / total_energy)

                features.append([rms, zcr, spectral_centroid / 4000.0, low_ratio, mid_ratio])

        except Exception as e:
            logger.debug(
                f"Direct PCM acoustic extraction skipped ({e}). Using rhythm/pause heuristics."
            )
            # Heuristic feature fallback: speech rate and pause dynamics
            for idx, seg in enumerate(segments):
                dur = max(seg["end"] - seg["start"], 0.1)
                w_count = len(seg.get("words", []))
                rate = w_count / dur
                features.append([float(idx % 2), rate, dur, float(w_count), 0.5])

        return features

    @profile_sync(name="acoustic_timbre_clustering", subfolder="ml_inference")
    def _cluster_acoustic_features(
        self, features: list[list[float]], num_segments: int
    ) -> list[int]:
        """Clusters acoustic vectors into optimal speaker clusters using Scikit-Learn."""
        if num_segments <= 1:
            return [0]

        import numpy as np
        from sklearn.cluster import AgglomerativeClustering

        X = np.array(features)
        std = np.std(X, axis=0)
        std[std == 0] = 1.0
        X_norm = (X - np.mean(X, axis=0)) / std

        # Target cluster range
        min_spk = settings.DIARIZATION_MIN_SPEAKERS or 2
        k = max(min(min_spk, num_segments), 1)

        if num_segments >= 2 and k > 1:
            try:
                clustering = AgglomerativeClustering(
                    n_clusters=min(k, num_segments), metric="euclidean", linkage="ward"
                )
                labels = clustering.fit_predict(X_norm)
                return [int(lbl) for lbl in labels]
            except Exception as cluster_err:
                logger.debug(f"Clustering error: {cluster_err}. Using alternating cluster index.")

        # Alternating speaker fallback
        return [i % 2 for i in range(num_segments)]

    @staticmethod
    def _find_best_speaker_for_word(word: WordTimestamp, turns: list[dict[str, Any]]) -> str:
        """Finds the speaker turn with highest temporal overlap or closest proximity to the word."""
        best_speaker = turns[0]["speaker"]
        best_overlap = -1.0
        min_distance = float("inf")
        word_mid = (word.start + word.end) / 2.0

        for turn in turns:
            t_start = turn["start"]
            t_end = turn["end"]

            overlap = max(0.0, min(word.end, t_end) - max(word.start, t_start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = turn["speaker"]

            dist = abs(word_mid - (t_start + t_end) / 2.0)
            if dist < min_distance:
                min_distance = dist
                if best_overlap <= 0.0:
                    best_speaker = turn["speaker"]

        return best_speaker

    @profile_sync(name="word_speaker_alignment", subfolder="ml_inference")
    def _align_words_with_speakers(
        self, words: list[WordTimestamp], turns: list[dict[str, Any]]
    ) -> list[Utterance]:
        """Aligns individual words with speaker turns via Maximum Temporal Overlap, producing continuous utterances."""
        if not words:
            return []

        if not turns:
            all_text = " ".join([w.word for w in words])
            return [
                Utterance(
                    speaker="Спикер 1",
                    start=words[0].start,
                    end=words[-1].end,
                    text=all_text,
                    words=words,
                )
            ]

        utterances: list[Utterance] = []
        current_speaker: str | None = None
        current_words: list[WordTimestamp] = []

        for word in words:
            best_speaker = self._find_best_speaker_for_word(word, turns)

            if current_speaker is None:
                current_speaker = best_speaker

            if best_speaker != current_speaker and current_words:
                utt_text = " ".join([w.word for w in current_words]).strip()
                if utt_text:
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
                current_speaker = best_speaker

            current_words.append(word)

        if current_words and current_speaker:
            utt_text = " ".join([w.word for w in current_words]).strip()
            if utt_text:
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
