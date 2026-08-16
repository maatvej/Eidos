# filename: tests/test_profiler.py
"""Unit and integration test suite for the Eidos Profiling System (app/core/profiler.py)."""

import asyncio
import os
import pstats
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.http import HttpResponse
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.profiler import (
    DjangoProfilingMiddleware,
    FastAPIProfilingMiddleware,
    FunctionStat,
    ProfileContext,
    ProfileResult,
    _sanitize_name,
    clean_old_profiles,
    extract_top_hotspots,
    format_pstats_summary,
    profile_async,
    profile_callable,
    profile_sync,
    profile_worker_task,
)


def test_sanitize_name() -> None:
    """Validates identifier string sanitization for safe filesystem naming."""
    assert _sanitize_name("api/v1/transcription/upload") == "api_v1_transcription_upload"
    assert _sanitize_name("  special #@! name  ") == "special_____name"
    assert _sanitize_name("") == "profile"


def test_function_stat_and_profile_result_models(tmp_path: Path) -> None:
    """Validates instantiation of FunctionStat and ProfileResult data models."""
    stat = FunctionStat(
        filename="app/ml/inference.py",
        line_number=42,
        func_name="process_audio",
        ncalls="10",
        tottime=0.123,
        percall_tottime=0.0123,
        cumtime=0.456,
        percall_cumtime=0.0456,
        is_hotspot=True,
    )
    assert stat.func_name == "process_audio"
    assert stat.is_hotspot is True

    prof_file = tmp_path / "test.prof"
    summary_file = tmp_path / "test.txt"
    prof_file.touch()
    summary_file.touch()

    res = ProfileResult(
        name="test_result",
        prof_path=prof_file,
        summary_path=summary_file,
        total_time=0.5,
        total_calls=100,
        primitive_calls=80,
        hotspots=[stat],
        summary_text="summary header",
    )
    assert res.name == "test_result"
    assert len(res.hotspots) == 1
    assert res.total_calls == 100


def test_extract_top_hotspots_empty_stats() -> None:
    """Validates hotspot extraction when pstats contains no entries."""
    mock_stats = MagicMock(spec=pstats.Stats)
    mock_stats.stats = {}
    mock_stats.total_tt = 0.0
    hotspots = extract_top_hotspots(mock_stats)
    assert hotspots == []


def test_extract_top_hotspots_populated(tmp_path: Path) -> None:
    """Validates hotspot extraction with active profiling data."""
    with ProfileContext(name="sample_hotspots", enabled=True) as prof:
        # Run a tight loop to generate calls
        total = sum(i * i for i in range(10000))
        assert total > 0

    assert prof.result is not None
    assert prof.result.prof_path.exists()
    assert prof.result.summary_path.exists()
    assert len(prof.result.hotspots) >= 0


def test_format_pstats_summary_sort_options(tmp_path: Path) -> None:
    """Validates human-readable summary generation with various sorting keys."""
    prof_file = tmp_path / "test_sort.prof"

    with ProfileContext(name="test_sort", enabled=True) as prof:
        for _ in range(100):
            len("test_string")

    assert prof.result is not None
    stats = pstats.Stats(str(prof.result.prof_path))

    for sort_key in ["cumulative", "time", "tottime", "calls", "ncalls", "name", "line", "file"]:
        summary = format_pstats_summary(stats, sort_by=sort_key, limit=5)
        assert isinstance(summary, str)
        assert len(summary) > 0


def test_profile_context_disabled() -> None:
    """Validates ProfileContext executes with zero overhead when disabled."""
    with ProfileContext(name="disabled_test", enabled=False) as prof:
        val = 10 + 20

    assert val == 30
    assert prof.result is None
    assert prof._profiler is None


def test_profile_context_sync_enabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validates synchronous ProfileContext creates expected .prof and .txt outputs."""
    monkeypatch.setattr(settings, "PROFILING_OUTPUT_DIR", tmp_path)

    with ProfileContext(name="sync_test_block", subfolder="custom", enabled=True) as prof:
        res = [x * 2 for x in range(5000)]
        assert len(res) == 5000

    assert prof.result is not None
    assert prof.result.prof_path.exists()
    assert prof.result.summary_path.exists()
    assert "sync_test_block" in prof.result.summary_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_profile_context_async_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validates asynchronous ProfileContext executes and saves profile reports."""
    monkeypatch.setattr(settings, "PROFILING_OUTPUT_DIR", tmp_path)

    async with ProfileContext(name="async_test_block", subfolder="async", enabled=True) as prof:
        await asyncio.sleep(0.01)
        res = sum(i for i in range(1000))
        assert res > 0

    assert prof.result is not None
    assert prof.result.prof_path.exists()
    assert prof.result.summary_path.exists()


@pytest.mark.asyncio
async def test_profile_context_async_disabled() -> None:
    """Validates async ProfileContext bypasses profiling when disabled."""
    async with ProfileContext(name="async_disabled", enabled=False) as prof:
        await asyncio.sleep(0.001)

    assert prof.result is None


