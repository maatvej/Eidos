# filename: tests/test_middleware.py
"""Unit and integration tests for Security and Rate Limiting Middleware (app/api/middleware.py)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from httpx import ASGITransport, AsyncClient

from app.api.middleware import SecurityAndRateLimitMiddleware
from app.core.config import settings


@pytest.mark.asyncio
async def test_middleware_without_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validates middleware execution when Redis is disabled (USE_REDIS=False)."""
    monkeypatch.setattr(settings, "USE_REDIS", False)

    test_app = FastAPI()
    test_app.add_middleware(SecurityAndRateLimitMiddleware, requests_per_minute=10)

    @test_app.get("/ping")
    async def ping():
        return PlainTextResponse("pong")

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        response = await ac.get("/ping")
        assert response.status_code == 200
        assert response.text == "pong"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "Strict-Transport-Security" in response.headers


@pytest.mark.asyncio
async def test_middleware_with_redis_rate_limiting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validates rate limiting enforcement and 429 status code with Redis active."""
    monkeypatch.setattr(settings, "USE_REDIS", True)

    mock_redis = MagicMock()
    # 1st request -> 1 (sets expire), 2nd -> 2, 3rd -> 3 (exceeds limit 2)
    mock_redis.incr = AsyncMock(side_effect=[1, 2, 3])
    mock_redis.expire = AsyncMock(return_value=True)

    with patch("redis.asyncio.Redis", return_value=mock_redis):
        test_app = FastAPI()
        test_app.add_middleware(SecurityAndRateLimitMiddleware, requests_per_minute=2)

        @test_app.get("/limited")
        async def limited():
            return PlainTextResponse("ok")

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            # Request 1: Allowed (incr=1, expire called)
            r1 = await ac.get("/limited")
            assert r1.status_code == 200
            mock_redis.expire.assert_called_once()

            # Request 2: Allowed (incr=2)
            r2 = await ac.get("/limited")
            assert r2.status_code == 200

            # Request 3: Blocked (incr=3 > limit=2) -> 429
            r3 = await ac.get("/limited")
            assert r3.status_code == 429
            assert "Rate limit exceeded" in r3.json()["detail"]


@pytest.mark.asyncio
async def test_middleware_redis_connection_and_runtime_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validates graceful degradation when Redis connection fails or throws runtime exceptions."""
    monkeypatch.setattr(settings, "USE_REDIS", True)

    # 1. Init connection error
    with patch("redis.asyncio.Redis", side_effect=Exception("Redis connection refused")):
        middleware = SecurityAndRateLimitMiddleware(app=FastAPI())
        assert middleware.redis_client is None

    # 2. Runtime error during check
    mock_redis = MagicMock()
    mock_redis.incr = AsyncMock(side_effect=RuntimeError("Redis timeout"))

    with patch("redis.asyncio.Redis", return_value=mock_redis):
        test_app = FastAPI()
        test_app.add_middleware(SecurityAndRateLimitMiddleware, requests_per_minute=5)

        @test_app.get("/error-test")
        async def error_test():
            return PlainTextResponse("ok")

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            resp = await ac.get("/error-test")
            assert resp.status_code == 200
            assert resp.text == "ok"
