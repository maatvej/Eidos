# filename: app/main.py
"""FastAPI Application bootstrap with Lifespan management for Hybrid Django + FastAPI Platform."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import django


# Ensure Django settings are configured whenever FastAPI is initialized
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.core.django_settings")
django.setup()

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from app.api.v1.endpoints.account import router as account_router  # noqa: E402
from app.api.v1.endpoints.auth import router as auth_router  # noqa: E402
from app.api.v1.endpoints.events import router as events_router  # noqa: E402
from app.api.v1.endpoints.transcription import router as transcription_router  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.security import DjangoUserSchema, get_current_django_user  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager initializing required application storage."""
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    """Redirects unauthenticated UI requests to Django Allauth login page while preserving API JSON errors."""
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        # Avoid redirecting REST API calls or static resource requests
        path = request.url.path
        is_api = path.startswith((settings.API_V1_STR, "/api/"))
        is_static = path.startswith(("/static", "/django-static"))
        if not is_api and not is_static:
            next_url = path
            if request.url.query:
                next_url += f"?{request.url.query}"
            redirect_url = "/accounts/login/"
            if next_url and next_url != "/":
                redirect_url = f"/accounts/login/?next={next_url}"
            return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


# Mount API Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(account_router, prefix=settings.API_V1_STR)
app.include_router(transcription_router, prefix=settings.API_V1_STR)
app.include_router(events_router, prefix=settings.API_V1_STR)

# Mount Static Files for Web UI
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "architecture": "django-fastapi-hybrid"}


# Explicit SPA Routes for Direct Deep-Link Navigation and Browser Refresh
@app.get("/")
@app.get("/dashboard")
@app.get("/studio")
@app.get("/jobs/{job_id}")
@app.get("/transcriptions/{job_id}")
@app.get("/account")
@app.get("/account/history")
@app.get("/account/profile")
@app.get("/account/security")
@app.get("/account/{subpath:path}")
async def serve_spa_app(
    request: Request,
    user: DjangoUserSchema = Depends(get_current_django_user),
) -> FileResponse:
    """Renders web SPA interface for all primary frontend views for authenticated users."""
    return FileResponse("static/index.html")


# SPA Catch-all Route for client-side deep routing
@app.get("/{full_path:path}")
async def spa_catch_all(
    request: Request,
    full_path: str,
    user: DjangoUserSchema = Depends(get_current_django_user),
) -> FileResponse:
    """Catch-all fallback route serving index.html for client-side routing while protecting APIs."""
    if (
        full_path.startswith(("api/", "static/", "django-static/", "admin/", "accounts/"))
        or full_path == "health"
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    return FileResponse("static/index.html")
