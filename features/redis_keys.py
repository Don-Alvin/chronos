from features.contract import FEATURES, FEATURE_REDIS_KEYS

KNOWN_USERS_KEY = "known_users"

def feature_key(user_id: str, feature_name: str) -> str:
    template = FEATURE_REDIS_KEYS[feature_name]
    return template.replace("{user_id}", user_id)

def all_feature_keys(user_id: str) -> dict[str, str]:
    return {
        feature_name: feature_key(user_id, feature_name)
        for feature_name in FEATURE_REDIS_KEYS
    }

def window_events_key(user_id: str, feature_name: str) -> str:
    feature = next(f for f in FEATURES if f['name'] == feature_name)
    return feature['events_key'].replace("{user_id}", user_id)

def session_start_key(user_id: str) -> str:
    return f"user:{user_id}:session:login_start"

def processed_event_key(event_id: str) -> str:
    return f"processed:events:{event_id}"

def bandit_count_key(user_id: str, intervention: str) -> str:
    return f"bandit:{user_id}:{intervention}:count"

def bandit_success_key(user_id: str, intervention: str) -> str:
    return f"bandit:{user_id}:{intervention}:success"

def bandit_q_value_key(user_id: str, intervention: str) -> str:
    return f"bandit:{user_id}:{intervention}:q_value"