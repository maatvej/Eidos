# filename: app/core/profiler.py
"""Comprehensive cProfile and pstats profiling engine for hybrid FastAPI & Django architecture.

Provides context managers, synchronous and asynchronous function decorators,
FastAPI & Django middleware, structured `.prof` binary exporter, human-readable
performance summaries, and CPU hotspot detector with zero runtime overhead when disabled.
"""

import asyncio
import cProfile
import io
import pstats
import re
import time
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from typing import Any, ParamSpec, TypeVar
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import settings
from app.core.logging import logger


P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class FunctionStat:
    """Represents statistical execution metrics for an individual function call.

    Attributes:
        filename: Path or identifier of the source file.
        line_number: Line number where the function is defined.
        func_name: Name of the function or method.
        ncalls: Call count string (e.g., '100' or '100/50' for recursive invocations).
        tottime: Total time spent in the function itself excluding subcalls (seconds).
        percall_tottime: Average time spent in function per call (tottime / primitive calls).
        cumtime: Cumulative time spent in function and all subcalls (seconds).
        percall_cumtime: Average cumulative time per call (cumtime / total calls).
        is_hotspot: Flag indicating whether this function is classified as a CPU hotspot.
    """

    filename: str
    line_number: int
    func_name: str
    ncalls: str
    tottime: float
    percall_tottime: float
    cumtime: float
    percall_cumtime: float
    is_hotspot: bool = False


@dataclass
class ProfileResult:
    """Result container holding metadata and paths for an executed profile session.

    Attributes:
        name: Logical name or identifier of the profiling target.
        prof_path: Filesystem path to the structured binary `.prof` file.
        summary_path: Filesystem path to the formatted text summary file.
        total_time: Total elapsed wall-clock time for the profiled block (seconds).
        total_calls: Total number of function calls recorded.
        primitive_calls: Number of non-recursive function calls.
        hotspots: List of top underperforming functions and CPU hotspots.
        summary_text: Human-readable pstats formatted string.
    """

    name: str
    prof_path: Path
    summary_path: Path
    total_time: float
    total_calls: int
    primitive_calls: int
    hotspots: list[FunctionStat] = field(default_factory=list)
    summary_text: str = ""


def _sanitize_name(name: str) -> str:
    """Sanitizes an arbitrary identifier into a filesystem-safe string.

    Args:
        name: Raw identifier string.

    Returns:
        Cleaned, filesystem-safe string.

    Example:
        >>> _sanitize_name("api/v1/transcription/upload")
        'api_v1_transcription_upload'
    """
    clean = re.sub(r"[^\w\-.]", "_", name.strip())
    return clean.strip("_") or "profile"


def extract_top_hotspots(
    stats: pstats.Stats,
    limit: int = 10,
    cumtime_threshold_ratio: float = 0.05,
) -> list[FunctionStat]:
    """Extracts top underperforming functions and CPU hotspots from a pstats.Stats object.

    Args:
        stats: Populated pstats.Stats instance.
        limit: Maximum number of hotspot functions to return.
        cumtime_threshold_ratio: Minimum ratio of function cumulative time relative
            to total session time required to qualify as a hotspot.

    Returns:
        List of FunctionStat objects representing identified hotspots.

    Example:
        >>> hotspots = extract_top_hotspots(stats, limit=5)
    """
    hotspots: list[FunctionStat] = []
    total_session_time = getattr(stats, "total_tt", 0.0) or 0.0001

    raw_stats = getattr(stats, "stats", {})
    if not raw_stats:
        return hotspots

    # Sort entries by cumulative time descending
    sorted_entries = sorted(
        raw_stats.items(),
        key=lambda item: item[1][3],  # item[1][3] is cumtime
        reverse=True,
    )

    for (file_path, line_no, func_name), (cc, nc, tt, ct, _) in sorted_entries[:limit]:
        # cc: primitive calls, nc: total calls, tt: total self time, ct: cumulative time
        ncalls_str = str(nc) if cc == nc else f"{nc}/{cc}"
        percall_tt = tt / cc if cc > 0 else 0.0
        percall_ct = ct / nc if nc > 0 else 0.0

        # Mark as hotspot if cumulative time represents a significant ratio or high self time
        is_hot = (ct / total_session_time >= cumtime_threshold_ratio) or (
            tt / total_session_time >= cumtime_threshold_ratio / 2
        )

        hotspots.append(
            FunctionStat(
                filename=str(file_path),
                line_number=int(line_no),
                func_name=str(func_name),
                ncalls=ncalls_str,
                tottime=round(tt, 6),
                percall_tottime=round(percall_tt, 6),
                cumtime=round(ct, 6),
                percall_cumtime=round(percall_ct, 6),
                is_hotspot=is_hot,
            )
        )

    return hotspots


