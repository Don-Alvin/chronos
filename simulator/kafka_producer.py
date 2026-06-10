# simulator/kafka_producer.py

import json
import logging
from kafka import KafkaProducer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# PRODUCER
# ─────────────────────────────────────────────────────────────

class EventProducer:
    """
    Wraps KafkaProducer to send user events reliably.

    Handles:
        - JSON serialization
        - Delivery confirmation callbacks
        - Graceful error handling without crashing the simulator
        - Clean shutdown
    """

    def __init__(self, bootstrap_servers: str, topic: str):
        """
        Args:
            bootstrap_servers: Kafka broker address.
                               e.g. "localhost:9092" locally,
                                    "kafka:9092" inside Docker.
            topic:             Kafka topic to send events to.
                               e.g. "user-events"
        """
        self.topic   = topic
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,

            # serialize every message as UTF-8 encoded JSON
            value_serializer=lambda event: json.dumps(event).encode("utf-8"),

            # use user_id as the partition key
            # this ensures all events for the same user
            # go to the same Kafka partition, preserving order
            key_serializer=lambda key: key.encode("utf-8") if key else None,

            # wait for the broker to acknowledge receipt
            # acks=1 means the leader broker confirms the write
            # acks=0 would be faster but risks data loss
            acks=1,

            # retry up to 3 times on transient failures
            retries=3,

            # wait up to 100ms to batch messages together
            # improves throughput without significant latency cost
            linger_ms=100,
        )

        logger.info(
            f"EventProducer initialized | "
            f"brokers={bootstrap_servers} | "
            f"topic={topic}"
        )


    def send_event(self, event: dict) -> bool:
        """
        Sends a single event to Kafka.

        Uses the user_id as the partition key to guarantee
        that all events for the same user arrive in order
        at the consumer.

        Args:
            event: complete event dictionary matching event schema

        Returns:
            True if send succeeded, False if it failed.
            Never raises — errors are logged and swallowed
            so the simulator loop never crashes from a single
            failed send.
        """
        try:
            user_id = event.get("user_id")

            future = self.producer.send(
                topic=self.topic,
                key=user_id,
                value=event,
            )

            # register callbacks for async confirmation
            future.add_callback(self._on_success)
            future.add_errback(self._on_error)

            return True

        except KafkaError as e:
            logger.error(f"Failed to send event | user_id={event.get('user_id')} | error={e}")
            return False


    def _on_success(self, record_metadata) -> None:
        """
        Called when Kafka confirms message delivery.
        Logs partition and offset for debugging.
        """
        logger.debug(
            f"Event delivered | "
            f"topic={record_metadata.topic} | "
            f"partition={record_metadata.partition} | "
            f"offset={record_metadata.offset}"
        )


    def _on_error(self, exception) -> None:
        """
        Called when Kafka fails to deliver a message
        after all retries are exhausted.
        """
        logger.error(f"Event delivery failed permanently | error={exception}")


    def flush(self) -> None:
        """
        Blocks until all pending messages are delivered.

        Call this before shutting down to ensure no
        messages are lost in the internal send buffer.
        """
        self.producer.flush()
        logger.info("Producer flushed — all pending messages delivered")


    def close(self) -> None:
        """
        Flushes and closes the producer cleanly.
        Always call this on shutdown.
        """
        self.flush()
        self.producer.close()
        logger.info("Producer closed")