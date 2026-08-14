# filename: app/core/metrics.py
"""Prometheus metrics registry for enterprise observability."""

from prometheus_client import Counter, Gauge, Histogram


INFERENCE_LATENCY = Histogram(
    "ml_inference_latency_seconds",
    "Latency of ML inference steps in seconds",
    ["step"],
    buckets=[0.5, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)

ACTIVE_JOBS = Gauge(
    "transcription_active_jobs",
    "Current active transcription jobs by status",
    ["status"],
)

PROCESSED_AUDIO_SECONDS = Counter(
    "processed_audio_seconds_total", "Total seconds of audio processed successfully"
)

QUEUE_DEPTH = Gauge("transcription_queue_depth", "Number of pending jobs in Redis queue")
