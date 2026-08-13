# PART 1: Full System Module Breakdown

```text
project_root/
├── app/
│   ├── core/
│   │   ├── config.py                 # Pydantic settings & env management (DEV_MODE & USE_REDIS flags)
│   │   ├── logging.py                # Structured JSON logging formatter
│   │   ├── metrics.py                # Prometheus metrics registry (P50/P95/P99 latencies, queue depth)
│   │   ├── security.py               # JWT generation, validation & RBAC role checkers
│   │   ├── circuit_breaker.py        # 3-state Circuit Breaker (CLOSED/OPEN/HALF_OPEN)
│   │   └── tenant.py                 # Multi-tenant ContextVar isolation & storage enclaves
│   ├── db/
│   │   ├── session.py                # Async SQLAlchemy 2.0 engine & sessionmaker (SQLite/Postgres)
│   │   └── models.py                 # SQLAlchemy ORM models (TranscriptionJobModel)
│   ├── domain/
│   │   ├── entities.py               # Domain models (Job, Utterance, WordTimestamp, ActionItem, Analysis)
│   │   ├── exceptions.py             # Domain exception hierarchy (AudioProcessingError, JobNotFoundError)
│   │   └── protocols.py              # Structural duck-typing interfaces (typing.Protocol)
│   ├── repository/
│   │   ├── job_repository.py         # Standard async DB CRUD repository
│   │   └── hardened_repository.py    # Optimistic concurrency repository (version_id verification)
│   ├── ml/
│   │   ├── audio_processor.py        # Async FFmpeg subprocess wrapper (16kHz mono PCM & VAD)
│   │   ├── inference_engine.py       # Faster-Whisper + PyAnnote dynamic word/speaker alignment engine
│   │   ├── llm_processor.py          # Structured executive intelligence extraction
│   │   ├── dynamic_batcher.py        # Async GPU batch aggregator (micro-windowing)
│   │   ├── drift_detector.py         # Signal quality analyzer (SNR, clipping ratio, audio degradation)
│   │   ├── speaker_biometrics.py     # PyAnnote voice embedding extraction & cosine vector matching
│   │   └── hotword_engine.py         # Custom industry vocabulary prompt injection & fuzzy correction
│   ├── services/
│   │   ├── export_service.py         # Multi-format document exporter (PDF, DOCX, SRT, VTT, JSON)
│   │   ├── event_bus.py              # Decoupled Event Bus, Webhook retries & Dead-Letter Queue (DLQ)
│   │   └── translation_service.py    # Real-time multi-lingual transcript translation engine
│   ├── workers/
│   │   └── tasks.py                  # Arq background worker lifecycle hooks & async task pipelines
│   ├── api/
│   │   ├── middleware.py             # Security headers & Redis token-bucket rate limiter (with local bypass)
│   │   ├── dependencies.py           # Global FastAPI dependencies (auth, database, RBAC, tenant)
│   │   └── v1/
│   │       └── endpoints/
│   │           ├── transcription.py  # File upload, status polling, edits, speaker renames, exports
│   │           ├── live.py           # Real-time WebSocket live audio chunk ingestion
│   │           └── events.py         # Real-time Server-Sent Events (SSE) progress streaming
│   └── main.py                       # FastAPI ASGI application bootstrap & lifespan context
├── static/
│   ├── css/
│   │   └── app.css                   # CSS variable design system, dark/light themes, glassmorphism
│   ├── index.html                    # Production SPA workspace HTML shell
│   └── js/
│       ├── store.js                  # Centralized reactive Proxy store
│       ├── app.js                    # SPA bootstrapper, theme switcher & SSE event connector
│       ├── audio-worklet-processor.js # In-browser 16kHz PCM downsampler AudioWorklet
│       └── components/
│           ├── FileUploadDropzone.js           # Drag-and-drop file uploader with chunk tracking
│           ├── AudioWaveformVisualizer.js      # Canvas waveform scrubber & colorized speaker timeline
│           ├── ExecutiveIntelligenceCard.js   # Structured summary, decisions, action items & sentiment
│           ├── TranscriptPlayer.js             # Word-level audio playback sync & inline text editor
│           ├── LiveStreamTranscriber.js        # Real-time WebSocket microphone streaming component
│           └── SpeakerBiometricsManager.js     # Speaker voice enrollment & domain hotwords manager
├── alembic/
│   ├── env.py                        # Async Alembic migration environment
│   └── versions/
│       └── 001_initial_schema.py     # Initial DB schema migration script
├── k8s/
│   ├── deployment.yaml               # K8s namespace, API deployment & GPU worker deployment
│   └── hpa.yaml                      # Horizontal Pod Autoscaler driven by Prometheus queue depth
├── monitoring/
│   └── grafana_dashboard.json        # Production Grafana dashboard specification
├── tests/
│   ├── conftest.py                   # Pytest async fixtures & isolated test DB setup
│   ├── test_domain.py                # Unit tests for domain models & export generators
│   ├── test_api.py                   # Integration tests for REST endpoints & error handling
│   └── load/
│       └── locustfile.py             # Distributed Locust performance & load testing script
├── run_local.py                      # Zero-dependency single-command launcher (Local Dev Mode)
├── .github/
│   └── workflows/
│       └── deploy.yml                # GitHub Actions pipeline (Ruff, MyPy, Pytest, Docker, K8s)
├── Dockerfile                        # Multi-stage CUDA 12.1 runtime Docker image
└── pyproject.toml                    # Tooling config (Ruff, MyPy, Pytest) & Python dependencies
```

