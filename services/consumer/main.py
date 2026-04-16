import os
import json
import time
import logging
from datetime import datetime

from consumer import KafkaConsumerWrapper, KafkaProducerWrapper
from scorer import score_page
from cache import RedisCache
from db import Database

# structured JSON logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("consumer")


def log(level, msg, **extra):
    entry = {"timestamp": datetime.utcnow().isoformat(), "level": level, "message": msg}
    entry.update(extra)
    logger.info(json.dumps(entry))


def main():
    # load config from env
    kafka_brokers = os.getenv("KAFKA_BROKERS", "localhost:9092")
    input_topic = os.getenv("INPUT_TOPIC", "page-metadata")
    output_topic = os.getenv("OUTPUT_TOPIC", "analysis-results")
    consumer_group = os.getenv("CONSUMER_GROUP", "consumer-group")
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = os.getenv("REDIS_PORT", "6379")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")
    db_name = os.getenv("DB_NAME", "crawler")

    log("INFO", "Starting consumer service", group=consumer_group, topic=input_topic)

    # init connections
    kafka_consumer = KafkaConsumerWrapper(kafka_brokers, consumer_group, input_topic)
    kafka_producer = KafkaProducerWrapper(kafka_brokers)
    cache = RedisCache(redis_host, redis_port)
    db = Database(db_host, db_port, db_user, db_password, db_name)

    log("INFO", "Connected to Kafka, Redis, and Postgres")

    try:
        while True:
            msg = kafka_consumer.poll(timeout=1.0)
            if msg is None:
                continue

            url = msg.get("url", "")
            log("INFO", "Received message", url=url)

            # cache-aside: skip if we already processed this URL
            cached = cache.get_cached(url)
            if cached:
                log("INFO", "Cache hit, skipping", url=url)
                continue

            # score the page
            score = score_page(msg)
            log("INFO", "Scored page", url=url, score=score)

            # persist to postgres
            page_id = db.insert_page(
                url=url,
                domain=msg.get("domain", ""),
                title=msg.get("title", ""),
                meta_description=msg.get("meta_description", ""),
                score=score,
                material=msg.get("material") or None,
                source_label=msg.get("source_label") or None,
                job_id=msg.get("job_id") or None,
            )
            log("INFO", "Inserted into DB", url=url, page_id=page_id)

            # cache the result so we don't reprocess
            cache.set_cache(url, {"page_id": page_id, "score": score})

            # forward to analysis-results topic for AI service
            output_msg = {
                "page_id": page_id,
                "url": url,
                "domain": msg.get("domain", ""),
                "title": msg.get("title", ""),
                "score": score,
            }
            kafka_producer.send(output_topic, output_msg)
            log("INFO", "Forwarded to analysis-results", page_id=page_id)

    except KeyboardInterrupt:
        log("INFO", "Shutting down consumer")
    finally:
        kafka_consumer.close()
        kafka_producer.close()
        db.close()


if __name__ == "__main__":
    main()
