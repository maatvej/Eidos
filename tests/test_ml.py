# filename: tests/test_ml.py
"""Unit tests for ML Audio Processing and Speech Inference Engines (app/ml/)."""

import math
import struct
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import torch

from app.core.config import settings
from app.domain.entities import TranscriptionResult, WordTimestamp
from app.domain.exceptions import AudioProcessingError
from app.ml.audio_processor import FFmpegAudioProcessor
from app.ml.inference_engine import InferenceEngine


def create_test_wav(
    path: Path, channels: int = 1, sample_rate: int = 16000, duration: float = 1.0
) -> None:
    """Helper creating synthetic PCM 16-bit WAV file for testing."""
    num_samples = int(sample_rate * duration)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(num_samples):
            val = int(32767.0 * 0.5 * math.sin(2.0 * math.pi * 440.0 * i / sample_rate))
            if channels == 1:
                wf.writeframes(struct.pack("<h", val))
            else:
                wf.writeframes(struct.pack("<hh", val, val))


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

    monkeypatch.setattr(settings, "PYANNOTE_AUTH_TOKEN", "hf_dummy_token")

    engine.load_models()
    assert engine._is_loaded is True
    assert engine.diarization_pipeline is None

    # Idempotent re-load call
    engine.load_models()


def test_inference_engine_torch_threads_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validates exception handling during torch.set_num_threads."""
    engine = InferenceEngine()
    with (
        patch("torch.set_num_threads", side_effect=RuntimeError("Cannot change thread count")),
        patch.dict("sys.modules", {"faster_whisper": MagicMock(WhisperModel=MagicMock())}),
    ):
        engine._load_whisper_model()
        assert engine.whisper_model is not None


def test_inference_engine_faster_whisper_import_error() -> None:
    """Validates fallback when faster_whisper cannot be imported."""
    engine = InferenceEngine()
    with patch.dict("sys.modules", {"faster_whisper": None}):
        engine._load_whisper_model()
        assert engine.whisper_model is None


def test_inference_engine_pyannote_loading_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validates pyannote pipeline loading on CUDA, MPS, and exception fallback."""
    engine = InferenceEngine()
    monkeypatch.setattr(settings, "PYANNOTE_AUTH_TOKEN", "hf_valid_real_token")

    mock_pipeline_inst = MagicMock()
    mock_pipeline_class = MagicMock(from_pretrained=MagicMock(return_value=mock_pipeline_inst))

    # 1. CUDA branch
    with (
        patch.dict("sys.modules", {"pyannote.audio": MagicMock(Pipeline=mock_pipeline_class)}),
        patch("torch.cuda.is_available", return_value=True),
    ):
        engine._load_diarization_pipeline()
        assert engine.diarization_pipeline == mock_pipeline_inst
        mock_pipeline_inst.to.assert_called_with(torch.device("cuda"))

    # 2. MPS branch
    mock_pipeline_inst_mps = MagicMock()
    mock_pipeline_class_mps = MagicMock(
        from_pretrained=MagicMock(return_value=mock_pipeline_inst_mps)
    )
    with (
        patch.dict("sys.modules", {"pyannote.audio": MagicMock(Pipeline=mock_pipeline_class_mps)}),
        patch("torch.cuda.is_available", return_value=False),
        patch.object(torch.backends, "mps", MagicMock(is_available=MagicMock(return_value=True))),
    ):
        engine._load_diarization_pipeline()
        assert engine.diarization_pipeline == mock_pipeline_inst_mps
        mock_pipeline_inst_mps.to.assert_called_with(torch.device("mps"))

    # 3. Exception branch
    mock_pipeline_class_err = MagicMock(
        from_pretrained=MagicMock(side_effect=RuntimeError("PyAnnote network error"))
    )
    with patch.dict("sys.modules", {"pyannote.audio": MagicMock(Pipeline=mock_pipeline_class_err)}):
        engine._load_diarization_pipeline()
        assert engine.diarization_pipeline is None


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


