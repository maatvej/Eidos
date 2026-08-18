# Architecture Rules & System Engineering Guidelines

This document serves as the single source of truth for the architectural standards, design patterns, invariants, and implementation rules of the **Eidos** platform. Every AI agent, engineer, and automated system modifying this repository MUST strictly follow these rules.

---

## 1. Executive Tech Stack & Version Manifest

- **Backend Runtime:** Python `3.11+` strictly managed via local virtual environment [`.venv/`](.venv/)
- **Web & ASGI Frameworks:**
  - **FastAPI:** `0.115.0+` with Starlette ASGI runtime for high-performance async REST API, SSE streaming, and SPA routing.
  - **Django:** `5.0.0+` for authentication, session management, user management, and Django Admin panel (`django-allauth >= 0.61.0`).
- **Data Persistence & ORM:**
  - **Django ORM:** Primary entity definition, schema migrations, and admin integration in [`app/db/models.py`](app/db/models.py).
  - **SQLAlchemy Async 2.0:** Async database engine ([`app/db/session.py`](app/db/session.py)) and hardened repository with optimistic concurrency control ([`app/repository/hardened_repository.py`](app/repository/hardened_repository.py)).
  - **Alembic:** Async migration engine in [`alembic/`](alembic/).
  - **Database Engine:** SQLite 3 with Write-Ahead Logging (WAL mode), `busy_timeout=30000ms`, `synchronous=NORMAL`.
- **Machine Learning & Audio Pipeline (Offline-First / Air-Gapped):**
  - **ASR Engine:** `faster-whisper >= 1.0.0` (CTranslate2 backend, INT8/FP16 quantization).
  - **Speaker Diarization:** `pyannote.audio >= 3.1.0` with offline acoustic timbre spectral clustering fallback.
  - **Audio DSP:** `ffmpeg` filter graphs (loudnorm, afftdn, highpass, silenceremove) via [`app/ml/audio_processor.py`](app/ml/audio_processor.py).
  - **Intelligence & Summarization:** Local graph-based LexRank/TextRank centrality summarizer ([`app/ml/llm_processor.py:LocalDynamicSummarizer`](app/ml/llm_processor.py:179)) and offline OpenAI-compatible local LLM endpoints (e.g., Ollama).
- **Frontend & Client Architecture:**
  - **Framework & UI:** React `19.0.0`, TypeScript `5.7.3`, Vite `6.1.0`, Tailwind CSS `3.4.17`, Lucide React.
  - **State Management:** Zustand `5.0.3` with deep URL synchronization and local storage hydration.
- **Observability & Async Workers:**
  - **Background Tasks:** Local in-process async background tasks with full compatibility for `arq` / Redis.
  - **Profiling & Telemetry:** Custom non-intrusive profiler decorators ([`app/core/profiler.py`](app/core/profiler.py)) storing JSON execution traces in `local_storage/profiling/`.
- **Quality & Static Analysis:**
  - **Test Runners:** `pytest` (Backend - mandatory 100% statement coverage rule) and `vitest` (Frontend - React Testing Library).
  - **Linters & Type Checkers:** `ruff` (linter & formatter), `mypy` (strict mode), `tsc` (TypeScript compiler with `noEmit`).

---

## 2. Unified ASGI & Hybrid Web Server Architecture

Eidos runs as a single unified ASGI process managed by [`app/asgi.py:UnifiedASGIApplication`](app/asgi.py:27):

```
                       ┌────────────────────────────────────────┐
                       │           Incoming HTTP / WS           │
                       │           (Uvicorn / ASGI)             │
                       └───────────────────┬────────────────────┘
                                           │
                                           ▼
                       ┌────────────────────────────────────────┐
                       │     UnifiedASGIApplication (asgi.py)   │
                       └───────────────────┬────────────────────┘
                                           │
                    Path starts with:      │      All other paths:
            /admin, /accounts,             │      /api/v1/*, /, /app/*,
            /django-static                 │      SPA deep links
                                           │
                                           ├────────────────────────┐
                                           │                        │
                                           ▼                        ▼
                       ┌───────────────────────┐ ┌───────────────────────┐
                       │  Django ASGI Handler  │ │  FastAPI Application │
                       │    (Auth, Admin,      │ │  (REST API, SSE,      │
                       │     Static files)     │ │   SPA Catch-all)      │
                       └───────────────────────┘ └───────────────────────┘
```