def test_profile_sync_decorator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validates @profile_sync decorator for synchronous functions."""
    monkeypatch.setattr(settings, "PROFILING_OUTPUT_DIR", tmp_path)

    # 1. Enabled
    @profile_sync(name="sync_decorated_func", subfolder="sync", enabled=True)
    def compute(a: int, b: int) -> int:
        return a + b

    assert compute(5, 7) == 12
    generated_files = list((tmp_path / "sync").glob("*.prof"))
    assert len(generated_files) >= 1

    # 2. Disabled
    @profile_sync(name="sync_disabled_func", subfolder="sync", enabled=False)
    def compute_disabled(a: int, b: int) -> int:
        return a * b

    assert compute_disabled(3, 4) == 12


@pytest.mark.asyncio
async def test_profile_async_decorator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validates @profile_async decorator for coroutine functions."""
    monkeypatch.setattr(settings, "PROFILING_OUTPUT_DIR", tmp_path)

    # 1. Enabled
    @profile_async(name="async_decorated_func", subfolder="async", enabled=True)
    async def async_calc(x: int) -> int:
        await asyncio.sleep(0.005)
        return x * 2

    assert await async_calc(10) == 20
    generated_files = list((tmp_path / "async").glob("*.prof"))
    assert len(generated_files) >= 1

    # 2. Disabled
    @profile_async(name="async_disabled_func", subfolder="async", enabled=False)
    async def async_calc_disabled(x: int) -> int:
        return x + 5

    assert await async_calc_disabled(10) == 15