def test_inference_engine_run_diarization_pipeline_exception_fallback() -> None:
    """Validates fallback to acoustic diarization when PyAnnote pipeline throws exception."""
    engine = InferenceEngine()
    engine.diarization_pipeline = MagicMock(side_effect=RuntimeError("PyAnnote runtime crash"))

    words = [
        WordTimestamp(word="Привет", start=0.0, end=1.0, probability=0.9),
    ]
    turns = engine._run_diarization(Path("dummy.wav"), words)
    assert len(turns) == 1
    assert turns[0]["speaker"] == "Спикер 1"


def test_inference_engine_run_diarization_local_clustering() -> None:
    """Validates gap-based local speaker turn clustering."""
    engine = InferenceEngine()

    # Empty words
    turns_empty = engine._run_diarization(Path("dummy.wav"), [])
    assert len(turns_empty) == 1
    assert turns_empty[0]["speaker"] == "Спикер 1"

    # Words with gap >= 0.8s triggering speaker alternation
    words = [
        WordTimestamp(word="Привет", start=0.0, end=1.0, probability=0.9),
        WordTimestamp(word="коллеги.", start=1.1, end=1.5, probability=0.9),
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

    # Empty turns fallback
    words_single = [WordTimestamp(word="Hello", start=0.0, end=1.0, probability=0.9)]
    aligned_no_turns = engine._align_words_with_speakers(words_single, [])
    assert len(aligned_no_turns) == 1
    assert aligned_no_turns[0].speaker == "Спикер 1"
    assert aligned_no_turns[0].text == "Hello"

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


def test_ffmpeg_audio_processor_filter_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validates FFmpeg audio filter chain construction."""
    processor = FFmpegAudioProcessor()

    monkeypatch.setattr(settings, "AUDIO_BANDPASS_FILTER", True)
    monkeypatch.setattr(settings, "AUDIO_NOISE_REDUCTION", True)
    monkeypatch.setattr(settings, "AUDIO_NORMALIZE_LOUDNESS", True)
    graph = processor._build_audio_filter_graph()
    assert "highpass=f=70,lowpass=f=7600" in graph
    assert "afftdn=nf=-25" in graph
    assert "loudnorm=I=-16" in graph

    monkeypatch.setattr(settings, "AUDIO_BANDPASS_FILTER", False)
    monkeypatch.setattr(settings, "AUDIO_NOISE_REDUCTION", False)
    monkeypatch.setattr(settings, "AUDIO_NORMALIZE_LOUDNESS", False)
    assert processor._build_audio_filter_graph() == ""


@pytest.mark.asyncio
async def test_ffmpeg_audio_processor_fallback_on_filter_failure(tmp_path: Path) -> None:
    """Validates fallback to plain 16kHz PCM when advanced FFmpeg filters fail."""
    processor = FFmpegAudioProcessor()
    input_file = tmp_path / "test.mp3"
    input_file.write_bytes(b"DATA")
    output_file = tmp_path / "test.wav"

    mock_res_fail = MagicMock(returncode=1, stderr="No such filter: afftdn")
    mock_res_success = MagicMock(returncode=0, stderr="")

    with patch("subprocess.run", side_effect=[mock_res_fail, mock_res_success]) as mock_sub:
        res = await processor.normalize_and_vad(input_file, output_file)
        assert res == output_file
        assert mock_sub.call_count == 2


def test_inference_engine_whisper_primary_fail_fallback_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validates WhisperModel fallback when primary model size cannot be loaded."""
    engine = InferenceEngine()
    mock_whisper_class = MagicMock(side_effect=[Exception("Out of VRAM"), MagicMock()])

    monkeypatch.setattr(settings, "WHISPER_MODEL_SIZE", "large-v3-turbo")
    monkeypatch.setattr(settings, "WHISPER_FALLBACK_MODEL_SIZE", "medium")

    with patch.dict("sys.modules", {"faster_whisper": MagicMock(WhisperModel=mock_whisper_class)}):
        engine.load_models()
        assert engine._is_loaded is True
        assert mock_whisper_class.call_count == 2
        assert mock_whisper_class.call_args_list[0][0][0] == "large-v3-turbo"
        assert mock_whisper_class.call_args_list[1][0][0] == "medium"


def test_inference_engine_whisper_transcription_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validates that transcribe passes enhanced beam search, vad, and repetition parameters."""
    engine = InferenceEngine()
    mock_whisper = MagicMock()
    mock_info = MagicMock(language="ru", duration=12.0)
    mock_word = MagicMock(word=" Тестовое ", start=1.0, end=2.0, probability=0.98)
    mock_segment = MagicMock(words=[mock_word])

    mock_whisper.transcribe.return_value = ([mock_segment], mock_info)
    engine.whisper_model = mock_whisper

    monkeypatch.setattr(settings, "WHISPER_BEAM_SIZE", 5)
    monkeypatch.setattr(settings, "WHISPER_BEST_OF", 5)
    monkeypatch.setattr(settings, "WHISPER_REPETITION_PENALTY", 1.05)
    monkeypatch.setattr(settings, "WHISPER_NO_REPEAT_NGRAM_SIZE", 3)

    words, lang, dur = engine._run_transcription(Path("audio.wav"))
    assert lang == "ru"
    assert dur == 12.0
    assert len(words) == 1
    assert words[0].word == "Тестовое"

    mock_whisper.transcribe.assert_called_once()
    _, kwargs = mock_whisper.transcribe.call_args
    assert kwargs["beam_size"] == 5
    assert kwargs["best_of"] == 5
    assert kwargs["repetition_penalty"] == 1.05
    assert kwargs["no_repeat_ngram_size"] == 3
    assert kwargs["word_timestamps"] is True
    assert kwargs["vad_filter"] is True
    assert "min_silence_duration_ms" in kwargs["vad_parameters"]


def test_inference_engine_diarization_pyannote_integration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validates PyAnnote pipeline turn extraction and speaker mapping."""
    engine = InferenceEngine()

    mock_turn1 = MagicMock(start=0.0, end=3.0)
    mock_turn2 = MagicMock(start=3.2, end=6.0)

    mock_track1 = (mock_turn1, None, "SPEAKER_00")
    mock_track2 = (mock_turn2, None, "SPEAKER_01")

    mock_diarization_res = MagicMock()
    mock_diarization_res.itertracks.return_value = [mock_track1, mock_track2]

    mock_pipeline = MagicMock(return_value=mock_diarization_res)
    engine.diarization_pipeline = mock_pipeline

    monkeypatch.setattr(settings, "DIARIZATION_MIN_SPEAKERS", 2)
    monkeypatch.setattr(settings, "DIARIZATION_MAX_SPEAKERS", 4)

    turns = engine._run_diarization(Path("audio.wav"), [])
    assert len(turns) == 2
    assert turns[0]["speaker"] == "Спикер 1"
    assert turns[1]["speaker"] == "Спикер 2"
    mock_pipeline.assert_called_once_with("audio.wav", min_speakers=2, max_speakers=4)


def test_inference_engine_real_wav_features_and_clustering(tmp_path: Path) -> None:
    """Validates acoustic feature extraction with real mono and stereo WAV files, and clustering edges."""
    engine = InferenceEngine()

    # 1. Mono WAV
    mono_wav = tmp_path / "mono.wav"
    create_test_wav(mono_wav, channels=1, duration=1.0)

    segments = [
        {"start": 0.0, "end": 0.4, "words": [1, 2]},
        {"start": 0.5, "end": 0.9, "words": [3, 4]},
        {"start": 0.95, "end": 0.96, "words": []},  # Short chunk < 200 samples
    ]
    features_mono = engine._extract_segment_acoustic_features(mono_wav, segments)
    assert len(features_mono) == 3
    assert features_mono[2] == [0.0, 0.0, 0.0, 0.0, 0.0]

    # 2. Stereo WAV
    stereo_wav = tmp_path / "stereo.wav"
    create_test_wav(stereo_wav, channels=2, duration=1.0)
    features_stereo = engine._extract_segment_acoustic_features(stereo_wav, segments[:2])
    assert len(features_stereo) == 2

    # 3. Clustering edges: num_segments <= 1
    assert engine._cluster_acoustic_features([[1.0, 2.0]], 1) == [0]

    # 4. Clustering exception fallback
    with patch(
        "sklearn.cluster.AgglomerativeClustering.fit_predict",
        side_effect=RuntimeError("Clustering failed"),
    ):
        labels_fallback = engine._cluster_acoustic_features([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]], 3)
        assert labels_fallback == [0, 1, 0]
