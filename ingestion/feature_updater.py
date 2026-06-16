import logging
from redis import Redis

from features.contract import (
    EVENT_TO_FEATURES,
    FEATURE_TYPES,
    FEATURES,
    FeatureType
)
from features.redis_keys import processed_event_key
from features.strategies import (
    apply_counter,
    apply_window_counter,
    apply_gauge_raw,
    apply_gauge_ts,
    apply_session_start,
    apply_session_end,
    PROCESSED_EVENT_TTL_SECONDS
)

logger = logging.getLogger(__name__)

# WINDOW LOOKUP
_WINDOW_DAYS = {
    f["name"]: f["window_days"]
    for f in FEATURES
    if f["type"] == FeatureType.WINDOW_COUNTER
}

# IDEMPOTENCY
def already_processed(redis_client: Redis, event_id: str) -> bool:
    """
    Returns True if this event_id has been processed before
    """

    return redis_client.exists(processed_event_key(event_id)) ==1

def mark_processed(redis_client: Redis, event_id: str) -> None:
    """
    Record that an event_id has been fully processed, with a 24h TTL.
    A retry within 24h is skipped after that the key expires and storage is reclaimed
    """

    key = processed_event_key(event_id)
    redis_client.set(key, 1)
    redis_client.expire(key, PROCESSED_EVENT_TTL_SECONDS)

# Single feature dispatch
def _apply_one_feature(
    redis_client: Redis,
    user_id: str,
    feature_name: str,
    event_id: str,
    timestamp: int
) -> None:
    """
    Routes one feature to the correct strategy based on its type
    """
    ftype = FEATURE_TYPES[feature_name]

    if ftype == FeatureType.COUNTER:
        apply_counter(redis_client, user_id, feature_name)
    elif ftype == FeatureType.WINDOW_COUNTER:
        apply_window_counter(
            redis_client, user_id, feature_name,
            event_id=event_id, timestamp=timestamp,
            window_days=_WINDOW_DAYS[feature_name]
        )
    elif ftype == FeatureType.GAUGE_TS:
        apply_gauge_ts(redis_client, user_id, feature_name, timestamp)
    elif ftype == FeatureType.GAUGE_RAW:
        apply_gauge_raw(redis_client, user_id, feature_name, timestamp)
    else:
        logger.warning(f"No strategy for feature type {ftype} on {feature_name}")

def _apply_raw_gauge(
    redis_client: Redis,
    user_id: str,
    feature_name: str,
    timestamp: int
) -> None:
    """
    Handles GAUGE_RAW features that are set as a side effect of an
    event rather than carrying an event-supplied number.
    """

    pass

def process_event(redis_client: Redis, event: dict) -> bool:
    """
    Applies all feature updates for one validated event.
    Returns True if event was applied,False if skipped as a duplicate
    """
    event_id = event["event_id"]
    user_id = event["user_id"]
    event_type = event["event_type"]
    timestamp = event["timestamp"]

    # Idempotency
    if already_processed(redis_client, event_id):
        logger.debug(f"Skipping duplicate event {event_id}")
        return False
    
    # Generic feature updates
    for feature_name in EVENT_TO_FEATURES.get(event_type, []):
        _apply_one_feature(redis_client, user_id, feature_name, event_id, timestamp)

    # Special case routing
    if event_type == "trial_start":
        apply_gauge_raw(redis_client, user_id, "is_trial_user", 1)
    elif event_type == "trial_end":
        apply_gauge_raw(redis_client, user_id, "is_trial_user", 0)

    if event_type == "login":
        apply_session_start(redis_client, user_id, timestamp)
    elif event_type == "logout":
        apply_session_end(redis_client, user_id, timestamp)
    

    # Mark processed
    mark_processed(redis_client, event_id)
    return True
