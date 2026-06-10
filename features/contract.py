# features/contract.py

from enum import Enum


# ─────────────────────────────────────────────────────────────
# FEATURE CATEGORIES
# ─────────────────────────────────────────────────────────────

class FeatureType(Enum):
    """
    Every feature is one of three types.
    This determines how it is stored in Redis and how it is
    read back at prediction time.

    COUNTER         → increments by 1 on each relevant event
                      stored as a raw integer
                      example: total_purchases = 12

    WINDOW_COUNTER  → count of events within a time window
                      stored as a raw integer, backed by a sorted set
                      example: support_tickets_last_30d = 3

    GAUGE           → current state, replaced on each relevant event
                      two sub-types:
                        raw            → stored and read as-is
                        days_since_ts  → stored as Unix timestamp,
                                         converted to days at read time
                      example: is_trial_user = 1
                      example: days_since_last_active = 3 (converted from ts)
    """
    COUNTER        = "counter"
    WINDOW_COUNTER = "window_counter"
    GAUGE_RAW      = "gauge_raw"
    GAUGE_TS       = "gauge_ts"          # stored as timestamp, read as days


# ─────────────────────────────────────────────────────────────
# FEATURE DEFINITIONS
# ─────────────────────────────────────────────────────────────

FEATURES = [

    # ── RECENCY FEATURES ──────────────────────────────────────

    {
        "name":          "days_since_last_active",
        "type":          FeatureType.GAUGE_TS,
        "redis_key":     "user:{user_id}:feature:last_active_ts",
        "default":       999,
        "updated_by":    [
                            "login",
                            "purchase",
                            "page_view",
                            "settings_change",
                            "password_reset",
                            "feedback_submitted",
                            "discount_used",
                            "email_open",
                         ],
        "description":   "Days since user last performed any meaningful activity",
    },

    {
        "name":          "days_since_last_purchase",
        "type":          FeatureType.GAUGE_TS,
        "redis_key":     "user:{user_id}:feature:last_purchase_ts",
        "default":       999,
        "updated_by":    ["purchase"],
        "description":   "Days since user last made a purchase",
    },

    {
        "name":          "days_since_last_support_ticket",
        "type":          FeatureType.GAUGE_TS,
        "redis_key":     "user:{user_id}:feature:last_support_ts",
        "default":       999,
        "updated_by":    ["support_ticket"],
        "description":   "Days since user last raised a support ticket",
    },

    {
        "name":          "days_since_last_email_open",
        "type":          FeatureType.GAUGE_TS,
        "redis_key":     "user:{user_id}:feature:last_email_open_ts",
        "default":       999,
        "updated_by":    ["email_open"],
        "description":   "Days since user last opened a marketing email",
    },

    {
        "name":          "days_since_last_discount",
        "type":          FeatureType.GAUGE_TS,
        "redis_key":     "user:{user_id}:feature:last_discount_ts",
        "default":       999,
        "updated_by":    ["discount_used"],
        "description":   "Days since user last used a discount code",
    },

    {
        "name":          "days_since_last_feedback",
        "type":          FeatureType.GAUGE_TS,
        "redis_key":     "user:{user_id}:feature:last_feedback_ts",
        "default":       999,
        "updated_by":    ["feedback_submitted"],
        "description":   "Days since user last submitted feedback",
    },

    {
        "name":          "days_since_trial_end",
        "type":          FeatureType.GAUGE_TS,
        "redis_key":     "user:{user_id}:feature:trial_end_ts",
        "default":       999,
        "updated_by":    ["trial_end"],
        "description":   "Days since user trial ended",
    },

    # ── FREQUENCY FEATURES ────────────────────────────────────

    {
        "name":          "page_views_last_7d",
        "type":          FeatureType.WINDOW_COUNTER,
        "redis_key":     "user:{user_id}:feature:page_views_7d",
        "window_days":   7,
        "events_key":    "user:{user_id}:events:page_views",
        "default":       0,
        "updated_by":    ["page_view", "login", "purchase"],
        "description":   "Number of page views in the last 7 days",
    },

    {
        "name":          "page_views_last_30d",
        "type":          FeatureType.WINDOW_COUNTER,
        "redis_key":     "user:{user_id}:feature:page_views_30d",
        "window_days":   30,
        "events_key":    "user:{user_id}:events:page_views",
        "default":       0,
        "updated_by":    ["page_view", "login", "purchase"],
        "description":   "Number of page views in the last 30 days",
    },

    {
        "name":          "support_tickets_last_30d",
        "type":          FeatureType.WINDOW_COUNTER,
        "redis_key":     "user:{user_id}:feature:support_tickets_30d",
        "window_days":   30,
        "events_key":    "user:{user_id}:events:support_tickets",
        "default":       0,
        "updated_by":    ["support_ticket"],
        "description":   "Number of support tickets raised in the last 30 days",
    },

    {
        "name":          "email_opens_last_30d",
        "type":          FeatureType.WINDOW_COUNTER,
        "redis_key":     "user:{user_id}:feature:email_opens_30d",
        "window_days":   30,
        "events_key":    "user:{user_id}:events:email_opens",
        "default":       0,
        "updated_by":    ["email_open"],
        "description":   "Number of emails opened in the last 30 days",
    },

    # ── VOLUME FEATURES ───────────────────────────────────────

    {
        "name":          "total_purchases",
        "type":          FeatureType.COUNTER,
        "redis_key":     "user:{user_id}:feature:total_purchases",
        "default":       0,
        "updated_by":    ["purchase"],
        "description":   "Total number of purchases ever made",
    },

    {
        "name":          "total_support_tickets",
        "type":          FeatureType.COUNTER,
        "redis_key":     "user:{user_id}:feature:total_support_tickets",
        "default":       0,
        "updated_by":    ["support_ticket"],
        "description":   "Total number of support tickets ever raised",
    },

    {
        "name":          "total_discounts_used",
        "type":          FeatureType.COUNTER,
        "redis_key":     "user:{user_id}:feature:total_discounts_used",
        "default":       0,
        "updated_by":    ["discount_used"],
        "description":   "Total number of discount codes ever used",
    },

    {
        "name":          "total_feedback_submitted",
        "type":          FeatureType.COUNTER,
        "redis_key":     "user:{user_id}:feature:total_feedback_submitted",
        "default":       0,
        "updated_by":    ["feedback_submitted"],
        "description":   "Total number of feedback submissions ever made",
    },

    {
        "name":          "total_settings_changes",
        "type":          FeatureType.COUNTER,
        "redis_key":     "user:{user_id}:feature:total_settings_changes",
        "default":       0,
        "updated_by":    ["settings_change"],
        "description":   "Total number of settings changes ever made",
    },

    {
        "name":          "total_password_resets",
        "type":          FeatureType.COUNTER,
        "redis_key":     "user:{user_id}:feature:total_password_resets",
        "default":       0,
        "updated_by":    ["password_reset"],
        "description":   "Total number of password resets ever performed",
    },

    # ── STATE FEATURES ────────────────────────────────────────

    {
        "name":          "is_trial_user",
        "type":          FeatureType.GAUGE_RAW,
        "redis_key":     "user:{user_id}:feature:is_trial_user",
        "default":       0,
        "updated_by":    ["trial_start", "trial_end"],
        "description":   "Whether user is currently on a trial (1=yes, 0=no)",
    },

    {
        "name":          "avg_session_duration_mins",
        "type":          FeatureType.GAUGE_RAW,
        "redis_key":     "user:{user_id}:feature:avg_session_duration_mins",
        "default":       0,
        "updated_by":    ["logout"],
        "description":   "Average session duration in minutes across all sessions",
    },

]


