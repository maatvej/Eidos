# filename: tests/test_profiler_cli.py
"""Unit test suite for Profiler CLI Command-Line Utility (app/core/profiler_cli.py)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.core.profiler import ProfileContext
from app.core.profiler_cli import main


@pytest.fixture
def cli_sample_prof(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Creates a sample profile in test directory for CLI testing."""
    monkeypatch.setattr(settings, "PROFILING_OUTPUT_DIR", tmp_path)
    with ProfileContext(name="cli_test_session", subfolder="cli_test", enabled=True) as prof:
        _ = sum(i * 2 for i in range(1000))

    assert prof.result is not None
    return prof.result.prof_path


def test_cli_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Validates CLI --clean argument."""
    monkeypatch.setattr(settings, "PROFILING_OUTPUT_DIR", tmp_path)
    exit_code = main(["--clean", "5"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Cleaned" in captured.out


def test_cli_latest_and_path(
    cli_sample_prof: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validates CLI analysis with --latest and explicit --path flags."""
    monkeypatch.setattr(settings, "PROFILING_OUTPUT_DIR", cli_sample_prof.parent)

    # 1. Using --latest
    exit_code = main(["--latest"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "EIDOS PERFORMANCE PROFILE" in captured.out

    # 2. Using default fallback when profiles exist (no arguments)
    exit_code_default = main([])
    assert exit_code_default == 0
    captured_default = capsys.readouterr()
    assert "EIDOS PERFORMANCE PROFILE" in captured_default.out

    # 3. Using explicit --path
    exit_code_path = main(["--path", str(cli_sample_prof), "--sort", "time", "--limit", "10"])
    assert exit_code_path == 0
    captured_path = capsys.readouterr()
    assert "TOP 10 FUNCTIONS SORTED BY TIME" in captured_path.out


def test_cli_hotspots_only(cli_sample_prof: Path, capsys: pytest.CaptureFixture) -> None:
    """Validates CLI --hotspots-only flag."""
    exit_code = main(["--path", str(cli_sample_prof), "--hotspots-only"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "[TOP IDENTIFIED CPU HOTSPOTS]" in captured.out


def test_cli_json_and_markdown(cli_sample_prof: Path, capsys: pytest.CaptureFixture) -> None:
    """Validates CLI --json and --markdown output modes."""
    # JSON mode
    exit_code_json = main(["--path", str(cli_sample_prof), "--json"])
    assert exit_code_json == 0
    captured_json = capsys.readouterr()
    parsed_json = json.loads(captured_json.out)
    assert "profile_file" in parsed_json
    assert "total_time_seconds" in parsed_json

    # Markdown mode
    exit_code_md = main(["--path", str(cli_sample_prof), "--markdown"])
    assert exit_code_md == 0
    captured_md = capsys.readouterr()
    assert "# Performance Diagnostic Report:" in captured_md.out


def test_cli_compare(cli_sample_prof: Path, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Validates CLI --compare flag against baseline."""
    base_prof = tmp_path / "base.prof"
    with ProfileContext(name="base_session", subfolder="cli_test", enabled=True) as prof_base:
        _ = sum(i for i in range(5000))
    assert prof_base.result is not None

    # Text compare
    exit_code = main(["--path", str(cli_sample_prof), "--compare", str(prof_base.result.prof_path)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "EIDOS PROFILE COMPARISON" in captured.out
    assert "Speedup:" in captured.out

    # JSON compare
    exit_code_json = main(
        ["--path", str(cli_sample_prof), "--compare", str(prof_base.result.prof_path), "--json"]
    )
    assert exit_code_json == 0
    captured_json = capsys.readouterr()
    parsed_comp = json.loads(captured_json.out)
    assert "speedup_factor" in parsed_comp


def test_cli_snakeviz(cli_sample_prof: Path) -> None:
    """Validates CLI --snakeviz flag."""
    with patch("app.core.profiler_analyzer.ProfileAnalyzer.launch_snakeviz") as mock_launch:
        exit_code = main(["--path", str(cli_sample_prof), "--snakeviz", "--port", "8888"])
        assert exit_code == 0
        mock_launch.assert_called_once_with(cli_sample_prof, port=8888, browser=True, wait=True)


def test_cli_error_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Validates CLI error branches and exit codes."""
    # 1. No files found in directory for --latest
    monkeypatch.setattr(settings, "PROFILING_OUTPUT_DIR", tmp_path / "empty_dir")
    assert main(["--latest"]) == 1

    # 2. Non-existent target file
    assert main(["--path", str(tmp_path / "missing.prof")]) == 1

    # 3. Non-existent compare baseline file
    existing_prof = tmp_path / "exist.prof"
    existing_prof.touch()
    assert (
        main(["--path", str(existing_prof), "--compare", str(tmp_path / "missing_base.prof")]) == 1
    )

    # 4. No arguments and no latest profile
    assert main([]) == 1


def test_cli_main_execution(cli_sample_prof: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validates executing the CLI module as __main__."""
    import runpy
    import sys

    monkeypatch.setattr(sys, "argv", ["profiler_cli.py", "--path", str(cli_sample_prof), "--json"])
    monkeypatch.delitem(sys.modules, "app.core.profiler_cli", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("app.core.profiler_cli", run_name="__main__", alter_sys=True)
    assert exc_info.value.code == 0
