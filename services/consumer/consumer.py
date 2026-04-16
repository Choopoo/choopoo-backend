import json
from confluent_kafka import Consumer, Producer, KafkaError


class KafkaConsumerWrapper:
    def __init__(self, brokers, group_id, topic):
        self.consumer = Consumer({
            "bootstrap.servers": brokers,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
        })
        self.consumer.subscribe([topic])

    def poll(self, timeout=1.0):
        msg = self.consumer.poll(timeout)
        if msg is None:
            return None
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                return None  # just end of partition, not a real error
            if msg.error().code() == KafkaError.UNKNOWN_TOPIC_OR_PART:
                return None  # topic not created yet, will retry
            raise Exception(f"Kafka error: {msg.error()}")
        # deserialize the JSON payload
        return json.loads(msg.value().decode("utf-8"))

    def close(self):
        self.consumer.close()


class KafkaProducerWrapper:
    def __init__(self, brokers):
        self.producer = Producer({"bootstrap.servers": brokers})

    def send(self, topic, message):
        payload = json.dumps(message).encode("utf-8")
        self.producer.produce(topic, value=payload)
        self.producer.flush()

    def close(self):
        self.producer.flush()
