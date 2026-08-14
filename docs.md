---
title: "AI voice analytics"
subtitle: "Comprehensive System Architecture, Technical Subsystem Specifications, and Execution Guide"
author: [Tensorika]
date: "01.08.2026"
---

# 1. SYSTEM PURPOSE AND BUSINESS SCOPE

## 1.1 Platform Vision and Business Value
The Enterprise AI Audio Transcription and Conversation Intelligence Platform is a software platform designed to convert unstructured multi-speaker audio recordings into structured, actionable business intelligence. Built on **Domain-Driven Clean Architecture**, the platform processes multi-speaker conversations, executive briefings, customer calls, and board meetings into fully aligned, speaker-attributed transcripts accompanied by executive summaries, key decisions, action items, and sentiment analytics.

The core value proposition centers on decoupling heavy computational machine learning inference tasks—such as automatic speech recognition (ASR), voice activity detection (VAD), speaker diarization, and LLM post-processing—from API gateway operations and user interfaces. This separation guarantees high scalability, sub-second API response times, and resilient background task execution across both cloud GPU worker nodes and local zero-dependency development environments.

## 1.2 Core Capabilities and Operational Requirements
The system delivers end-to-end processing across six primary capabilities:

1. **Multi-Speaker Diarization and Timestamp Alignment**: Separates contiguous speech turns between distinct individuals using acoustic voice embeddings, mapping word-level timestamps ($10\,\mathrm{ms}$ precision) to speaker labels.
2. **Interactive Audio-Transcript Synchronization**: Provides native HTML5 audio synchronization where clicking any word or phrase seeks audio playback to the exact start timestamp while dynamically highlighting active text during playback.
3. **Structured Conversation Intelligence**: Leverages Large Language Models (LLMs) to automatically generate executive summaries, key decisions, prioritized action items (with owner assignments and due dates), and overall conversation sentiment distribution.
4. **Interactive Editing and Global Speaker Reassignment**: Supports real-time inline text modification and global bulk speaker renaming with optimistic concurrency control to prevent collaborative overwrite conflicts.
5. **Multi-Tenant Data Privacy and Compliance**: Enforces strict tenant isolation via runtime context variables (`X-Tenant-ID`), zero-trust role-based access control (RBAC), and optional on-premises execution enclaves to meet enterprise GDPR and HIPAA standards.
6. **Dynamic Multi-Format Export Generator**: Dynamically renders output formats including PDF briefing reports, Word documents (`.docx`), subtitle streams (`.srt`, `.vtt`), and structured JSON payloads.

\newpage

# 2. DOMAIN-DRIVEN PROJECT STRUCTURE

The codebase strictly adheres to Domain-Driven Design (DDD) and Clean Architecture principles. The layout segregates core application configuration, pure business entities, database access layers, ML pipelines, background workers, and static frontend assets.

\newpage

# 3. ARCHITECTURAL DATA FLOW DIAGRAMS

The following diagram illustrates the complete processing pipeline from initial audio ingestion through machine learning execution layers to persistent storage and real-time frontend rendering.

\begingroup\centering

