# filename: app/api/v1/endpoints/account.py
"""FastAPI Router for Account Management and Individual Transcription History with Django ORM integration."""

import math
from pathlib import Path
from uuid import UUID

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User as DjangoUser
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse

from app.core.security import DjangoUserSchema, get_current_django_user
from app.db.models import Transcription
from app.schemas.account import (
    PaginatedTranscriptionListResponse,
    TranscriptionResponse,
    UserProfileResponse,
    UserProfileUpdate,
)


router = APIRouter(prefix="/account", tags=["Account & Transcription History"])


@sync_to_async(thread_sensitive=True)
def _get_django_user_orm(user_id: int) -> DjangoUser | None:
    """Fetch active Django user ORM instance by ID."""
    User = get_user_model()
    try:
        return User.objects.get(pk=user_id, is_active=True)
    except User.DoesNotExist:
        return None


@router.get("/me", response_model=UserProfileResponse)
async def get_account_profile(
    current_user: DjangoUserSchema = Depends(get_current_django_user),
) -> UserProfileResponse:
    """Retrieve the current authenticated user's profile details."""
    user_orm = await _get_django_user_orm(current_user.id)
    if not user_orm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    full_name = f"{user_orm.first_name} {user_orm.last_name}".strip() or user_orm.username

    return UserProfileResponse(
        id=user_orm.pk,
        username=user_orm.username,
        email=user_orm.email,
        first_name=user_orm.first_name,
        last_name=user_orm.last_name,
        full_name=full_name,
        is_active=user_orm.is_active,
        is_staff=user_orm.is_staff,
        is_superuser=user_orm.is_superuser,
        date_joined=user_orm.date_joined,
    )


@router.patch("/me", response_model=UserProfileResponse)
async def update_account_profile(
    payload: UserProfileUpdate,
    current_user: DjangoUserSchema = Depends(get_current_django_user),
) -> UserProfileResponse:
    """Update user profile attributes (first_name, last_name, email) or change password with verification."""
    user_orm = await _get_django_user_orm(current_user.id)
    if not user_orm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    # Password Change Logic
    if payload.new_password:
        if not payload.current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is required to set a new password.",
            )

        password_correct = await sync_to_async(user_orm.check_password)(payload.current_password)
        if not password_correct:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect current password provided.",
            )

        await sync_to_async(user_orm.set_password)(payload.new_password)

    # General profile updates
    if payload.first_name is not None:
        user_orm.first_name = payload.first_name
    if payload.last_name is not None:
        user_orm.last_name = payload.last_name
    if payload.email is not None:
        user_orm.email = payload.email

    await sync_to_async(user_orm.save)()

    full_name = f"{user_orm.first_name} {user_orm.last_name}".strip() or user_orm.username

    return UserProfileResponse(
        id=user_orm.pk,
        username=user_orm.username,
        email=user_orm.email,
        first_name=user_orm.first_name,
        last_name=user_orm.last_name,
        full_name=full_name,
        is_active=user_orm.is_active,
        is_staff=user_orm.is_staff,
        is_superuser=user_orm.is_superuser,
        date_joined=user_orm.date_joined,
    )


@sync_to_async(thread_sensitive=True)
def _get_paginated_transcriptions(
    user_id: int, page: int, limit: int, search: str | None, sort_by: str
) -> tuple[list[Transcription], int]:
    """Sync wrapper for retrieving paginated and filtered user transcriptions."""
    qs = Transcription.objects.filter(user_id=user_id)

    if search:
        qs = qs.filter(title__icontains=search.strip())

    valid_sort_fields = {
        "created_at": "created_at",
        "-created_at": "-created_at",
        "title": "title",
        "-title": "-title",
        "duration_seconds": "duration_seconds",
        "-duration_seconds": "-duration_seconds",
        "status": "status",
        "-status": "-status",
    }
    ordering = valid_sort_fields.get(sort_by, "-created_at")
    qs = qs.order_by(ordering)

    total = qs.count()
    offset = (page - 1) * limit
    items = list(qs[offset : offset + limit])

    return items, total


