# filename: tests/test_domain.py
"""Unit testing suite for domain entities, exception handling, and export formats."""

from uuid import uuid4

from app.db.models import VoiceProfile
from app.domain.entities import (
    TranscriptionResult,
    Utterance,
    VoiceProfileEntity,
    WordTimestamp,
)
from app.services.export_service import ExportService


def test_word_timestamp_validation() -> None:
    word = WordTimestamp(word="Engine", start=0.0, end=0.5, probability=0.98)
    assert word.word == "Engine"
    assert word.start == 0.0
    assert word.end == 0.5


def test_export_service_srt_and_vtt() -> None:
    export_svc = ExportService()
    result = TranscriptionResult(
        utterances=[
            Utterance(
                speaker="SPEAKER_00",
                start=0.0,
                end=2.0,
                text="Hello world.",
                words=[WordTimestamp(word="Hello", start=0.0, end=1.0, probability=0.99)],
            )
        ],
        duration_seconds=2.0,
    )

    srt = export_svc.to_srt(result)
    assert "00:00:00,000 --> 00:00:02,000" in srt
    assert "[SPEAKER_00]: Hello world." in srt

    vtt = export_svc.to_vtt(result)
    assert "WEBVTT" in vtt
    assert "00:00:00.000 --> 00:00:02.000" in vtt


def test_voice_profile_entity_and_model_str() -> None:
    """Validates VoiceProfileEntity instantiation and VoiceProfile ORM __str__ method."""
    profile_id = uuid4()
    entity = VoiceProfileEntity(
        id=profile_id,
        user_id=42,
        name="Сергей Смирнов",
        embedding=[0.1] * 32,
        samples_count=3,
    )
    assert entity.id == profile_id
    assert entity.name == "Сергей Смирнов"
    assert entity.samples_count == 3

    model = VoiceProfile(id=profile_id, user_id=42, name="Сергей Смирнов")
    assert str(model) == "Сергей Смирнов (user_id=42)"