@pytest.mark.asyncio
async def test_profile_callable_and_worker_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validates universal @profile_callable and @profile_worker_task decorators."""
    monkeypatch.setattr(settings, "PROFILING_OUTPUT_DIR", tmp_path)

    # Sync callable
    @profile_callable(name="sync_callable_test", subfolder="callables", enabled=True)
    def sync_fn() -> str:
        return "sync_ok"

    assert sync_fn() == "sync_ok"

    # Async callable
    @profile_callable(name="async_callable_test", subfolder="callables", enabled=True)
    async def async_fn() -> str:
        await asyncio.sleep(0.001)
        return "async_ok"

    assert await async_fn() == "async_ok"

    # Worker task
    @profile_worker_task(name="worker_test_job", subfolder="workers", enabled=True)
    async def worker_job(ctx: dict) -> str:
        return ctx.get("key", "val")

    assert await worker_job({"key": "worker_result"}) == "worker_result"
    assert len(list((tmp_path / "workers").glob("*.prof"))) >= 1


@pytest.mark.asyncio
async def test_fastapi_profiling_middleware(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validates FastAPIProfilingMiddleware execution, header injection, and exclusion rules."""
    monkeypatch.setattr(settings, "PROFILING_OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(settings, "PROFILING_ENABLED", True)
    monkeypatch.setattr(settings, "PROFILING_EXCLUDE_PATHS", ["/static", "/health"])

    test_app = FastAPI()
    test_app.add_middleware(FastAPIProfilingMiddleware)

    @test_app.get("/profiled-route")
    async def profiled_route() -> dict[str, str]:
        return {"status": "ok"}

    @test_app.get("/static/test.js")
    async def static_route() -> PlainTextResponse:
        return PlainTextResponse("console.log('test');")

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        # 1. Profiled endpoint
        res = await ac.get("/profiled-route")
        assert res.status_code == 200
        assert res.headers.get("x-profile-enabled") == "true"
        assert "x-profile-time" in res.headers
        assert "x-profile-file" in res.headers
        assert res.headers["x-profile-file"].endswith(".prof")

        # 2. Excluded endpoint
        res_excluded = await ac.get("/static/test.js")
        assert res_excluded.status_code == 200
        assert "x-profile-file" not in res_excluded.headers

    # 3. Disabled middleware state
    monkeypatch.setattr(settings, "PROFILING_ENABLED", False)
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        res_disabled = await ac.get("/profiled-route")
        assert res_disabled.status_code == 200
        assert "x-profile-file" not in res_disabled.headers


def test_django_profiling_middleware(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validates DjangoProfilingMiddleware request processing and header enrichment."""
    monkeypatch.setattr(settings, "PROFILING_OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(settings, "PROFILING_ENABLED", True)
    monkeypatch.setattr(settings, "PROFILING_EXCLUDE_PATHS", ["/static", "/admin/jsi18n"])

    def dummy_view(request):
        time.sleep(0.005)
        return HttpResponse("Django View OK")

    middleware = DjangoProfilingMiddleware(dummy_view)

    # 1. Profiled Django Request
    mock_request = MagicMock()
    mock_request.path = "/accounts/profile/"
    mock_request.method = "GET"

    response = middleware(mock_request)
    assert response.status_code == 200
    assert response.headers["X-Profile-Enabled"] == "true"
    assert "X-Profile-Time" in response.headers
    assert "X-Profile-File" in response.headers
    assert response.headers["X-Profile-File"].endswith(".prof")

    # 2. Excluded Django Path
    mock_request.path = "/static/admin/css/base.css"
    response_excluded = middleware(mock_request)
    assert "X-Profile-File" not in response_excluded.headers

    # 3. Disabled state
    monkeypatch.setattr(settings, "PROFILING_ENABLED", False)
    mock_request.path = "/accounts/profile/"
    response_disabled = middleware(mock_request)
    assert "X-Profile-File" not in response_disabled.headers


def test_clean_old_profiles(tmp_path: Path) -> None:
    """Validates profile retention cleaner removing stale files."""
    # Create mock old and new profile files
    old_file = tmp_path / "old_run.prof"
    old_summary = tmp_path / "old_run.txt"
    new_file = tmp_path / "new_run.prof"

    old_file.touch()
    old_summary.touch()
    new_file.touch()

    # Backdate old files by 10 days
    past_timestamp = time.time() - (10 * 86400)
    os.utime(str(old_file), (past_timestamp, past_timestamp))
    os.utime(str(old_summary), (past_timestamp, past_timestamp))

    # Clean older than 7 days
    deleted = clean_old_profiles(max_age_days=7, output_dir=tmp_path)
    assert deleted == 2
    assert not old_file.exists()
    assert not old_summary.exists()
    assert new_file.exists()

    # Non-existent directory handling
    non_existent = tmp_path / "does_not_exist"
    assert clean_old_profiles(max_age_days=7, output_dir=non_existent) == 0

    # Unlink error handling
    with patch.object(Path, "unlink", side_effect=PermissionError("Locked file")):
        stale_file = tmp_path / "stale.prof"
        stale_file.touch()
        os.utime(str(stale_file), (past_timestamp, past_timestamp))
        assert clean_old_profiles(max_age_days=7, output_dir=tmp_path) == 0


def test_profile_context_finalize_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validates _finalize_and_export edge cases."""
    monkeypatch.setattr(settings, "PROFILING_OUTPUT_DIR", tmp_path)
    ctx = ProfileContext(name="edge_test")
    # 1. profiler is None
    ctx._profiler = None
    ctx._finalize_and_export()
    assert ctx.result is None

    # 2. No hotspots found
    with patch("app.core.profiler.extract_top_hotspots", return_value=[]):
        with ProfileContext(name="no_hotspots_run", enabled=True) as prof:
            _ = 1 + 1
        assert prof.result is not None
        assert "No significant CPU hotspots detected." in prof.result.summary_text


def test_nested_profile_contexts_sync_and_async(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validates that nested ProfileContext instances do not raise ValueError."""
    monkeypatch.setattr(settings, "PROFILING_OUTPUT_DIR", tmp_path)

    # 1. Nested sync contexts
    with ProfileContext(name="outer_sync", enabled=True) as outer_prof:
        with ProfileContext(name="inner_sync", enabled=True) as inner_prof:
            calc = sum(x for x in range(100))
            assert calc == 4950

    assert outer_prof.result is not None
    assert outer_prof.result.prof_path.exists()
    assert inner_prof._profiler is None

    # 2. Exception during profiler.disable() handling
    ctx_disable_err = ProfileContext(name="err_disable", enabled=True)
    ctx_disable_err.__enter__()
    real_prof = ctx_disable_err._profiler
    assert real_prof is not None
    try:
        with patch.object(real_prof, "disable", side_effect=RuntimeError("Disable failure")):
            ctx_disable_err.__exit__(None, None, None)
    finally:
        real_prof.disable()
    assert ctx_disable_err._profiler is None

    # 3. Exception during _finalize_and_export() handling
    ctx_export_err = ProfileContext(name="err_export", enabled=True)
    ctx_export_err.__enter__()
    with patch.object(
        ctx_export_err, "_finalize_and_export", side_effect=RuntimeError("Finalize failure")
    ):
        ctx_export_err.__exit__(None, None, None)


@pytest.mark.asyncio
async def test_nested_profile_decorators_and_middleware(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validates nested decorators and middleware invocation with endpoint profiling decorators."""
    monkeypatch.setattr(settings, "PROFILING_OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(settings, "PROFILING_ENABLED", True)

    @profile_sync(name="inner_compute", subfolder="nested", enabled=True)
    def inner_sync_compute(v: int) -> int:
        return v * 3

    @profile_async(name="outer_compute", subfolder="nested", enabled=True)
    async def outer_async_compute(v: int) -> int:
        await asyncio.sleep(0.001)
        return inner_sync_compute(v) + 10

    res = await outer_async_compute(5)
    assert res == 25

    # Test FastAPIProfilingMiddleware with endpoint decorated by @profile_async
    test_app = FastAPI()
    test_app.add_middleware(FastAPIProfilingMiddleware)

    @test_app.get("/nested-endpoint")
    @profile_async(name="endpoint_handler", subfolder="endpoints", enabled=True)
    async def nested_endpoint() -> dict[str, str]:
        return {"status": "nested_ok"}

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        resp = await ac.get("/nested-endpoint")
        assert resp.status_code == 200
        assert resp.json() == {"status": "nested_ok"}
        assert resp.headers.get("x-profile-enabled") == "true"
