#!/usr/bin/env python3
"""
Heuristic recovery metrics for experiment 4 (local Docker Compose).

Uses kill_event_*.json (killed_at) + metrics_kill_*.json (docker_stats for gateway).
Recovery time: seconds from killed_at until the first gateway docker_stats sample after the kill
whose CPU% is within [0.5×, 3×] the median gateway CPU in the pre-kill window (samples before killed_at).

Limitations: Gateway CPU is a rough proxy; load_test aggregates do not separate pre/post kill.
Message loss is not tracked (Kafka offsets not instrumented).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_EXP4 = os.path.join(SCRIPT_DIR, "..", "experiments", "exp4_fault_tolerance")


def _parse_ts(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _parse_cpu(cpu_raw: Any) -> float:
    if cpu_raw is None:
        return 0.0
    s = str(cpu_raw).replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def _gateway_series(docker_stats: List[Dict[str, Any]]) -> List[Tuple[datetime, float]]:
    out: List[Tuple[datetime, float]] = []
    for row in docker_stats:
        name = row.get("container") or ""
        if "gateway" not in name.lower():
            continue
        ts = row.get("timestamp")
        if not ts:
            continue
        try:
            out.append((_parse_ts(ts), _parse_cpu(row.get("cpu_percent"))))
        except (ValueError, TypeError):
            continue
    out.sort(key=lambda x: x[0])
    return out


def recovery_seconds_heuristic(
    docker_stats: List[Dict[str, Any]], killed_at_iso: str
) -> Optional[float]:
    """Seconds until first post-kill gateway sample in 'normal' band vs pre-kill median."""
    kill_t = _parse_ts(killed_at_iso)
    series = _gateway_series(docker_stats)
    if not series:
        return None

    pre = [cpu for t, cpu in series if t < kill_t]
    baseline = statistics.median(pre) if pre else 0.05
    if baseline < 0.01:
        baseline = 0.01

    lo = max(0.005, 0.5 * baseline)
    hi = max(baseline * 3.0, baseline + 1.0)

    for t, cpu in series:
        if t <= kill_t:
            continue
        if lo <= cpu <= hi:
            return (t - kill_t).total_seconds()
    return None


def summarize_one_target(
    results_dir: str, target: str
) -> Optional[Dict[str, Any]]:
    kill_path = os.path.join(results_dir, f"kill_event_{target}.json")
    metrics_path = os.path.join(results_dir, f"metrics_kill_{target}.json")
    load_path = os.path.join(results_dir, f"loadtest_kill_{target}.json")

    if not os.path.isfile(kill_path) or not os.path.isfile(metrics_path):
        return None

    with open(kill_path) as f:
        kill = json.load(f)
    with open(metrics_path) as f:
        metrics = json.load(f)

    killed_at = kill.get("killed_at")
    if not killed_at:
        return None

    rec_s = recovery_seconds_heuristic(metrics.get("docker_stats") or [], killed_at)

    load: Dict[str, Any] = {}
    if os.path.isfile(load_path):
        with open(load_path) as lf:
            load = json.load(lf)

    tput = load.get("throughput_rps")
    errs = load.get("errors", 0)

    return {
        "target": target,
        "killed_at": killed_at,
        "recovery_seconds_gateway_cpu_heuristic": round(rec_s, 2) if rec_s is not None else None,
        "loadtest_throughput_rps": tput,
        "loadtest_errors": errs,
        "messages_lost": "not measured (no Kafka offset instrumentation)",
        "notes": "Aggregate load test spans pre-kill and post-kill; throughput is not a clean baseline comparison.",
    }


def summarize_exp4_dir(results_dir: str) -> Dict[str, Any]:
    """Write exp4_recovery_summary.json and return the dict."""
    targets = ["producer", "consumer", "redis"]
    rows = []
    for t in targets:
        row = summarize_one_target(results_dir, t)
        if row:
            rows.append(row)

    out = {
        "experiment": "exp4_fault_tolerance",
        "methodology": (
            "Recovery time uses docker_stats for the gateway container vs kill_event killed_at; "
            "see module docstring."
        ),
        "targets": rows,
    }
    out_path = os.path.join(results_dir, "exp4_recovery_summary.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {out_path}")
    return out


def main():
    parser = argparse.ArgumentParser(description="Summarize experiment 4 recovery heuristics")
    parser.add_argument(
        "results_dir",
        nargs="?",
        default=DEFAULT_EXP4,
        help="Path to exp4_fault_tolerance directory",
    )
    args = parser.parse_args()
    path = os.path.abspath(args.results_dir)
    if not os.path.isdir(path):
        print("Not a directory:", path, file=sys.stderr)
        sys.exit(1)
    summarize_exp4_dir(path)


if __name__ == "__main__":
    main()
