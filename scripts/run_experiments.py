#!/usr/bin/env python3
"""
Experiment runner for the distributed pipeline.
Orchestrates Docker Compose scaling, load tests, and metrics collection.

Usage:
    python run_experiments.py --experiment 1    # Producer scaling
    python run_experiments.py --experiment 2    # Consumer scaling
    python run_experiments.py --experiment 3    # Resilience patterns
    python run_experiments.py --experiment 4    # Fault tolerance
    python run_experiments.py --all             # Run all experiments
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime

COMPOSE_CMD = ["docker-compose", "-f", "docker-compose.yml", "-f", "docker-compose.experiment.yml"]
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "experiments")
GATEWAY_URL = "http://localhost:8081"
SETTLE_TIME = 15  # seconds to wait after scaling before testing
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))


def run(cmd, cwd=None, check=True):
    """Run a shell command and print it."""
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=False)


def run_capture(cmd, cwd=None):
    """Run a command and capture output."""
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def ensure_results_dir(experiment_name):
    """Create results directory for an experiment."""
    path = os.path.join(RESULTS_DIR, experiment_name)
    os.makedirs(path, exist_ok=True)
    return path


def wait_for_gateway(timeout=60):
    """Wait for the gateway to become healthy."""
    print(f"Waiting for gateway at {GATEWAY_URL}...")
    from urllib.request import urlopen
    from urllib.error import URLError
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = urlopen(f"{GATEWAY_URL}/health", timeout=5)
            if resp.status == 200:
                print("  Gateway is healthy.")
                return True
        except (URLError, Exception):
            pass
        time.sleep(2)
    print("  Gateway did not become healthy in time.")
    return False


# Compose service names for fault-injection targets (experiment 4)
TARGET_TO_SERVICE = {"producer": "producer", "consumer": "consumer", "redis": "redis"}


def list_running_container_ids_for_service(backend_dir, service):
    """Return non-empty container IDs for a compose service name."""
    ps = run_capture(COMPOSE_CMD + ["ps", "-q", service], cwd=backend_dir)
    err = (ps.stderr or "").strip()
    if err and ps.returncode != 0 and "warning" not in err.lower():
        print(f"  docker-compose ps -q {service} stderr: {err[:500]}")
    return [x for x in ps.stdout.strip().split("\n") if x.strip()]


def wait_for_postgres(backend_dir, timeout=120, interval=2):
    """Wait until the postgres service accepts connections (avoids consumer crash on startup)."""
    start = time.time()
    print("Waiting for PostgreSQL to accept connections...")
    while time.time() - start < timeout:
        r = run_capture(
            COMPOSE_CMD + ["exec", "-T", "postgres", "pg_isready", "-U", "pipeline", "-d", "pipeline"],
            cwd=backend_dir,
        )
        if r.returncode == 0:
            print("  PostgreSQL is ready.")
            return True
        time.sleep(interval)
    print("  PostgreSQL did not become ready in time.")
    return False


def restart_db_dependent_services(backend_dir):
    """
    Consumer/ai-service may have exited during compose boot before Postgres was ready.
    Restart them once DB is up so experiment 4 can kill running tasks.
    """
    for svc in ("consumer", "ai-service"):
        subprocess.run(COMPOSE_CMD + ["restart", svc], cwd=backend_dir, check=False)
    time.sleep(12)


def wait_for_running_service(backend_dir, service, timeout=120, interval=2):
    """
    Wait until docker-compose reports at least one running container for `service`.
    Returns the first container ID, or None on timeout.
    """
    start = time.time()
    while time.time() - start < timeout:
        ids = list_running_container_ids_for_service(backend_dir, service)
        if ids:
            print(f"  Service '{service}' running ({len(ids)} task(s)).")
            return ids[0]
        time.sleep(interval)
    print(f"  Timeout: no running container for compose service '{service}'.")
    snap = run_capture(COMPOSE_CMD + ["ps", "-a"], cwd=backend_dir)
    out = (snap.stdout or "") + (snap.stderr or "")
    print(f"  docker-compose ps -a (truncated):\n{out[:3000]}")
    return None


def compose_up(backend_dir, scale_args=None, env_overrides=None):
    """Start docker-compose with optional scaling and env overrides."""
    cmd = COMPOSE_CMD + ["up", "-d"]
    if scale_args:
        for service, count in scale_args.items():
            cmd.extend(["--scale", f"{service}={count}"])

    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)

    print(f"\nStarting services...")
    subprocess.run(cmd, cwd=backend_dir, env=env, check=True)
    time.sleep(SETTLE_TIME)


def compose_down(backend_dir):
    """Stop all services."""
    print("\nStopping services...")
    run(COMPOSE_CMD + ["down", "-v"], cwd=backend_dir, check=False)


def run_load_test(concurrency, total, batch_size, output_file):
    """Run the load test script."""
    cmd = [
        sys.executable, os.path.join(SCRIPTS_DIR, "load_test.py"),
        "-g", GATEWAY_URL,
        "-c", str(concurrency),
        "-n", str(total),
        "-b", str(batch_size),
        "-o", output_file,
    ]
    run(cmd)


def collect_metrics(duration, output_file, stats=False):
    """Run metrics collection in background."""
    cmd = [
        sys.executable, os.path.join(SCRIPTS_DIR, "collect_metrics.py"),
        "--live", "--duration", str(duration),
        "-o", output_file,
    ]
    if stats:
        cmd.append("--stats")
    proc = subprocess.Popen(cmd)
    return proc


def save_experiment_metadata(results_dir, metadata):
    """Save experiment config and timestamp."""
    metadata["timestamp"] = datetime.now().isoformat()
    with open(os.path.join(results_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)


# ─── Experiment 1: Producer Horizontal Scaling ─────────────────────

def experiment_1(backend_dir):
    """Scale producers 2 → 5 → 10, measure throughput."""
    results_dir = ensure_results_dir("exp1_producer_scaling")
    producer_counts = [2, 5, 10]

    print("\n" + "=" * 60)
    print("EXPERIMENT 1: Producer Horizontal Scaling")
    print("=" * 60)

    for count in producer_counts:
        print(f"\n--- {count} producers ---")

        compose_down(backend_dir)
        compose_up(backend_dir, scale_args={"producer": count})

        if not wait_for_gateway():
            print(f"Skipping {count} producers — gateway not ready")
            continue

        # collect metrics in background
        metrics_file = os.path.join(results_dir, f"metrics_{count}producers.json")
        metrics_proc = collect_metrics(90, metrics_file, stats=True)

        # wait a bit for metrics collector to start
        time.sleep(5)

        # run load test — fixed rate, enough requests to see throughput
        load_file = os.path.join(results_dir, f"loadtest_{count}producers.json")
        run_load_test(concurrency=10, total=200, batch_size=3, output_file=load_file)

        # wait for metrics to finish
        metrics_proc.wait()
        print(f"Results saved for {count} producers")

    save_experiment_metadata(results_dir, {
        "experiment": "Producer Horizontal Scaling",
        "producer_counts": producer_counts,
        "load_config": {"concurrency": 10, "total": 200, "batch_size": 3},
    })

    compose_down(backend_dir)
    print("\nExperiment 1 complete.")


# ─── Experiment 2: Consumer Group Scaling ──────────────────────────

def experiment_2(backend_dir):
    """Push 5/20/50 concurrent requests, scale consumers."""
    results_dir = ensure_results_dir("exp2_consumer_scaling")
    concurrency_levels = [5, 20, 50]

    print("\n" + "=" * 60)
    print("EXPERIMENT 2: Consumer Group Scaling & Bottleneck Migration")
    print("=" * 60)

    for conc in concurrency_levels:
        print(f"\n--- {conc} concurrent requests ---")

        compose_down(backend_dir)
        # scale consumers proportionally: 1 for low, 3 for medium, 5 for high
        consumer_count = {5: 1, 20: 3, 50: 5}[conc]
        compose_up(backend_dir, scale_args={"consumer": consumer_count})

        if not wait_for_gateway():
            print(f"Skipping {conc} concurrent — gateway not ready")
            continue

        metrics_file = os.path.join(results_dir, f"metrics_{conc}concurrent.json")
        metrics_proc = collect_metrics(120, metrics_file, stats=True)

        time.sleep(5)

        load_file = os.path.join(results_dir, f"loadtest_{conc}concurrent.json")
        run_load_test(concurrency=conc, total=conc * 10, batch_size=3, output_file=load_file)

        metrics_proc.wait()
        print(f"Results saved for {conc} concurrent")

    save_experiment_metadata(results_dir, {
        "experiment": "Consumer Group Scaling",
        "concurrency_levels": concurrency_levels,
    })

    compose_down(backend_dir)
    print("\nExperiment 2 complete.")


# ─── Experiment 3: Resilience Patterns ─────────────────────────────

def experiment_3(backend_dir):
    """Compare backoff vs backpressure vs circuit_breaker."""
    results_dir = ensure_results_dir("exp3_resilience_patterns")
    modes = ["backoff", "backpressure", "circuit_breaker"]
    concurrency_levels = [50, 100, 200]

    print("\n" + "=" * 60)
    print("EXPERIMENT 3: Resilience Pattern Comparison")
    print("=" * 60)

    for mode in modes:
        for conc in concurrency_levels:
            print(f"\n--- mode={mode}, {conc} concurrent ---")

            compose_down(backend_dir)

            # override AI service env
            env = {
                "RESILIENCE_MODE": mode,
                "MOCK_API_FAILURE_RATE": "0.3",
                "MOCK_API_LATENCY_MS": "200",
            }
            # we need to pass these through docker-compose
            # update the ai-service environment inline
            compose_up(backend_dir, env_overrides=env)

            if not wait_for_gateway():
                print(f"Skipping mode={mode}, {conc} concurrent — gateway not ready")
                continue

            metrics_file = os.path.join(results_dir, f"metrics_{mode}_{conc}conc.json")
            metrics_proc = collect_metrics(120, metrics_file, stats=True)

            time.sleep(5)

            load_file = os.path.join(results_dir, f"loadtest_{mode}_{conc}conc.json")
            run_load_test(concurrency=conc, total=conc * 5, batch_size=2, output_file=load_file)

            metrics_proc.wait()
            print(f"Results saved for mode={mode}, {conc} concurrent")

    save_experiment_metadata(results_dir, {
        "experiment": "Resilience Pattern Comparison",
        "modes": modes,
        "concurrency_levels": concurrency_levels,
        "mock_config": {"failure_rate": 0.3, "latency_ms": 200},
    })

    compose_down(backend_dir)
    print("\nExperiment 3 complete.")


# ─── Experiment 4: Fault Tolerance ─────────────────────────────────

def experiment_4(backend_dir):
    """Kill components under load, measure recovery."""
    results_dir = ensure_results_dir("exp4_fault_tolerance")
    targets = ["producer", "consumer", "redis"]

    print("\n" + "=" * 60)
    print("EXPERIMENT 4: Fault Tolerance & Recovery")
    print("=" * 60)

    for target in targets:
        print(f"\n--- Killing {target} ---")

        compose_down(backend_dir)
        compose_up(backend_dir, scale_args={"producer": 2, "consumer": 2})

        if not wait_for_postgres(backend_dir):
            print(f"Skipping {target} kill — PostgreSQL not ready.")
            continue

        restart_db_dependent_services(backend_dir)

        if not wait_for_gateway():
            print(f"Skipping {target} kill — gateway not ready")
            continue

        service = TARGET_TO_SERVICE[target]
        # Only the target service must be running to inject the fault (other services may still be starting).
        if wait_for_running_service(backend_dir, service, timeout=120) is None:
            print(f"Skipping {target} kill — compose service '{service}' never became ready.")
            continue

        # start metrics collection (longer window to capture recovery)
        metrics_file = os.path.join(results_dir, f"metrics_kill_{target}.json")
        metrics_proc = collect_metrics(180, metrics_file, stats=True)

        time.sleep(5)

        # start load test in background
        load_file = os.path.join(results_dir, f"loadtest_kill_{target}.json")
        load_cmd = [
            sys.executable, os.path.join(SCRIPTS_DIR, "load_test.py"),
            "-g", GATEWAY_URL, "-c", "20", "-n", "300", "-b", "3",
            "-o", load_file,
        ]
        load_proc = subprocess.Popen(load_cmd)

        # wait for load to build up, then kill one task for the target service
        time.sleep(15)

        container_id = wait_for_running_service(backend_dir, service, timeout=90)
        if not container_id:
            print(f"  Could not resolve running container for service '{service}' — skip kill.")
            load_proc.wait()
            metrics_proc.wait()
            continue

        # Resolve human-readable name for logs (optional)
        name_result = run_capture(
            ["docker", "inspect", "-f", "{{.Name}}", container_id],
            cwd=backend_dir,
        )
        container_name = name_result.stdout.strip().lstrip("/") if name_result.returncode == 0 else container_id

        print(f"  Killing container: {container_name} ({container_id[:12]}…)")
        subprocess.run(["docker", "kill", container_id], check=False)
        kill_time = datetime.now().isoformat()

        with open(os.path.join(results_dir, f"kill_event_{target}.json"), "w") as f:
            json.dump({
                "target": target,
                "service": service,
                "container_id": container_id,
                "container": container_name,
                "killed_at": kill_time,
            }, f, indent=2)

        # wait for load test and metrics to finish
        load_proc.wait()
        metrics_proc.wait()
        print(f"Results saved for {target} kill")

    save_experiment_metadata(results_dir, {
        "experiment": "Fault Tolerance & Recovery",
        "targets": targets,
        "load_config": {"concurrency": 20, "total": 300, "batch_size": 3},
    })

    subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "analyze_exp4_recovery.py"), results_dir],
        cwd=backend_dir,
        check=False,
    )

    compose_down(backend_dir)
    print("\nExperiment 4 complete.")


# ─── Main ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Experiment runner")
    parser.add_argument("--experiment", type=int, choices=[1, 2, 3, 4],
                        help="Run a specific experiment (1-4)")
    parser.add_argument("--all", action="store_true",
                        help="Run all experiments sequentially")
    args = parser.parse_args()

    backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    os.makedirs(RESULTS_DIR, exist_ok=True)

    experiments = {
        1: experiment_1,
        2: experiment_2,
        3: experiment_3,
        4: experiment_4,
    }

    if args.all:
        for num in [1, 2, 3, 4]:
            experiments[num](backend_dir)
    elif args.experiment:
        experiments[args.experiment](backend_dir)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
