# filename: tests/test_auth_endpoints.py
"""Integration tests for Authentication endpoints (app/api/v1/endpoints/auth.py)."""

import pytest
from asgiref.sync import sync_to_async
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_get_token_info(client: AsyncClient) -> None:
    """Validates GET request on token endpoint returning guidance."""
    response = await client.get("/api/v1/auth/token")
    assert response.status_code == 200
    data = response.json()
    assert "POST" in data["method_required"]
    assert "message" in data


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_login_for_access_token_success(client: AsyncClient, test_user) -> None:
    """Validates issuing JWT token with correct Django credentials."""
    await sync_to_async(test_user.set_password)("secure_pass_123")
    await sync_to_async(test_user.save)()

    form_data = {
        "username": test_user.username,
        "password": "secure_pass_123",
    }
    response = await client.post("/api/v1/auth/token", data=form_data)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == test_user.username


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_login_for_access_token_invalid_credentials(client: AsyncClient, test_user) -> None:
    """Validates HTTP 401 response on invalid login credentials."""
    form_data = {
        "username": test_user.username,
        "password": "wrong_password_xyz",
    }
    response = await client.post("/api/v1/auth/token", data=form_data)
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"
