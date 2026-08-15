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
from app.core.profiler import FastAPIProfilingMiddleware  # noqa: E402
from app.core.security import DjangoUserSchema, get_current_django_user  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager initializing required application storage."""
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    settings.PROFILING_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Register profiling middleware for ASGI request profiling
app.add_middleware(FastAPIProfilingMiddleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    """Redirects unauthenticated UI requests to Django Allauth login page while preserving API JSON errors."""
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        # Avoid redirecting REST API calls or static resource requests
        path = request.url.path
        is_api = path.startswith((settings.API_V1_STR, "/api/"))
        is_static = path.startswith(("/static", "/django-static", "/assets"))
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

# Mount Built React Assets if available
if settings.FRONTEND_DIST_DIR.exists() and (settings.FRONTEND_DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(settings.FRONTEND_DIST_DIR / "assets")), name="assets")


def get_spa_index_path() -> str:
    """Resolves SPA index.html path favoring compiled React frontend with fallback to static.

    Returns:
        str: Relative filesystem path to the SPA HTML entry point.

    Example:
        >>> path = get_spa_index_path()
        >>> isinstance(path, str)
        True
    """
    react_index = settings.FRONTEND_DIST_DIR / "index.html"
    if react_index.exists():
        return str(react_index)
    return "static/index.html"


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint.

    Returns:
        dict[str, str]: Health and architecture status metadata payload.

    Example:
        >>> import asyncio
        >>> res = asyncio.run(health_check())
        >>> res["status"]
        'healthy'
    """
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
    """Renders web SPA interface for all primary frontend views for authenticated users.

    Args:
        request: Incoming FastAPI HTTP request instance.
        user: Authenticated Django user schema extracted from session or bearer token.

    Returns:
        FileResponse: Static or compiled React SPA index.html.

    Example:
        >>> # Invoked automatically by FastAPI routing handlers
    """
    return FileResponse(get_spa_index_path())


# SPA Catch-all Route for client-side deep routing
@app.get("/{full_path:path}")
async def spa_catch_all(
    request: Request,
    full_path: str,
    user: DjangoUserSchema = Depends(get_current_django_user),
) -> FileResponse:
    """Catch-all fallback route serving index.html for client-side routing while protecting APIs.

    Args:
        request: Incoming FastAPI HTTP request instance.
        full_path: Unmatched subpath string.
        user: Authenticated Django user schema extracted from session or bearer token.

    Returns:
        FileResponse: Static or compiled React SPA index.html.

    Raises:
        HTTPException: 404 Not Found if path matches protected API, admin, or static prefixes.

    Example:
        >>> # Invoked automatically by FastAPI routing handlers
    """
    if (
        full_path.startswith(("api/", "static/", "django-static/", "admin/", "accounts/", "assets/"))
        or full_path == "health"
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    return FileResponse(get_spa_index_path())
