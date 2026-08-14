# filename: tests/conftest.py
"""Global Pytest async test fixtures and Django DB setup for test execution."""

import os
from collections.abc import AsyncGenerator

import django
import pytest
from httpx import ASGITransport, AsyncClient


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.core.django_settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

from app.core.security import (  # noqa: E402
    DjangoUserSchema,
    create_jwt_for_django_user,
    get_current_django_user,
)
from app.main import app  # noqa: E402


@pytest.fixture
def test_user():
    """Creates a mock Django test user."""
    User = get_user_model()
    user, _ = User.objects.get_or_create(
        username="test_admin",
        defaults={
            "email": "test@eidos.ai",
            "is_active": True,
            "is_staff": True,
            "is_superuser": True,
        },
    )
    return user


@pytest.fixture
def auth_headers(test_user) -> dict[str, str]:
    """Generates valid JWT Bearer headers for testing."""
    token = create_jwt_for_django_user(test_user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client(test_user) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client with pre-authenticated user dependency override."""
    mock_user_schema = DjangoUserSchema(
        id=test_user.pk,
        username=test_user.username,
        email=test_user.email,
        is_active=True,
        is_staff=True,
        is_superuser=True,
        groups=["Admin"],
        permissions=["db.add_transcriptionjob", "db.change_transcriptionjob"],
    )

    app.dependency_overrides[get_current_django_user] = lambda: mock_user_schema

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