def format_pstats_summary(
    stats: pstats.Stats,
    sort_by: str = "cumulative",
    limit: int = 30,
) -> str:
    """Formats a human-readable performance summary string from a pstats.Stats instance.

    Args:
        stats: Populated pstats.Stats object.
        sort_by: Sorting criterion ('cumulative', 'time', 'calls', 'ncalls', 'name').
        limit: Number of top functions to include in the output table.

    Returns:
        Formatted summary text containing header and top function table.

    Example:
        >>> summary = format_pstats_summary(stats, sort_by="time", limit=20)
    """
    stream = io.StringIO()
    # Temporarily redirect output stream
    orig_stream = stats.stream
    stats.stream = stream
    stats.strip_dirs()

    valid_sorts = {
        "cumulative": pstats.SortKey.CUMULATIVE,
        "time": pstats.SortKey.TIME,
        "tottime": pstats.SortKey.TIME,
        "calls": pstats.SortKey.CALLS,
        "ncalls": pstats.SortKey.CALLS,
        "name": pstats.SortKey.NAME,
        "line": pstats.SortKey.LINE,
        "file": pstats.SortKey.FILENAME,
    }
    sort_key = valid_sorts.get(sort_by.lower(), pstats.SortKey.CUMULATIVE)
    stats.sort_stats(sort_key)
    stats.print_stats(limit)

    output = stream.getvalue()
    stats.stream = orig_stream
    return output


