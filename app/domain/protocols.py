# filename: app/domain/protocols.py
"""Domain protocols (structural interfaces) adhering to duck typing principles."""

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from app.domain.entities import ConversationAnalysis


@runtime_checkable
class AudioPreprocessorProtocol(Protocol):
    async def normalize_and_vad(self, input_path: Path, output_path: Path) -> Path:
        """Normalizes sample rate, channels, and extracts active voice frames."""
        ...


@runtime_checkable
class SpeechRecognizerProtocol(Protocol):
    async def transcribe(self, audio_path: Path) -> tuple[str, list[dict[str, Any]]]:
        """Transcribes audio, yielding language and raw word segments."""
        ...


@runtime_checkable
class DiarizerProtocol(Protocol):
    async def diarize(self, audio_path: Path) -> list[dict[str, Any]]:
        """Extracts speaker turns with start, end, and speaker IDs."""
        ...


@runtime_checkable
class LLMIntelligenceEngineProtocol(Protocol):
    async def extract_intelligence(self, text: str, language: str = "auto") -> ConversationAnalysis:
        """Performs structured extraction of summaries, action items, and sentiment."""
        ...
