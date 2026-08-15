# filename: tests/test_account_api.py
"""Integration tests for Account Management and Individual Transcription History endpoints."""

from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from httpx import AsyncClient

from app.api.v1.endpoints.account import _get_django_user_orm
from app.db.models import Transcription
from app.repository.job_repository import VoiceProfileRepository


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_get_django_user_orm_missing() -> None:
    """Validates _get_django_user_orm returns None when user does not exist."""
    user = await _get_django_user_orm(999999)
    assert user is None


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_get_account_profile(client: AsyncClient, test_user) -> None:
    """Validates fetching profile information for current user."""
    response = await client.get("/api/v1/account/me")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_user.pk
    assert data["username"] == test_user.username
    assert data["email"] == test_user.email


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_get_account_profile_user_not_found(client: AsyncClient) -> None:
    """Validates 404 response when user ORM instance is not found in get_account_profile."""
    with patch("app.api.v1.endpoints.account._get_django_user_orm", return_value=None):
        response = await client.get("/api/v1/account/me")
        assert response.status_code == 404
        assert response.json()["detail"] == "User account not found."


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_update_account_profile(client: AsyncClient, test_user) -> None:
    """Validates updating first name, last name, and email in profile."""
    payload = {
        "first_name": "Иван",
        "last_name": "Петров",
        "email": "ivan.petrov@eidos.ai",
    }
    response = await client.patch("/api/v1/account/me", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "Иван"
    assert data["last_name"] == "Петров"
    assert data["email"] == "ivan.petrov@eidos.ai"
    assert data["full_name"] == "Иван Петров"


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_update_account_profile_user_not_found(client: AsyncClient) -> None:
    """Validates 404 response when user ORM instance is not found in update_account_profile."""
    payload = {"first_name": "Алексей"}
    with patch("app.api.v1.endpoints.account._get_django_user_orm", return_value=None):
        response = await client.patch("/api/v1/account/me", json=payload)
        assert response.status_code == 404
        assert response.json()["detail"] == "User account not found."


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_update_password_validation(client: AsyncClient, test_user) -> None:
    """Validates password update requirement for current password verification."""
    await sync_to_async(test_user.set_password)("old_password_123")
    await sync_to_async(test_user.save)()

    # 1. Missing current password when new password provided -> 400 Bad Request
    missing_curr_payload = {
        "new_password": "new_secure_password_123",
    }
    resp_missing = await client.patch("/api/v1/account/me", json=missing_curr_payload)
    assert resp_missing.status_code == 400
    assert "Current password is required" in resp_missing.json()["detail"]

    # 2. Attempt with wrong current password -> 400 Bad Request
    wrong_payload = {
        "current_password": "wrong_password",
        "new_password": "new_secure_password_123",
    }
    resp_wrong = await client.patch("/api/v1/account/me", json=wrong_payload)
    assert resp_wrong.status_code == 400
    assert "Incorrect current password" in resp_wrong.json()["detail"]

    # 3. Attempt with correct current password -> 200 OK
    correct_payload = {
        "current_password": "old_password_123",
        "new_password": "new_secure_password_123",
    }
    resp_correct = await client.patch("/api/v1/account/me", json=correct_payload)
    assert resp_correct.status_code == 200


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_transcription_history_pagination_and_search(client: AsyncClient, test_user) -> None:
    """Validates listing user's transcriptions with pagination, search, and sorting."""
    await sync_to_async(Transcription.objects.filter(user_id=test_user.pk).delete)()

    await sync_to_async(Transcription.objects.create)(
        user_id=test_user.pk,
        title="Еженедельный созвон команды",
        original_filename="weekly_call.mp3",
        duration_seconds=120.0,
        status="completed",
        transcription_text="Привет всем коллегам.",
    )
    await sync_to_async(Transcription.objects.create)(
        user_id=test_user.pk,
        title="Стратегическое планирование 2026",
        original_filename="strategy.wav",
        duration_seconds=300.0,
        status="completed",
        transcription_text="Обсуждаем задачи на квартал.",
    )

    # 1. Fetch paginated list
    resp = await client.get("/api/v1/account/transcriptions?page=1&limit=10&sort_by=title")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    assert len(data["items"]) >= 2

    # 2. Search filtering
    search_resp = await client.get("/api/v1/account/transcriptions?search=Стратегическое")
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert search_data["total"] == 1
    assert search_data["items"][0]["title"] == "Стратегическое планирование 2026"


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_transcription_detail_and_ownership(client: AsyncClient, test_user) -> None:
    """Validates object-level ownership check on transcription detail view."""
    User = get_user_model()
    other_user, _ = await sync_to_async(User.objects.get_or_create)(
        username="other_user", defaults={"email": "other@eidos.ai"}
    )

    my_trans = await sync_to_async(Transcription.objects.create)(
        user_id=test_user.pk,
        title="Моя транскрипция",
        original_filename="my_file.wav",
        transcription_text="Текст моей транскрипции.",
    )

    other_trans = await sync_to_async(Transcription.objects.create)(
        user_id=other_user.pk,
        title="Чужая транскрипция",
        original_filename="other_file.wav",
        transcription_text="Секретный текст чужого пользователя.",
    )

    # 1. Fetch owned record -> 200 OK
    resp_my = await client.get(f"/api/v1/account/transcriptions/{my_trans.id}")
    assert resp_my.status_code == 200
    assert resp_my.json()["title"] == "Моя транскрипция"

    # 2. Fetch other user's record -> 404 Not Found
    resp_other = await client.get(f"/api/v1/account/transcriptions/{other_trans.id}")
    assert resp_other.status_code == 404


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_delete_transcription_with_disk_file_and_oserror(
    client: AsyncClient, test_user, tmp_path: Path
) -> None:
    """Validates deleting owned transcription record, removing file from disk, and handling OSError."""
    audio_file = tmp_path / "test_to_delete.wav"
    audio_file.write_bytes(b"TEST_AUDIO")

    my_trans = await sync_to_async(Transcription.objects.create)(
        user_id=test_user.pk,
        title="Транскрипция к удалению",
        original_filename="delete_me.wav",
        file_path=str(audio_file),
    )

    # 1. Delete owned record and remove file
    resp_del = await client.delete(f"/api/v1/account/transcriptions/{my_trans.id}")
    assert resp_del.status_code == 204
    assert not audio_file.exists()

    # 2. Delete when Path.unlink raises OSError
    audio_file2 = tmp_path / "test_oserror.wav"
    audio_file2.write_bytes(b"TEST_AUDIO_2")

    my_trans2 = await sync_to_async(Transcription.objects.create)(
        user_id=test_user.pk,
        title="Транскрипция с ошибкой удаления файла",
        original_filename="error_file.wav",
        file_path=str(audio_file2),
    )

    with patch.object(Path, "unlink", side_effect=OSError("Disk locked")):
        resp_del2 = await client.delete(f"/api/v1/account/transcriptions/{my_trans2.id}")
        assert resp_del2.status_code == 204

    # 3. Delete non-existent record -> 404
    resp_404 = await client.delete(f"/api/v1/account/transcriptions/{uuid4()}")
    assert resp_404.status_code == 404


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_stream_transcription_audio(client: AsyncClient, test_user, tmp_path: Path) -> None:
    """Validates audio file streaming endpoint, media types detection, and missing file paths."""
    # 1. Record not found -> 404
    resp_not_found = await client.get(f"/api/v1/account/transcriptions/{uuid4()}/audio")
    assert resp_not_found.status_code == 404

    # 2. Record has no file_path -> 404
    no_file_trans = await sync_to_async(Transcription.objects.create)(
        user_id=test_user.pk,
        title="Без файла",
        original_filename="no_file.wav",
        file_path="",
    )
    resp_no_path = await client.get(f"/api/v1/account/transcriptions/{no_file_trans.id}/audio")
    assert resp_no_path.status_code == 404
    assert "No audio file path recorded" in resp_no_path.json()["detail"]

    # 3. Audio file path does not exist on disk -> 404
    missing_file_trans = await sync_to_async(Transcription.objects.create)(
        user_id=test_user.pk,
        title="Файл отсутствует на диске",
        original_filename="missing.wav",
        file_path="/tmp/non_existent_audio_path_12345.wav",
    )
    resp_disk_missing = await client.get(
        f"/api/v1/account/transcriptions/{missing_file_trans.id}/audio"
    )
    assert resp_disk_missing.status_code == 404
    assert "Audio file not found on storage disk" in resp_disk_missing.json()["detail"]

    # 4. Stream various formats successfully
    formats_to_test = [
        (".mp3", "audio/mpeg"),
        (".wav", "audio/wav"),
        (".m4a", "audio/mp4"),
        (".flac", "audio/flac"),
        (".ogg", "audio/ogg"),
        (".webm", "audio/webm"),
        (".bin", "application/octet-stream"),
    ]

    for ext, expected_content_type in formats_to_test:
        f = tmp_path / f"audio_sample{ext}"
        f.write_bytes(b"RIFF_SAMPLE_DATA")

        rec = await sync_to_async(Transcription.objects.create)(
            user_id=test_user.pk,
            title=f"Запись {ext}",
            original_filename=f"audio_sample{ext}",
            file_path=str(f),
        )

        resp = await client.get(f"/api/v1/account/transcriptions/{rec.id}/audio")
        assert resp.status_code == 200
        assert expected_content_type in resp.headers["content-type"]


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_user_voice_profiles_crud(client: AsyncClient, test_user) -> None:
    """Validates listing and deleting saved voice profiles for current user."""
    repo = VoiceProfileRepository()

    # Create test voice profile
    profile = await repo.save_or_update_voice_profile(
        user_id=test_user.pk,
        name="Иван Иванов",
        embedding=[0.1] * 32,
    )

    # 1. List voice profiles
    resp = await client.get("/api/v1/account/voices")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    matched = [p for p in data if p["id"] == str(profile.id)]
    assert len(matched) == 1
    assert matched[0]["name"] == "Иван Иванов"
    assert matched[0]["samples_count"] == 1

    # 2. Delete existing voice profile
    del_resp = await client.delete(f"/api/v1/account/voices/{profile.id}")
    assert del_resp.status_code == 204

    # Verify deleted
    deleted_check = await repo.get_voice_profile_by_id(profile.id, test_user.pk)
    assert deleted_check is None

    # 3. Delete non-existent profile -> 404
    del_404 = await client.delete(f"/api/v1/account/voices/{uuid4()}")
    assert del_404.status_code == 404
