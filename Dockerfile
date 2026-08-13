# filename: Dockerfile
# Multi-stage production container build with CUDA 12.1 runtime and FFmpeg support

FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04 AS base

# System dependencies setup
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3-pip \
    ffmpeg \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Setup Python alias
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

WORKDIR /app

# Stage 2: Dependencies Builder
FROM base AS builder
COPY pyproject.toml .
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel
RUN python -m pip install --no-cache-dir .

# Stage 3: Production Runtime Environment
FROM base AS runner

# Create non-root application execution user
RUN useradd -m -u 1001 appuser
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/dist-packages /usr/local/lib/python3.11/dist-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY app app
COPY static static
COPY alembic alembic
COPY alembic.ini .

# Set storage directory permissions
RUN mkdir -p /tmp/conversation_ai && chown -R appuser:appuser /tmp/conversation_ai /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"] 