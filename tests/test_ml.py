# filename: tests/test_ml.py
"""Unit tests for ML Audio Processing and Speech Inference Engines (app/ml/)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import settings
from app.domain.entities import TranscriptionResult, WordTimestamp
from app.domain.exceptions import AudioProcessingError
from app.ml.audio_processor import FFmpegAudioProcessor
from app.ml.inference_engine import InferenceEngine


@pytest.mark.asyncio
async def test_ffmpeg_audio_processor_non_existent_input() -> None:
    """Validates AudioProcessingError raised when input audio file does not exist."""
    processor = FFmpegAudioProcessor()
    fake_input = Path("/non/existent/path/audio.wav")
    fake_output = Path("/tmp/output.wav")

    with pytest.raises(AudioProcessingError) as exc_info:
        await processor.normalize_and_vad(fake_input, fake_output)
    assert "Input audio file does not exist" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ffmpeg_audio_processor_success_and_failure_cmd(tmp_path: Path) -> None:
    """Validates FFmpeg execution paths for success and subprocess failure."""
    processor = FFmpegAudioProcessor()
    input_file = tmp_path / "input.mp3"
    input_file.write_bytes(b"DATA")
    output_file = tmp_path / "output.wav"

    # 1. Success path
    mock_run_success = MagicMock(returncode=0, stderr="")
    with patch("subprocess.run", return_value=mock_run_success):
        res = await processor.normalize_and_vad(input_file, output_file)
        assert res == output_file

    # 2. Failure path
    mock_run_failed = MagicMock(returncode=1, stderr="FFmpeg error: Invalid input format")
    with patch("subprocess.run", return_value=mock_run_failed):
        with pytest.raises(AudioProcessingError) as exc_info:
            await processor.normalize_and_vad(input_file, output_file)
        assert "Audio normalization failed" in str(exc_info.value)


def test_inference_engine_load_models_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validates model loading logic and fallback flags."""
    engine = InferenceEngine()
    assert engine._is_loaded is False

    # Force PyAnnote token to dummy
    monkeypatch.setattr(settings, "PYANNOTE_AUTH_TOKEN", "hf_dummy_token")

    engine.load_models()
    assert engine._is_loaded is True
    assert engine.diarization_pipeline is None

    # Idempotent re-load call
    engine.load_models()


@pytest.mark.asyncio
async def test_inference_engine_process_audio_fallback_demo(tmp_path: Path) -> None:
    """Validates end-to-end process_audio execution using demo fallback."""
    engine = InferenceEngine()
    dummy_audio = tmp_path / "speech.wav"
    dummy_audio.write_bytes(b"WAVE")

    result = await engine.process_audio(dummy_audio)
    assert isinstance(result, TranscriptionResult)
    assert len(result.utterances) > 0
    assert result.detected_language == "ru"
    assert result.duration_seconds > 0.0


def test_inference_engine_transcribe_with_whisper_model() -> None:
    """Validates word timestamp extraction when WhisperModel instance is active."""
    engine = InferenceEngine()

    mock_word = MagicMock(word=" Hello ", start=0.5, end=1.0, probability=0.99)
    mock_segment = MagicMock(words=[mock_word])
    mock_info = MagicMock(language="en", duration=2.5)

    mock_whisper = MagicMock()
    mock_whisper.transcribe.return_value = ([mock_segment], mock_info)
    engine.whisper_model = mock_whisper

    words, lang, duration = engine._run_transcription(Path("dummy.wav"))
    assert lang == "en"
    assert duration == 2.5
    assert len(words) == 1
    assert words[0].word == "Hello"
    assert words[0].start == 0.5


def test_inference_engine_run_diarization_local_clustering() -> None:
    """Validates gap-based local speaker turn clustering."""
    engine = InferenceEngine()

    # Empty words
    turns_empty = engine._run_diarization(Path("dummy.wav"), [])
    assert len(turns_empty) == 1
    assert turns_empty[0]["speaker"] == "Спикер 1"

    # Words with gap > 1.2s triggering speaker alternation
    words = [
        WordTimestamp(word="Привет", start=0.0, end=1.0, probability=0.9),
        WordTimestamp(word="коллеги.", start=1.1, end=1.5, probability=0.9),
        # Gap of 2.0s
        WordTimestamp(word="Здравствуйте!", start=3.5, end=4.5, probability=0.9),
    ]

    turns = engine._run_diarization(Path("dummy.wav"), words)
    assert len(turns) == 2
    assert turns[0]["speaker"] == "Спикер 1"
    assert turns[1]["speaker"] == "Спикер 2"


def test_inference_engine_align_words_with_speakers() -> None:
    """Validates word timestamp to speaker turn alignment."""
    engine = InferenceEngine()

    # Empty
    assert engine._align_words_with_speakers([], []) == []

    words = [
        WordTimestamp(word="One", start=0.0, end=0.5, probability=0.9),
        WordTimestamp(word="Two", start=0.6, end=1.0, probability=0.9),
        WordTimestamp(word="Three", start=2.0, end=2.5, probability=0.9),
    ]
    turns = [
        {"start": 0.0, "end": 1.2, "speaker": "Alice"},
        {"start": 1.8, "end": 3.0, "speaker": "Bob"},
    ]

    utterances = engine._align_words_with_speakers(words, turns)
    assert len(utterances) == 2
    assert utterances[0].speaker == "Alice"
    assert utterances[0].text == "One Two"
    assert utterances[1].speaker == "Bob"
    assert utterances[1].text == "Three"


def test_inference_engine_load_models_with_faster_whisper(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validates WhisperModel initialization with optimized cpu_threads and device parameters."""
    engine = InferenceEngine()
    mock_whisper_class = MagicMock()

    monkeypatch.setattr(settings, "WHISPER_DEVICE", "auto")
    monkeypatch.setattr(settings, "WHISPER_COMPUTE_TYPE", "auto")
    monkeypatch.setattr(settings, "WHISPER_CPU_THREADS", 4)
    monkeypatch.setattr(settings, "WHISPER_NUM_WORKERS", 1)

    with patch.dict("sys.modules", {"faster_whisper": MagicMock(WhisperModel=mock_whisper_class)}):
        engine.load_models()
        assert engine._is_loaded is True
        mock_whisper_class.assert_called_once()
        _, kwargs = mock_whisper_class.call_args
        assert kwargs["cpu_threads"] == 4
        assert kwargs["num_workers"] == 1
        assert kwargs["compute_type"] in ("int8", "float16")
