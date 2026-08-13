# filename: app/domain/entities.py
"""Domain entities representing core business models and transcription schema."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(StrEnum):
    PENDING = "PENDING"
    PREPROCESSING = "PREPROCESSING"
    TRANSCRIBING = "TRANSCRIBING"
    DIARIZING = "DIARIZING"
    POST_PROCESSING = "POST_PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WordTimestamp(BaseModel):
    """Word-level alignment timestamp."""

    model_config = ConfigDict(frozen=True)

    word: str
    start: float = Field(ge=0.0, description="Start time in seconds")
    end: float = Field(ge=0.0, description="End time in seconds")
    probability: float = Field(ge=0.0, le=1.0)


class Utterance(BaseModel):
    """A contiguous turn of speech attributed to a specific speaker."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    speaker: str
    start: float = Field(ge=0.0)
    end: float = Field(ge=0.0)
    text: str
    words: list[WordTimestamp] = Field(default_factory=list)


class ActionItem(BaseModel):
    """Extracted actionable task from conversation intelligence."""

    task: str
    owner: str | None = None
    due_date: str | None = None
    priority: str = Field(default="MEDIUM", pattern="^(HIGH|MEDIUM|LOW)$")


class ConversationAnalysis(BaseModel):
    """Structured executive intelligence extracted via LLM."""

    title: str | None = Field(
        default=None, description="Auto-generated concise topic/title for the transcript"
    )
    timestamp: str | None = Field(
        default=None, description="Formatted ISO timestamp of transcription generation"
    )
    executive_summary: str
    key_decisions: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    overall_sentiment: str = Field(default="NEUTRAL")


class TranscriptionResult(BaseModel):
    """Complete transcript representation containing utterances and extracted intelligence."""

    utterances: list[Utterance] = Field(default_factory=list)
    analysis: ConversationAnalysis | None = None
    duration_seconds: float = Field(ge=0.0, default=0.0)
    detected_language: str = "en"


class JobProgress(BaseModel):
    """Real-time progress updates for backend status polling."""

    status: JobStatus
    progress_percentage: float = Field(ge=0.0, le=100.0)
    current_step: str
    error_message: str | None = None


class TranscriptionJobEntity(BaseModel):
    """Domain representation of a processing job."""

    id: UUID
    filename: str
    file_path: str
    status: JobStatus
    progress_percentage: float = 0.0
    current_step: str = "Initialized"
    result: TranscriptionResult | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
