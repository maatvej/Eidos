# filename: tests/test_account_api.py
"""Integration tests for Account Management and Individual Transcription History endpoints."""

import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from httpx import AsyncClient

from app.db.models import Transcription


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
async def test_update_password_validation(client: AsyncClient, test_user) -> None:
    """Validates password update requirement for current password verification."""
    # Set known password for test user
    await sync_to_async(test_user.set_password)("old_password_123")
    await sync_to_async(test_user.save)()

    # 1. Attempt with wrong current password -> 400 Bad Request
    wrong_payload = {
        "current_password": "wrong_password",
        "new_password": "new_secure_password_123",
    }
    resp_wrong = await client.patch("/api/v1/account/me", json=wrong_payload)
    assert resp_wrong.status_code == 400
    assert "Incorrect current password" in resp_wrong.json()["detail"]

    # 2. Attempt with correct current password -> 200 OK
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
    # Clean up any existing records for test user
    await sync_to_async(Transcription.objects.filter(user_id=test_user.pk).delete)()

    # Create test transcriptions in DB
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
    resp = await client.get("/api/v1/account/transcriptions?page=1&limit=10")
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

    # Create record owned by test_user
    my_trans = await sync_to_async(Transcription.objects.create)(
        user_id=test_user.pk,
        title="Моя транскрипция",
        original_filename="my_file.wav",
        transcription_text="Текст моей транскрипции.",
    )

    # Create record owned by other_user
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

    # 2. Fetch other user's record -> 404 Not Found (Object-level permission check)
    resp_other = await client.get(f"/api/v1/account/transcriptions/{other_trans.id}")
    assert resp_other.status_code == 404


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_delete_transcription_ownership(client: AsyncClient, test_user) -> None:
    """Validates deleting owned transcription record and permission isolation for non-owned records."""
    User = get_user_model()
    other_user, _ = await sync_to_async(User.objects.get_or_create)(
        username="other_user_2", defaults={"email": "other2@eidos.ai"}
    )

    my_trans = await sync_to_async(Transcription.objects.create)(
        user_id=test_user.pk,
        title="Транскрипция к удалению",
        original_filename="delete_me.wav",
    )
    other_trans = await sync_to_async(Transcription.objects.create)(
        user_id=other_user.pk,
        title="Защищенная транскрипция",
        original_filename="protected.wav",
    )

    # 1. Attempt to delete other user's record -> 404 Not Found
    resp_del_other = await client.delete(f"/api/v1/account/transcriptions/{other_trans.id}")
    assert resp_del_other.status_code == 404

    # 2. Delete own record -> 204 No Content
    resp_del_my = await client.delete(f"/api/v1/account/transcriptions/{my_trans.id}")
    assert resp_del_my.status_code == 204

    # Verify record is deleted from DB
    exists = await sync_to_async(Transcription.objects.filter(id=my_trans.id).exists)()
    assert exists is False
