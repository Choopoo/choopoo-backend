"""Workflow service — consumes goal.created.v1 and runs the autopilot saga.

Architecture:
  goal.created.v1 (Kafka)  --->  this service
                                     ├── plan saga (extract material entities)
                                     ├── call gateway via service-secret
                                     ├── each step updates workflow_runs (observable)
                                     └── emit autopilot.step.v1 events (optional, not
                                         consumed yet; reserved for UI live-stream)

Idempotency: keyed by (org_id, goal_id). Re-delivery of the same event just
creates another workflow_runs row — acceptable for v1. Add a UNIQUE (org_id,
kind, subject_ref->>'goal_id') WHERE state IN ('planning','running') later
if concurrent re-delivery becomes an issue.
"""
from __future__ import annotations
import json
import logging
import os
import signal
import sys

import psycopg2
from confluent_kafka import Consumer, KafkaError

from gateway_client import Gateway
from saga import run_saga

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("workflow")

KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "kafka:29092")
DB_DSN = (
    f"host={os.getenv('DB_HOST','postgres')} port={os.getenv('DB_PORT','5432')} "
    f"user={os.getenv('DB_USER','pipeline')} password={os.getenv('DB_PASSWORD','pipeline')} "
    f"dbname={os.getenv('DB_NAME','pipeline')}"
)


def make_consumer() -> Consumer:
    return Consumer({
        "bootstrap.servers": KAFKA_BROKERS,
        "group.id": "workflow-autopilot",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })


def parse_event(msg) -> dict:
    headers = dict(msg.headers() or [])
    org_id = int(headers.get("X-Org-Id", b"0"))
    payload = json.loads(msg.value().decode("utf-8"))
    return {"_org_id": org_id, "_event_id": int(headers.get("X-Event-Id", b"0")), "payload": payload}


def main():
    consumer = make_consumer()
    consumer.subscribe(["goal.created.v1"])
    log.info("workflow service starting — subscribed to goal.created.v1")

    db = psycopg2.connect(DB_DSN)
    gateway = Gateway()

    stopping = False
    def _stop(_sig, _frm):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    while not stopping:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            log.error("kafka error: %s", msg.error())
            continue
        try:
            event = parse_event(msg)
            log.info("received goal.created.v1 org=%s goal=%s", event["_org_id"], event["payload"].get("goal_id"))
            run_saga(db, gateway, event)
            consumer.commit(msg, asynchronous=False)
        except Exception:
            log.exception("saga error; not committing so message will be redelivered")
            # Sleep briefly to avoid tight-loop on a poison pill.
            import time as _t
            _t.sleep(1.0)

    consumer.close()
    db.close()
    log.info("workflow service stopped")


if __name__ == "__main__":
    sys.exit(main() or 0)
