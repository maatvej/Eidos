# filename: app/core/security.py
"""FastAPI & Django Shared Authentication & Permission Bridge.

Supports decoding both Django Session Cookies and Signed JWT Bearer Tokens,
and enforces Django granular Permissions and Group memberships via async ORM wrappers.
"""

from datetime import UTC, datetime, timedelta

import jwt
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User as DjangoUser
from django.contrib.sessions.models import Session
from django.utils import timezone
from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.core.django_settings import SECRET_KEY


ALGORITHM = "HS256"
JWT_EXPIRATION_MINUTES = 60 * 24  # 24 Hours

security_bearer = HTTPBearer(auto_error=False)


class DjangoUserSchema(BaseModel):
    """Pydantic representation of the authenticated Django user."""

    id: int
    username: str
    email: str
    is_active: bool
    is_staff: bool
    is_superuser: bool
    groups: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


def create_jwt_for_django_user(user: DjangoUser, expires_delta: timedelta | None = None) -> str:
    """Creates a signed JWT access token containing Django user claims."""
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=JWT_EXPIRATION_MINUTES))
    payload = {
        "user_id": user.pk,
        "username": user.username,
        "email": user.email,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


@sync_to_async(thread_sensitive=True)
def _get_django_user_from_session(session_key: str) -> DjangoUser | None:
    """Retrieves and validates active Django user associated with a session ID."""
    User = get_user_model()
    try:
        session = Session.objects.get(session_key=session_key, expire_date__gt=timezone.now())
        session_data = session.get_decoded()
        user_id = session_data.get("_auth_user_id")
        if not user_id:
            return None
        user = User.objects.get(pk=user_id)
        return user if user.is_active else None
    except (Session.DoesNotExist, User.DoesNotExist):
        return None


@sync_to_async(thread_sensitive=True)
def _get_django_user_by_id(user_id: int) -> DjangoUser | None:
    """Retrieves active Django user by primary key."""
    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
        return user if user.is_active else None
    except User.DoesNotExist:
        return None


@sync_to_async(thread_sensitive=True)
def _check_django_permission(user: DjangoUser, perm: str) -> bool:
    """Async wrapper to check if user has a specific Django permission."""
    User = get_user_model()
    try:
        fresh_user = User.objects.get(pk=user.pk)
    except User.DoesNotExist:
        return False

    if not fresh_user.is_active:
        return False
    if fresh_user.is_superuser:
        return True
    return fresh_user.has_perm(perm)


@sync_to_async(thread_sensitive=True)
def _check_django_group(user: DjangoUser, group_name: str) -> bool:
    """Async wrapper to check if user belongs to a specific Django Group."""
    User = get_user_model()
    try:
        fresh_user = User.objects.get(pk=user.pk)
    except User.DoesNotExist:
        return False

    if not fresh_user.is_active:
        return False
    if fresh_user.is_superuser:
        return True
    return fresh_user.groups.filter(name=group_name).exists()


@sync_to_async(thread_sensitive=True)
def _get_user_metadata(user: DjangoUser) -> tuple[list[str], list[str]]:
    """Fetches user groups and all explicit permissions."""
    groups = list(user.groups.values_list("name", flat=True))
    permissions = list(user.get_all_permissions())
    return groups, permissions


async def get_current_django_user(
    request: Request,
    bearer: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    sessionid: str | None = Cookie(default=None),
) -> DjangoUserSchema:
    """FastAPI reusable dependency resolving user from Bearer JWT or Django Session Cookie."""
    auth_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user: DjangoUser | None = None

    # 1. Try Bearer JWT Authentication header
    if bearer and bearer.credentials:
        try:
            payload = jwt.decode(bearer.credentials, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: int | None = payload.get("user_id")
            if user_id is not None:
                user = await _get_django_user_by_id(user_id)
        except jwt.PyJWTError:
            raise auth_exception

    # 2. Try Django Session Cookie fallback
    if user is None and sessionid:
        user = await _get_django_user_from_session(sessionid)

    if user is None:
        raise auth_exception

    groups, permissions = await _get_user_metadata(user)

    return DjangoUserSchema(
        id=user.pk,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        is_staff=user.is_staff,
        is_superuser=user.is_superuser,
        groups=groups,
        permissions=permissions,
    )


class RequirePermission:
    """FastAPI dependency enforcing specific Django granular permissions (e.g. 'db.add_transcriptionjob')."""

    def __init__(self, permission: str) -> None:
        self.permission = permission

    async def __call__(
        self,
        user_schema: DjangoUserSchema = Depends(get_current_django_user),
    ) -> DjangoUserSchema:
        if user_schema.is_superuser:
            return user_schema

        user = await _get_django_user_by_id(user_schema.id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User account not found"
            )

        has_perm = await _check_django_permission(user, self.permission)
        if not has_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required permission: '{self.permission}'",
            )
        return user_schema


class RequireGroup:
    """FastAPI dependency enforcing Django Group membership."""

    def __init__(self, group_name: str) -> None:
        self.group_name = group_name

    async def __call__(
        self,
        user_schema: DjangoUserSchema = Depends(get_current_django_user),
    ) -> DjangoUserSchema:
        if user_schema.is_superuser:
            return user_schema

        user = await _get_django_user_by_id(user_schema.id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User account not found"
            )

        in_group = await _check_django_group(user, self.group_name)
        if not in_group:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden. User must belong to group '{self.group_name}'",
            )
        return user_schema