### Invariants for Unified ASGI:
1. **Routing Separation:**
   - Django handles `/admin*`, `/accounts*`, `/django-static*`.
   - FastAPI handles `/api/v1/*`, `/health`, static client assets, and SPA route fallback.
2. **SPA Deep-Link Fallback:**
   - The FastAPI instance in [`app/main.py:spa_catch_all()`](app/main.py:153) serves `frontend/dist/index.html` (or fallback static HTML) for non-API, non-Django GET routes, enabling client-side routing.
3. **Authentication Handshake & 401 Interception:**
   - Unauthenticated browser requests targeting protected FastAPI routes or HTML views are intercepted by [`app/main.py:http_exception_handler()`](app/main.py:47) and redirected to `/accounts/login/?next=...`.

---

## 3. Directory Layout & Layer Boundaries

The codebase enforces strict separation of concerns following Domain-Driven Design (DDD) and Clean Architecture principles:

```
Eidos/
├── alembic/                      # SQLAlchemy async database migrations
├── app/                          # Core application package
│   ├── api/                      # Web delivery layer (FastAPI routers, middleware)
│   │   ├── middleware.py         # Request profiling & CORS middleware
│   │   └── v1/endpoints/         # Endpoint modules (auth, transcription, account, events)
│   ├── core/                     # Configuration, logging, profiler, security, Django settings
│   │   ├── config.py             # Pydantic BaseSettings & offline env flags
│   │   ├── django_settings.py    # Django framework settings
│   │   ├── profiler.py           # Execution profiling decorators & trace emitters
│   │   └── security.py           # JWT & Django Session dual-auth dependencies
│   ├── db/                       # Data persistence models & database engine
│   │   ├── migrations/           # Django ORM schema migrations
│   │   ├── models.py             # Django ORM models (Transcription, TranscriptionJob, VoiceProfile)
│   │   └── session.py            # SQLAlchemy 2.0 async engine & session factory
│   ├── domain/                   # Enterprise business entities, protocols & exceptions
│   │   ├── entities.py           # Pure Pydantic v2 domain schemas (no ORM dependencies)
│   │   ├── exceptions.py         # Domain-level custom exceptions
│   │   └── protocols.py          # Abstract interfaces for ML processors & storage
│   ├── ml/                       # Machine learning inference & DSP pipeline
│   │   ├── audio_processor.py    # FFmpeg audio conversion & filter graphs
│   │   ├── inference_engine.py   # Faster-Whisper ASR, PyAnnote diarization, Timbre clustering
│   │   └── llm_processor.py      # LexRank/TextRank summarization & local LLM engine
│   ├── repository/               # Data Access Layer (DAL)
│   │   ├── hardened_repository.py# SQLAlchemy async repository with optimistic concurrency
│   │   └── job_repository.py     # Async repository interfacing with Django ORM models
│   ├── schemas/                  # Request / Response DTOs for API endpoints
│   ├── services/                 # Application service layer (e.g., ExportService)
│   └── workers/                  # Async job orchestration & worker pipelines
├── frontend/                     # React 19 + TypeScript + Vite SPA
│   └── src/
│       ├── components/           # Modular UI components (Audio dropzone, Player, Intelligence)
│       ├── services/             # API client & HTTP error handlers
│       ├── store/                # Zustand stores (useAppStore, toastStore)
│       └── types/                # TypeScript interface declarations mirroring domain entities
└── tests/                        # Backend Pytest test suite (100% statement coverage)
```

### Strict Import Boundaries:
1. **Domain Isolation:** [`app/domain/`](app/domain/) MUST NOT import from `app/api/`, `app/db/`, `app/ml/`, or `app/repository/`. It must contain only standard library, `pydantic`, and pure Python typing.
2. **Repository Boundary:** API endpoints MUST interact with persistence models via Repositories ([`app/repository/job_repository.py`](app/repository/job_repository.py)) or Domain Entities ([`app/domain/entities.py`](app/domain/entities.py)), never writing raw SQL queries inside route controllers.
3. **ML Encapsulation:** ML pipelines in [`app/ml/`](app/ml/) MUST implement interfaces defined in [`app/domain/protocols.py`](app/domain/protocols.py) (e.g. [`AudioPreprocessorProtocol`](app/domain/protocols.py:11), [`SpeechRecognizerProtocol`](app/domain/protocols.py:18), [`DiarizerProtocol`](app/domain/protocols.py:25), [`LLMIntelligenceEngineProtocol`](app/domain/protocols.py:32)).
4. **Async/Sync Django Boundary:** Any Django ORM operation invoked from async FastAPI code MUST be wrapped with `asgiref.sync.sync_to_async(thread_sensitive=True)` or native Django 5.0 async ORM methods (`aget`, `acreate`, `asave`).

