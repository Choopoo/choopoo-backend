#!/usr/bin/env python3
"""
Run pipeline load tests against the live ECS + ALB deployment (us-west-2).

Uses aws ecs update-service for scaling and register-task-definition for AI
service resilience env (no terraform apply per step).

Usage:
  python run_aws_experiments.py --experiment 1
  python run_aws_experiments.py --experiment 2
  python run_aws_experiments.py --experiment 3
  GATEWAY_URL=http://pipeline-alb-xxx.elb.amazonaws.com python run_aws_experiments.py --experiment 1
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(SCRIPTS_DIR, "..")
TERRAFORM_DIR = os.path.join(BACKEND_DIR, "terraform")
AWS_EXPERIMENTS = os.path.join(BACKEND_DIR, "experiments", "aws")

# Match project/backend/terraform/variables.tf defaults + service names (app_name=pipeline)
CLUSTER = os.environ.get("ECS_CLUSTER", "pipeline-cluster")
REGION = os.environ.get("AWS_REGION", "us-west-2")
PREFIX = os.environ.get("PIPELINE_PREFIX", "pipeline")
SETTLE_SEC = int(os.environ.get("AWS_EXPERIMENT_SETTLE", "45"))


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check)


def run_json(cmd: list[str]) -> dict:
    out = subprocess.check_output(cmd, text=True)
    return json.loads(out)


def get_gateway_url() -> str:
    env = os.environ.get("GATEWAY_URL", "").strip()
    if env:
        return env.rstrip("/")
    try:
        raw = subprocess.check_output(
            ["terraform", "output", "-raw", "alb_dns_name"],
            cwd=TERRAFORM_DIR,
            text=True,
        ).strip()
        if raw:
            return f"http://{raw}".rstrip("/")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Could not read terraform output: {e}", file=sys.stderr)
    raise SystemExit(
        "Set GATEWAY_URL=http://<alb-dns> or run from a machine with terraform state in backend/terraform"
    )


def ecs_update_desired(service: str, desired: int) -> None:
    run(
        [
            "aws",
            "ecs",
            "update-service",
            "--cluster",
            CLUSTER,
            "--service",
            f"{PREFIX}-{service}",
            "--desired-count",
            str(desired),
            "--region",
            REGION,
            "--query",
            "service.{name:serviceName,desired:desiredCount,running:runningCount}",
            "--output",
            "text",
        ]
    )


def ecs_wait_stable(services: list[str]) -> None:
    for svc in services:
        run(
            [
                "aws",
                "ecs",
                "wait",
                "services-stable",
                "--cluster",
                CLUSTER,
                "--services",
                f"{PREFIX}-{svc}",
                "--region",
                REGION,
            ]
        )


def run_load_test(gateway: str, concurrency: int, total: int, batch_size: int, out_path: str) -> None:
    cmd = [
        sys.executable,
        os.path.join(SCRIPTS_DIR, "load_test.py"),
        "-g",
        gateway,
        "-c",
        str(concurrency),
        "-n",
        str(total),
        "-b",
        str(batch_size),
        "-o",
        out_path,
    ]
    run(cmd)


def _strip_task_def(td: dict) -> dict:
    for k in (
        "taskDefinitionArn",
        "revision",
        "status",
        "requiresAttributes",
        "compatibilities",
        "registeredAt",
        "registeredBy",
        "deregisteredAt",
    ):
        td.pop(k, None)
    td.pop("compatibilities", None)
    # keep requiresCompatibilities
    return td


def _set_container_env(container: dict, name: str, value: str) -> None:
    env = container.get("environment") or []
    for e in env:
        if e.get("name") == name:
            e["value"] = value
            return
    env.append({"name": name, "value": value})
    container["environment"] = env


def register_ai_service_resilience(
    mode: str,
    mock_latency_ms: str = "200",
    mock_failure_rate: str = "0.3",
) -> str:
    """Clone current pipeline-ai-service task def, patch env, register, return new revision ARN."""
    fam = f"{PREFIX}-ai-service"
    raw = subprocess.check_output(
        [
            "aws",
            "ecs",
            "describe-task-definition",
            "--task-definition",
            fam,
            "--region",
            REGION,
            "--output",
            "json",
        ],
        text=True,
    )
    td = _strip_task_def(json.loads(raw)["taskDefinition"])
    if not td.get("containerDefinitions"):
        raise RuntimeError("task definition has no containerDefinitions")
    c0 = td["containerDefinitions"][0]
    _set_container_env(c0, "RESILIENCE_MODE", mode)
    _set_container_env(c0, "MOCK_API_LATENCY_MS", mock_latency_ms)
    _set_container_env(c0, "MOCK_API_FAILURE_RATE", mock_failure_rate)

    proc = subprocess.run(
        [
            "aws",
            "ecs",
            "register-task-definition",
            "--region",
            REGION,
            "--cli-input-json",
            json.dumps(td),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        raise RuntimeError("register-task-definition failed")
    reg = json.loads(proc.stdout)
    arn = reg["taskDefinition"]["taskDefinitionArn"]
    run(
        [
            "aws",
            "ecs",
            "update-service",
            "--cluster",
            CLUSTER,
            "--service",
            f"{PREFIX}-ai-service",
            "--task-definition",
            arn,
            "--force-new-deployment",
            "--region",
            REGION,
            "--query",
            "service.taskDefinition",
            "--output",
            "text",
        ]
    )
    ecs_wait_stable(["ai-service"])
    return arn


def ensure_dirs() -> None:
    os.makedirs(os.path.join(AWS_EXPERIMENTS, "exp1"), exist_ok=True)
    os.makedirs(os.path.join(AWS_EXPERIMENTS, "exp2"), exist_ok=True)
    os.makedirs(os.path.join(AWS_EXPERIMENTS, "exp3"), exist_ok=True)


def save_metadata(name: str, data: dict) -> None:
    data["timestamp"] = datetime.now().isoformat()
    path = os.path.join(AWS_EXPERIMENTS, name)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {path}")


def experiment_1(gateway: str) -> None:
    print("\n" + "=" * 60 + "\nAWS EXPERIMENT 1: Producer scaling\n" + "=" * 60)
    out_dir = os.path.join(AWS_EXPERIMENTS, "exp1")
    counts = [2, 5, 10]
    for n in counts:
        print(f"\n--- {n} producers ---")
        ecs_update_desired("producer", n)
        ecs_wait_stable(["producer"])
        time.sleep(SETTLE_SEC)
        out = os.path.join(out_dir, f"{n}producers.json")
        run_load_test(gateway, concurrency=10, total=200, batch_size=3, out_path=out)
    save_metadata(
        "exp1_metadata.json",
        {
            "experiment": "producer_scaling_aws",
            "cluster": CLUSTER,
            "region": REGION,
            "gateway": gateway,
            "producer_counts": counts,
            "load": {"concurrency": 10, "total": 200, "batch_size": 3},
        },
    )


def experiment_2(gateway: str) -> None:
    print("\n" + "=" * 60 + "\nAWS EXPERIMENT 2: Consumer scaling\n" + "=" * 60)
    out_dir = os.path.join(AWS_EXPERIMENTS, "exp2")
    # align with local docker: single producer for consumer-scaling focus
    ecs_update_desired("producer", 1)
    ecs_wait_stable(["producer"])
    levels = [(5, 1), (20, 3), (50, 5)]
    for conc, consumer_n in levels:
        print(f"\n--- {conc} concurrent, {consumer_n} consumers ---")
        ecs_update_desired("consumer", consumer_n)
        ecs_wait_stable(["consumer"])
        time.sleep(SETTLE_SEC)
        out = os.path.join(out_dir, f"{conc}concurrent.json")
        run_load_test(gateway, concurrency=conc, total=conc * 10, batch_size=3, out_path=out)
    save_metadata(
        "exp2_metadata.json",
        {
            "experiment": "consumer_scaling_aws",
            "cluster": CLUSTER,
            "region": REGION,
            "gateway": gateway,
            "steps": [{"concurrent": c, "consumers": n} for c, n in levels],
            "load": {"batch_size": 3, "total_formula": "concurrent * 10"},
        },
    )


def experiment_3(gateway: str) -> None:
    print("\n" + "=" * 60 + "\nAWS EXPERIMENT 3: Resilience modes\n" + "=" * 60)
    out_dir = os.path.join(AWS_EXPERIMENTS, "exp3")
    modes = ["backoff", "backpressure", "circuit_breaker"]
    for mode in modes:
        print(f"\n--- RESILIENCE_MODE={mode} ---")
        register_ai_service_resilience(mode)
        time.sleep(SETTLE_SEC)
        out = os.path.join(out_dir, f"{mode}_50conc.json")
        run_load_test(gateway, concurrency=50, total=250, batch_size=2, out_path=out)
    save_metadata(
        "exp3_metadata.json",
        {
            "experiment": "resilience_aws",
            "cluster": CLUSTER,
            "region": REGION,
            "gateway": gateway,
            "modes": modes,
            "mock": {"MOCK_API_FAILURE_RATE": "0.3", "MOCK_API_LATENCY_MS": "200"},
            "load": {"concurrency": 50, "total": 250, "batch_size": 2},
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AWS ECS + ALB experiments")
    parser.add_argument("--experiment", type=int, choices=[1, 2, 3], required=True)
    args = parser.parse_args()

    ensure_dirs()
    gateway = get_gateway_url()
    print(f"Gateway: {gateway}")

    if args.experiment == 1:
        experiment_1(gateway)
    elif args.experiment == 2:
        experiment_2(gateway)
    else:
        experiment_3(gateway)

    print("\nDone.")


if __name__ == "__main__":
    main()
