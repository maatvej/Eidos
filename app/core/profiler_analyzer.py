# filename: app/core/profiler_analyzer.py
"""Diagnostic utility and statistical analyzer for Python cProfile artifacts.

Extracts CPU bottlenecks, analyzes call hierarchies, computes performance regressions,
generates Markdown/JSON diagnostic reports, and integrates with SnakeViz for interactive visualization.
"""

import io
import pstats
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import logger
from app.core.profiler import FunctionStat, extract_top_hotspots


class ProfileAnalyzer:
    """Diagnostic engine for parsing, analyzing, and visualizing cProfile .prof dumps."""

    @staticmethod
    def load_stats(prof_path: Path | str) -> pstats.Stats:
        """Loads and returns a pstats.Stats object from a .prof binary file.

        Args:
            prof_path: Path to the .prof file.

        Returns:
            Configured pstats.Stats instance.

        Raises:
            FileNotFoundError: If the specified .prof file does not exist.

        Example:
            >>> stats = ProfileAnalyzer.load_stats("profiles/fastapi/upload.prof")
        """
        path = Path(prof_path)
        if not path.is_file():
            raise FileNotFoundError(f"Profile binary file not found: {path}")

        stream = io.StringIO()
        return pstats.Stats(str(path), stream=stream)

    @classmethod
    def find_latest_profile(
        cls,
        directory: Path | str | None = None,
        pattern: str = "*.prof",
    ) -> Path | None:
        """Locates the most recently generated .prof file in the profile directory.

        Args:
            directory: Directory to search (defaults to `settings.PROFILING_OUTPUT_DIR`).
            pattern: Glob pattern to match files.

        Returns:
            Path to the latest .prof file, or None if no files are found.

        Example:
            >>> latest = ProfileAnalyzer.find_latest_profile()
        """
        target_dir = Path(directory) if directory else settings.PROFILING_OUTPUT_DIR
        if not target_dir.exists():
            return None

        matching_files = list(target_dir.rglob(pattern))
        if not matching_files:
            return None

        matching_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return matching_files[0]

    @classmethod
    def analyze_hotspots(
        cls,
        prof_path: Path | str,
        limit: int = 10,
        sort_by: str = "cumulative",
    ) -> list[FunctionStat]:
        """Extracts prioritized CPU hotspots from a profile artifact.

        Args:
            prof_path: Path to the target .prof file.
            limit: Maximum count of hotspot functions.
            sort_by: Sorting criterion ('cumulative', 'time', 'calls').

        Returns:
            List of FunctionStat entries flagged as hotspots.

        Example:
            >>> hotspots = ProfileAnalyzer.analyze_hotspots("profiles/my_run.prof", limit=5)
        """
        stats = cls.load_stats(prof_path)
        return extract_top_hotspots(stats, limit=limit)

    @classmethod
    def diagnose_bottlenecks(cls, prof_path: Path | str) -> dict[str, Any]:
        """Performs deep diagnostic inspection on a profile file to highlight bottlenecks.

        Args:
            prof_path: Path to the .prof file.

        Returns:
            Dictionary containing structured performance metrics, top self-time hotspots,
            top cumulative-time hotspots, and diagnostic findings.

        Example:
            >>> report = ProfileAnalyzer.diagnose_bottlenecks("profiles/worker.prof")
        """
        path = Path(prof_path)
        stats = cls.load_stats(path)

        total_time = float(getattr(stats, "total_tt", 0.0))
        total_calls = int(getattr(stats, "total_calls", 0))
        prim_calls = int(getattr(stats, "prim_calls", 0))

        raw_stats = getattr(stats, "stats", {})

        # 1. Top Cumulative Time Functions (overall latency contributors)
        sorted_by_cum = sorted(
            raw_stats.items(),
            key=lambda item: item[1][3],
            reverse=True,
        )[:10]

        top_cum = [
            {
                "function": f"{Path(fpath).name}:{lno}({fname})",
                "full_path": f"{fpath}:{lno}",
                "func_name": fname,
                "ncalls": nc,
                "tottime": round(tt, 6),
                "cumtime": round(ct, 6),
                "percent_of_total": round((ct / total_time * 100) if total_time > 0 else 0.0, 2),
            }
            for (fpath, lno, fname), (_cc, nc, tt, ct, _) in sorted_by_cum
        ]

        # 2. Top Self-Time Functions (pure CPU hogs)
        sorted_by_self = sorted(
            raw_stats.items(),
            key=lambda item: item[1][2],
            reverse=True,
        )[:10]

        top_self = [
            {
                "function": f"{Path(fpath).name}:{lno}({fname})",
                "full_path": f"{fpath}:{lno}",
                "func_name": fname,
                "ncalls": nc,
                "tottime": round(tt, 6),
                "cumtime": round(ct, 6),
                "percent_of_total": round((tt / total_time * 100) if total_time > 0 else 0.0, 2),
            }
            for (fpath, lno, fname), (_cc, nc, tt, ct, _) in sorted_by_self
        ]

        # 3. Rule-based Diagnostic Categorization
        diagnostics = cls._evaluate_diagnostic_rules(raw_stats, total_time)

        return {
            "profile_file": str(path),
            "file_size_bytes": path.stat().st_size,
            "total_time_seconds": round(total_time, 6),
            "total_function_calls": total_calls,
            "primitive_calls": prim_calls,
            "top_cumulative_hotspots": top_cum,
            "top_self_time_hotspots": top_self,
            "diagnostic_findings": diagnostics,
        }

    @classmethod
    def _evaluate_diagnostic_rules(
        cls,
        raw_stats: dict[tuple[str, int, str], tuple[int, int, float, float, dict]],
        total_time: float,
    ) -> list[str]:
        """Evaluates heuristic bottleneck rules against recorded stats."""
        diagnostics: list[str] = []
        orm_time = 0.0
        ml_inference_time = 0.0
        regex_time = 0.0

        for (fpath, _, _), (_, _, tt, ct, _) in raw_stats.items():
            fpath_lower = fpath.lower()
            if (
                "django/db" in fpath_lower
                or "sqlalchemy" in fpath_lower
                or "aiosqlite" in fpath_lower
            ):
                orm_time += ct
            if "whisper" in fpath_lower or "pyannote" in fpath_lower or "torch" in fpath_lower:
                ml_inference_time += ct
            if "re.py" in fpath_lower or "sre_compile" in fpath_lower:
                regex_time += tt

        if total_time > 0:
            if (orm_time / total_time) > 0.4:
                diagnostics.append(
                    f"High Database/ORM latency detected: ~{orm_time:.3f}s cumulative "
                    f"({(orm_time / total_time) * 100:.1f}% of total session time). Check for N+1 queries."
                )
            if (ml_inference_time / total_time) > 0.6:
                diagnostics.append(
                    f"ML / Torch compute dominates session: ~{ml_inference_time:.3f}s cumulative. "
                    "Ensure GPU acceleration or optimal thread count is enabled."
                )
            if (regex_time / total_time) > 0.15:
                diagnostics.append(
                    f"High Regex self-time detected: ~{regex_time:.3f}s self-time. "
                    "Consider precompiling regex patterns."
                )

        if not diagnostics:
            diagnostics.append("Execution profile exhibits balanced resource distribution.")

        return diagnostics

    @classmethod
    def compare_profiles(
        cls,
        base_path: Path | str,
        candidate_path: Path | str,
    ) -> dict[str, Any]:
        """Compares two profile artifacts to calculate speedup and detect regressions.

        Args:
            base_path: Path to baseline .prof file.
            candidate_path: Path to candidate/optimized .prof file.

        Returns:
            Dictionary detailing total execution deltas and function-level comparisons.

        Example:
            >>> comparison = ProfileAnalyzer.compare_profiles("base.prof", "new.prof")
        """
        base_stats = cls.load_stats(base_path)
        cand_stats = cls.load_stats(candidate_path)

        base_tt = float(getattr(base_stats, "total_tt", 0.0))
        cand_tt = float(getattr(cand_stats, "total_tt", 0.0))

        speedup_factor = (base_tt / cand_tt) if cand_tt > 0 else 1.0
        time_diff = cand_tt - base_tt
        percent_change = ((cand_tt - base_tt) / base_tt * 100) if base_tt > 0 else 0.0

        return {
            "base_profile": str(base_path),
            "candidate_profile": str(candidate_path),
            "base_total_time": round(base_tt, 6),
            "candidate_total_time": round(cand_tt, 6),
            "time_difference_seconds": round(time_diff, 6),
            "percent_change": round(percent_change, 2),
            "speedup_factor": round(speedup_factor, 2),
            "is_improved": cand_tt < base_tt,
        }

    @classmethod
    def generate_markdown_report(cls, prof_path: Path | str) -> str:
        """Generates a structured Markdown diagnostic summary report.

        Args:
            prof_path: Path to the .prof file.

        Returns:
            Markdown-formatted report string.
        """
        diag = cls.diagnose_bottlenecks(prof_path)

        md = [
            f"# Performance Diagnostic Report: `{Path(diag['profile_file']).name}`",
            "",
            "## Summary Metrics",
            f"- **Total Execution Time:** `{diag['total_time_seconds']:.6f}s`",
            f"- **Total Function Calls:** `{diag['total_function_calls']}` (`{diag['primitive_calls']}` primitive)",
            f"- **Profile Size:** `{diag['file_size_bytes']} bytes`",
            "",
            "## Diagnostic Findings",
        ]

        md.extend([f"- ⚠️ {finding}" for finding in diag["diagnostic_findings"]])
        md.extend(
            [
                "",
                "## Top Cumulative Time Hotspots",
                "| Function | Total Time (s) | Cum Time (s) | % of Total | Calls |",
                "| :--- | :--- | :--- | :--- | :--- |",
            ]
        )
        md.extend(
            [
                f"| `{item['function']}` | `{item['tottime']:.6f}` | `{item['cumtime']:.6f}` | `{item['percent_of_total']}%` | `{item['ncalls']}` |"
                for item in diag["top_cumulative_hotspots"]
            ]
        )
        md.extend(
            [
                "",
                "## Top Self-Time Hotspots (CPU Consumers)",
                "| Function | Total Time (s) | Cum Time (s) | % of Total | Calls |",
                "| :--- | :--- | :--- | :--- | :--- |",
            ]
        )
        md.extend(
            [
                f"| `{item['function']}` | `{item['tottime']:.6f}` | `{item['cumtime']:.6f}` | `{item['percent_of_total']}%` | `{item['ncalls']}` |"
                for item in diag["top_self_time_hotspots"]
            ]
        )

        return "\n".join(md)

    @classmethod
    def launch_snakeviz(
        cls,
        prof_path: Path | str,
        port: int = 8080,
        browser: bool = True,
        wait: bool = False,
    ) -> subprocess.Popen | None:
        """Launches a SnakeViz visualization web server for interactive flame graphs.

        Args:
            prof_path: Path to the .prof file.
            port: Port for SnakeViz HTTP server.
            browser: Whether to automatically launch the default web browser.
            wait: Whether to block and wait for the process to exit.

        Returns:
            The subprocess.Popen instance representing the SnakeViz server, or None if launch failed.

        Example:
            >>> proc = ProfileAnalyzer.launch_snakeviz("profiles/fastapi/run.prof", port=8080)
        """
        path = Path(prof_path)
        if not path.is_file():
            raise FileNotFoundError(f"Profile binary file not found: {path}")

        cmd = [
            sys.executable,
            "-m",
            "snakeviz",
            str(path),
            "--port",
            str(port),
        ]
        if not browser:
            cmd.append("--server-only")

        logger.info(f"Launching SnakeViz: {' '.join(cmd)}")
        try:
            process = subprocess.Popen(cmd)  # noqa: S603
            if wait:
                process.wait()
            return process
        except Exception as err:
            logger.error(f"Failed to launch SnakeViz: {err}")
            return None
