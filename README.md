# Eidos — Enterprise AI Conversation Intelligence & Audio Transcription Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com)
[![Django 5.0](https://img.shields.io/badge/Django-5.0+-092e20.svg)](https://www.djangoproject.com)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2.6+-e92063.svg)](https://docs.pydantic.dev)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checked: mypy](https://img.shields.io/badge/type%20checked-mypy%20strict-blue.svg)](https://mypy.readthedocs.io/)

**Eidos** is a production-grade enterprise platform designed to process multi-speaker conversations, executive briefings, and customer calls into aligned transcripts, executive summaries, key decisions, prioritized action items, and sentiment analytics.

---

## Quick Start (Zero-Dependency Local Dev)

Clone the repository and start the entire unified platform with SQLite and FastAPI background execution in a single command:

```bash
# 1. Clone the repository
git clone https://github.com/maatvej/Eidos.git
cd Eidos

# 2. Create & activate Python 3.11 virtual environment
# Linux / macOS:
python3.11 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell):
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies in editable mode
pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"

# 4. Launch unified server (Hot-reload enabled)
python run_local.py
```

### Access URLs

| Interface           | URL                                                                            | Description                                                         |
|:--------------------|:-------------------------------------------------------------------------------|:--------------------------------------------------------------------|
| **Web UI**          | [http://localhost:8000/](http://localhost:8000/)                               | Interactive audio player, live wave visualizer & intelligence cards |
| **FastAPI Swagger** | [http://localhost:8000/docs](http://localhost:8000/docs)                       | Interactive REST API documentation & schema explorer                |
| **ReDoc**           | [http://localhost:8000/redoc](http://localhost:8000/redoc)                     | Alternative OpenAPI documentation                                   |
| **Django Admin**    | [http://localhost:8000/admin/](http://localhost:8000/admin/)                   | Administrative panel for database models                            |
| **Django Allauth**  | [http://localhost:8000/accounts/login/](http://localhost:8000/accounts/login/) | User authentication & account management                            |

---

## System Architecture

Eidos uses a **Hybrid ASGI Architecture** combining **FastAPI** for high-throughput asynchronous REST/WebSocket APIs with **Django** for battle-tested ORM, admin panel, and session management.

```
                  ┌──────────────────────────────────────────────┐
                  │           Unified ASGI Dispatcher            │
                  │              (app/asgi.py)                   │
                  └──────────────────────┬───────────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 │                                               │
                 ▼ (paths: /admin, /accounts, /django-static)    ▼ (all other paths)
   ┌───────────────────────────┐                   ┌───────────────────────────┐
   │        Django ASGI        │                   │      FastAPI Gateway      │
   │  - Django Admin Panel     │                   │  - Async REST API (/api)  │
   │  - Django Allauth Auth    │                   │  - Realtime SSE & WS      │
   │  - Static Asset Handler   │                   │  - Vanilla UI Frontend    │
   └─────────────┬─────────────┘                   └─────────────┬─────────────┘
                 │                                               │
                 └───────────────────────┬───────────────────────┘
                                         │
                                         ▼
                 ┌───────────────────────────────────────────────┐
                 │           Shared Persistence Layer            │
                 │  - SQLite (Local Dev) / PostgreSQL (Prod)     │
                 │  - SQLAlchemy 2.0 Async + Django ORM models   │
                 └───────────────────────────────────────────────┘
```

---

## Prerequisites & Detailed Setup Guide

### 1. System Requirements
- **Python 3.11+**
- **FFmpeg 5.0+** (Required for audio probing, channel downmixing to 16kHz mono PCM, and VAD):
  - **Windows**: `winget install Gyan.FFmpeg` or `choco install ffmpeg`
  - **Ubuntu / Debian**: `sudo apt-get update && sudo apt-get install -y ffmpeg libsndfile1`
  - **macOS**: `brew install ffmpeg`

### 2. Environment Configuration (`.env`)
Create a `.env` file in the root directory if you want to override default configurations:

```ini
# Operational Flags
DEV_MODE=True
USE_REDIS=False

# Database URL (SQLAlchemy 2.0 Async format)
DATABASE_URL=sqlite+aiosqlite:///./dev_app.db

# Django Security
DJANGO_SECRET_KEY=your-custom-secure-key-for-local-dev
DJANGO_DEBUG=True

# Speech Recognition & Diarization
WHISPER_MODEL_SIZE=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
PYANNOTE_AUTH_TOKEN=hf_your_huggingface_token

# LLM Intelligence Engine
LLM_API_KEY=your-openai-or-custom-llm-api-key
LLM_MODEL_NAME=gpt-4o
```

### 3. Create Django Superuser
To access the Django Admin panel at `/admin/`:

```bash
python manage.py createsuperuser
```

---

## Testing and Quality Assurance

The project enforces strict typing, code formatting, and automated test coverage.

```bash
# Run pytest with coverage reporting
pytest

# Strict static type checking with MyPy
mypy app

# Ruff code quality and format check
ruff check app tests
```

---

## Docker Deployment

To build and run the production-grade multi-stage container with CUDA support:

```bash
# Build Docker image
docker build -t eidos-platform .

# Run container
docker run -p 8000:8000 --env-file .env eidos-platform
```

---

## Project Structure

```
Eidos/
├── alembic/                  # Alembic DB migration environment
├── app/
│   ├── api/                  # FastAPI routers, middlewares, and API v1 endpoints
│   ├── core/                 # Config, Django settings, logging, security, metrics
│   ├── db/                   # Django & SQLAlchemy models, migrations, DB session
│   ├── domain/               # Pure domain entities, business exceptions, protocols
│   ├── ml/                   # Audio processor, Faster-Whisper, PyAnnote, LLM engine
│   ├── repository/           # Job repository with optimistic concurrency locking
│   ├── schemas/              # Pydantic v2 schemas and DTOs
│   ├── services/             # Export service (PDF, DOCX, SRT, VTT), event bus
│   ├── workers/              # Asynchronous worker tasks (Arq / BackgroundTasks)
│   ├── asgi.py               # Unified ASGI dispatcher routing Django & FastAPI
│   └── main.py               # FastAPI application lifecycle & configuration
├── django_static/            # Collected Django static assets
├── local_storage/            # Local media file store (audio uploads and exports)
├── static/                   # Frontend SPA (Vanilla JS, CSS components, Audio visualizer)
├── templates/                # Django Allauth HTML templates
├── tests/                    # Pytest test suite (API, ML, Repository, Security)
├── manage.py                 # Django CLI management entrypoint
├── pyproject.toml            # Project dependencies and tool configurations
├── run_local.py              # Zero-dependency local development launcher
└── Dockerfile                # Production multi-stage Dockerfile with CUDA support
```

---

## License

Internal Enterprise Proprietary & Confidential.
