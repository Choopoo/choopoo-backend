import json
from confluent_kafka import Consumer, KafkaError


class KafkaConsumerWrapper:
    def __init__(self, brokers, topic, group_id):
        self.topic = topic
        self.consumer = Consumer({
            'bootstrap.servers': brokers,
            'group.id': group_id,
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': True,
        })
        self.consumer.subscribe([topic])
        print(f"Subscribed to topic: {topic}")

    def poll(self, timeout=1.0):
        """Poll for a single message. Returns parsed dict or None."""
        msg = self.consumer.poll(timeout)
        if msg is None:
            return None
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                return None  # just end of partition, not a real error
            print(f"Kafka error: {msg.error()}")
            return None

        try:
            value = json.loads(msg.value().decode('utf-8'))
            return value
        except json.JSONDecodeError as e:
            print(f"Bad message, skipping: {e}")
            return None

    def close(self):
        self.consumer.close()
