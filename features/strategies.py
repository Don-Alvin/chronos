import time
from redis import Redis
from features.redis_keys import session_start_key, window_events_key, feature_key

SECONDS_PER_DAY = 86400
SESSION_TTL_SECONDS = 86400
PROCESSED_EVENT_TTL_SECONDS = 86400

def apply_counter(
    redis_client: Redis,
    user_id: str,
    feature_name: str,
) -> int:
    key = feature_key(user_id, feature_name)
    return redis_client.incr(key)

def apply_window_counter(
    redis_client: Redis,
    user_id: str,
    feature_name: str,
    event_id: str,
    timestamp: int,
    window_days: int
) -> int:
    events_key = window_events_key(user_id, feature_name)
    feat_key = feature_key(user_id, feature_name)
    cutoff = timestamp - (window_days * SECONDS_PER_DAY)

    pipe = redis_client.pipeline()
    pipe.zadd(events_key, {event_id: timestamp})
    pipe.zremrangebyscore(events_key, 0, cutoff)
    pipe.zcount(events_key, cutoff, timestamp)
    results = pipe.execute()

    count = results[2]
    redis_client.set(feat_key, count)

    return count

def apply_gauge_raw(
    redis_client: Redis,
    user_id: str,
    feature_name: str,
    value: float
) -> None:
    key = feature_key(user_id, feature_name)
    redis_client.set(key, value)
    return value

def apply_gauge_ts(
    redis_client: Redis,
    user_id: str,
    feature_name: str,
    timestamp: int
) -> None:
    key = feature_key(user_id, feature_name)
    redis_client.set(key, timestamp)

def apply_session_start(
    redis_client: Redis,
    user_id: str,
    timestamp: int
) -> None:
    key = session_start_key(user_id)
    redis_client.set(key, timestamp)
    redis_client.expire(key, SESSION_TTL_SECONDS)

def apply_session_end(
    redis_client: Redis,
    user_id: str,
    timestamp: int
) -> None:
    start_key = session_start_key(user_id)
    start_ts = redis_client.get(start_key)

    if start_ts is None:
        return
    
    start_ts = int(start_ts)
    duration_mins = (timestamp - start_ts) / 60

    if duration_mins <= 0 or duration_mins > 1440:
        redis_client.delete(start_key)
        return
    
    avg_key = feature_key(user_id, "avg_session_duration_mins")
    count_key = f"user:{user_id}:session:count"

    pipe = redis_client.pipeline()
    pipe.get(avg_key)
    pipe.incr(count_key)
    results = pipe.execute()

    old_avg = float(results[0]) if results[0] else 0.0
    new_count = int(results[1])
    new_avg = (old_avg * (new_count - 1) + duration_mins) / new_count

    redis_client.set(avg_key, round(new_avg, 2))
    redis_client.delete(start_key)

def timestamp_to_days(stored_timestamp: int, now: int = None) -> float:
    if now is None:
        now = int(time.time())
    days = (now - stored_timestamp) / SECONDS_PER_DAY
    return round(max(days, 0.0), 2)
