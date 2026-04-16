#!/usr/bin/env python3
"""
Optional AWS-safe fault demo: stop one running ECS task for a service, record timestamps.

Uses AWS CLI (no boto3). Does not stop ElastiCache, MSK, or RDS — only ECS tasks.

Example:
  python3 ecs_stop_task_experiment.py --cluster pipeline-cluster --service pipeline-producer --region us-west-2
  python3 ecs_stop_task_experiment.py --cluster pipeline-cluster --service pipeline-consumer --region us-west-2 --wait-stable
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone


def aws_json(cmd):
    out = subprocess.check_output(cmd, text=True, timeout=120)
    return json.loads(out)


def main():
    p = argparse.ArgumentParser(description="Stop one ECS task (class-safe fault injection)")
    p.add_argument("--cluster", required=True)
    p.add_argument("--service", required=True, help="ECS service name, e.g. pipeline-producer")
    p.add_argument("--region", default="us-west-2")
    p.add_argument(
        "--wait-stable",
        action="store_true",
        help="After stop, run aws ecs wait services-stable (can take several minutes)",
    )
    args = p.parse_args()

    list_cmd = [
        "aws", "ecs", "list-tasks",
        "--cluster", args.cluster,
        "--service-name", args.service,
        "--desired-status", "RUNNING",
        "--region", args.region,
        "--output", "json",
    ]
    try:
        listed = aws_json(list_cmd)
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as e:
        print("AWS CLI failed:", e, file=sys.stderr)
        sys.exit(1)

    arns = listed.get("taskArns") or []
    if not arns:
        print("No RUNNING tasks for service", args.service, file=sys.stderr)
        sys.exit(2)

    task_arn = arns[0]
    started = datetime.now(timezone.utc).isoformat()
    print("Stopping task:", task_arn)
    print("Started (UTC):", started)

    stop_cmd = [
        "aws", "ecs", "stop-task",
        "--cluster", args.cluster,
        "--task", task_arn,
        "--reason", "exp4-class-fault-demo",
        "--region", args.region,
        "--output", "json",
    ]
    try:
        stopped = aws_json(stop_cmd)
    except subprocess.CalledProcessError as e:
        print("stop-task failed:", e, file=sys.stderr)
        sys.exit(3)

    print(json.dumps({"stop_task_response": stopped}, indent=2))

    if args.wait_stable:
        wait_cmd = [
            "aws", "ecs", "wait", "services-stable",
            "--cluster", args.cluster,
            "--services", args.service,
            "--region", args.region,
        ]
        print("Waiting for services-stable ...")
        subprocess.run(wait_cmd, check=False)
        done = datetime.now(timezone.utc).isoformat()
        print("services-stable complete (UTC):", done)


if __name__ == "__main__":
    main()
