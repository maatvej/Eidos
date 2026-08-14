# filename: Dockerfile
# Multi-stage production container build with CUDA 12.1 runtime, FFmpeg, and uv package manager

# Stage 1: Base CUDA 12.1 Runtime Environment
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04 AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# System dependencies setup
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    ffmpeg \
    libsndfile1 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Setup Python alias
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Install standalone uv binary from official Astral distribution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Stage 2: Dependencies Builder
FROM base AS builder

# Copy dependency manifests for optimal layer caching
COPY pyproject.toml uv.lock ./

# Install locked dependencies into standalone virtualenv (/app/.venv) without installing project root first
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copy application source code for editable/wheel project install
COPY app app
COPY README.md ./

# Complete project build and installation
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Stage 3: Production Runtime Environment
FROM base AS runner

# Create non-root application execution user
RUN useradd -m -u 1001 appuser
WORKDIR /app

# Copy isolated virtual environment and project artifacts
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser app app
COPY --chown=appuser:appuser static static
COPY --chown=appuser:appuser templates templates
COPY --chown=appuser:appuser django_static django_static
COPY --chown=appuser:appuser alembic alembic
COPY --chown=appuser:appuser alembic.ini manage.py run_local.py pyproject.toml ./

# Ensure storage directories exist with proper permissions for appuser
RUN mkdir -p /tmp/conversation_ai ./local_storage && \
    chown -R appuser:appuser /tmp/conversation_ai ./local_storage /app

# Expose virtual environment binaries on PATH
ENV PATH="/app/.venv/bin:$PATH"

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