# ─────────────────────────────────────────────────────────────
# DERIVED LOOKUPS
# Built once at import time from FEATURES above.
# These are what the rest of the system actually uses.
# ─────────────────────────────────────────────────────────────

# The ordered list of feature names exactly as the model expects them
# Position 0 in this list = position 0 in the feature vector
FEATURE_NAMES: list[str] = [f["name"] for f in FEATURES]

# Default value for every feature, keyed by name
FEATURE_DEFAULTS: dict[str, float] = {
    f["name"]: f["default"] for f in FEATURES
}

# Feature type keyed by name — used by serving layer
FEATURE_TYPES: dict[str, FeatureType] = {
    f["name"]: f["type"] for f in FEATURES
}

# Redis key template keyed by feature name
# Note: these are templates, {user_id} must be replaced at runtime
FEATURE_REDIS_KEYS: dict[str, str] = {
    f["name"]: f["redis_key"] for f in FEATURES
}

# Which features each event type should update
# Inverted index: event_type → list of feature names
EVENT_TO_FEATURES: dict[str, list[str]] = {}

for feature in FEATURES:
    for event_type in feature["updated_by"]:
        if event_type not in EVENT_TO_FEATURES:
            EVENT_TO_FEATURES[event_type] = []
        EVENT_TO_FEATURES[event_type].append(feature["name"])


# ─────────────────────────────────────────────────────────────
# VALID EVENT TYPES
# ─────────────────────────────────────────────────────────────

VALID_EVENT_TYPES: set[str] = {
    "login",
    "logout",
    "page_view",
    "purchase",
    "support_ticket",
    "trial_start",
    "trial_end",
    "email_open",
    "discount_used",
    "feedback_submitted",
    "settings_change",
    "password_reset",
}


# ─────────────────────────────────────────────────────────────
# RISK THRESHOLDS
# ─────────────────────────────────────────────────────────────

RISK_THRESHOLDS = {
    "LOW":      (0.00, 0.40),
    "MEDIUM":   (0.40, 0.60),
    "HIGH":     (0.60, 0.75),
    "CRITICAL": (0.75, 1.00),
}

INTERVENTION_THRESHOLD = 0.60    # trigger intervention at HIGH and above


# ─────────────────────────────────────────────────────────────
# PROXY REWARD WINDOW
# ─────────────────────────────────────────────────────────────

PROXY_REWARD_DAYS = 14    # user re-engaged within 14 days = intervention success