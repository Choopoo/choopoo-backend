#!/usr/bin/env python3
"""Generate PNG charts and infra figures for docs/screenshots from experiment JSON + AWS CLI."""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SHOTS = os.path.join(ROOT, "docs", "screenshots")
EXP = os.path.join(ROOT, "backend", "experiments")
EXP_AWS = os.path.join(EXP, "aws")
EXP4 = os.path.join(EXP, "exp4_fault_tolerance")
AWS_DOC = os.path.join(ROOT, "docs", "aws")


def load_json(path):
    with open(path) as f:
        return json.load(f)


def ensure_dirs():
    os.makedirs(SHOTS, exist_ok=True)
    os.makedirs(AWS_DOC, exist_ok=True)


def chart_exp1_throughput():
    paths = {
        2: os.path.join(EXP, "exp1", "2producers.json"),
        5: os.path.join(EXP, "exp1", "5producers.json"),
        10: os.path.join(EXP, "exp1", "10producers.json"),
    }
    counts = []
    rps = []
    for n, p in sorted(paths.items()):
        d = load_json(p)
        counts.append(n)
        rps.append(d["throughput_rps"])

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([str(c) for c in counts], rps, color="#2563eb")
    ax.set_xlabel("Producer replicas (docker compose --scale producer=N)")
    ax.set_ylabel("Gateway throughput (HTTP req/s)")
    ax.set_title("Experiment 1: Producer scaling vs gateway accept rate")
    for i, v in enumerate(rps):
        ax.text(i, v + 0.5, f"{v:.1f}", ha="center", fontsize=10)
    fig.tight_layout()
    out = os.path.join(SHOTS, "exp1-throughput-chart.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print("Wrote", out)


def chart_exp2_latency():
    paths = {
        5: os.path.join(EXP, "exp2", "5concurrent.json"),
        20: os.path.join(EXP, "exp2", "20concurrent.json"),
        50: os.path.join(EXP, "exp2", "50concurrent.json"),
    }
    loads = []
    p50, p95, p99 = [], [], []
    for k in sorted(paths.keys()):
        d = load_json(paths[k])
        loads.append(k)
        lat = d["latency_ms"]
        p50.append(lat["p50"])
        p95.append(lat["p95"])
        p99.append(lat["p99"])

    x = range(len(loads))
    w = 0.25
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar([i - w for i in x], p50, width=w, label="p50", color="#0d9488")
    ax.bar(x, p95, width=w, label="p95", color="#ca8a04")
    ax.bar([i + w for i in x], p99, width=w, label="p99", color="#b91c1c")
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{c} concurrent" for c in loads])
    ax.set_ylabel("Latency (ms)")
    ax.set_title("Experiment 2: Gateway accept latency by load (POST /api/crawl -> 202)")
    ax.legend()
    fig.tight_layout()
    out = os.path.join(SHOTS, "exp2-latency-chart.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print("Wrote", out)


def chart_exp3_comparison():
    modes = {
        "backoff": os.path.join(EXP, "exp3", "backoff_50conc.json"),
        "backpressure": os.path.join(EXP, "exp3", "backpressure_50conc.json"),
        "circuit_breaker": os.path.join(EXP, "exp3", "circuit_breaker_50conc.json"),
    }
    labels = []
    p50s, p95s, p99s, tput = [], [], [], []
    for name, path in modes.items():
        d = load_json(path)
        labels.append(name.replace("_", "\n"))
        p50s.append(d["latency_ms"]["p50"])
        p95s.append(d["latency_ms"]["p95"])
        p99s.append(d["latency_ms"]["p99"])
        tput.append(d["throughput_rps"])

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    x = range(len(labels))
    w = 0.25
    ax = axes[0]
    ax.bar([i - w for i in x], p50s, width=w, label="p50")
    ax.bar(x, p95s, width=w, label="p95")
    ax.bar([i + w for i in x], p99s, width=w, label="p99")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("ms")
    ax.set_title("Latency (gateway 202 accept)")
    ax.legend(fontsize=8)

    ax2 = axes[1]
    ax2.bar(labels, tput, color="#7c3aed")
    ax2.set_ylabel("req/s")
    ax2.set_title("Throughput (same run)")
    fig.suptitle(
        "Experiment 3: Resilience modes @ 50 concurrent, mock fail=0.3, latency=200ms",
        fontsize=11,
    )
    fig.tight_layout()
    out = os.path.join(SHOTS, "exp3-comparison-chart.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print("Wrote", out)


def chart_exp1_throughput_aws():
    paths = {
        2: os.path.join(EXP_AWS, "exp1", "2producers.json"),
        5: os.path.join(EXP_AWS, "exp1", "5producers.json"),
        10: os.path.join(EXP_AWS, "exp1", "10producers.json"),
    }
    if not all(os.path.isfile(p) for p in paths.values()):
        print("Skip AWS exp1 chart (missing JSON under experiments/aws/exp1/)", file=sys.stderr)
        return
    counts = []
    rps = []
    for n, p in sorted(paths.items()):
        d = load_json(p)
        counts.append(n)
        rps.append(d["throughput_rps"])

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([str(c) for c in counts], rps, color="#1d4ed8")
    ax.set_xlabel("Producer ECS desired count (pipeline-producer)")
    ax.set_ylabel("Gateway throughput (HTTP req/s) via ALB")
    ax.set_title("Experiment 1 (AWS): Producer scaling — ALB → gateway 202 accept rate")
    for i, v in enumerate(rps):
        ax.text(i, v + 0.5, f"{v:.1f}", ha="center", fontsize=10)
    fig.tight_layout()
    out = os.path.join(SHOTS, "exp1-throughput-chart-aws.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print("Wrote", out)


def chart_exp2_latency_aws():
    paths = {
        5: os.path.join(EXP_AWS, "exp2", "5concurrent.json"),
        20: os.path.join(EXP_AWS, "exp2", "20concurrent.json"),
        50: os.path.join(EXP_AWS, "exp2", "50concurrent.json"),
    }
    if not all(os.path.isfile(p) for p in paths.values()):
        print("Skip AWS exp2 chart (missing JSON under experiments/aws/exp2/)", file=sys.stderr)
        return
    loads = []
    p50, p95, p99 = [], [], []
    for k in sorted(paths.keys()):
        d = load_json(paths[k])
        loads.append(k)
        lat = d["latency_ms"]
        p50.append(lat["p50"])
        p95.append(lat["p95"])
        p99.append(lat["p99"])

    x = range(len(loads))
    w = 0.25
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar([i - w for i in x], p50, width=w, label="p50", color="#0d9488")
    ax.bar(x, p95, width=w, label="p95", color="#ca8a04")
    ax.bar([i + w for i in x], p99, width=w, label="p99", color="#b91c1c")
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{c} concurrent" for c in loads])
    ax.set_ylabel("Latency (ms)")
    ax.set_title("Experiment 2 (AWS): Gateway accept latency by load (ALB)")
    ax.legend()
    fig.tight_layout()
    out = os.path.join(SHOTS, "exp2-latency-chart-aws.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print("Wrote", out)


def chart_exp3_comparison_aws():
    modes = {
        "backoff": os.path.join(EXP_AWS, "exp3", "backoff_50conc.json"),
        "backpressure": os.path.join(EXP_AWS, "exp3", "backpressure_50conc.json"),
        "circuit_breaker": os.path.join(EXP_AWS, "exp3", "circuit_breaker_50conc.json"),
    }
    if not all(os.path.isfile(p) for p in modes.values()):
        print("Skip AWS exp3 chart (missing JSON under experiments/aws/exp3/)", file=sys.stderr)
        return
    labels = []
    p50s, p95s, p99s, tput = [], [], [], []
    for name, path in modes.items():
        d = load_json(path)
        labels.append(name.replace("_", "\n"))
        p50s.append(d["latency_ms"]["p50"])
        p95s.append(d["latency_ms"]["p95"])
        p99s.append(d["latency_ms"]["p99"])
        tput.append(d["throughput_rps"])

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    x = range(len(labels))
    w = 0.25
    ax = axes[0]
    ax.bar([i - w for i in x], p50s, width=w, label="p50")
    ax.bar(x, p95s, width=w, label="p95")
    ax.bar([i + w for i in x], p99s, width=w, label="p99")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("ms")
    ax.set_title("Latency (gateway 202 via ALB)")
    ax.legend(fontsize=8)

    ax2 = axes[1]
    ax2.bar(labels, tput, color="#7c3aed")
    ax2.set_ylabel("req/s")
    ax2.set_title("Throughput")
    fig.suptitle(
        "Experiment 3 (AWS): Resilience @ 50 concurrent, mock 0.3 / 200ms",
        fontsize=11,
    )
    fig.tight_layout()
    out = os.path.join(SHOTS, "exp3-comparison-chart-aws.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print("Wrote", out)


def aws_ecs_bar_chart():
    region = "us-west-2"
    cluster = "pipeline-cluster"
    cmd = [
        "aws", "ecs", "describe-services",
        "--cluster", cluster,
        "--services",
        "pipeline-zookeeper", "pipeline-consumer", "pipeline-producer",
        "pipeline-gateway", "pipeline-kafka", "pipeline-ai-service",
        "--region", region, "--output", "json",
    ]
    try:
        raw = subprocess.check_output(cmd, text=True, timeout=60)
        data = json.loads(raw)
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as e:
        print("AWS CLI unavailable, skipping ECS chart:", e, file=sys.stderr)
        return

    services = data.get("services", [])
    names = []
    running = []
    desired = []
    for s in sorted(services, key=lambda x: x["serviceName"]):
        names.append(s["serviceName"].replace("pipeline-", ""))
        running.append(s["runningCount"])
        desired.append(s["desiredCount"])

    fig, ax = plt.subplots(figsize=(9, 4))
    x = range(len(names))
    ax.bar(x, running, color="#059669", label="running")
    ax.plot(x, desired, "ro", label="desired")
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, rotation=25, ha="right")
    ax.set_ylabel("Tasks")
    ax.set_title(
        f"ECS Fargate — {cluster} ({region}) @ "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    ax.legend()
    fig.tight_layout()
    out = os.path.join(SHOTS, "aws-ecs-pipeline-cluster.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print("Wrote", out)


def write_aws_snapshot():
    region = "us-west-2"
    cmds = [
        ("ecs-cluster.txt", ["aws", "ecs", "describe-clusters", "--clusters", "pipeline-cluster", "--region", region]),
        ("ecs-services.json", [
            "aws", "ecs", "describe-services",
            "--cluster", "pipeline-cluster",
            "--services",
            "pipeline-zookeeper", "pipeline-consumer", "pipeline-producer",
            "pipeline-gateway", "pipeline-kafka", "pipeline-ai-service",
            "--region", region, "--output", "json",
        ]),
        ("alb.json", ["aws", "elbv2", "describe-load-balancers", "--region", region, "--output", "json"]),
    ]
    for fname, cmd in cmds:
        try:
            out = subprocess.check_output(cmd, text=True, timeout=60)
            path = os.path.join(AWS_DOC, fname)
            with open(path, "w") as f:
                f.write(out)
            print("Wrote", path)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print("Skip", fname, e, file=sys.stderr)


def chart_exp4_recovery():
    """Bar chart of heuristic gateway CPU recovery times from exp4_recovery_summary.json."""
    summary_path = os.path.join(EXP4, "exp4_recovery_summary.json")
    if not os.path.isfile(summary_path):
        print("Skip Exp4 chart (missing experiments/exp4_fault_tolerance/exp4_recovery_summary.json)", file=sys.stderr)
        return
    data = load_json(summary_path)
    targets = data.get("targets") or []
    labels = []
    secs = []
    for row in targets:
        t = row.get("target", "?")
        s = row.get("recovery_seconds_gateway_cpu_heuristic")
        if s is None:
            continue
        labels.append(t)
        secs.append(float(s))

    if not labels:
        print("Skip Exp4 chart (no recovery_seconds in summary)", file=sys.stderr)
        return

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(labels, secs, color="#0f766e")
    ax.set_ylabel("Recovery time (s), gateway CPU heuristic")
    ax.set_title("Experiment 4: Time to gateway CPU band after kill (local Docker)")
    for i, v in enumerate(secs):
        ax.text(i, v + 0.3, f"{v:.1f}", ha="center", fontsize=10)
    fig.tight_layout()
    out = os.path.join(SHOTS, "exp4-recovery-chart.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print("Wrote", out)


def docker_ps_table_image():
    backend = os.path.join(ROOT, "backend")
    try:
        txt = subprocess.check_output(["docker", "compose", "ps"], cwd=backend, text=True, timeout=30)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print("docker compose ps failed:", e, file=sys.stderr)
        return

    lines = [ln for ln in txt.splitlines() if ln.strip() and "warning" not in ln.lower()]
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.axis("off")
    ax.text(0.01, 0.95, "docker compose ps (project/backend)", fontsize=11, family="monospace", va="top")
    body = "\n".join(lines[-14:])
    ax.text(0.01, 0.85, body, fontsize=7, family="monospace", va="top")
    fig.tight_layout()
    out = os.path.join(SHOTS, "docker-compose-up.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print("Wrote", out)


def main():
    ensure_dirs()
    chart_exp1_throughput()
    chart_exp2_latency()
    chart_exp3_comparison()
    chart_exp1_throughput_aws()
    chart_exp2_latency_aws()
    chart_exp3_comparison_aws()
    chart_exp4_recovery()
    aws_ecs_bar_chart()
    write_aws_snapshot()
    docker_ps_table_image()


if __name__ == "__main__":
    main()