---

## Detailed Module Responsibilities

### 1. Core Infrastructure & Domain Layer

- **`app/domain/entities.py`**: Enforces tight typing and validation using Pydantic v2 for `WordTimestamp`, `Utterance`, `ActionItem`, `ConversationAnalysis`, `TranscriptionResult`, and `TranscriptionJobEntity`.
- **`app/domain/exceptions.py`**: Centralized base `DomainError` hierarchy mapping domain failures to HTTP error handling (`JobNotFoundError`, `AudioProcessingError`, `ModelInferenceError`, `ExportGenerationError`).
- **`app/core/config.py`**: Production and development settings management using `pydantic-settings` to dynamically toggle `DEV_MODE` and `USE_REDIS` with local fallback defaults.
- **`app/core/metrics.py`**: Prometheus metrics registry exporting latencies (`INFERENCE_LATENCY`), active job counts (`ACTIVE_JOBS`), queue depth (`QUEUE_DEPTH`), and total processed seconds.
- **`app/core/security.py`**: OAuth2 bearer authentication, JWT token encoding/decoding, and Role-Based Access Control (RBAC) authorization dependencies.
- **`app/core/circuit_breaker.py`**: 3-state Circuit Breaker preventing cascading system collapses when upstream LLMs or inference nodes fail.
- **`app/core/tenant.py`**: Context-isolated storage enclaves and `ContextVar` context management enforcing enterprise tenant data separation (`X-Tenant-ID`).

### 2. Machine Learning & Inference Pipeline

- **`app/ml/audio_processor.py`**: Asynchronous FFmpeg subprocess wrapper converting uploaded audio streams (MP3, WAV, M4A, FLAC) into standardized 16kHz mono PCM WAV files.
- **`app/ml/inference_engine.py`**: Orchestrates Faster-Whisper speech recognition with PyAnnote speaker diarization, performing time-overlap calculations to map word timestamps to speaker turns.
- **`app/ml/llm_processor.py`**: Calls structured LLM engines (OpenAI/vLLM) to extract executive summaries, key decisions, action items (with owner and priority), and overall sentiment.
- **`app/ml/dynamic_batcher.py`**: Dynamic GPU batching engine aggregating individual micro-requests over micro-windows (e.g., 10ms) to maximize CUDA tensor core saturation.
- **`app/ml/drift_detector.py`**: Calculates Signal-to-Noise Ratio (SNR) in dB, clipping percentages, and acoustic quality degradation metrics.
- **`app/ml/speaker_biometrics.py`**: Extracts 512-dimensional PyAnnote voice vectors and computes cosine similarity to resolve speaker labels (`SPEAKER_00`) to enrolled identities.
- **`app/ml/hotword_engine.py`**: Custom domain glossary injection into Faster-Whisper decoder prompts and post-transcription fuzzy term corrections.

### 3. Data Persistence & Messaging Services

- **`app/db/session.py` & `models.py`**: SQLAlchemy 2.0 async engine configuration and ORM mapping supporting both local SQLite and PostgreSQL.
- **`app/repository/job_repository.py` & `hardened_repository.py`**: Async repository pattern handling standard CRUD and optimistic concurrency locking (`version_id`) to prevent race conditions during collaborative editing.
- **`app/services/export_service.py`**: Document rendering engine producing formatted downloadable outputs (`PDF`, `DOCX`, `SRT`, `VTT`, `JSON`).
- **`app/services/event_bus.py`**: Event-driven architecture executing asynchronous webhook deliveries with exponential backoff retries and Dead-Letter Queue (DLQ) containment.
- **`app/services/translation_service.py`**: Real-time transcript translation engine translating speech turns into target foreign languages.
- **`app/workers/tasks.py`**: Arq background task worker lifecycle managing long-running audio processing jobs via Redis (or in-memory fallback).

### 4. API Controllers & Routing Layer

- **`app/api/v1/endpoints/transcription.py`**: REST API handling uploads, status polling, cancellations, inline utterance editing, global speaker renames, multi-format exports, and dual task routing (Redis Arq vs local `BackgroundTasks`).
- **`app/api/v1/endpoints/live.py`**: WebSocket router ingesting live PCM audio frames and emitting real-time partial transcriptions.
- **`app/api/v1/endpoints/events.py`**: Server-Sent Events (SSE) streaming endpoint broadcasting job progress frames (`progress`, `complete`, `error`) to UI clients.
- **`app/api/middleware.py`**: Token-bucket rate limiter enforcing client IP limits with auto-bypass in local dev mode, alongside OWASP security headers.

### 5. Frontend Reactive Web Architecture