```{.mermaid format=pdf}
flowchart TD
    subgraph Ingestion["Ingestion & Queue"]
        A([Client UI]) -->|"HTTP Upload"| B["FastAPI Gateway"]
        B -->|"Normalize PCM"| C["FFmpeg Subprocess"]
        C -->|"Enqueue Job"| D[(Redis / Arq Queue)]
    end

    subgraph Processing["ML Pipeline Execution"]
        D -->|"Dequeue Task"| E["Background Worker"]
        E -->|"Batch Audio"| F["Faster-Whisper (ASR)"]
        E -->|"Extract Turns"| G["PyAnnote (Diarization)"]
        F --> H["Alignment Engine"]
        G --> H
        H -->|"Structure Text"| I["LLM Processor"]
    end

    subgraph Persistence["Storage & State"]
        I -->|"Persist Entity"| J[(PostgreSQL DB)]
        E -->|"Stream SSE"| A
        J -->|"Poll / Export"| B
    end

    style A fill:#1e293b,stroke:#3b82f6,stroke-width:1px,color:#fff
    style B fill:#1e293b,stroke:#3b82f6,stroke-width:1px,color:#fff
    style C fill:#1e293b,stroke:#3b82f6,stroke-width:1px,color:#fff
    style D fill:#1e293b,stroke:#f59e0b,stroke-width:1px,color:#fff
    style E fill:#1e293b,stroke:#3b82f6,stroke-width:1px,color:#fff
    style F fill:#1e293b,stroke:#10b981,stroke-width:1px,color:#fff
    style G fill:#1e293b,stroke:#10b981,stroke-width:1px,color:#fff
    style H fill:#1e293b,stroke:#10b981,stroke-width:1px,color:#fff
    style I fill:#1e293b,stroke:#10b981,stroke-width:1px,color:#fff
    style J fill:#1e293b,stroke:#f59e0b,stroke-width:1px,color:#fff
```

\endgroup

## 3.1 End-to-End Request Lifecycle Stages

1. **Ingestion and Normalization**: The API gateway receives raw audio (`.mp3`, `.wav`, `.m4a`, `.flac`) via *upload_audio_file*. It invokes an asynchronous `FFmpeg` subprocess to downmix channels to 16kHz mono PCM `pcm_s16le`.
2. **Asynchronous Enqueuing**: The normalized file path and job record (`JobStatus.PENDING`) are persisted in PostgreSQL. The job UUID is enqueued into Redis via `Arq`. In local development mode (`USE\_REDIS=False`), it falls back to FastAPI `BackgroundTasks`.
3. **Machine Learning Execution**:
   - **Speech Recognition**: `Faster-Whisper` executes voice activity detection (VAD) and emits word timestamps ($t_{\mathit{start}}, t_{\mathit{end}}$) with token probabilities.
   - **Speaker Diarization**: `PyAnnote.audio` extracts voice embeddings and calculates speaker turn boundaries.
   - **Dynamic Time-Overlap Alignment**: Words are mapped to speaker turns based on midpoint timestamp containment ($t_{\mathit{mid}} = \frac{t_{\mathit{start}} + t_{\mathit{end}}}{2}$).
4. **Structured Intelligence Extraction**: The aligned transcript is processed by `LLMIntelligenceEngine`, generating structured JSON outputs containing executive summaries, key decisions, action items, and sentiment scores.
5. **Persistence and Frontend Sync**: The result is saved to PostgreSQL (`TranscriptionJobModel.result\_json`). Frontends receive real-time updates via Server-Sent Events (SSE) via `stream\_job\_progress`.

\newpage

# 4. DEEP-DIVE SUBSYSTEM MODULE SPECIFICATIONS

## 4.1 Subsystem Implementations

### Configuration Subsystem (`app/core/config.py`)
Manages configuration using Pydantic's `BaseSettings`. Automatically parses environment variables and `.env` files. Toggles operational flags (`DEV_MODE`, `USE_REDIS`) and sets storage path defaults (`STORAGE_DIR`), database connection strings (`DATABASE_URL`), and machine learning model parameters (`WHISPER_MODEL_SIZE`, `WHISPER_DEVICE`).

### Database and ORM Subsystem (`app/db/session.py`, `app/db/models.py`)
Built on SQLAlchemy 2.0 async engines using `AsyncSession`. The `TranscriptionJobModel` table stores UUID primary keys, status flags, step strings, progress float percentages, and JSON transcript strings (`result_json`).

### Mathematical Formulations and Pipeline Algorithms

