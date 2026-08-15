# filename: app/schemas/account.py
"""Pydantic v2 schemas for Account Management and Transcription History."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserProfileResponse(BaseModel):
    """Schema for returning user profile details."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    first_name: str = ""
    last_name: str = ""
    full_name: str = ""
    is_active: bool
    is_staff: bool
    is_superuser: bool
    date_joined: datetime | None = None


class UserProfileUpdate(BaseModel):
    """Schema for updating user profile attributes and security credentials."""

    first_name: str | None = Field(default=None, max_length=150)
    last_name: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=254)
    current_password: str | None = Field(
        default=None,
        description="Current password required for changing password or sensitive profile settings",
    )
    new_password: str | None = Field(
        default=None, min_length=8, description="New password meeting security policies"
    )


class TranscriptionResponse(BaseModel):
    """Schema for returning detailed transcription history records."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: int
    title: str
    original_filename: str
    audio_url: str | None = ""
    file_path: str | None = ""
    transcription_text: str = ""
    language: str | None = "ru"
    duration_seconds: float = 0.0
    status: str
    created_at: datetime
    updated_at: datetime


class PaginatedTranscriptionListResponse(BaseModel):
    """Paginated wrapper for user transcription history."""

    items: list[TranscriptionResponse]
    total: int
    page: int
    limit: int
    total_pages: int


class SpeakerRenameRequest(BaseModel):
    """Schema for bulk speaker renaming request payload."""

    old_speaker_label: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Existing speaker identifier or label to be replaced.",
    )
    new_speaker_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="New human-readable speaker name or alias.",
    )


class VoiceProfileResponse(BaseModel):
    """Schema for returning saved speaker voice profile details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: int
    name: str
    samples_count: int
    created_at: datetime
    updated_at: datetime
