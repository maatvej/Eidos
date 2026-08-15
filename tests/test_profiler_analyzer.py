# filename: tests/test_profiler_analyzer.py
"""Unit test suite for the Profiler Diagnostic Analyzer (app/core/profiler_analyzer.py)."""

import os
import pstats
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.profiler import ProfileContext
from app.core.profiler_analyzer import ProfileAnalyzer


@pytest.fixture
def sample_profile_file(tmp_path: Path) -> Path:
    """Generates a valid real .prof binary file for analyzer testing."""
    target_prof = tmp_path / "sample_test.prof"
    with ProfileContext(name="test_sample_analysis", subfolder="test", enabled=True) as prof:
        # Run some real operations
        _ = [x**2 for x in range(2000)]

    assert prof.result is not None
    return prof.result.prof_path


def test_load_stats(sample_profile_file: Path) -> None:
    """Validates stats loading and FileNotFoundError on invalid paths."""
    stats = ProfileAnalyzer.load_stats(sample_profile_file)
    assert isinstance(stats, pstats.Stats)
    assert hasattr(stats, "total_tt")

    # Non-existent file
    with pytest.raises(FileNotFoundError):
        ProfileAnalyzer.load_stats(sample_profile_file.parent / "non_existent.prof")


def test_find_latest_profile(tmp_path: Path) -> None:
    """Validates finding the latest .prof file in a directory."""
    # 1. Non-existent directory
    assert ProfileAnalyzer.find_latest_profile(tmp_path / "missing_dir") is None

    # 2. Empty directory
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    assert ProfileAnalyzer.find_latest_profile(empty_dir) is None

    # 3. Multiple files with different mtimes
    prof1 = empty_dir / "first.prof"
    prof2 = empty_dir / "second.prof"
    prof1.touch()
    prof2.touch()

    # Set prof2 mtime higher
    os.utime(str(prof1), (100, 100))
    os.utime(str(prof2), (200, 200))

    latest = ProfileAnalyzer.find_latest_profile(empty_dir)
    assert latest == prof2


def test_analyze_hotspots(sample_profile_file: Path) -> None:
    """Validates hotspot analysis returning FunctionStat list."""
    hotspots = ProfileAnalyzer.analyze_hotspots(sample_profile_file, limit=5)
    assert isinstance(hotspots, list)
    assert len(hotspots) <= 5


def test_diagnose_bottlenecks_and_rule_categorization(tmp_path: Path) -> None:
    """Validates diagnostic bottleneck analysis and rule-based diagnostic findings."""
    prof_path = tmp_path / "diagnostics.prof"

    # Create a profile with specific simulated workloads
    with ProfileContext(name="diagnostics_run", subfolder="diag", enabled=True) as prof:
        for _ in range(500):
            import re

            re.search(r"(\w+)", "sample string for regex analysis")

    assert prof.result is not None
    diag = ProfileAnalyzer.diagnose_bottlenecks(prof.result.prof_path)

    assert "profile_file" in diag
    assert diag["total_time_seconds"] >= 0.0
    assert diag["total_function_calls"] > 0
    assert len(diag["top_cumulative_hotspots"]) > 0
    assert len(diag["top_self_time_hotspots"]) > 0
    assert len(diag["diagnostic_findings"]) > 0

    # Test simulated ORM/ML findings via mock
    mock_stats = MagicMock()
    mock_stats.total_tt = 1.0
    mock_stats.total_calls = 50
    mock_stats.prim_calls = 40
    mock_stats.stats = {
        ("django/db/models/sql/compiler.py", 10, "execute_sql"): (10, 10, 0.1, 0.5, {}),
        ("faster_whisper/transcribe.py", 20, "transcribe"): (5, 5, 0.2, 0.7, {}),
        ("re.py", 30, "_compile"): (100, 100, 0.3, 0.35, {}),
    }

    with patch.object(ProfileAnalyzer, "load_stats", return_value=mock_stats):
        with patch.object(Path, "stat") as mock_stat:
            mock_stat.return_value.st_size = 1024
            sim_diag = ProfileAnalyzer.diagnose_bottlenecks(prof.result.prof_path)
            findings_text = " ".join(sim_diag["diagnostic_findings"])
            assert "High Database/ORM latency detected" in findings_text
            assert "ML / Torch compute dominates session" in findings_text
            assert "High Regex self-time detected" in findings_text


def test_compare_profiles(tmp_path: Path) -> None:
    """Validates delta comparison between baseline and candidate profiles."""
    with ProfileContext(name="base_run", subfolder="comp", enabled=True) as prof_base:
        _ = sum(i for i in range(10000))

    with ProfileContext(name="cand_run", subfolder="comp", enabled=True) as prof_cand:
        _ = sum(i for i in range(2000))

    assert prof_base.result is not None
    assert prof_cand.result is not None

    comp = ProfileAnalyzer.compare_profiles(prof_base.result.prof_path, prof_cand.result.prof_path)
    assert comp["base_total_time"] >= 0
    assert comp["candidate_total_time"] >= 0
    assert "speedup_factor" in comp
    assert "is_improved" in comp


def test_generate_markdown_report(sample_profile_file: Path) -> None:
    """Validates Markdown diagnostic report generation."""
    md = ProfileAnalyzer.generate_markdown_report(sample_profile_file)
    assert md.startswith("# Performance Diagnostic Report:")
    assert "## Summary Metrics" in md
    assert "## Top Cumulative Time Hotspots" in md
    assert "## Top Self-Time Hotspots" in md


def test_launch_snakeviz(sample_profile_file: Path) -> None:
    """Validates SnakeViz process launching and error handling."""
    # 1. Non-existent file raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        ProfileAnalyzer.launch_snakeviz(sample_profile_file.parent / "non_existent.prof")

    # 2. Mocked subprocess execution
    mock_proc = MagicMock()
    with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        proc = ProfileAnalyzer.launch_snakeviz(
            sample_profile_file, port=8080, browser=False, wait=True
        )
        assert proc == mock_proc
        mock_popen.assert_called_once()
        mock_proc.wait.assert_called_once()
        cmd_called = mock_popen.call_args[0][0]
        assert "--server-only" in cmd_called
        assert "--port" in cmd_called
        assert "8080" in cmd_called

    # 3. Subprocess failure handling
    with patch("subprocess.Popen", side_effect=OSError("SnakeViz execution failed")):
        proc_fail = ProfileAnalyzer.launch_snakeviz(sample_profile_file, port=8080)
        assert proc_fail is None