1. **Signal-to-Noise Ratio ($\mathit{SNR}_{\mathit{dB}}$)**: Signal health is evaluated by parsing 16-bit PCM samples ($s_i \in [-32768, 32767]$) across $N$ sample frames:
$$\mathit{P}_{\mathit{signal}} = \frac{1}{N} \sum_{i=1}^{N} s_i^2$$
$$\mathit{SNR}_{\mathit{dB}} = 10 \cdot \log_{10} \left( \frac{\mathit{P}_{\mathit{signal}}}{\mathit{P}_{\mathit{noise}}} \right)$$
where $\mathit{P}_{\mathit{noise}}$ represents the mean power of the bottom $10\%$ lowest-energy audio frames.

2. **Speaker Vector Cosine Distance**: Speaker identification maps 512-dimensional PyAnnote voice embedding vectors ($\mathbf{v}_1, \mathbf{v}_2 \in \mathbb{R}^{512}$) to enrolled profiles using cosine similarity:
$$\mathit{Sim}(\mathbf{v}_1, \mathbf{v}_2) = \frac{\mathbf{v}_1 \cdot \mathbf{v}_2}{\|\mathbf{v}_1\|_2 \|\mathbf{v}_2\|_2} = \frac{\sum_{k=1}^{512} v_{1,k} v_{2,k}}{\sqrt{\sum_{k=1}^{512} v_{1,k}^2} \sqrt{\sum_{k=1}^{512} v_{2,k}^2}}$$

3. **Word-to-Speaker Alignment Criterion**: Individual word tokens $w_j$ with boundaries $[t_{\mathit{start}}^j, t_{\mathit{end}}^j]$ are assigned to speaker turns $S_k = [\tau_{\mathit{start}}^k, \tau_{\mathit{end}}^k]$ using the temporal midpoint rule:
$$t_{\mathit{mid}}^j = \frac{t_{\mathit{start}}^j + t_{\mathit{end}}^j}{2}$$
$$w_j \in S_k \iff \tau_{\mathit{start}}^k \le t_{\mathit{mid}}^j \le \tau_{\mathit{end}}^k$$

\begin{longtable}{|p{3.0cm}|p{4.5cm}|p{2.0cm}|p{7.0cm}|}
\hline
\textbf{Symbol} & \textbf{Code Variable} & \textbf{Type} & \textbf{Meaning} \\ \hline
\endhead
$\mathit{SNR}_{\mathit{dB}}$ & \textit{snr\_db} & \texttt{float} & Signal-to-Noise Ratio in Decibels \\ \hline
$\mathit{P}_{\mathit{signal}}$ & \textit{signal\_power} & \texttt{float} & Total mean power of audio frame samples \\ \hline
$\mathit{P}_{\mathit{noise}}$ & \textit{noise\_power} & \texttt{float} & Estimated noise floor power ($10\%$ percentile) \\ \hline
$\mathbf{v}_k$ & \textit{embedding\_vector} & \texttt{list[float]} & 512-dimensional PyAnnote speaker vector \\ \hline
$\mathit{Sim}(\mathbf{v}_1, \mathbf{v}_2)$ & \textit{highest\_similarity} & \texttt{float} & Cosine similarity match score ($0.0$ to $1.0$) \\ \hline
$t_{\mathit{mid}}$ & \textit{word\_mid} & \texttt{float} & Temporal midpoint timestamp of a word token \\ \hline
\end{longtable}

\newpage

# 5. DEPENDENCY MANAGEMENT AND CONTAINERIZATION

## 5.1 System-Level Infrastructure Dependencies
1. **FFmpeg (`>= 5.0`)**: Required for audio stream probing, downmixing, resampling, and VAD frame extraction.
2. **uv (`>= 0.5.0`)**: High-performance Python package manager and build tool.
3. **NVIDIA CUDA Toolkit (`12.1`) and cuDNN (`>= 8.9`)**: Required for GPU acceleration across Faster-Whisper (CTranslate2) and PyAnnote (PyTorch).
4. **Redis (`>= 7.0`)**: Message broker for Arq task queues and state storage for rate-limiting counters.

## 5.2 Multi-Stage Docker Build Architecture (`Dockerfile`)