---

## 4. Data Layer & Schema Conventions

### Dual ORM Co-existence Strategy:
- **Primary Schema Definition:** Managed via Django ORM in [`app/db/models.py`](app/db/models.py). Django migrations in [`app/db/migrations/`](app/db/migrations/) are the authoritative source for database table creation and schema changes.
- **SQLAlchemy Async Compatibility:** SQLAlchemy tables and async queries ([`app/db/session.py`](app/db/session.py), [`app/repository/hardened_repository.py`](app/repository/hardened_repository.py)) operate directly over the same underlying tables (`db_transcription`, `db_transcriptionjob`, `db_voiceprofile`).
- **Alembic Synchronization:** When adding or modifying columns, ensure Django migrations (`python manage.py makemigrations`) and Alembic migration scripts ([`alembic/versions/`](alembic/versions/)) remain strictly in sync.

### Concurrency & Locking:
1. **SQLite WAL Mode:** SQLite database connections MUST use `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`, and a `busy_timeout` of at least 30,000ms.
2. **Optimistic Locking:** High-concurrency operations on transcripts (such as word or utterance edits) MUST use optimistic concurrency verification via [`app/repository/hardened_repository.py:HardenedJobRepository`](app/repository/hardened_repository.py:26) to prevent race conditions without table-level locking.

---

## 5. Machine Learning & Audio Processing Pipeline

```
 [ Audio File Upload ]
          │
          ▼
 ┌──────────────────────────────────────────────────────────┐
 │ FFmpegAudioProcessor (loudnorm, afftdn, highpass)        │
 └────────────────────────┬─────────────────────────────────┘
                          │ (16kHz Mono 16-bit PCM WAV)
                          ▼
 ┌──────────────────────────────────────────────────────────┐
 │ InferenceEngine._run_transcription (Faster-Whisper ASR)  │
 └────────────────────────┬─────────────────────────────────┘
                          │ (Word Timestamps & Segments)
                          ▼
 ┌──────────────────────────────────────────────────────────┐
 │ Diarization: PyAnnote Pipeline OR Timbre Clustering      │
 └────────────────────────┬─────────────────────────────────┘
                          │ (Speaker Turns & Acoustic Embeddings)
                          ▼
 ┌──────────────────────────────────────────────────────────┐
 │ Speaker Alignment & Voice Memory Cosine Matching        │
 └────────────────────────┬─────────────────────────────────┘
                          │ (Utterances with Speaker Labels)
                          ▼
 ┌──────────────────────────────────────────────────────────┐
 │ LLMIntelligenceEngine: LexRank/TextRank OR Local LLM     │
 └────────────────────────┬─────────────────────────────────┘
                          │
                          ▼
          [ Structured Meeting Intelligence & Result ]
```

### Air-Gapped / Offline-First Invariants:
1. **Strict Offline Environment:** When `LOCAL_MODELS_ONLY=True` or `ALLOW_EXTERNAL_API_CALLS=False` in [`app/core/config.py:Settings`](app/core/config.py:10), no external network calls may be made.
2. **Offline Acoustic Timbre Clustering Fallback:** If `pyannote.audio` weights or HuggingFace tokens are not present, the system automatically uses [`app/ml/inference_engine.py:InferenceEngine._run_acoustic_diarization()`](app/ml/inference_engine.py:833) (MFCC, Zero-crossing rate, spectral energy, pitch F0 estimation, and k-means clustering).
3. **Graph Summarization Fallback:** If a remote or local LLM server is unreachable or offline, [`app/ml/llm_processor.py:LocalDynamicSummarizer`](app/ml/llm_processor.py:179) executes LexRank/TextRank sentence centrality, decision boundary detection, and sentiment analysis entirely offline with zero dependencies.

