import os
import sys
import json
import time
import psycopg2

from consumer import KafkaConsumerWrapper
from ai_client import MockAIClient
from resilience import ExponentialBackoff, Backpressure, CircuitBreaker


def log_metric(page_id, latency_ms, success, resilience_mode, circuit_state=None):
    """Print a structured JSON log line for experiment parsing."""
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "page_id": page_id,
        "latency_ms": round(latency_ms, 1),
        "success": success,
        "resilience_mode": resilience_mode,
    }
    if circuit_state:
        entry["circuit_state"] = circuit_state
    print(json.dumps(entry), flush=True)


def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres"),
        dbname=os.getenv("DB_NAME", "pipeline"),
    )
    # auto-create table if it doesn't exist
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS analysis_results (
                id SERIAL PRIMARY KEY,
                page_id INTEGER,
                summary TEXT,
                recommendation TEXT,
                processed_at TIMESTAMP DEFAULT NOW()
            )
        """)
    conn.commit()
    return conn


def save_result(conn, page_id, summary, recommendation):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO analysis_results (page_id, summary, recommendation) VALUES (%s, %s, %s)",
            (page_id, summary, recommendation),
        )
    conn.commit()


def main():
    # load config from env
    kafka_brokers = os.getenv("KAFKA_BROKERS", "localhost:9092")
    input_topic = os.getenv("INPUT_TOPIC", "analysis-results")
    consumer_group = os.getenv("CONSUMER_GROUP", "ai-service-group")
    resilience_mode = os.getenv("RESILIENCE_MODE", "backoff")

    mock_latency = int(os.getenv("MOCK_API_LATENCY_MS", "100"))
    mock_failure_rate = float(os.getenv("MOCK_API_FAILURE_RATE", "0.1"))
    mock_rate_limit = int(os.getenv("MOCK_API_RATE_LIMIT", "50"))

    print(f"Starting AI service — mode={resilience_mode}, "
          f"latency={mock_latency}ms, failure_rate={mock_failure_rate}")

    # init components
    consumer = KafkaConsumerWrapper(kafka_brokers, input_topic, consumer_group)
    ai_client = MockAIClient(mock_latency, mock_failure_rate, mock_rate_limit)
    conn = get_db_connection()

    # pick resilience strategy
    if resilience_mode == "backoff":
        strategy = ExponentialBackoff()
    elif resilience_mode == "backpressure":
        strategy = Backpressure()
    elif resilience_mode == "circuit_breaker":
        strategy = CircuitBreaker()
    else:
        print(f"Unknown resilience mode: {resilience_mode}, defaulting to backoff")
        strategy = ExponentialBackoff()

    print("Listening for messages...")

    try:
        while True:
            # backpressure mode: skip polling if we need to cool down
            if resilience_mode == "backpressure" and strategy.should_pause():
                time.sleep(1)
                continue

            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue

            page_id = msg.get("page_id")
            print(f"Processing page_id={page_id}")

            # call the AI with resilience wrapper
            start = time.time()
            result = strategy.call(ai_client, msg)
            latency_ms = (time.time() - start) * 1000

            success = result["status"] == 200
            circuit_state = None
            if resilience_mode == "circuit_breaker":
                circuit_state = strategy.get_state()

            log_metric(page_id, latency_ms, success, resilience_mode, circuit_state)

            # save to DB on success
            if success:
                body = result["body"]
                save_result(conn, page_id, body["summary"], body["recommendation"])
            elif result["status"] == 503:
                # circuit breaker fallback — still save the fallback text
                body = result["body"]
                save_result(conn, page_id, body["summary"], body["recommendation"])

    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        consumer.close()
        conn.close()


if __name__ == "__main__":
    main()