```dockerfile
# Stage 1: Base CUDA 12.1 Runtime Environment
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04 AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    ffmpeg \
    libsndfile1 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Install uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Stage 2: Dependencies Builder
FROM base AS builder

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY app app
COPY README.md ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Stage 3: Production Execution Image
FROM base AS runner

RUN useradd -m -u 1001 appuser
WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser app app
COPY --chown=appuser:appuser static static
COPY --chown=appuser:appuser templates templates
COPY --chown=appuser:appuser django_static django_static
COPY --chown=appuser:appuser alembic alembic
COPY --chown=appuser:appuser manage.py run_local.py pyproject.toml ./

RUN mkdir -p /tmp/conversation_ai ./local_storage && \
    chown -R appuser:appuser /tmp/conversation_ai ./local_storage /app

ENV PATH="/app/.venv/bin:$PATH"

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

\newpage

# 6. DEVELOPMENT AND PRODUCTION EXECUTION GUIDES

## 6.1 Local Zero-Dependency Execution
Developers can launch the platform locally without Docker, Redis, or external PostgreSQL databases:

```bash
# 1. Synchronize locked dependencies and virtual environment
uv sync

# 2. Build distribution packages (optional)
uv build

# 3. Launch single-command zero-dependency development engine
uv run python run_local.py
```
The launcher auto-detects system dependencies, initializes local SQLite tables (`sqlite+aiosqlite:///./dev\_app.db`), sets up storage paths, and starts Uvicorn with hot-reloading at `http://127.0.0.1:8000`.

## 6.2 Quality Assurance and Migration Commands

```bash
# Execute static type checking (Strict MyPy)
uv run mypy --strict app

# Execute Ruff linting & formatting checks
uv run ruff check app tests

# Run Database Schema Migrations
uv run alembic upgrade head

# Run Pytest suite with coverage analysis
uv run pytest --cov=app --cov-report=term-missing tests/
```

## 6.3 Production Kubernetes Deployment

Deploy production infrastructure manifests (`k8s/deployment.yaml`, `k8s/hpa.yaml`):

```bash
# Apply secrets and namespace configurations
kubectl apply -f k8s/deployment.yaml

# Enable Prometheus-driven Horizontal Pod Autoscaling (HPA)
kubectl apply -f k8s/hpa.yaml

# Verify deployment rollout status
kubectl rollout status deployment/api-server -n conversation-ai
kubectl rollout status deployment/gpu-worker -n conversation-ai
```

\newpage

# 7. COMPREHENSIVE USER AND API MANUAL

## 7.1 REST API Endpoint Specifications

\begin{longtable}{|p{3.5cm}|p{6.5cm}|p{6.5cm}|}
\hline
\textbf{HTTP Endpoint} & \textbf{Payload / Parameters} & \textbf{Response Specification} \\ \hline
\endhead
\path{POST /api/v1/transcription/upload} & \texttt{multipart/form-data} file upload stream. & \texttt{HTTP 202 Accepted}. Returns \textit{job\_id} UUID and status (\path{QUEUED_LOCAL} or \path{QUEUED_REDIS}). \\ \hline
\path{GET /api/v1/transcription/jobs/{id}} & Path parameter \textit{job\_id} UUID. & \texttt{HTTP 200 OK}. Returns full \textit{TranscriptionJobEntity} JSON. \\ \hline
\path{POST /api/v1/transcription/jobs/{id}/cancel} & Path parameter \textit{job\_id} UUID. & \texttt{HTTP 200 OK}. Cancels queued or running job. \\ \hline
\path{PATCH /api/v1/transcription/jobs/{id}/utterances/{utt_id}} & Path parameters \textit{job\_id}, \textit{utterance\_id}, query \textit{new\_text}. & \texttt{HTTP 200 OK}. Updates text with optimistic concurrency verification. \\ \hline
\path{POST /api/v1/transcription/jobs/{id}/speaker-rename} & Query params \textit{old\_speaker\_label}, \textit{new\_speaker\_name}. & \texttt{HTTP 200 OK}. Bulk updates speaker labels across transcript. \\ \hline
\path{GET /api/v1/transcription/jobs/{id}/export} & Query param \textit{export\_format} (\texttt{pdf}, \texttt{docx}, \texttt{srt}, \texttt{vtt}, \texttt{json}). & \texttt{HTTP 200 OK}. Returns binary document stream attachment. \\ \hline
\path{GET /api/v1/events/sse/{job_id}} & Path parameter \textit{job\_id} UUID. & \texttt{text/event-stream}. Emits SSE progress frames (\textit{progress}, \textit{complete}, \textit{error}). \\ \hline
\path{WS /api/v1/live/ws/transcribe} & Binary 16kHz PCM Int16 frame stream. & WebSocket stream returning partial JSON transcription fragments. \\ \hline
\end{longtable}

