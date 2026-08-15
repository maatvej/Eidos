# filename: tests/test_security.py
"""Unit and integration tests for FastAPI & Django Security Bridge (app/core/security.py)."""

from unittest.mock import MagicMock
from uuid import uuid4

import jwt
import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from fastapi import HTTPException

from app.core.django_settings import SECRET_KEY
from app.core.security import (
    ALGORITHM,
    DjangoUserSchema,
    RequireGroup,
    RequirePermission,
    _check_django_group,
    _check_django_permission,
    _get_django_user_by_id,
    _get_django_user_from_session,
    _get_user_metadata,
    create_jwt_for_django_user,
    get_current_django_user,
)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_create_jwt_for_django_user(test_user) -> None:
    """Verifies creation and decoding of JWT tokens for Django users."""
    token = create_jwt_for_django_user(test_user)
    assert isinstance(token, str)

    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["user_id"] == test_user.pk
    assert payload["username"] == test_user.username
    assert payload["email"] == test_user.email
    assert payload["is_staff"] is True
    assert payload["is_superuser"] is True


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_get_django_user_by_id(test_user) -> None:
    """Verifies fetching active user by ID and handling missing/inactive users."""
    user = await _get_django_user_by_id(test_user.pk)
    assert user is not None
    assert user.pk == test_user.pk

    missing = await _get_django_user_by_id(999999)
    assert missing is None

    def set_user_inactive():
        test_user.is_active = False
        test_user.save()

    def set_user_active():
        test_user.is_active = True
        test_user.save()

    await sync_to_async(set_user_inactive)()
    inactive = await _get_django_user_by_id(test_user.pk)
    assert inactive is None

    await sync_to_async(set_user_active)()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_get_django_user_from_session(test_user) -> None:
    """Verifies session-based user retrieval and expired/invalid session handling."""

    def create_test_session(user_id: str | None = None):
        from django.contrib.sessions.backends.db import SessionStore

        s = SessionStore()
        if user_id:
            s["_auth_user_id"] = user_id
        s.save()
        return s.session_key

    session_key = await sync_to_async(create_test_session)(str(test_user.pk))
    user = await _get_django_user_from_session(session_key)
    assert user is not None
    assert user.pk == test_user.pk

    # Session exists but has no _auth_user_id
    session_no_uid = await sync_to_async(create_test_session)(None)
    user_no_uid = await _get_django_user_from_session(session_no_uid)
    assert user_no_uid is None

    invalid_session = await _get_django_user_from_session("non_existent_key")
    assert invalid_session is None


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_check_django_permission_and_group(test_user) -> None:
    """Validates permission and group checks for superusers, normal users, missing and inactive users."""
    User = get_user_model()
    unique_username = f"normal_user_{uuid4().hex[:8]}"

    def setup_normal_user():
        normal_user = User.objects.create_user(
            username=unique_username, password="password123", is_active=True
        )
        group, _ = Group.objects.get_or_create(name="AdminGroup")
        normal_user.groups.add(group)
        return normal_user, group

    normal_user, _group = await sync_to_async(setup_normal_user)()

    # Superuser check
    assert await _check_django_permission(test_user, "any.permission") is True
    assert await _check_django_group(test_user, "AnyGroup") is True

    # Normal user check
    assert await _check_django_permission(normal_user, "db.add_transcriptionjob") is False
    assert await _check_django_group(normal_user, "AdminGroup") is True

    # Inactive user check
    def set_normal_user_inactive():
        normal_user.is_active = False
        normal_user.save()

    await sync_to_async(set_normal_user_inactive)()
    assert await _check_django_permission(normal_user, "db.add_transcriptionjob") is False
    assert await _check_django_group(normal_user, "AdminGroup") is False

    # Missing user check (User.DoesNotExist branch)
    fake_user = User(pk=999999)
    assert await _check_django_permission(fake_user, "db.add_transcriptionjob") is False
    assert await _check_django_group(fake_user, "AdminGroup") is False


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_get_user_metadata(test_user) -> None:
    """Validates fetching group list and explicit permissions for user."""

    def add_user_to_group():
        group, _ = Group.objects.get_or_create(name="Editors")
        test_user.groups.add(group)

    await sync_to_async(add_user_to_group)()

    groups, _permissions = await _get_user_metadata(test_user)
    assert "Editors" in groups


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_get_current_django_user_via_bearer_and_session(test_user) -> None:
    """Verifies get_current_django_user dependency resolution via Bearer JWT and Session Cookie."""
    token = create_jwt_for_django_user(test_user)
    bearer = MagicMock(credentials=token)
    request = MagicMock()

    # 1. Bearer token resolution
    user_schema = await get_current_django_user(request=request, bearer=bearer)
    assert user_schema.id == test_user.pk
    assert user_schema.username == test_user.username

    # 2. Session cookie resolution fallback
    def create_session():
        from django.contrib.sessions.backends.db import SessionStore

        s = SessionStore()
        s["_auth_user_id"] = str(test_user.pk)
        s.save()
        return s.session_key

    s_key = await sync_to_async(create_session)()
    user_from_sess = await get_current_django_user(request=request, bearer=None, sessionid=s_key)
    assert user_from_sess.id == test_user.pk


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_get_current_django_user_invalid_token_or_missing() -> None:
    """Verifies HTTP 401 when token is invalid or user is not found."""
    request = MagicMock()
    invalid_bearer = MagicMock(credentials="invalid.jwt.token")

    with pytest.raises(HTTPException) as exc_info:
        await get_current_django_user(request=request, bearer=invalid_bearer)
    assert exc_info.value.status_code == 401

    with pytest.raises(HTTPException) as exc_info2:
        await get_current_django_user(request=request, bearer=None, sessionid=None)
    assert exc_info2.value.status_code == 401


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_require_permission_and_require_group_dependencies(test_user) -> None:
    """Verifies RequirePermission and RequireGroup FastAPI dependency callable classes."""
    User = get_user_model()
    unique_username = f"perm_user_{uuid4().hex[:8]}"

    def setup_user_with_permission():
        user = User.objects.create_user(
            username=unique_username, password="password123", is_active=True
        )
        group, _ = Group.objects.get_or_create(name="Managers")
        user.groups.add(group)

        # Grant specific permission to user
        content_type = ContentType.objects.get_for_model(User)
        perm, _ = Permission.objects.get_or_create(
            codename="change_user",
            content_type=content_type,
            defaults={"name": "Can change user"},
        )
        user.user_permissions.add(perm)
        return user

    normal_user = await sync_to_async(setup_user_with_permission)()

    user_schema = DjangoUserSchema(
        id=normal_user.pk,
        username=normal_user.username,
        email="",
        is_active=True,
        is_staff=False,
        is_superuser=False,
    )

    perm_dep_allowed = RequirePermission("auth.change_user")
    perm_dep_forbidden = RequirePermission("db.add_transcriptionjob")
    group_dep_allowed = RequireGroup("Managers")
    group_dep_forbidden = RequireGroup("UnknownGroup")

    admin_schema = DjangoUserSchema(
        id=test_user.pk,
        username=test_user.username,
        email=test_user.email,
        is_active=True,
        is_staff=True,
        is_superuser=True,
    )
    # Superuser passes any check
    assert await perm_dep_forbidden(admin_schema) == admin_schema
    assert await group_dep_forbidden(admin_schema) == admin_schema

    # Normal user with granted permission and group
    assert await perm_dep_allowed(user_schema) == user_schema
    assert await group_dep_allowed(user_schema) == user_schema

    # Normal user without permission or group -> 403
    with pytest.raises(HTTPException) as exc1:
        await perm_dep_forbidden(user_schema)
    assert exc1.value.status_code == 403

    with pytest.raises(HTTPException) as exc2:
        await group_dep_forbidden(user_schema)
    assert exc2.value.status_code == 403

    # User not found in DB -> 401
    missing_user_schema = DjangoUserSchema(
        id=999999,
        username="ghost_user",
        email="",
        is_active=True,
        is_staff=False,
        is_superuser=False,
    )
    with pytest.raises(HTTPException) as exc_missing_perm:
        await perm_dep_allowed(missing_user_schema)
    assert exc_missing_perm.value.status_code == 401

    with pytest.raises(HTTPException) as exc_missing_grp:
        await group_dep_allowed(missing_user_schema)
    assert exc_missing_grp.value.status_code == 401
