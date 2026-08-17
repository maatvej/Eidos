# filename: rebuild.py
"""Automated zero-touch project rebuild script for FastAPI + Django + React SPA.

Performs a full clean rebuild of the Eidos application:
1. Purges all Python, Vite, test, and build caches.
2. Resets the local SQLite database and media storage.
3. Synchronizes Python dependencies via uv.
4. Installs and compiles the React 19 + TypeScript frontend bundle.
5. Applies Django database migrations and collects static files.
6. Automatically creates/resets the default admin superuser (admin/admin).
"""

import contextlib
import os
import shutil
import subprocess
import sys
from pathlib import Path


# Root directory of the repository
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

# Configure Django settings module environment variable
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.core.django_settings")


def print_banner(text: str, color_code: str = "\033[1;36m") -> None:
    """Prints a styled banner with border lines.

    Args:
        text: Header message to display in the banner.
        color_code: ANSI escape color code for terminal output.

    Example:
        >>> print_banner("EIDOS FULL REBUILD")
    """
    reset = "\033[0m"
    width = 75
    print(f"\n{color_code}{'=' * width}")
    print(f"  {text.center(width - 4)}")
    print(f"{'=' * width}{reset}\n")


def print_step(step_idx: int, total_steps: int, title: str) -> None:
    """Prints a step header with step numbering.

    Args:
        step_idx: 1-based index of the current step.
        total_steps: Total number of execution steps.
        title: Descriptive title of the step.

    Example:
        >>> print_step(1, 6, "Cleaning Caches and Resetting Database")
    """
    cyan = "\033[1;34m"
    bold = "\033[1m"
    reset = "\033[0m"
    print(f"{cyan}[{step_idx}/{total_steps}]{reset} {bold}{title}...{reset}")


def _clean_sqlite_databases(base_dir: Path) -> None:
    """Removes SQLite database files matching development patterns.

    Args:
        base_dir: Root directory path of the workspace repository.
    """
    db_patterns = ["dev_app.db", "dev_app.db-shm", "dev_app.db-wal", "test_*.db", "*.sqlite3"]
    for pattern in db_patterns:
        for db_file in base_dir.glob(pattern):
            if db_file.is_file():
                with contextlib.suppress(OSError):
                    db_file.unlink(missing_ok=True)
                    print(f"  - Deleted database file: {db_file.name}")


def _clean_storage_and_profiles(base_dir: Path) -> None:
    """Resets media storage and profiling output directories.

    Args:
        base_dir: Root directory path of the workspace repository.
    """
    storage_dir = base_dir / "local_storage"
    if storage_dir.exists():
        for item in storage_dir.iterdir():
            if item.name == ".gitkeep":
                continue
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)
        print("  - Cleaned local media storage (local_storage/)")
    else:
        storage_dir.mkdir(parents=True, exist_ok=True)
        (storage_dir / ".gitkeep").touch()

    profiles_dir = base_dir / "profiles"
    if profiles_dir.exists():
        shutil.rmtree(profiles_dir, ignore_errors=True)
        print("  - Removed profiling output directory (profiles/)")

    django_static_dir = base_dir / "django_static"
    if django_static_dir.exists():
        shutil.rmtree(django_static_dir, ignore_errors=True)
        print("  - Cleaned Django collected static directory (django_static/)")


def _clean_python_caches(base_dir: Path) -> None:
    """Removes Python bytecode, build artifacts, and test runner caches.

    Args:
        base_dir: Root directory path of the workspace repository.
    """
    cache_dir_names = {
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".coverage",
        "htmlcov",
        ".hypothesis",
        "build",
        "dist",
    }
    for item in base_dir.rglob("*"):
        if "node_modules" in item.parts or ".venv" in item.parts:
            continue
        if item.is_dir() and item.name in cache_dir_names:
            shutil.rmtree(item, ignore_errors=True)
        elif item.is_file() and item.suffix in (".pyc", ".pyo", ".pyd"):
            item.unlink(missing_ok=True)

    print("  - Cleared Python bytecode and testing caches")


def _clean_frontend_artifacts(base_dir: Path) -> None:
    """Purges frontend distribution bundle and Vite cache directories.

    Args:
        base_dir: Root directory path of the workspace repository.
    """
    dist_dir = base_dir / "frontend" / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir, ignore_errors=True)
        print("  - Removed frontend distribution build (frontend/dist/)")

    vite_cache_dir = base_dir / "frontend" / ".vite"
    if vite_cache_dir.exists():
        shutil.rmtree(vite_cache_dir, ignore_errors=True)
        print("  - Removed Vite cache (frontend/.vite/)")


def clean_caches_and_database(base_dir: Path) -> None:
    """Coordinates the removal of temporary files, database files, and caches.

    Args:
        base_dir: Root directory path of the workspace repository.

    Example:
        >>> clean_caches_and_database(Path("."))
    """
    _clean_sqlite_databases(base_dir)
    _clean_storage_and_profiles(base_dir)
    _clean_python_caches(base_dir)
    _clean_frontend_artifacts(base_dir)