## 7.2 End-User Interactive Workflows

1. **Audio Ingestion**: Users drag and drop an audio file onto the `file-upload-dropzone` component. The upload progress bar tracks chunk progress. Once completed, the interface opens an EventSource connection to `/api/v1/events/sse/{job_id}`, animating real-time pipeline status text.
2. **Interactive Transcript Navigation**: Upon job completion, the `audio-waveform-visualizer` component renders audio amplitude peaks colored by speaker identity. Clicking any peak or transcript word seeks playback directly to that timestamp.
3. **Global Speaker Renaming**: Clicking a speaker tag (e.g., `SPEAKER_00`) triggers a prompt modal. Entering a new display name (e.g., `Sarah Jenkins`) renames all corresponding utterance tags across the interface and updates the database.
4. **Document Export**: Users click export format buttons (`PDF`, `DOCX`, `SRT`, `VTT`, `JSON`) in the export bar to generate and download formatted reports.

\newpage

# APPENDIX. SYSTEM FUNCTIONS AND MODULES REGISTER

\begin{longtable}{|p{5.5cm}|p{11.0cm}|}
\hline
\textbf{Function / Module Name} & \textbf{Purpose (Description)} \\ \hline
\endhead
\path{app/core/config.py} & System configuration settings management using Pydantic BaseSettings. \\ \hline
\textit{Settings} & Pydantic configuration class defining application environments and operational flags. \\ \hline
\path{app/core/logging.py} & Structured JSON logging system setup module. \\ \hline
\textit{JSONFormatter} & Formats log entries into structured JSON objects for observability. \\ \hline
\textit{setup\_logging()} & Initializes application logger handlers and formatting configurations. \\ \hline
\path{app/core/metrics.py} & Prometheus operational metrics registration collector. \\ \hline
\path{app/core/security.py} & JWT authentication token management and RBAC security checkers. \\ \hline
\textit{create\_access\_token()} & Generates signed JWT access tokens containing user claims and expiry timestamps. \\ \hline
\textit{get\_current\_user()} & Decodes and validates JWT bearer tokens from incoming API headers. \\ \hline
\textit{RoleChecker} & Dependency enforcing Role-Based Access Control permissions on endpoints. \\ \hline
\path{app/core/circuit_breaker.py} & 3-state Circuit Breaker implementation protecting upstream services. \\ \hline
\textit{CircuitBreaker} & State machine managing failure counts and cooldown recovery periods. \\ \hline
\path{app/core/tenant.py} & ContextVar multi-tenant execution isolation management module. \\ \hline
\textit{set\_tenant\_context()} & Assigns active tenant identifier to the current async context. \\ \hline
\textit{get\_tenant\_context()} & Retrieves active tenant context string for isolated execution. \\ \hline
\textit{get\_tenant\_storage\_dir()} & Generates tenant-isolated filesystem directory paths for data segregation. \\ \hline
\path{app/db/session.py} & SQLAlchemy 2.0 async database connection engine and session factory. \\ \hline
\textit{get\_db\_session()} & Async generator yielding database session instances for FastAPI routes. \\ \hline
\path{app/db/models.py} & Declarative ORM database models specification module. \\ \hline
\textit{TranscriptionJobModel} & SQLAlchemy ORM model mapping job state records to database tables. \\ \hline
\path{app/domain/entities.py} & Domain logic entity models definition module. \\ \hline
\textit{JobStatus} & StrEnum representing processing lifecycle states (\texttt{PENDING}, \texttt{COMPLETED}, etc.). \\ \hline
\textit{WordTimestamp} & Frozen Pydantic model encapsulating word-level text and timestamp boundaries. \\ \hline
\textit{Utterance} & Pydantic entity representing a continuous turn of speech attributed to a speaker. \\ \hline
\textit{ActionItem} & Structured representation of tasks extracted from conversation intelligence. \\ \hline
\textit{ConversationAnalysis} & Domain model containing executive summaries, decisions, and sentiment analytics. \\ \hline
\textit{TranscriptionResult} & Model aggregating transcript utterances and structured intelligence. \\ \hline
\textit{TranscriptionJobEntity} & Pure business domain representation of a transcription job process. \\ \hline
\path{app/domain/exceptions.py} & Domain exception hierarchy definitions module. \\ \hline
\textit{DomainError} & Base exception class for all custom domain errors. \\ \hline
\textit{AudioProcessingError} & Raised when FFmpeg audio normalization or VAD operations fail. \\ \hline
\textit{ModelInferenceError} & Raised when Whisper ASR or PyAnnote diarization pipelines encounter errors. \\ \hline
\textit{JobNotFoundError} & Raised when a requested job UUID is missing from the persistence database. \\ \hline
\textit{ExportGenerationError} & Raised when multi-format report output rendering fails. \\ \hline
\path{app/domain/protocols.py} & Structural typing duck-typing interface contracts module. \\ \hline
\path{app/repository/job\_repository.py} & Async database repository handling standard job CRUD operations. \\ \hline
\textit{JobRepository} & Encapsulates database queries for job entities. \\ \hline
\path{app/repository/hardened\_repository.py} & Advanced data repository enforcing optimistic concurrency locking. \\ \hline
\textit{HardenedJobRepository} & Prevents race conditions during concurrent transcript modifications. \\ \hline
\path{app/ml/audio\_processor.py} & FFmpeg async subprocess audio normalization engine module. \\ \hline
\textit{FFmpegAudioProcessor} & Converts audio to 16kHz mono PCM WAV format for processing pipelines. \\ \hline
\path{app/ml/inference\_engine.py} & Speech recognition and diarization alignment engine module. \\ \hline
\textit{InferenceEngine} & Manages Faster-Whisper, PyAnnote, and timestamp/speaker turn alignment. \\ \hline
\path{app/ml/llm\_processor.py} & LLM post-processing engine for structured intelligence extraction. \\ \hline
\textit{LLMIntelligenceEngine} & Extracts executive summaries, decisions, action items, and sentiment. \\ \hline
\path{app/ml/dynamic\_batcher.py} & High-throughput dynamic GPU batch aggregator module. \\ \hline
\textit{AsyncDynamicBatcher} & Aggregates individual inference requests over micro-windows for GPU processing. \\ \hline
\path{app/ml/drift\_detector.py} & Audio quality analysis and signal health diagnostics module. \\ \hline
\textit{AcousticDriftDetector} & Calculates Signal-to-Noise Ratio (SNR) and sample clipping ratios from audio streams. \\ \hline
\path{app/ml/speaker_biometrics.py} & PyAnnote voice embedding speaker identification engine module. \\ \hline
\textit{SpeakerBiometricsEngine} & Matches 512-dimensional voice vectors against enrolled profiles using cosine distance. \\ \hline
\path{app/ml/hotword\_engine.py} & Custom domain vocabulary injection and term correction engine. \\ \hline
\textit{HotwordEngine} & Injects hotwords into Whisper decoder prompts and applies fuzzy replacements. \\ \hline
\path{app/services/export\_service.py} & Multi-format document exporter service module. \\ \hline
\textit{ExportService} & Generates downloadable PDF, DOCX, SRT, VTT, and JSON output files. \\ \hline
\path{app/services/event\_bus.py} & Decoupled event pub-sub broker and webhook dispatching module. \\ \hline
\textit{EventBus} & Dispatches domain events and manages outbound webhooks with retries. \\ \hline
\textit{DeadLetterQueue} & Stores failed webhook payloads after retry exhaustion. \\ \hline
\path{app/services/translation\_service.py} & Real-time multi-lingual transcript translation service module. \\ \hline
\textit{TranslationService} & Translates transcribed speech turns into target foreign languages. \\ \hline
\path{app/workers/tasks.py} & Arq background worker task pipelines execution module. \\ \hline
\textit{process\_transcription\_job()} & Async worker pipeline handling ingestion, VAD, Whisper, Diarization, and LLM processing. \\ \hline
\path{app/api/middleware.py} & Rate limiter middleware and security headers setup module. \\ \hline
\textit{SecurityAndRateLimitMiddleware} & Enforces IP rate limiting via Redis token bucket with zero-redis bypass. \\ \hline
\path{app/api/v1/endpoints/transcription.py} & Core REST API routing endpoints for job lifecycle management. \\ \hline
\textit{upload\_audio\_file()} & Endpoint handling audio uploads and routing to Redis or Local task queues. \\ \hline
\textit{get\_job\_status()} & Endpoint returning real-time job processing status and transcript payloads. \\ \hline
\textit{cancel\_job()} & Endpoint signaling cancellation for pending or active processing jobs. \\ \hline
\textit{edit\_utterance()} & Endpoint enabling inline text edits with optimistic locking verification. \\ \hline
\textit{bulk\_rename\_speaker()} & Endpoint performing global speaker label renames across transcripts. \\ \hline
\textit{export\_transcript()} & Endpoint returning formatted downloadable document streams. \\ \hline
\path{app/api/v1/endpoints/live.py} & Real-time WebSocket audio streaming ingestion router module. \\ \hline
\textit{websocket\_live\_transcribe()} & Receives binary PCM audio chunks and emits real-time partial transcripts. \\ \hline
\path{app/api/v1/endpoints/events.py} & Server-Sent Events (SSE) progress streaming router module. \\ \hline
\textit{stream\_job\_progress()} & Streams real-time job state transitions and progress frames to clients. \\ \hline
\path{app/main.py} & FastAPI application bootstrap and lifespan management module. \\ \hline
\textit{lifespan()} & Context manager handling database connection setup and graceful shutdown. \\ \hline
\path{static/js/store.js} & Reactive state management store using JavaScript Proxy patterns. \\ \hline
\textit{Store} & Event-driven reactive Proxy store synchronizing UI component state. \\ \hline
\path{static/js/audio-worklet-processor.js} & In-browser audio downsampling AudioWorklet processor script. \\ \hline
\path{static/js/components/FileUploadDropzone.js} & Drag-and-drop file uploader Web Component. \\ \hline
\path{static/js/components/AudioWaveformVisualizer.js} & Canvas audio waveform scrubber and speaker turns Web Component. \\ \hline
\path{static/js/components/ExecutiveIntelligenceCard.js} & Executive summary, key decisions, and action items Web Component. \\ \hline
\path{static/js/components/TranscriptPlayer.js} & Interactive audio-transcript synchronization Web Component. \\ \hline
\path{static/js/components/LiveStreamTranscriber.js} & Real-time WebSocket live microphone streaming Web Component. \\ \hline
\path{static/js/components/SpeakerBiometricsManager.js} & Speaker voice enrollment and glossary management Web Component. \\ \hline
\path{run\_local.py} & Zero-dependency local development launcher script. \\ \hline
\textit{init\_local\_db()} & Auto-creates local SQLite database tables for zero-config execution. \\ \hline
\textit{main()} & Launcher entrypoint running local Uvicorn web server instance. \\ \hline
\end{longtable}
