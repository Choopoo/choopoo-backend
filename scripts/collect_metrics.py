#!/usr/bin/env python3
"""
Metrics collector for the distributed pipeline.
Parses structured JSON logs from docker containers and extracts experiment-relevant metrics.

Usage:
    # Collect from running containers (live)
    python collect_metrics.py --live --duration 60 --output results/exp1_2producers.json

    # Parse saved log files
    python collect_metrics.py --logfile consumer.log --service consumer

    # Collect docker stats (CPU/memory) alongside logs
    python collect_metrics.py --live --duration 60 --stats --output results/exp1_stats.json
"""

import argparse
import json
import subprocess
import time
import threading
import statistics
import re
from datetime import datetime
from collections import defaultdict


def parse_ai_service_log(line):
    """Parse structured JSON log from AI service.
    Format: {"timestamp": "...", "page_id": N, "latency_ms": F, "success": bool, "resilience_mode": "..."}
    """
    try:
        data = json.loads(line.strip())
        if "latency_ms" in data and "success" in data:
            return {
                "service": "ai-service",
                "type": "metric",
                "page_id": data.get("page_id"),
                "latency_ms": data["latency_ms"],
                "success": data["success"],
                "resilience_mode": data.get("resilience_mode"),
                "circuit_state": data.get("circuit_state"),
                "timestamp": data.get("timestamp"),
            }
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def parse_consumer_log(line):
    """Parse structured JSON log from consumer service.
    Format: {"timestamp": "...", "level": "INFO", "message": "...", ...extra}
    """
    try:
        data = json.loads(line.strip())
        msg = data.get("message", "")
        result = {"service": "consumer", "type": "log", "message": msg}

        if "Cache hit" in msg:
            result["type"] = "cache_hit"
            result["url"] = data.get("url")
        elif "Inserted into DB" in msg:
            result["type"] = "db_insert"
            result["url"] = data.get("url")
            result["page_id"] = data.get("page_id")
        elif "Scored page" in msg:
            result["type"] = "scored"
            result["score"] = data.get("score")
        elif "Forwarded to analysis-results" in msg:
            result["type"] = "forwarded"
            result["page_id"] = data.get("page_id")

        return result
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def parse_producer_log(line):
    """Parse Go log output from producer service.
    Format: standard Go log with timestamps.
    """
    # look for crawl completion lines
    if "published metadata" in line.lower() or "crawled" in line.lower():
        return {"service": "producer", "type": "crawled", "raw": line.strip()}
    if "worker" in line.lower() and ("error" in line.lower() or "failed" in line.lower()):
        return {"service": "producer", "type": "error", "raw": line.strip()}
    return None


