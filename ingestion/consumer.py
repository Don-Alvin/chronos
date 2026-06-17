import json
import logging
import os
import signal
import time

from kafka import KafkaConsumer
from redis import Redis
from dotenv import load_dotenv

from ingestion.validator import validate_event, build_dlq_payload
from ingestion.feature_updater import process_event
from simulator.kafka_producer import EventProducer

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Config
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "user-events")
KAFKA_DLQ_TOPIC = os.getenv("KAFKA_DLQ_TOPIC", "user-events-dlq")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "chronos-consumer-group")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CONSUMER_ID = os.getenv("HOSTNAME", "consumer-1")
STATS_INTERVAL_SECONDS = 10

# Clean shutdown
class CleanShutdown:
    """
    Catches SIGINT/SIGTERM so the loop can finish its current event, commit and close cleanly instead
    of dying mid process
    """
    def __init__(self):
        self.requested = False
        signal.signal(signal.SIGINT, self._handle)
        signal.signal(signal.SIGTERM, self._handle)
    
    def _handle(self, signum, frame):
        logger.info(f"Shutdown signal recieved ({signum}) - finishing current event")
        self.requested = True


# Stats
class ConsumerStats:
    def __init__(self):
        self.processed = 0
        self.duplicates = 0
        self.dlq = 0
        self.last_report = time.time()
    
    def should_report(self) -> bool:
        return (time.time() - self.last_report) >= STATS_INTERVAL_SECONDS
    
    def report(self):
        elapsed = time.time() - self.last_report
        rate = self.processed / elapsed if elapsed > 0 else 0
        logger.info(
            f"Consumer stats | processed={self.processed} | "
            f"duplicates={self.duplicates} | dlq={self.dlq} | "
            f"rate={rate:.1f} events/sec"
        )

        self.processed = 0
        self.duplicates = 0
        self.dlq = 0
        self.last_report = time.time()

# Redis connection
def make_redis(url: str) -> Redis:
    """
    Builds a Redis client with decode_responses=True so values comeback as tr, not bytes.
    """
    return Redis.from_url(url, decode_responses=True)

# Consume loop
def run(consumer, redis_client, dlq_producer, stats, shutdown):
    """
    The consume loop
    """
    logger.info("Consumer loop started, waiting for events")

    while not shutdown.requested:
        batch = consumer.poll(timeout_ms=1000)

        for topic_partition, messages in batch.items():
            for message in messages:
                _handle_message(message, redis_client, dlq_producer, stats)
                consumer.commit()

                if shutdown.requested:
                    break
            
        if stats.should_report():
            stats.report()

def _handle_message(message, redis_client, dlq_producer, stats):
    """
    Handles one Kafka message end to end.
    """
    # Deserialize
    try:
        event = json.loads(message.value.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning(f"Undeserialize message at offset {message.offset}: {e}")
        dlq_producer.send_event({
            "original_event": str(message.value),
            "error_type": "DeserializationError",
            "error_message": str(e),
            "failed_at": int(time.time()),
            "consumer_id": CONSUMER_ID
        })
        stats.dlq += 1
        return
    
    # Validate
    result = validate_event(event)
    if not result.is_valid:
        logger.debug(f"Invalid event -> DLQ: {result.error_type}")
        dlq_producer.send_event(build_dlq_payload(event, result, CONSUMER_ID))
        stats.dlq += 1
    
    # Process
    try:
        applied = process_event(redis_client, event)
        if applied:
            stats.processed += 1
        else:
            stats.duplicates += 1
    except Exception as e:
        logger.error(f"Processing failed for {event.get('event_id')}: {e}")
        dlq_producer.send_event({
            "original_event": event,
            "error_type":     "ProcessingError",
            "error_message":  str(e),
            "failed_at":      int(time.time()),
            "consumer_id":    CONSUMER_ID,
        })
        stats.dlq += 1

# Entry point
def main():
    logger.info("Chronos Consumer starting")
    logger.info(
        f"Config | brokers={KAFKA_BOOTSTRAP_SERVERS} | topic={KAFKA_TOPIC} | "
        f"group={KAFKA_GROUP_ID}"
    )

    shutdown = CleanShutdown()
    stats = ConsumerStats()

    redis_client = make_redis(REDIS_URL)
    redis_client.ping()
    logger.info("Connected to Redis")

    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=KAFKA_GROUP_ID,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        value_deserializer=None
    )
    logger.info("Connected to Kafka")
    dlq_producer = EventProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        topic=KAFKA_DLQ_TOPIC
    )

    try:
        run(consumer, redis_client, dlq_producer, stats, shutdown)
    finally:
        logger.info("Shutting down....commiting final offset and closing")
        try:
            consumer.commit()
        except Exception as e:
            logger.warning(f"Final commit failed: {e}")
        consumer.close()
        dlq_producer.close()
        logger.info("Consumer stopped cleanly")


if __name__ == "__main__":
    main()


