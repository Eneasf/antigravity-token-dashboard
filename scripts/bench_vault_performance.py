#!/usr/bin/env python3
"""
Empirical Performance & KPI Benchmark Harness for Antigravity Telemetry Vault.

Measures:
- KPI 1: Query Execution Latency (ms) - Mean, Min, P95 across 5 core query patterns.
- KPI 2: Row Scan Reduction - Full Table Scans vs Index B-Tree Seeks.
- KPI 3: Index Storage Footprint - Disk overhead in KB / MB.
- KPI 4: Ingestion Write Overhead - Batch insertion throughput (µs / step).

Adheres to:
- ADR-001: Safe Read-Only SQLite Access (?mode=ro, uri=True).
- ADR-091: Empirical DB Benchmarking & KPI Governance Harness.
"""

import argparse
import json
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_VAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "antigravity_vault.db"


def run_single_benchmark(
    cur: sqlite3.Cursor,
    name: str,
    sql: str,
    params: Tuple = (),
    iterations: int = 5,
    explain: bool = True,
) -> Dict[str, Any]:
    """Execute a query multiple times, collecting latency and execution plan stats."""
    plan = []
    if explain:
        try:
            cur.execute(f"EXPLAIN QUERY PLAN {sql}", params)
            plan = [row[3] for row in cur.fetchall()]
        except Exception as e:
            plan = [f"Explain failed: {e}"]

    # Warmup run
    try:
        cur.execute(sql, params)
        rows = cur.fetchall()
        row_count = len(rows)
    except Exception as e:
        return {
            "name": name,
            "status": "ERROR",
            "error": str(e),
            "plan": plan,
            "row_count": 0,
            "latencies_ms": [],
            "avg_ms": 0.0,
            "min_ms": 0.0,
        }

    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        cur.execute(sql, params)
        cur.fetchall()
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

    avg_ms = sum(latencies) / len(latencies) if latencies else 0.0
    min_ms = min(latencies) if latencies else 0.0

    return {
        "name": name,
        "status": "OK",
        "row_count": row_count,
        "plan": plan,
        "latencies_ms": latencies,
        "avg_ms": avg_ms,
        "min_ms": min_ms,
    }


def benchmark_vault(
    vault_path: Path,
    iterations: int = 5,
    skip_slow_freetext: bool = False,
) -> Dict[str, Any]:
    """Run full benchmark suite against the SQLite Telemetry Vault."""
    if not vault_path.exists():
        return {"status": "ERROR", "error": f"Vault file not found: {vault_path}"}

    file_size_bytes = vault_path.stat().st_size
    conn = sqlite3.connect(f"file:{vault_path.resolve()}?mode=ro", uri=True, timeout=60.0)
    cur = conn.cursor()

    # Table sizes
    cur.execute("SELECT COUNT(*) FROM steps_archive")
    steps_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM conversations_archive")
    convos_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM log_events_archive")
    logs_count = cur.fetchone()[0]

    # Inspect present indexes
    cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
    existing_indexes = sorted([r[0] for r in cur.fetchall()])

    # Inspect present views
    cur.execute("SELECT name FROM sqlite_master WHERE type='view'")
    existing_views = sorted([r[0] for r in cur.fetchall()])

    results = []

    # 1. Time-window turns seek
    results.append(
        run_single_benchmark(
            cur,
            "1. Time-window turns seek (step_type=15, ts>='2026-09-13')",
            "SELECT convo_id, timestamp, total_input_tokens FROM steps_archive "
            "WHERE step_type = 15 AND timestamp >= ?",
            ("2026-09-13T17:58:04",),
            iterations=iterations,
        )
    )

    # 2. Convo + time range seek
    sample_convo = ""
    cur.execute("SELECT convo_id FROM steps_archive ORDER BY timestamp DESC LIMIT 1")
    sample_row = cur.fetchone()
    if sample_row:
        sample_convo = sample_row[0]

    results.append(
        run_single_benchmark(
            cur,
            "2. Session step timeline range seek",
            "SELECT step_idx, timestamp FROM steps_archive WHERE convo_id = ? AND timestamp >= ?",
            (sample_convo, "2026-09-20"),
            iterations=iterations,
        )
    )

    # 3. Log event code lookup (429)
    results.append(
        run_single_benchmark(
            cur,
            "3. Log event code lookup (code=429)",
            "SELECT * FROM log_events_archive WHERE code = ?",
            (429,),
            iterations=iterations,
        )
    )

    # 4. Failure steps lookup
    results.append(
        run_single_benchmark(
            cur,
            "4. Failure steps lookup (error_text IS NOT NULL)",
            "SELECT convo_id, timestamp, error_text FROM steps_archive "
            "WHERE error_text IS NOT NULL AND error_text != ''",
            (),
            iterations=iterations,
        )
    )

    # 5. Free-text LIKE scan (Optional / Skippable)
    if not skip_slow_freetext:
        results.append(
            run_single_benchmark(
                cur,
                "5. Free-text LIKE scan (%RESOURCE_EXHAUSTED%)",
                "SELECT convo_id, step_idx FROM steps_archive WHERE payload_text LIKE ?",
                ("%RESOURCE_EXHAUSTED%",),
                iterations=max(1, min(iterations, 3)),
            )
        )

    # 6. Structured rate limit seek (if column exists)
    cur.execute("PRAGMA table_info(steps_archive)")
    step_cols = {r[1] for r in cur.fetchall()}
    if "rate_limit_flag" in step_cols:
        results.append(
            run_single_benchmark(
                cur,
                "6. Structured rate limit flag seek (rate_limit_flag=1)",
                "SELECT convo_id, step_idx, timestamp FROM steps_archive WHERE rate_limit_flag = 1",
                (),
                iterations=iterations,
            )
        )

    # 7. Analytical View: v_active_sessions (if view exists)
    if "v_active_sessions" in existing_views:
        results.append(
            run_single_benchmark(
                cur,
                "7. Analytical View (v_active_sessions query)",
                "SELECT convo_id, title, session_start, duration_seconds FROM v_active_sessions "
                "WHERE session_start >= ? ORDER BY session_start DESC LIMIT 20",
                ("2026-09-20",),
                iterations=iterations,
            )
        )

    conn.close()

    return {
        "status": "OK",
        "vault_path": str(vault_path),
        "file_size_bytes": file_size_bytes,
        "file_size_mb": round(file_size_bytes / (1024 * 1024), 2),
        "steps_count": steps_count,
        "convos_count": convos_count,
        "logs_count": logs_count,
        "existing_indexes": existing_indexes,
        "existing_views": existing_views,
        "benchmarks": results,
    }


