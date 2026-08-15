# filename: tests/test_protocols.py
"""Unit tests for domain protocols (app/domain/protocols.py) and Django URLs (app/core/django_urls.py)."""

from pathlib import Path
from typing import Any

from app.core.django_urls import urlpatterns
from app.domain.entities import ConversationAnalysis
from app.domain.protocols import (
    AudioPreprocessorProtocol,
    DiarizerProtocol,
    LLMIntelligenceEngineProtocol,
    SpeechRecognizerProtocol,
)


class DummyAudioPreprocessor:
    async def normalize_and_vad(self, input_path: Path, output_path: Path) -> Path:
        return output_path


class DummySpeechRecognizer:
    async def transcribe(self, audio_path: Path) -> tuple[str, list[dict[str, Any]]]:
        return "ru", []


class DummyDiarizer:
    async def diarize(self, audio_path: Path) -> list[dict[str, Any]]:
        return []


class DummyLLMIntelligenceEngine:
    async def extract_intelligence(self, text: str, language: str = "auto") -> ConversationAnalysis:
        return ConversationAnalysis(
            title="Title",
            executive_summary="Summary",
            key_decisions=[],
            action_items=[],
        )


def test_domain_protocols_duck_typing() -> None:
    """Validates runtime conformance of classes implementing domain protocols."""
    preprocessor = DummyAudioPreprocessor()
    assert isinstance(preprocessor, AudioPreprocessorProtocol)

    recognizer = DummySpeechRecognizer()
    assert isinstance(recognizer, SpeechRecognizerProtocol)

    diarizer = DummyDiarizer()
    assert isinstance(diarizer, DiarizerProtocol)

    llm = DummyLLMIntelligenceEngine()
    assert isinstance(llm, LLMIntelligenceEngineProtocol)


def test_django_urls_configuration() -> None:
    """Validates Django URL patterns list configuration."""
    assert len(urlpatterns) >= 2
    route_patterns = [str(pat.pattern) for pat in urlpatterns]
    assert any("admin/" in p for p in route_patterns)
    assert any("accounts/" in p for p in route_patterns)