def collect_docker_logs(container_name, duration_seconds, results, stop_event):
    """Stream docker logs from a container for a given duration."""
    try:
        proc = subprocess.Popen(
            ["docker", "logs", "-f", "--since", "1s", container_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        while not stop_event.is_set():
            line = proc.stdout.readline()
            if not line:
                break

            parsed = None
            if "ai-service" in container_name or "ai_service" in container_name:
                parsed = parse_ai_service_log(line)
            elif "consumer" in container_name:
                parsed = parse_consumer_log(line)
            elif "producer" in container_name:
                parsed = parse_producer_log(line)

            if parsed:
                results.append(parsed)

        proc.terminate()
    except Exception as e:
        print(f"Error collecting logs from {container_name}: {e}")


def collect_docker_stats(duration_seconds, interval=2):
    """Collect CPU/memory stats from all pipeline containers."""
    snapshots = []
    end_time = time.time() + duration_seconds

    while time.time() < end_time:
        try:
            result = subprocess.run(
                ["docker", "stats", "--no-stream", "--format",
                 "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"],
                capture_output=True, text=True, timeout=10
            )
            timestamp = datetime.now().isoformat()
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 4:
                    snapshots.append({
                        "timestamp": timestamp,
                        "container": parts[0],
                        "cpu_percent": parts[1].replace("%", ""),
                        "mem_usage": parts[2],
                        "mem_percent": parts[3].replace("%", ""),
                    })
        except (subprocess.TimeoutExpired, Exception) as e:
            print(f"Stats collection error: {e}")

        time.sleep(interval)

    return snapshots


def get_pipeline_containers():
    """Find running pipeline containers."""
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        capture_output=True, text=True
    )
    containers = []
    for name in result.stdout.strip().split("\n"):
        if any(svc in name for svc in ["producer", "consumer", "ai-service", "ai_service", "gateway"]):
            containers.append(name)
    return containers


def compute_ai_service_metrics(events):
    """Compute summary metrics from AI service log events."""
    latencies = [e["latency_ms"] for e in events if e.get("type") == "metric"]
    successes = [e for e in events if e.get("type") == "metric" and e.get("success")]
    failures = [e for e in events if e.get("type") == "metric" and not e.get("success")]

    if not latencies:
        return {"warning": "no AI service metrics collected"}

    sorted_lat = sorted(latencies)
    n = len(sorted_lat)

    metrics = {
        "total_requests": n,
        "successes": len(successes),
        "failures": len(failures),
        "error_rate": round(len(failures) / n, 3) if n else 0,
        "latency_ms": {
            "min": round(min(latencies), 1),
            "avg": round(statistics.mean(latencies), 1),
            "p50": round(sorted_lat[n // 2], 1),
            "p95": round(sorted_lat[int(n * 0.95)], 1),
            "p99": round(sorted_lat[min(int(n * 0.99), n - 1)], 1),
            "max": round(max(latencies), 1),
        },
    }

    # circuit breaker state transitions
    states = [e.get("circuit_state") for e in events if e.get("circuit_state")]
    if states:
        metrics["circuit_breaker_states"] = dict(
            (s, states.count(s)) for s in set(states)
        )

    # resilience mode
    modes = [e.get("resilience_mode") for e in events if e.get("resilience_mode")]
    if modes:
        metrics["resilience_mode"] = modes[0]

    return metrics


def compute_consumer_metrics(events):
    """Compute summary metrics from consumer log events."""
    cache_hits = len([e for e in events if e.get("type") == "cache_hit"])
    db_inserts = len([e for e in events if e.get("type") == "db_insert"])
    forwarded = len([e for e in events if e.get("type") == "forwarded"])
    total_processed = cache_hits + db_inserts

    return {
        "total_processed": total_processed,
        "cache_hits": cache_hits,
        "db_inserts": db_inserts,
        "forwarded_to_ai": forwarded,
        "cache_hit_rate": round(cache_hits / total_processed, 3) if total_processed else 0,
    }


def compute_producer_metrics(events):
    """Compute summary metrics from producer log events."""
    crawled = len([e for e in events if e.get("type") == "crawled"])
    errors = len([e for e in events if e.get("type") == "error"])

    return {
        "urls_crawled": crawled,
        "errors": errors,
    }


def run_live_collection(duration, collect_stats, output_file):
    """Collect metrics from running Docker containers."""
    containers = get_pipeline_containers()
    if not containers:
        print("No pipeline containers found. Is docker-compose running?")
        return

    print(f"Found containers: {', '.join(containers)}")
    print(f"Collecting for {duration} seconds...")

    all_events = []
    stop_event = threading.Event()

    # start log collectors
    threads = []
    for container in containers:
        t = threading.Thread(
            target=collect_docker_logs,
            args=(container, duration, all_events, stop_event),
        )
        t.daemon = True
        t.start()
        threads.append(t)

    # optionally collect stats
    stats_data = []
    if collect_stats:
        stats_thread = threading.Thread(
            target=lambda: stats_data.extend(collect_docker_stats(duration)),
        )
        stats_thread.daemon = True
        stats_thread.start()

    # wait for duration
    time.sleep(duration)
    stop_event.set()

    # give threads a moment to finish
    for t in threads:
        t.join(timeout=3)

    # sort events by service
    ai_events = [e for e in all_events if e.get("service") == "ai-service"]
    consumer_events = [e for e in all_events if e.get("service") == "consumer"]
    producer_events = [e for e in all_events if e.get("service") == "producer"]

    # compute summaries
    report = {
        "collected_at": datetime.now().isoformat(),
        "duration_seconds": duration,
        "containers": containers,
        "ai_service": compute_ai_service_metrics(ai_events),
        "consumer": compute_consumer_metrics(consumer_events),
        "producer": compute_producer_metrics(producer_events),
        "raw_event_count": len(all_events),
    }

    if stats_data:
        report["docker_stats"] = stats_data

    # print summary
    print("\n" + "=" * 50)
    print("METRICS SUMMARY")
    print("=" * 50)
    print(json.dumps(report, indent=2, default=str))

    if output_file:
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nSaved to {output_file}")

    return report


def parse_logfile(logfile, service):
    """Parse a saved log file."""
    events = []
    parser = {
        "ai-service": parse_ai_service_log,
        "consumer": parse_consumer_log,
        "producer": parse_producer_log,
    }.get(service)

    if not parser:
        print(f"Unknown service: {service}")
        return

    with open(logfile) as f:
        for line in f:
            parsed = parser(line)
            if parsed:
                events.append(parsed)

    print(f"Parsed {len(events)} events from {logfile}")

    if service == "ai-service":
        metrics = compute_ai_service_metrics(events)
    elif service == "consumer":
        metrics = compute_consumer_metrics(events)
    elif service == "producer":
        metrics = compute_producer_metrics(events)

    print(json.dumps(metrics, indent=2))
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Pipeline metrics collector")
    parser.add_argument("--live", action="store_true",
                        help="Collect from running Docker containers")
    parser.add_argument("--duration", type=int, default=60,
                        help="Collection duration in seconds (default: 60)")
    parser.add_argument("--stats", action="store_true",
                        help="Also collect Docker CPU/memory stats")
    parser.add_argument("--logfile", type=str,
                        help="Parse a saved log file instead of live collection")
    parser.add_argument("--service", type=str,
                        choices=["ai-service", "consumer", "producer"],
                        help="Service name (required with --logfile)")
    parser.add_argument("-o", "--output", type=str,
                        help="Save results to JSON file")
    args = parser.parse_args()

    if args.logfile:
        if not args.service:
            print("--service is required with --logfile")
            return
        parse_logfile(args.logfile, args.service)
    elif args.live:
        run_live_collection(args.duration, args.stats, args.output)
    else:
        print("Specify --live or --logfile. Use -h for help.")


if __name__ == "__main__":
    main()
