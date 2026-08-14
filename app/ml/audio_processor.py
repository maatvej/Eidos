# filename: app/ml/audio_processor.py
"""FFmpeg audio normalization and preprocessing engine with cross-platform support."""

import asyncio
import subprocess
from pathlib import Path

from app.core.logging import logger
from app.domain.exceptions import AudioProcessingError


class FFmpegAudioProcessor:
    """Handles subprocess execution for audio conversion and normalization."""

    async def normalize_and_vad(self, input_path: Path, output_path: Path) -> Path:
        """Converts audio to 16kHz mono WAV PCM format."""
        if not input_path.exists():
            raise AudioProcessingError(f"Input audio file does not exist: {input_path}")

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ]

        logger.info(f"Executing FFmpeg command: {' '.join(cmd)}")

        def _run_ffmpeg() -> tuple[int, str]:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
            return res.returncode, res.stderr

        # Run synchronously in thread pool for Windows & Linux compatibility
        returncode, stderr_text = await asyncio.to_thread(_run_ffmpeg)

        if returncode != 0:
            logger.error(f"FFmpeg process failed: {stderr_text}")
            raise AudioProcessingError(f"Audio normalization failed: {stderr_text}")

        return output_path
