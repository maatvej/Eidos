# filename: app/db/models.py
"""Django ORM database models for Eidos application."""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class TranscriptionStatus(models.TextChoices):
    """Enumeration of possible transcription processing states."""

    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class Transcription(models.Model):
    """Django ORM model representing individual user transcriptions."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transcriptions",
        db_index=True,
    )
    title = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    audio_url = models.CharField(max_length=512, blank=True, default="")
    file_path = models.CharField(max_length=512, blank=True, default="")
    transcription_text = models.TextField(blank=True, default="")
    language = models.CharField(max_length=50, blank=True, null=True, default="ru")
    duration_seconds = models.FloatField(default=0.0)
    status = models.CharField(
        max_length=20,
        choices=TranscriptionStatus.choices,
        default=TranscriptionStatus.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "transcriptions"
        verbose_name = "Transcription"
        verbose_name_plural = "Transcriptions"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.title} ({self.status})"


class TranscriptionJob(models.Model):
    """Django ORM model representing asynchronous transcription jobs."""

    id = models.CharField(max_length=36, primary_key=True, default=uuid.uuid4)
    filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=512)
    status = models.CharField(max_length=50, db_index=True, default="PENDING")
    progress_percentage = models.FloatField(default=0.0)
    current_step = models.CharField(max_length=100, default="Initialized")
    result_json = models.TextField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "transcription_jobs"
        verbose_name = "Transcription Job"
        verbose_name_plural = "Transcription Jobs"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.filename} ({self.status})"


class VoiceProfile(models.Model):
    """Django ORM model representing saved speaker voice profiles with acoustic embeddings."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="voice_profiles",
        db_index=True,
    )
    name = models.CharField(max_length=255, db_index=True)
    embedding = models.JSONField(default=list)
    samples_count = models.IntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "voice_profiles"
        verbose_name = "Voice Profile"
        verbose_name_plural = "Voice Profiles"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="unique_user_voice_profile_name")
        ]

    def __str__(self) -> str:
        return f"{self.name} (user_id={self.user_id})"


# Model aliases for multi-ORM compatibility
TranscriptionJobModel = TranscriptionJob
VoiceProfileModel = VoiceProfile
