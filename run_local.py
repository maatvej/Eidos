# filename: run_local.py
"""Single-command local development launcher script for Hybrid Django + FastAPI app.

Runs the Eidos AI platform locally without needing Docker or Redis.
"""

import os
import shutil

# Set Django Settings Module for local run
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.core.django_settings")

import django
from django.core.management import call_command

from app.core.config import settings
from app.core.logging import logger


def check_ffmpeg() -> bool:
    """Checks if FFmpeg binary is installed on system path."""
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        logger.warning(
            "FFmpeg binary was not found on system PATH. "
            "Audio normalization will fall back to raw stream reads."
        )
        return False
    logger.info(f"FFmpeg detected at: {ffmpeg_path}")
    return True


def main() -> None:
    """Bootstraps directories, runs Django database migrations & static collection, and starts Uvicorn ASGI server."""
    print("=" * 75)
    print("  EIDOS HYBRID PLATFORM (DJANGO + FASTAPI) — LOCAL DEVELOPMENT MODE  ")
    print("=" * 75)

    # Ensure local storage directory exists
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    # Check FFmpeg dependency
    check_ffmpeg()

    # Initialize Django ORM, collect static assets, and run database migrations
    print(
        "\n[1/2] Initializing Django ORM, collecting static files, and applying SQLite migrations..."
    )
    django.setup()
    call_command("collectstatic", "--noinput", verbosity=0)
    call_command("makemigrations", "db")
    call_command("migrate")
    print("-> Django static collection & migrations applied successfully.")

    print("\n[2/2] Starting Unified ASGI Server at http://localhost:8000")
    print(" -> FastAPI API Docs:   http://localhost:8000/docs")
    print(" -> Django Admin Panel: http://localhost:8000/admin/")
    print(" -> Auth Token Endpoint: http://localhost:8000/api/v1/auth/token")
    print("Press CTRL+C to stop the application.\n")

    try:
        import uvicorn

        uvicorn.run(
            "app.asgi:application", host="127.0.0.1", port=8000, reload=True, log_level="info"
        )
    except KeyboardInterrupt:
        print("\nShutdown signal received. Exiting...")


if __name__ == "__main__":
    main()