---

## 6. Authentication, Authorization & Security Governance

1. **Dual-Auth Scheme:**
   - FastAPI dependencies in [`app/core/security.py:get_current_django_user()`](app/core/security.py:123) accept either a standard Bearer JWT token in the `Authorization` header or an active Django `sessionid` cookie.
2. **Granular RBAC:**
   - Use [`RequirePermission`](app/core/security.py:168) for fine-grained permission enforcement (e.g., `RequirePermission("db.add_transcriptionjob")`).
   - Use [`RequireGroup`](app/core/security.py:196) for role/group checks (e.g., `RequireGroup("Auditors")`).
3. **Data Ownership & Tenant Isolation:**
   - All operations on transcriptions, voice profiles, and jobs MUST strictly filter queries by the authenticated user's ID (`user_id == current_user.id`). Superusers may view system-wide resources when explicitly handled.

---

## 7. Frontend SPA & State Management Architecture

1. **Zustand Single Store with URL Sync:**
   - [`frontend/src/store/useAppStore.ts:useAppStore`](frontend/src/store/useAppStore.ts:240) orchestrates all application views (`transcription`, `account`), active jobs, and media player synchronization.
   - `navigate()` and `resolveCurrentRoute()` ensure complete synchronization between browser URL parameters (`?job_id=...`, `?tab=...`), `localStorage` snapshots, and backend job polling.
2. **Audio-Transcript Real-time Synchronization:**
   - Active playback in [`frontend/src/components/TranscriptPlayer.tsx`](frontend/src/components/TranscriptPlayer.tsx) calculates current word highlighting and utterance auto-scroll based on sub-second audio timestamps (`WordTimestamp.start` / `WordTimestamp.end`).
3. **Type Parity:**
   - All TypeScript interfaces in [`frontend/src/types/index.ts`](frontend/src/types/index.ts) MUST precisely mirror Python domain entities in [`app/domain/entities.py`](app/domain/entities.py).

---

## 8. Quality, Testing & Linting Standards

1. **Mandatory 100% Test Coverage:**
   - Every single backend module in [`app/`](app/) must maintain 100% statement coverage.
   - Run tests via `.venv\Scripts\pytest --cov=app --cov-report=term-missing` before any task finalization.
2. **Frontend Test Suite:**
   - Run `npm run test` (Vitest) in `frontend/` to ensure all React component and store test suites pass.
3. **Static Analysis & Type Checking:**
   - Backend: Run `ruff check app tests` and `mypy app tests`.
   - Frontend: Run `npx tsc --noEmit` in `frontend/` to ensure zero TypeScript compiler warnings or errors.
4. **Google-Style Docstrings:**
   - Every function, class, and method MUST contain a Google-style docstring detailing `Args:`, `Returns:`, `Raises:`, and usage context.
5. **No Code Placeholders:**
   - Never write `# TODO`, `// ... rest of code`, or partial implementations. All committed code must be 100% complete and production-grade.

---

## 9. Critical Architectural Constraints (Do's and Don'ts)

### DO:
- **DO** use the project virtual environment `.venv/` for all Python tool execution and testing.
- **DO** use Guard Clauses (early returns) to prevent deeply nested `if/else` control flow.
- **DO** profile critical pipeline bottlenecks using `@profile_sync` and `@profile_async` from [`app/core/profiler.py`](app/core/profiler.py).
- **DO** ensure all timestamps and datetime objects are timezone-aware using `datetime.now(timezone.utc)`.
- **DO** write comprehensive unit tests in [`tests/`](tests/) for every newly introduced backend service, repository, route, or ML helper.

### DON'T:
- **DON'T** remove or bypass the `UnifiedASGIApplication` router in [`app/asgi.py`](app/asgi.py).
- **DON'T** call blocking sync Django ORM queries directly in async FastAPI path operations without `sync_to_async`.
- **DON'T** execute external HTTP/API requests if `LOCAL_MODELS_ONLY=True` or `ALLOW_EXTERNAL_API_CALLS=False`.
- **DON'T** hardcode secret keys or credentials; use [`app/core/config.py:Settings`](app/core/config.py:10).
- **DON'T** commit changes without verifying both backend (`pytest`) and frontend (`npm run test`) test suites.
