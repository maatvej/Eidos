# filename: app/ml/audio_processor.py
"""FFmpeg audio normalization and preprocessing engine with cross-platform support."""

import asyncio
import subprocess
from pathlib import Path

from app.core.config import settings
from app.core.logging import logger
from app.core.profiler import profile_async, profile_sync
from app.domain.exceptions import AudioProcessingError


class FFmpegAudioProcessor:
    """Handles subprocess execution for audio conversion, dynamic loudness normalization, and denoising."""

    @profile_sync(name="ffmpeg_filter_graph_builder", subfolder="audio")
    def _build_audio_filter_graph(self) -> str:
        """Constructs an optimized FFmpeg audio filter chain for speech clarity."""
        filters: list[str] = []

        if settings.AUDIO_BANDPASS_FILTER:
            # Cut low-frequency mic rumble (< 70Hz) and high-frequency hiss (> 7600Hz)
            filters.append("highpass=f=70,lowpass=f=7600")

        if settings.AUDIO_NOISE_REDUCTION:
            # Adaptive FFT denoiser filter for background noise suppression
            filters.append("afftdn=nf=-25")

        if settings.AUDIO_NORMALIZE_LOUDNESS:
            # EBU R128 loudness normalization for optimal acoustic SNR in Whisper and PyAnnote
            filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")

        return ",".join(filters)

    @profile_async(name="ffmpeg_audio_normalization", subfolder="audio")
    async def normalize_and_vad(self, input_path: Path, output_path: Path) -> Path:
        """Converts audio to 16kHz mono WAV PCM format with speech enhancement filters."""
        if not input_path.exists():
            raise AudioProcessingError(f"Input audio file does not exist: {input_path}")

        filter_graph = self._build_audio_filter_graph()

        # Primary command with advanced speech-enhancing filters
        cmd = [
            "ffmpeg",
            "-y",
            "-nostdin",
            "-threads",
            str(settings.FFMPEG_THREADS),
            "-i",
            str(input_path),
            "-vn",
            "-sn",
            "-dn",
        ]

        if filter_graph:
            cmd.extend(["-af", filter_graph])

        cmd.extend(
            [
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(output_path),
            ]
        )

        logger.info(f"Executing enhanced FFmpeg command: {' '.join(cmd)}")

        def _run_cmd(command: list[str]) -> tuple[int, str]:
            res = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
            return res.returncode, res.stderr

        # Run synchronously in thread pool for cross-platform compatibility
        returncode, stderr_text = await asyncio.to_thread(_run_cmd, cmd)

        if returncode != 0 and filter_graph:
            # If advanced filters fail on a minimal FFmpeg installation, fallback to plain PCM conversion
            logger.warning(
                f"Enhanced FFmpeg filters failed ({stderr_text}). Falling back to basic 16kHz conversion."
            )
            fallback_cmd = [
                "ffmpeg",
                "-y",
                "-nostdin",
                "-threads",
                str(settings.FFMPEG_THREADS),
                "-i",
                str(input_path),
                "-vn",
                "-sn",
                "-dn",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(output_path),
            ]
            returncode, stderr_text = await asyncio.to_thread(_run_cmd, fallback_cmd)

        if returncode != 0:
            logger.error(f"FFmpeg process failed: {stderr_text}")
            raise AudioProcessingError(f"Audio normalization failed: {stderr_text}")

        return output_path
