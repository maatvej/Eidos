# Eidos — Enterprise AI Conversation Intelligence & Audio Transcription Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com)
[![Django 5.0](https://img.shields.io/badge/Django-5.0+-092e20.svg)](https://www.djangoproject.com)
[![React 19](https://img.shields.io/badge/React-19.1+-61dafb.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7+-3178c6.svg)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-6.1+-646cff.svg)](https://vitejs.dev/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4+-38bdf8.svg)](https://tailwindcss.com/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2.6+-e92063.svg)](https://docs.pydantic.dev)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checked: mypy](https://img.shields.io/badge/type%20checked-mypy%20strict-blue.svg)](https://mypy.readthedocs.io/)

**Eidos** is a production-grade enterprise platform designed to process multi-speaker conversations, executive briefings, and customer calls into aligned transcripts, executive summaries, key decisions, prioritized action items, and sentiment analytics.

---

## Quick Start (Zero-Dependency Local Dev with uv & npm)

Clone the repository and run the zero-touch rebuild script (cleans caches, resets database, syncs uv/npm, builds React frontend, and creates `admin`/`admin` superuser):

```bash
# 1. Clone the repository
git clone https://github.com/maatvej/Eidos.git
cd Eidos

# 2. Full clean rebuild (Zero-Touch)
# macOS / Linux:
./rebuild.sh
# Windows / Cross-platform:
uv run python rebuild.py

# 3. Launch unified server (Hot-reload enabled)
uv run python run_local.py
```

### Access URLs

| Interface           | URL                                                                            | Description                                                         |
|:--------------------|:-------------------------------------------------------------------------------|:--------------------------------------------------------------------|
| **Web UI (React SPA)** | [http://localhost:8000/](http://localhost:8000/)                             | Interactive audio player, live wave visualizer & intelligence cards |
| **Studio View**     | [http://localhost:8000/studio](http://localhost:8000/studio)                   | Audio transcription workspace and speaker editor                    |
| **Account Portal**  | [http://localhost:8000/account](http://localhost:8000/account)                 | Profile, security settings, and job history                         |
| **FastAPI Swagger** | [http://localhost:8000/docs](http://localhost:8000/docs)                       | Interactive REST API documentation & schema explorer                |
| **ReDoc**           | [http://localhost:8000/redoc](http://localhost:8000/redoc)                     | Alternative OpenAPI documentation                                   |
| **Django Admin**    | [http://localhost:8000/admin/](http://localhost:8000/admin/)                   | Administrative panel for database models                            |
| **Django Allauth**  | [http://localhost:8000/accounts/login/](http://localhost:8000/accounts/login/) | User authentication & account management                            |

---

## System Architecture

Eidos uses a **Hybrid ASGI Architecture** combining **FastAPI** for high-throughput asynchronous REST/WebSocket APIs and serving the compiled **React 19 SPA** with **Django** for battle-tested ORM, admin panel, and session management.

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
   │  - Static Asset Handler   │                   │  - React 19 SPA (dist/)   │
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
- **uv** package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh` or `irm https://astral.sh/uv/install.ps1 | iex`)
- **Node.js 18+ and npm** (Required for building and developing the React 19 + TypeScript SPA in [`frontend/`](frontend/package.json))
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

### 3. Development Workflows

#### Option A: Unified Production-Like Mode (Single Port)
Build the React SPA and serve everything via the FastAPI unified ASGI runner:

```bash
# Build React SPA
npm --prefix frontend run build

# Start Unified ASGI Server at http://localhost:8000
uv run python run_local.py
```

#### Option B: Frontend Hot Module Replacement (HMR) Development Mode
Run the backend and Vite development server in parallel across two terminals:

```bash
# Terminal 1: Backend ASGI Server (port 8000)
uv run python run_local.py

# Terminal 2: Vite Dev Server with HMR (port 5173)
npm --prefix frontend run dev
```
> Access the live-reloading UI at **[http://localhost:5173/](http://localhost:5173/)** (API, auth, admin, and static routes are automatically proxied to port `8000` via [`frontend/vite.config.ts`](frontend/vite.config.ts)).

### 4. Create Django Superuser
To access the Django Admin panel at `/admin/`:

```bash
uv run python manage.py createsuperuser
```

---

## Testing and Quality Assurance

The project enforces strict typing, code formatting, and automated test coverage across both backend and frontend.

```bash
# Run pytest with coverage reporting
uv run pytest

# Strict static type checking with MyPy
uv run mypy app

# Ruff code quality and format check
uv run ruff check app tests

# Frontend TypeScript type check and production build
npm --prefix frontend run build
```

---

## Docker Deployment

To build and run the production-grade multi-stage container with CUDA support and `uv` dependency caching:

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
├── django_static/            # Collected Django static assets (Admin panel)
├── frontend/                 # React 19 + TypeScript SPA (Vite + Tailwind CSS)
│   ├── src/
│   │   ├── components/       # UI components (Dropzone, Player, IntelligenceCard, Account, etc.)
│   │   ├── services/         # API client and backend communication
│   │   ├── store/            # Zustand global state stores (useAppStore, toastStore)
│   │   ├── types/            # TypeScript domain interfaces and schemas
│   │   ├── App.tsx           # Main application view coordinator
│   │   ├── index.css         # Tailwind directives and design system tokens
│   │   └── main.tsx          # React application entry point
│   ├── dist/                 # Compiled SPA distribution bundle (assets & index.html)
│   ├── package.json          # Node.js dependencies and build scripts
│   ├── tailwind.config.js    # Tailwind theme extension & color definitions
│   └── vite.config.ts        # Vite configuration & development proxy rules
├── local_storage/            # Local media file store (audio uploads and exports)
├── static/                   # Static assets for Django Allauth SSR styling (CSS)
│   └── css/
│       └── app.css           # Auth pages visual styling aligned with React theme
├── templates/                # Django Allauth HTML templates (login, signup, etc.)
├── tests/                    # Pytest test suite (API, ML, Repository, Security)
├── manage.py                 # Django CLI management entrypoint
├── pyproject.toml            # Project dependencies and tool configurations
├── uv.lock                   # Deterministic dependency lockfile generated by uv
├── run_local.py              # Zero-dependency local development launcher
├── quick-setup.md            # Russian quick-start and deployment guide
├── README.md                 # English platform documentation and architecture overview
└── Dockerfile                # Multi-stage CUDA 12.1 + uv production Dockerfile
```

---

## License

Internal Enterprise Proprietary & Confidential.