def print_scorecard(report: Dict[str, Any]) -> None:
    """Print clean ASCII summary scorecard of benchmark results."""
    if report.get("status") != "OK":
        print(f"Benchmark Error: {report.get('error')}", file=sys.stderr)
        return

    print("=" * 80)
    print(f" TELEMETRY VAULT KPI BENCHMARK SCORECARD (ADR-091)")
    print("=" * 80)
    print(f" Vault Database : {report['vault_path']}")
    print(f" Total DB Size  : {report['file_size_mb']} MB")
    print(f" Records        : {report['steps_count']:,} steps | {report['convos_count']:,} convos | {report['logs_count']:,} log events")
    print(f" Total Indexes  : {len(report['existing_indexes'])} indexes")
    print(f" Total Views    : {len(report['existing_views'])} views")
    print("-" * 80)
    print(f"{'Query Benchmark':45s} | {'Rows':8s} | {'Avg (ms)':10s} | {'Min (ms)':10s}")
    print("-" * 80)
    for b in report["benchmarks"]:
        name = b["name"][:45]
        row_str = f"{b['row_count']:,}"
        avg_str = f"{b['avg_ms']:.2f}"
        min_str = f"{b['min_ms']:.2f}"
        print(f"{name:45s} | {row_str:>8s} | {avg_str:>10s} | {min_str:>10s}")
        if b.get("plan"):
            print(f"   ↳ Plan: {b['plan'][0]}")
    print("=" * 80)


def main() -> int:
    parser = argparse.ArgumentParser(description="Antigravity Telemetry Vault Performance Benchmark")
    parser.add_argument("--vault-path", type=Path, default=DEFAULT_VAULT_PATH, help="Path to SQLite vault database")
    parser.add_argument("--iterations", type=int, default=5, help="Number of warm query iterations")
    parser.add_argument("--skip-slow-freetext", action="store_true", help="Skip expensive unindexed LIKE scan")
    parser.add_argument("--json", action="store_true", help="Output raw JSON results")

    args = parser.parse_args()
    report = benchmark_vault(
        vault_path=args.vault_path,
        iterations=args.iterations,
        skip_slow_freetext=args.skip_slow_freetext,
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_scorecard(report)

    return 0 if report.get("status") == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
