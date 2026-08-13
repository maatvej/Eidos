# filename: app/api/middleware.py
"""Rate limiter middleware supporting zero-redis local fallback."""

import time
from typing import Any

import redis.asyncio as aioredis
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import settings
from app.core.logging import logger


class SecurityAndRateLimitMiddleware(BaseHTTPMiddleware):
    """Enforces API rate limiting with graceful local bypass when Redis is disabled."""

    def __init__(self, app: Any, requests_per_minute: int = 100) -> None:
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.redis_client: aioredis.Redis | None = None

        if settings.USE_REDIS:
            try:
                self.redis_client = aioredis.Redis(
                    host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True
                )
            except Exception as err:
                logger.warning(f"Redis rate limiter disabled: {err}")
                self.redis_client = None

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Bypass Redis rate checks completely when running locally without Redis
        if settings.USE_REDIS and self.redis_client:
            client_ip = request.client.host if request.client else "127.0.0.1"
            current_minute = int(time.time() // 60)
            key = f"rate_limit:{client_ip}:{current_minute}"

            try:
                current_requests = await self.redis_client.incr(key)
                if current_requests == 1:
                    await self.redis_client.expire(key, 60)

                if current_requests > self.requests_per_minute:
                    logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={"detail": "Rate limit exceeded. Please try again later."},
                    )
            except Exception as e:
                logger.error(f"Redis rate limiter check failed: {str(e)}")

        response = await call_next(request)

        # Inject OWASP Security Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
