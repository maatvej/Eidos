# filename: app/api/v1/endpoints/auth.py
"""FastAPI Authentication Endpoints connected to Django User & Permissions subsystem."""

from asgiref.sync import sync_to_async
from django.contrib.auth import authenticate
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.core.security import (
    DjangoUserSchema,
    _get_user_metadata,
    create_jwt_for_django_user,
    get_current_django_user,
)


router = APIRouter(prefix="/auth", tags=["Authentication & User Management"])


class TokenResponse(BaseModel):
    """Token response schema containing Bearer access token."""

    access_token: str
    token_type: str = "bearer"
    user: DjangoUserSchema


@sync_to_async(thread_sensitive=True)
def _authenticate_django_user(username: str, password: str):
    """Async wrapper around Django's native authenticate function."""
    return authenticate(username=username, password=password)


@router.get("/token")
async def get_token_info() -> dict[str, str]:
    """Provides user guidance for issuing access tokens via POST requests or Swagger UI."""
    return {
        "message": "To obtain a signed JWT token, send a POST request with form-data ('username' and 'password'), or authenticate directly in Swagger UI at /docs.",
        "docs_url": "http://localhost:8000/docs",
        "method_required": "POST",
    }


@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> TokenResponse:
    """Authenticates Django credentials and issues a signed JWT token."""
    user = await _authenticate_django_user(form_data.username, form_data.password)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_jwt_for_django_user(user)

    groups, permissions = await _get_user_metadata(user)

    user_schema = DjangoUserSchema(
        id=user.pk,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        is_staff=user.is_staff,
        is_superuser=user.is_superuser,
        groups=groups,
        permissions=permissions,
    )

    return TokenResponse(access_token=access_token, token_type="bearer", user=user_schema)


@router.get("/me", response_model=DjangoUserSchema)
async def get_my_profile(
    current_user: DjangoUserSchema = Depends(get_current_django_user),
) -> DjangoUserSchema:
    """Returns profile and permission details for the currently authenticated user."""
    return current_user