class ProfileContext(
    AbstractContextManager["ProfileContext"], AbstractAsyncContextManager["ProfileContext"]
):
    """Dual synchronous and asynchronous context manager for cProfile sessions.

    Captures call count, total time, per-call time, and cumulative time.
    Exports structured binary `.prof` files and human-readable `.txt` performance summaries.
    Executes with zero runtime overhead when profiling is disabled.

    Attributes:
        name: Logical name for the profiling block.
        subfolder: Subdirectory name inside `settings.PROFILING_OUTPUT_DIR`.
        sort_by: Default sort key for the performance summary.
        limit: Number of functions in the text summary.
        enabled: Explicit override for profiling activation (defaults to `settings.PROFILING_ENABLED`).
        result: ProfileResult instance populated on block exit.
    """

    def __init__(
        self,
        name: str = "profile_block",
        subfolder: str = "",
        sort_by: str | None = None,
        limit: int | None = None,
        enabled: bool | None = None,
    ) -> None:
        """Initializes the ProfileContext instance.

        Args:
            name: Label identifying the profiled code section.
            subfolder: Optional subfolder inside the profiles directory.
            sort_by: Sort order for text summaries (e.g., 'cumulative', 'time').
            limit: Maximum functions listed in human-readable summary.
            enabled: Optional boolean toggle overriding `settings.PROFILING_ENABLED`.
        """
        self.name = _sanitize_name(name)
        self.subfolder = subfolder
        self.sort_by = sort_by or settings.PROFILING_SORT_BY
        self.limit = limit if limit is not None else settings.PROFILING_RESTRICTION_LIMIT
        self.enabled = settings.PROFILING_ENABLED if enabled is None else enabled

        self._profiler: cProfile.Profile | None = None
        self._start_time: float = 0.0
        self._elapsed_time: float = 0.0
        self.result: ProfileResult | None = None

    def __enter__(self) -> "ProfileContext":
        """Enters the synchronous profiling context.

        Returns:
            The active ProfileContext instance.
        """
        if not self.enabled:
            return self

        self._start_time = time.perf_counter()
        self._profiler = cProfile.Profile()
        self._profiler.enable()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exits the synchronous profiling context and saves outputs."""
        if not self.enabled or self._profiler is None:
            return

        self._profiler.disable()
        self._elapsed_time = time.perf_counter() - self._start_time
        self._finalize_and_export()

    async def __aenter__(self) -> "ProfileContext":
        """Enters the asynchronous profiling context.

        Returns:
            The active ProfileContext instance.
        """
        return self.__enter__()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exits the asynchronous profiling context and saves outputs."""
        self.__exit__(exc_type, exc_val, exc_tb)

    def _finalize_and_export(self) -> None:
        """Processes collected profiling stats, creates files, and populates `result`."""
        if self._profiler is None:
            return

        # Prepare target directories
        base_dir = settings.PROFILING_OUTPUT_DIR
        target_dir = base_dir / self.subfolder if self.subfolder else base_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        timestamp_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        unique_token = uuid4().hex[:6]
        file_prefix = f"{timestamp_str}_{self.name}_{unique_token}"

        prof_path = target_dir / f"{file_prefix}.prof"
        summary_path = target_dir / f"{file_prefix}.txt"

        # 1. Export structured .prof binary file
        self._profiler.dump_stats(str(prof_path))

        # 2. Extract stats and generate human-readable summary
        stream = io.StringIO()
        stats = pstats.Stats(self._profiler, stream=stream)

        summary_body = format_pstats_summary(stats, sort_by=self.sort_by, limit=self.limit)
        hotspots = extract_top_hotspots(stats, limit=10)

        # 3. Build comprehensive human-readable report header
        header_lines = [
            "=" * 80,
            f"EIDOS PERFORMANCE PROFILE REPORT: {self.name}",
            f"Timestamp (UTC): {datetime.now(UTC).isoformat()}",
            f"Elapsed Wall Time: {self._elapsed_time:.6f}s",
            f"Total Profiler Time: {getattr(stats, 'total_tt', 0.0):.6f}s",
            f"Total Function Calls: {getattr(stats, 'total_calls', 0)} ({getattr(stats, 'prim_calls', 0)} primitive)",
            f"Binary Profile: {prof_path.name}",
            "=" * 80,
            "\n[TOP IDENTIFIED CPU HOTSPOTS & BOTTLENECKS]",
        ]

        if hotspots:
            header_lines.append(
                f"{'NCALLS':<12} {'TOTTIME (s)':<14} {'PERCALL (s)':<14} {'CUMTIME (s)':<14} {'FUNCTION':<30}"
            )
            header_lines.append("-" * 88)
            for h in hotspots:
                loc = f"{Path(h.filename).name}:{h.line_number}({h.func_name})"
                flag = " [!] HOTSPOT" if h.is_hotspot else ""
                header_lines.append(
                    f"{h.ncalls:<12} {h.tottime:<14.6f} {h.percall_tottime:<14.6f} {h.cumtime:<14.6f} {loc:<30}{flag}"
                )
        else:
            header_lines.append("No significant CPU hotspots detected.")

        header_lines.extend(["\n[DETAILED PSTATS STATISTICAL BREAKDOWN]", summary_body])
        full_summary_text = "\n".join(header_lines)

        # Write formatted summary file to disk
        summary_path.write_text(full_summary_text, encoding="utf-8")

        self.result = ProfileResult(
            name=self.name,
            prof_path=prof_path,
            summary_path=summary_path,
            total_time=self._elapsed_time,
            total_calls=getattr(stats, "total_calls", 0),
            primitive_calls=getattr(stats, "prim_calls", 0),
            hotspots=hotspots,
            summary_text=full_summary_text,
        )

        logger.debug(
            f"Profile recorded for '{self.name}': {self._elapsed_time:.4f}s elapsed, "
            f"saved to {prof_path.name}"
        )