@router.get("/transcriptions", response_model=PaginatedTranscriptionListResponse)
async def list_user_transcriptions(
    page: int = Query(default=1, ge=1, description="Page number starting from 1"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page"),
    search: str | None = Query(default=None, description="Search term for filtering by title"),
    sort_by: str = Query(
        default="-created_at", description="Field to sort by (e.g. -created_at, title)"
    ),
    current_user: DjangoUserSchema = Depends(get_current_django_user),
) -> PaginatedTranscriptionListResponse:
    """Fetch paginated transcription history belonging strictly to the logged-in user."""
    items, total = await _get_paginated_transcriptions(
        user_id=current_user.id, page=page, limit=limit, search=search, sort_by=sort_by
    )

    total_pages = math.ceil(total / limit) if total > 0 else 1

    transcription_responses = [
        TranscriptionResponse(
            id=item.id,
            user_id=item.user_id,
            title=item.title,
            original_filename=item.original_filename,
            audio_url=item.audio_url or f"/api/v1/account/transcriptions/{item.id}/audio",
            file_path=item.file_path,
            transcription_text=item.transcription_text,
            language=item.language,
            duration_seconds=item.duration_seconds,
            status=item.status,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in items
    ]

    return PaginatedTranscriptionListResponse(
        items=transcription_responses,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )


@sync_to_async(thread_sensitive=True)
def _get_user_transcription_by_id(transcription_id: UUID, user_id: int) -> Transcription | None:
    """Retrieve user transcription ensuring strict resource ownership."""
    try:
        return Transcription.objects.get(id=transcription_id, user_id=user_id)
    except Transcription.DoesNotExist:
        return None


@router.get("/transcriptions/{transcription_id}", response_model=TranscriptionResponse)
async def get_user_transcription_detail(
    transcription_id: UUID,
    current_user: DjangoUserSchema = Depends(get_current_django_user),
) -> TranscriptionResponse:
    """Retrieve full details of a specific transcription owned by the logged-in user.

    Returns 404 Not Found if record belongs to another user or does not exist.
    """
    item = await _get_user_transcription_by_id(
        transcription_id=transcription_id, user_id=current_user.id
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcription record '{transcription_id}' not found.",
        )

    return TranscriptionResponse(
        id=item.id,
        user_id=item.user_id,
        title=item.title,
        original_filename=item.original_filename,
        audio_url=item.audio_url or f"/api/v1/account/transcriptions/{item.id}/audio",
        file_path=item.file_path,
        transcription_text=item.transcription_text,
        language=item.language,
        duration_seconds=item.duration_seconds,
        status=item.status,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.delete("/transcriptions/{transcription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_transcription(
    transcription_id: UUID,
    current_user: DjangoUserSchema = Depends(get_current_django_user),
) -> Response:
    """Delete a specific transcription record and permanently remove associated audio files from disk.

    Returns 204 No Content on success, or 404 Not Found if resource doesn't exist/belong to user.
    """
    item = await _get_user_transcription_by_id(
        transcription_id=transcription_id, user_id=current_user.id
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcription record '{transcription_id}' not found.",
        )

    file_path_str = item.file_path
    await sync_to_async(item.delete)()

    # Delete local audio file if path exists on disk
    if file_path_str:
        p = Path(file_path_str)
        if p.exists() and p.is_file():
            try:
                p.unlink()
            except OSError:
                pass

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/transcriptions/{transcription_id}/audio")
async def stream_transcription_audio(
    transcription_id: UUID,
    current_user: DjangoUserSchema = Depends(get_current_django_user),
) -> FileResponse:
    """Streams audio file associated with a user's transcription record."""
    item = await _get_user_transcription_by_id(
        transcription_id=transcription_id, user_id=current_user.id
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcription record '{transcription_id}' not found.",
        )

    if not item.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No audio file path recorded for this transcription.",
        )

    audio_path = Path(item.file_path)
    if not audio_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not found on storage disk.",
        )

    ext = audio_path.suffix.lower()
    content_types = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
        ".webm": "audio/webm",
    }
    media_type = content_types.get(ext, "application/octet-stream")
    return FileResponse(path=audio_path, media_type=media_type, filename=item.original_filename)
