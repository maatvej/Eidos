# filename: app/db/admin.py
"""Django Admin site registration for domain models."""

from django.contrib import admin

from app.db.models import Transcription, TranscriptionJob


@admin.register(TranscriptionJob)
class TranscriptionJobAdmin(admin.ModelAdmin):
    """Admin configuration for TranscriptionJob ORM model."""

    list_display = (
        "id",
        "filename",
        "status",
        "progress_percentage",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("id", "filename", "current_step")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Transcription)
class TranscriptionAdmin(admin.ModelAdmin):
    """Admin configuration for Transcription ORM model."""

    list_display = (
        "id",
        "title",
        "user",
        "status",
        "duration_seconds",
        "created_at",
    )
    list_filter = ("status", "created_at", "language")
    search_fields = ("id", "title", "original_filename", "user__username", "user__email")
    readonly_fields = ("id", "created_at", "updated_at")