def sync_python_dependencies() -> None:
    """Syncs Python virtual environment and dependencies using uv.

    Raises:
        RuntimeError: If uv command is missing or dependency sync fails.

    Example:
        >>> sync_python_dependencies()
    """
    uv_bin = shutil.which("uv")
    if not uv_bin:
        raise RuntimeError(
            "The 'uv' package manager was not found on system PATH.\n"
            "Install uv via: curl -LsSf https://astral.sh/uv/install.sh | sh (macOS/Linux) "
            "or pip install uv."
        )

    print(f"  - Using uv at: {uv_bin}")
    cmd = [uv_bin, "sync", "--all-extras"]
    result = subprocess.run(cmd, cwd=BASE_DIR, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to sync Python dependencies via uv (exit code {result.returncode})")
    print("  -> Python virtualenv & dependencies synced successfully.")


def rebuild_frontend(frontend_dir: Path) -> None:
    """Installs Node dependencies and compiles the React 19 + TypeScript SPA bundle.

    Args:
        frontend_dir: Path to the frontend directory containing package.json.

    Raises:
        RuntimeError: If node/npm are missing or frontend compilation fails.

    Example:
        >>> rebuild_frontend(Path("frontend"))
    """
    npm_bin = shutil.which("npm")
    if not npm_bin:
        raise RuntimeError(
            "Node.js package manager 'npm' was not found on system PATH.\n"
            "Please install Node.js (v18+) from https://nodejs.org or via 'brew install node'."
        )

    print(f"  - Using npm at: {npm_bin}")
    print("  - Installing frontend dependencies...")
    install_cmd = [npm_bin, "install"]
    install_res = subprocess.run(install_cmd, cwd=frontend_dir, check=False)
    if install_res.returncode != 0:
        raise RuntimeError(f"npm install failed with exit code {install_res.returncode}")

    print("  - Building React SPA production bundle (tsc && vite build)...")
    build_cmd = [npm_bin, "run", "build"]
    build_res = subprocess.run(build_cmd, cwd=frontend_dir, check=False)
    if build_res.returncode != 0:
        raise RuntimeError(f"npm run build failed with exit code {build_res.returncode}")

    print("  -> Frontend React SPA bundle compiled successfully into frontend/dist/")


def run_database_migrations_and_static() -> None:
    """Initializes Django ORM, applies database migrations, and collects static files.

    Raises:
        RuntimeError: If Django setup, migration, or static collection fails.

    Example:
        >>> run_database_migrations_and_static()
    """
    try:
        import django
        from django.core.management import call_command

        django.setup()
        print("  - Applying Django database migrations...")
        call_command("makemigrations", "db", verbosity=0)
        call_command("migrate", interactive=False, verbosity=1)
        print("  - Collecting Django static assets...")
        call_command("collectstatic", interactive=False, verbosity=0)
        print("  -> Database migrations & static assets collected successfully.")
    except Exception as exc:
        raise RuntimeError(f"Django setup or migration failed: {exc}") from exc


def create_or_reset_superuser(
    username: str = "admin",
    password: str = "admin",
    email: str = "admin@example.com",
) -> None:
    """Creates or updates the default Django superuser with admin privileges.

    Args:
        username: Administrator username (default: 'admin').
        password: Administrator password (default: 'admin').
        email: Administrator email address (default: 'admin@example.com').

    Raises:
        RuntimeError: If user model creation or update fails.

    Example:
        >>> create_or_reset_superuser("admin", "admin", "admin@example.com")
    """
    try:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_superuser": True,
                "is_staff": True,
                "is_active": True,
            },
        )
        user.set_password(password)
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.email = email
        user.save()

        # Synchronize Django Allauth EmailAddress table if allauth is installed
        with contextlib.suppress(Exception):
            from allauth.account.models import EmailAddress

            EmailAddress.objects.update_or_create(
                user=user,
                email=email,
                defaults={"verified": True, "primary": True},
            )

        action = "Created new" if created else "Updated existing"
        print(f"  -> {action} superuser '{username}' with password '{password}' (Email: {email})")
    except Exception as exc:
        raise RuntimeError(f"Failed to create/reset superuser: {exc}") from exc


def main() -> None:
    """Main orchestration entry point for zero-touch project rebuilding."""
    print_banner("EIDOS AI PLATFORM — ZERO-TOUCH CLEAN REBUILD", "\033[1;36m")

    total_steps = 5

    try:
        # Step 1: Cache and DB cleanup
        print_step(1, total_steps, "Purging Caches, Artifacts, and SQLite Database")
        clean_caches_and_database(BASE_DIR)
        print("  -> Cleanup complete.\n")

        # Step 2: Python virtualenv & dependencies via uv
        print_step(2, total_steps, "Syncing Python Dependencies via uv")
        sync_python_dependencies()
        print("")

        # Step 3: Frontend compilation
        print_step(3, total_steps, "Installing & Compiling React 19 SPA Frontend")
        rebuild_frontend(FRONTEND_DIR)
        print("")

        # Step 4: Django migrations & static collection
        print_step(4, total_steps, "Applying Database Migrations & Collecting Static Files")
        run_database_migrations_and_static()
        print("")

        # Step 5: Create superuser
        print_step(5, total_steps, "Creating Default Admin Superuser (admin / admin)")
        create_or_reset_superuser("admin", "admin", "admin@example.com")
        print("")

        # Completion summary
        green = "\033[1;32m"
        bold = "\033[1m"
        reset = "\033[0m"
        print_banner("PROJECT REBUILD COMPLETED SUCCESSFULLY!", green)
        print(f"{bold}Ready to start the platform locally:{reset}")
        print(f"  {green}uv run python run_local.py{reset}\n")
        print(f"{bold}Default Credentials:{reset}")
        print("  Username: \033[1;33madmin\033[0m")
        print("  Password: \033[1;33madmin\033[0m\n")
        print(f"{bold}Access Points:{reset}")
        print("  - Web Application:       http://localhost:8000/")
        print("  - Django Admin Panel:    http://localhost:8000/admin/")
        print("  - FastAPI Swagger Docs:  http://localhost:8000/docs\n")

    except Exception as exc:
        red = "\033[1;31m"
        reset = "\033[0m"
        print(f"\n{red}[ERROR] Rebuild failed:{reset} {exc}\n", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