def profile_async(
    name: str | None = None,
    subfolder: str = "async_functions",
    sort_by: str | None = None,
    limit: int | None = None,
    enabled: bool | None = None,
) -> Callable[[Callable[P, Any]], Callable[P, Any]]:
    """Decorator to profile asynchronous coroutine functions.

    Args:
        name: Logical name for the profile session (defaults to function name).
        subfolder: Subdirectory inside `PROFILING_OUTPUT_DIR`.
        sort_by: Sorting criterion for pstats.
        limit: Max functions in summary text.
        enabled: Optional explicit boolean enable toggle.

    Returns:
        Decorated asynchronous function.

    Example:
        >>> @profile_async(name="audio_inference")
        >>> async def run_model(audio_path: Path) -> dict: ...
    """

    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        target_name = name or func.__qualname__

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            is_active = settings.PROFILING_ENABLED if enabled is None else enabled
            # Guard clause: zero overhead when disabled
            if not is_active:
                return await func(*args, **kwargs)

            async with ProfileContext(
                name=target_name,
                subfolder=subfolder,
                sort_by=sort_by,
                limit=limit,
                enabled=True,
            ):
                return await func(*args, **kwargs)

        return wrapper

    return decorator


def profile_sync(
    name: str | None = None,
    subfolder: str = "sync_functions",
    sort_by: str | None = None,
    limit: int | None = None,
    enabled: bool | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to profile synchronous functions and methods.

    Args:
        name: Logical name for the profile session (defaults to function name).
        subfolder: Subdirectory inside `PROFILING_OUTPUT_DIR`.
        sort_by: Sorting criterion for pstats.
        limit: Max functions in summary text.
        enabled: Optional explicit boolean enable toggle.

    Returns:
        Decorated synchronous function.

    Example:
        >>> @profile_sync(name="audio_chunking")
        >>> def chunk_audio(data: bytes) -> list[bytes]: ...
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        target_name = name or func.__qualname__

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            is_active = settings.PROFILING_ENABLED if enabled is None else enabled
            # Guard clause: zero overhead when disabled
            if not is_active:
                return func(*args, **kwargs)

            with ProfileContext(
                name=target_name,
                subfolder=subfolder,
                sort_by=sort_by,
                limit=limit,
                enabled=True,
            ):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def profile_callable(
    name: str | None = None,
    subfolder: str = "callables",
    sort_by: str | None = None,
    limit: int | None = None,
    enabled: bool | None = None,
) -> Callable[[Callable[P, Any]], Callable[P, Any]]:
    """Universal decorator supporting both synchronous and asynchronous callables.

    Args:
        name: Identifier for the profile output.
        subfolder: Subfolder in profiles storage.
        sort_by: Sort mode ('cumulative', 'time', etc.).
        limit: Max functions in text summary.
        enabled: Optional override for activation.

    Returns:
        Decorated callable.

    Example:
        >>> @profile_callable(name="dynamic_step")
        >>> async def step(): ...
    """

    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        if asyncio.iscoroutinefunction(func):
            return profile_async(
                name=name,
                subfolder=subfolder,
                sort_by=sort_by,
                limit=limit,
                enabled=enabled,
            )(func)
        return profile_sync(
            name=name,
            subfolder=subfolder,
            sort_by=sort_by,
            limit=limit,
            enabled=enabled,
        )(func)

    return decorator


def profile_worker_task(
    name: str | None = None,
    subfolder: str = "workers",
    sort_by: str | None = None,
    limit: int | None = None,
    enabled: bool | None = None,
) -> Callable[[Callable[P, Any]], Callable[P, Any]]:
    """Specialized decorator for background workers and Arq asynchronous tasks.

    Args:
        name: Identifier for the worker task profile.
        subfolder: Target subfolder for worker profiles (defaults to 'workers').
        sort_by: Pstats sorting column.
        limit: Summary function count limit.
        enabled: Optional profiling toggle override.

    Returns:
        Decorated worker coroutine function.

    Example:
        >>> @profile_worker_task(name="transcription_worker_pipeline")
        >>> async def process_job(ctx: dict, job_id: str): ...
    """
    return profile_async(
        name=name,
        subfolder=subfolder,
        sort_by=sort_by,
        limit=limit,
        enabled=enabled,
    )


# ---------------------------------------------------------------------------
# FastAPI & Django Profiling Middleware
# ---------------------------------------------------------------------------


class FastAPIProfilingMiddleware(BaseHTTPMiddleware):
    """FastAPI & Starlette middleware profiling HTTP requests.

    Captures call count, total execution time, and cumulative time per endpoint.
    Saves `.prof` and `.txt` files in `profiles/fastapi/` and injects performance headers.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Intercepts HTTP requests, profiles execution, and enriches headers.

        Args:
            request: The incoming FastAPI HTTP request.
            call_next: The next request handler callable.

        Returns:
            The HTTP response with injected profiling performance headers.
        """
        if not settings.PROFILING_ENABLED:
            return await call_next(request)

        path: str = request.url.path
        # Guard clause: bypass excluded paths
        if any(path.startswith(prefix) for prefix in settings.PROFILING_EXCLUDE_PATHS):
            return await call_next(request)

        method: str = request.method
        route_label = f"fastapi_{method}_{path.replace('/', '_')}"

        context = ProfileContext(
            name=route_label,
            subfolder="fastapi",
            sort_by=settings.PROFILING_SORT_BY,
            limit=settings.PROFILING_RESTRICTION_LIMIT,
            enabled=True,
        )

        with context:
            response = await call_next(request)

        if context.result:
            response.headers["X-Profile-Enabled"] = "true"
            response.headers["X-Profile-Time"] = f"{context.result.total_time:.4f}s"
            response.headers["X-Profile-File"] = context.result.prof_path.name

        return response


class DjangoProfilingMiddleware:
    """Standard Django middleware profiling views, Allauth handlers, and ORM executions.

    Captures Django request-response cycle and outputs profile artifacts in `profiles/django/`.
    """

    def __init__(self, get_response: Callable) -> None:
        """Initializes Django middleware.

        Args:
            get_response: Django response-producing callable.
        """
        self.get_response = get_response

    def __call__(self, request: Any) -> Any:
        """Executes Django request processing within profiling boundary.

        Args:
            request: Django HttpRequest instance.

        Returns:
            Django HttpResponse instance.
        """
        if not settings.PROFILING_ENABLED:
            return self.get_response(request)

        path: str = getattr(request, "path", "")
        # Guard clause: bypass excluded paths
        if any(path.startswith(prefix) for prefix in settings.PROFILING_EXCLUDE_PATHS):
            return self.get_response(request)

        method: str = getattr(request, "method", "GET")
        route_label = f"django_{method}_{path.replace('/', '_')}"

        context = ProfileContext(
            name=route_label,
            subfolder="django",
            sort_by=settings.PROFILING_SORT_BY,
            limit=settings.PROFILING_RESTRICTION_LIMIT,
            enabled=True,
        )

        with context:
            response = self.get_response(request)

        if context.result and hasattr(response, "headers"):
            response.headers["X-Profile-Enabled"] = "true"
            response.headers["X-Profile-Time"] = f"{context.result.total_time:.4f}s"
            response.headers["X-Profile-File"] = context.result.prof_path.name

        return response


def clean_old_profiles(max_age_days: int = 7, output_dir: Path | None = None) -> int:
    """Removes profile artifacts older than the specified retention duration.

    Args:
        max_age_days: Number of days to retain profile files.
        output_dir: Root directory containing profiles (defaults to `settings.PROFILING_OUTPUT_DIR`).

    Returns:
        Count of deleted files.

    Example:
        >>> deleted = clean_old_profiles(max_age_days=3)
    """
    target_dir = output_dir or settings.PROFILING_OUTPUT_DIR
    if not target_dir.exists():
        return 0

    cutoff_timestamp = time.time() - (max_age_days * 86400)
    removed_count = 0

    for file_path in target_dir.rglob("*"):
        if (
            file_path.is_file()
            and file_path.suffix in (".prof", ".txt", ".json")
            and file_path.stat().st_mtime < cutoff_timestamp
        ):
            try:
                file_path.unlink()
                removed_count += 1
            except Exception as err:
                logger.debug(f"Failed to remove stale profile {file_path}: {err}")

    return removed_count
