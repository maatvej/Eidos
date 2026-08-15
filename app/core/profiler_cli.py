# filename: app/core/profiler_cli.py
"""Command-Line Interface (CLI) diagnostic utility for Eidos profiling system.

Usage Examples:
    python -m app.core.profiler_cli --latest
    python -m app.core.profiler_cli --path profiles/fastapi/upload.prof --sort time --limit 20
    python -m app.core.profiler_cli --latest --snakeviz --port 8080
    python -m app.core.profiler_cli --compare profiles/base.prof profiles/optimized.prof
    python -m app.core.profiler_cli --clean 7
"""

import argparse
import json
import sys
from pathlib import Path

from app.core.profiler import clean_old_profiles, format_pstats_summary
from app.core.profiler_analyzer import ProfileAnalyzer


def create_parser() -> argparse.ArgumentParser:
    """Creates and configures the CLI argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="python -m app.core.profiler_cli",
        description="Eidos Performance Profiling & Diagnostic Hotspot Utility",
    )

    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "-p",
        "--path",
        type=str,
        help="Path to specific .prof binary file for analysis.",
    )
    source_group.add_argument(
        "-l",
        "--latest",
        action="store_true",
        help="Automatically analyze the most recently generated .prof file.",
    )
    source_group.add_argument(
        "--clean",
        type=int,
        metavar="DAYS",
        help="Delete profiling artifacts older than the specified number of days.",
    )

    parser.add_argument(
        "-s",
        "--sort",
        type=str,
        default="cumulative",
        choices=["cumulative", "time", "tottime", "calls", "ncalls", "name", "line", "file"],
        help="Metric sorting key for pstats summary (default: cumulative).",
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=25,
        help="Number of top functions to display in summary tables (default: 25).",
    )
    parser.add_argument(
        "--hotspots-only",
        action="store_true",
        help="Display only functions flagged as significant CPU hotspots.",
    )
    parser.add_argument(
        "--compare",
        type=str,
        metavar="BASE_PROF",
        help="Compare candidate profile with specified baseline .prof file.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output diagnostics in structured JSON format.",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Output diagnostics as a GitHub-flavored Markdown report.",
    )
    parser.add_argument(
        "--snakeviz",
        action="store_true",
        help="Launch SnakeViz interactive flame graph web visualization server.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port number for SnakeViz server (default: 8080).",
    )

    return parser


def _resolve_target_path(args: argparse.Namespace, parser: argparse.ArgumentParser) -> Path | None:
    """Resolves target .prof path from arguments."""
    if args.path:
        return Path(args.path)

    latest = ProfileAnalyzer.find_latest_profile()
    if args.latest:
        if not latest:
            print("No .prof files found in profile output directory.")
            return None
        print(f"Analyzing latest profile: {latest}")
        return latest

    if not latest:
        parser.print_help()
        return None
    return latest


def _handle_compare(target_path: Path, args: argparse.Namespace) -> int:
    """Executes profile comparison against a baseline artifact."""
    base_path = Path(args.compare)
    if not base_path.exists():
        print(f"Error: Baseline profile '{base_path}' not found.", file=sys.stderr)
        return 1

    comparison = ProfileAnalyzer.compare_profiles(base_path, target_path)
    if args.json:
        print(json.dumps(comparison, indent=2))
        return 0

    print("=" * 60)
    print("EIDOS PROFILE COMPARISON")
    print("=" * 60)
    print(f"Baseline:    {comparison['base_profile']} ({comparison['base_total_time']}s)")
    print(f"Candidate:   {comparison['candidate_profile']} ({comparison['candidate_total_time']}s)")
    print(
        f"Delta:       {comparison['time_difference_seconds']}s ({comparison['percent_change']}%)"
    )
    print(f"Speedup:     {comparison['speedup_factor']}x")
    print(f"Verdict:     {'IMPROVED' if comparison['is_improved'] else 'REGRESSED'}")
    print("=" * 60)
    return 0


def _handle_output(target_path: Path, args: argparse.Namespace) -> int:
    """Renders profile report in formatted text, JSON, or Markdown."""
    if args.json:
        diag = ProfileAnalyzer.diagnose_bottlenecks(target_path)
        print(json.dumps(diag, indent=2))
        return 0

    if args.markdown:
        md = ProfileAnalyzer.generate_markdown_report(target_path)
        print(md)
        return 0

    diag = ProfileAnalyzer.diagnose_bottlenecks(target_path)
    stats = ProfileAnalyzer.load_stats(target_path)

    print("=" * 80)
    print(f"EIDOS PERFORMANCE PROFILE: {target_path.name}")
    print(f"Total Session Time: {diag['total_time_seconds']:.6f}s")
    print(f"Total Calls: {diag['total_function_calls']} ({diag['primitive_calls']} primitive)")
    print("=" * 80)

    print("\n[DIAGNOSTIC FINDINGS]")
    for finding in diag["diagnostic_findings"]:
        print(f"  * {finding}")

    if args.hotspots_only:
        hotspots = ProfileAnalyzer.analyze_hotspots(target_path, limit=args.limit)
        print("\n[TOP IDENTIFIED CPU HOTSPOTS]")
        print(f"{'NCALLS':<10} {'TOTTIME':<12} {'PERCALL':<12} {'CUMTIME':<12} {'FUNCTION':<30}")
        print("-" * 78)
        for h in hotspots:
            loc = f"{Path(h.filename).name}:{h.line_number}({h.func_name})"
            print(
                f"{h.ncalls:<10} {h.tottime:<12.6f} {h.percall_tottime:<12.6f} {h.cumtime:<12.6f} {loc:<30}"
            )
    else:
        print(f"\n[TOP {args.limit} FUNCTIONS SORTED BY {args.sort.upper()}]")
        print(format_pstats_summary(stats, sort_by=args.sort, limit=args.limit))

    return 0


def main(args_list: list[str] | None = None) -> int:
    """Main CLI execution routine.

    Args:
        args_list: Optional command-line arguments list (defaults to sys.argv[1:]).

    Returns:
        Process exit code (0 for success, 1 for error).
    """
    parser = create_parser()
    args = parser.parse_args(args_list)

    if args.clean is not None:
        deleted = clean_old_profiles(max_age_days=args.clean)
        print(f"Cleaned {deleted} profiling artifacts older than {args.clean} days.")
        return 0

    target_path = _resolve_target_path(args, parser)
    if target_path is None:
        return 1

    if not target_path.exists():
        print(f"Error: Target profile file '{target_path}' not found.", file=sys.stderr)
        return 1

    if args.compare:
        return _handle_compare(target_path, args)

    if args.snakeviz:
        print(f"Starting SnakeViz visualizer on http://127.0.0.1:{args.port}...")
        ProfileAnalyzer.launch_snakeviz(target_path, port=args.port, browser=True, wait=True)
        return 0

    return _handle_output(target_path, args)


if __name__ == "__main__":
    sys.exit(main())
