# simulator/main.py

import logging
import os
import random
import signal
import sys
import time
from dotenv import load_dotenv

from simulator.personas import PERSONA_NAMES, PERSONA_WEIGHTS
from simulator.event_generator import UserState, generate_event
from simulator.kafka_producer import EventProducer

load_dotenv()

# ─────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC             = os.getenv("KAFKA_TOPIC", "user-events")
NUM_USERS               = int(os.getenv("NUM_USERS", 1000))
EVENTS_PER_SECOND       = int(os.getenv("EVENTS_PER_SECOND", 100))
STATS_INTERVAL_SECONDS  = 10


# ─────────────────────────────────────────────────────────────
# USER POOL
# ─────────────────────────────────────────────────────────────

def create_user_pool(num_users: int) -> list[UserState]:
    """
    Creates a pool of virtual users with randomly
    assigned personas weighted by persona.weight.

    Args:
        num_users: total number of virtual users to simulate

    Returns:
        list of UserState objects ready to generate events
    """
    now   = int(time.time())
    users = []

    for i in range(num_users):
        persona_name = random.choices(
            PERSONA_NAMES,
            weights=PERSONA_WEIGHTS,
            k=1
        )[0]

        user = UserState(
            user_id      = f"user_{i:06d}",
            persona_name = persona_name,
            now          = now,
        )
        users.append(user)

    # log persona distribution
    from collections import Counter
    distribution = Counter(u.persona.name for u in users)
    logger.info(f"User pool created | total={num_users}")
    for persona_name, count in sorted(distribution.items()):
        logger.info(f"  {persona_name:<20} → {count} users ({count/num_users*100:.1f}%)")

    return users


# ─────────────────────────────────────────────────────────────
# STATS TRACKER
# ─────────────────────────────────────────────────────────────

class SimulatorStats:
    """
    Tracks simulator performance metrics.
    Logged every STATS_INTERVAL_SECONDS seconds.
    """

    def __init__(self):
        self.events_sent      = 0
        self.events_failed    = 0
        self.users_churned    = 0
        self.last_report_time = time.time()

    def record_sent(self):
        self.events_sent += 1

    def record_failed(self):
        self.events_failed += 1

    def record_churn(self):
        self.users_churned += 1

    def should_report(self) -> bool:
        return (time.time() - self.last_report_time) >= STATS_INTERVAL_SECONDS

    def report(self, active_users: int) -> None:
        elapsed  = time.time() - self.last_report_time
        rate     = self.events_sent / elapsed if elapsed > 0 else 0

        logger.info(
            f"Simulator stats | "
            f"active_users={active_users} | "
            f"churned={self.users_churned} | "
            f"events_sent={self.events_sent} | "
            f"events_failed={self.events_failed} | "
            f"rate={rate:.1f} events/sec"
        )

        # reset counters for next interval
        self.events_sent      = 0
        self.events_failed    = 0
        self.last_report_time = time.time()


# ─────────────────────────────────────────────────────────────
# GRACEFUL SHUTDOWN
# ─────────────────────────────────────────────────────────────

class GracefulShutdown:
    """
    Listens for SIGINT (Ctrl+C) and SIGTERM (Docker stop).
    Sets a flag that the main loop checks each iteration.

    This gives the simulator time to flush Kafka before exiting
    rather than cutting off mid-send.
    """

    def __init__(self):
        self.shutdown_requested = False
        signal.signal(signal.SIGINT,  self._handle)
        signal.signal(signal.SIGTERM, self._handle)

    def _handle(self, signum, frame):
        logger.info(f"Shutdown signal received ({signum}) — finishing current tick")
        self.shutdown_requested = True


# ─────────────────────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────────────────────

def run(
    users:    list[UserState],
    producer: EventProducer,
    stats:    SimulatorStats,
    shutdown: GracefulShutdown,
) -> None:
    """
    The main simulation loop.

    Each iteration is one tick. The loop:
        1. Iterates over all active users
        2. Attempts to generate an event for each
        3. Sends generated events to Kafka
        4. Reports stats every STATS_INTERVAL_SECONDS
        5. Sleeps to maintain EVENTS_PER_SECOND target rate
        6. Checks for shutdown signal

    Tick rate:
        EVENTS_PER_SECOND controls how fast real time
        passes in the simulation. Higher = faster simulation,
        more events per real second.
    """
    # ticks_per_day at the target rate
    # if EVENTS_PER_SECOND=100, each second = 100 ticks
    # each real second represents 100/86400 of a simulated day
    ticks_per_day    = EVENTS_PER_SECOND * SECONDS_PER_DAY
    sleep_per_tick   = 1.0 / EVENTS_PER_SECOND

    logger.info(
        f"Simulation starting | "
        f"users={len(users)} | "
        f"ticks_per_day={ticks_per_day:,} | "
        f"tick_rate={EVENTS_PER_SECOND}/sec"
    )

    while not shutdown.shutdown_requested:

        tick_start   = time.time()
        active_users = [u for u in users if not u.churned]

        for user in active_users:
            event = generate_event(user, ticks_per_day=ticks_per_day)

            if event is None:
                # check if user just churned this tick
                if user.churned:
                    stats.record_churn()
                continue

            success = producer.send_event(event)
            if success:
                stats.record_sent()
            else:
                stats.record_failed()

        # report stats periodically
        if stats.should_report():
            stats.report(active_users=len(active_users))

        # if all users have churned, regenerate the pool
        if len(active_users) == 0:
            logger.warning("All users churned — regenerating user pool")
            users = create_user_pool(NUM_USERS)
            for user in users:
                users.append(user)

        # sleep to maintain tick rate
        tick_elapsed = time.time() - tick_start
        sleep_time   = max(0, sleep_per_tick - tick_elapsed)
        time.sleep(sleep_time)


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

SECONDS_PER_DAY = 86400

def main():
    logger.info("Chronos Simulator starting")
    logger.info(f"Config | users={NUM_USERS} | rate={EVENTS_PER_SECOND} ticks/sec")

    # initialize components
    shutdown = GracefulShutdown()
    stats    = SimulatorStats()
    users    = create_user_pool(NUM_USERS)
    producer = EventProducer(
        bootstrap_servers = KAFKA_BOOTSTRAP_SERVERS,
        topic             = KAFKA_TOPIC,
    )

    try:
        run(users, producer, stats, shutdown)
    finally:
        # always flush and close on exit
        logger.info("Shutting down — flushing Kafka producer")
        producer.close()
        logger.info("Simulator stopped cleanly")


if __name__ == "__main__":
    main()