- **`static/css/app.css`**: CSS Variable design system providing light/dark theme toggling, container queries, custom scrollbars, and skeleton shimmer animations.
- **`static/js/audio-worklet-processor.js`**: Dedicated WebWorker thread downsampling browser microphone inputs (44.1/48kHz) to 16kHz mono PCM Int16 buffers in real time.
- **`static/js/components/FileUploadDropzone.js`**: Web Component managing drag-and-drop file ingestion, file format verification, and HTTP upload progress tracking.
- **`static/js/components/AudioWaveformVisualizer.js`**: HTML5 Canvas visualizer rendering waveform peaks, colorized speaker segment regions, and playhead scrubbing.
- **`static/js/components/ExecutiveIntelligenceCard.js`**: Web Component presenting structured AI insights with 4 explicit UI states (Loading, Success, Error, Empty).
- **`static/js/components/TranscriptPlayer.js`**: Interactive transcript player linking word-level timestamps to audio element time updates, speaker renames, and inline text edits.
- **`static/js/components/LiveStreamTranscriber.js`**: Streaming Web Component managing microphone permissions, WebAudio pipeline bindings, and WebSocket binary data dispatch.
- **`static/js/components/SpeakerBiometricsManager.js`**: Web Component for managing speaker identity enrollments and custom industry vocabulary hotwords.

### 6. Execution & Launcher Tools

- **`run_local.py`**: Zero-dependency launcher script initializing local SQLite storage, checking FFmpeg binaries, and starting an auto-reloading Uvicorn server for local development.
- **`Dockerfile`**: Production multi-stage CUDA 12.1 + Ubuntu 22.04 container build running as a non-root user with health checks.
- **`k8s/`**: Kubernetes manifests providing horizontal pod autoscaling (HPA) based on CPU and Redis queue depth metrics.
- **`monitoring/grafana_dashboard.json`**: Pre-configured Grafana telemetry dashboard tracking P50/P95/P99 latencies, audio hours processed, and queue depth.
- **`.github/workflows/deploy.yml`**: GitHub Actions pipeline executing static type checking (`mypy --strict`), linting (`ruff`), security scans (`bandit`), test suites (`pytest`), Docker builds, and Kubernetes rollouts.
- **`tests/`**: Pytest suite covering unit test validation, integration endpoints, and Locust distributed load testing scripts.

---

# PART 2: What To Do Next (Operational Launch Plan)

With all architectural components, zero-dependency local options, and enterprise infrastructure manifests complete, here is the updated roadmap for launching and maintaining the platform:

### Phase 1: Local & Zero-Dependency Testing

1. **Instant Zero-Dependency Execution:** Test the complete system locally without Docker or Redis:
   ```bash
   python run_local.py
   ```
   Open `http://127.0.0.1:8000/static/index.html` to test file dropzone ingestion, live WebSockets streaming, inline editing, and PDF/DOCX/SRT exports.
2. **Execute Automated Pytest Suite:** Run test coverage and lint checks:
   ```bash
   ruff check app tests
   mypy --strict app
   pytest --cov=app tests/
   ```

### Phase 2: Staging Deployment & Performance Profiling

1. **Spin up Staging Infrastructure:** Boot PostgreSQL, Redis, Prometheus, and Grafana using Docker Compose:
   ```bash
   docker compose up -d
   ```
2. **Execute Database Migrations:** Run Alembic to initialize database schema:
   ```bash
   alembic upgrade head
   ```
3. **Deploy GPU Worker Nodes:** Apply Kubernetes manifests (`k8s/deployment.yaml`, `k8s/hpa.yaml`) to GPU-enabled staging nodes (AWS EKS `g5.xlarge` or GCP GKE NVIDIA L4).
4. **Benchmark GPU Concurrency:** Run Locust performance scripts against the staging cluster to profile CUDA dynamic batching throughput:
   ```bash
   locust -f tests/load/locustfile.py --host=https://staging.yourdomain.com
   ```

### Phase 3: Production Rollout & Observability

1. **Configure Production Telemetry:** Import `monitoring/grafana_dashboard.json` into Grafana and connect Prometheus scraping rules to `/metrics`.
2. **Set Up Alertmanager Signals:** Define alerts for P99 latency spikes (>30s), queue depth backlog (>20 jobs), Dead-Letter Queue (DLQ) failures, and GPU VRAM OOM errors.
3. **Trigger Production Continuous Deployment:** Merge code into `main` to activate GitHub Actions for automated zero-downtime rolling upgrades.

### Phase 4: Future Scale & Integration Extensions (Post-Launch)

- **Dedicated Vector Database Migration:** Scale PyAnnote voice embedding lookups from in-memory cosine vectors to a dedicated distributed vector database (e.g., Qdrant or Milvus) for millions of enrolled speakers.
- **WebRTC High-Density Gateway:** Implement WebRTC media gateways to ingest multi-party teleconference audio feeds directly from Zoom, Microsoft Teams, or Google Meet SIP trunks.
- **Real-Time Automated Action Item Alerts:** Send instant Slack or Microsoft Teams webhook notifications as soon as high-priority action items are identified during live streams.
