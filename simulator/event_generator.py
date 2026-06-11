# simulator/event_generator.py

import random
import time
import uuid
from typing import Optional

from simulator.personas import Persona, PERSONA_MAP
from features.contract import VALID_EVENT_TYPES


# ─────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────

SECONDS_PER_DAY     = 86400
MAX_CHURN_PROB      = 0.95    # never absolute certainty
TRIGGER_INCREMENT   = 0.05    # each trigger event adds this to churn risk
TIME_DECAY_WEIGHT   = 0.40    # max churn increase from inactivity alone
TIME_DECAY_DAYS     = 30      # days of inactivity to reach max time decay


# ─────────────────────────────────────────────────────────────
# USER STATE
# ─────────────────────────────────────────────────────────────

class UserState:
    """
    Tracks the mutable state of a single simulated user.

    This is the "memory" of the simulator for each user.
    It is updated every time an event is generated.

    Attributes:
        user_id:            Unique identifier
        persona:            The user's behavioral profile
        signup_timestamp:   When the user signed up (Unix timestamp)
        last_active_ts:     When the user last generated an event
        trigger_count:      How many churn trigger events have fired
        churned:            Whether this user has churned
        churn_timestamp:    When they churned (if they did)
        is_on_trial:        Whether user is currently on a trial
        trial_end_ts:       When their trial ended (if it did)
        session_open:       Whether a session is currently open
        session_start_ts:   When the current session started
        event_count:        Total events generated so far
    """

    def __init__(self, user_id: str, persona_name: str, now: int):
        self.user_id          = user_id
        self.persona          = PERSONA_MAP[persona_name]
        self.signup_timestamp = now
        self.last_active_ts   = now
        self.trigger_count    = 0
        self.churned          = False
        self.churn_timestamp  = None
        self.is_on_trial      = persona_name == "trial_user"
        self.trial_end_ts     = None
        self.session_open     = False
        self.session_start_ts = None
        self.event_count      = 0

    @property
    def days_since_active(self) -> float:
        now = int(time.time())
        return (now - self.last_active_ts) / SECONDS_PER_DAY

    @property
    def days_since_signup(self) -> float:
        now = int(time.time())
        return (now - self.signup_timestamp) / SECONDS_PER_DAY

    def current_churn_probability(self) -> float:
        """
        Computes the user's current churn probability.

        Three components:
            base:     persona's starting risk
            time:     grows with inactivity, caps after 30 days
            triggers: each churn trigger event adds 0.05
        """
        base         = self.persona.churn_probability_base
        time_factor  = min(self.days_since_active / TIME_DECAY_DAYS, 1.0)
        time_component    = time_factor * TIME_DECAY_WEIGHT
        trigger_component = self.trigger_count * TRIGGER_INCREMENT

        return min(
            base + time_component + trigger_component,
            MAX_CHURN_PROB
        )


# ─────────────────────────────────────────────────────────────
# CHURN DECISION
# ─────────────────────────────────────────────────────────────

CHURN_HORIZON_DAYS = 30   # churn_probability means "risk over 30 days"

def should_churn(user: UserState, ticks_per_day: int) -> bool:
    """
    Decides whether a user churns at this tick.

    current_churn_probability() is interpreted as the probability
    of churning within CHURN_HORIZON_DAYS of simulated time.
    We spread that probability across every tick in the horizon,
    so churn speed scales correctly with simulation speed.
    """
    if user.churned:
        return False

    churn_prob   = user.current_churn_probability()
    per_tick_prob = churn_prob / (CHURN_HORIZON_DAYS * ticks_per_day)
    return random.random() < per_tick_prob


# ─────────────────────────────────────────────────────────────
# EVENT SELECTION
# ─────────────────────────────────────────────────────────────

def select_event_type(user: UserState, ticks_per_day: int = 8_640_000) -> Optional[str]:
    """
    Decides which event type fires for this user this tick.

    Two stage decision:
        Stage 1: does any event fire at all?
                 → based on base_event_rate / ticks_per_day
        Stage 2: which event type fires?
                 → weighted random choice from persona event_weights

    Args:
        ticks_per_day: controls simulation speed.
                       Default 8,640,000 = real-time (100 ticks/second).
                       Use lower values for testing and fast simulation.

    Returns None if no event fires this tick.
    """
    fire_probability = user.persona.base_event_rate / ticks_per_day
    if random.random() > fire_probability:
        return None

    # filter event weights to only valid event types
    weights = {
        k: v for k, v in user.persona.event_weights.items()
        if k in VALID_EVENT_TYPES
    }

    # handle session logic
    if not user.session_open and "logout" in weights:
        weights.pop("logout")

    if not user.is_on_trial and "trial_end" in weights:
        weights.pop("trial_end")

    if user.is_on_trial and "trial_start" in weights:
        weights.pop("trial_start")

    event_types   = list(weights.keys())
    event_weights = list(weights.values())

    return random.choices(event_types, weights=event_weights, k=1)[0]


# ─────────────────────────────────────────────────────────────
# METADATA BUILDER
# ─────────────────────────────────────────────────────────────

def build_metadata(event_type: str, user: UserState) -> dict:
    """
    Builds event-specific metadata for each event type.

    Fields that don't apply to the current event type
    are set to None. This keeps the schema consistent
    across all event types.
    """
    metadata = {
        "page":           None,
        "amount":         None,
        "ticket_type":    None,
        "email_subject":  None,
        "discount_code":  None,
        "persona":        user.persona.name,
    }

    if event_type == "page_view":
        pages = ["/home", "/pricing", "/features", "/dashboard", "/settings", "/checkout"]
        metadata["page"] = random.choice(pages)

    elif event_type == "purchase":
        metadata["amount"] = round(random.uniform(9.99, 99.99), 2)
        metadata["page"]   = "/checkout"

    elif event_type == "support_ticket":
        ticket_types = ["billing", "technical", "feature_request", "account"]
        metadata["ticket_type"] = random.choice(ticket_types)

    elif event_type == "email_open":
        subjects = [
            "Your weekly summary",
            "New features available",
            "Special offer inside",
            "Tips to get more value",
            "We miss you",
        ]
        metadata["email_subject"] = random.choice(subjects)

    elif event_type == "discount_used":
        metadata["discount_code"] = f"SAVE{random.randint(10,30)}_{user.user_id[-4:]}"

    return metadata


# ─────────────────────────────────────────────────────────────
# STATE UPDATER
# ─────────────────────────────────────────────────────────────

def update_user_state(user: UserState, event_type: str, timestamp: int) -> None:
    """
    Updates UserState after an event fires.

    This mirrors what the consumer does to Redis —
    the simulator tracks the same state in memory
    so it can make realistic decisions about future events.
    """
    # update last active timestamp for engagement events
    engagement_events = {
        "login", "purchase", "page_view", "settings_change",
        "password_reset", "feedback_submitted", "discount_used", "email_open"
    }
    if event_type in engagement_events:
        user.last_active_ts = timestamp

    # increment trigger count if this is a churn trigger
    if event_type in user.persona.churn_triggers:
        user.trigger_count += 1

    # handle session state
    if event_type == "login":
        user.session_open     = True
        user.session_start_ts = timestamp

    elif event_type == "logout":
        user.session_open     = False
        user.session_start_ts = None

    # handle trial state
    if event_type == "trial_start":
        user.is_on_trial = True

    elif event_type == "trial_end":
        user.is_on_trial  = False
        user.trial_end_ts = timestamp

    user.event_count += 1


# ─────────────────────────────────────────────────────────────
# MAIN EVENT GENERATOR
# ─────────────────────────────────────────────────────────────

def generate_event(user: UserState, ticks_per_day: int = 8_640_000) -> Optional[dict]:
    """
    Attempts to generate one event for a user.

    Returns None if:
        - the user has already churned
        - no event fires this tick (base_event_rate check)

    Returns a complete event dict if an event fires,
    matching the event schema exactly.

    Also handles churn detection — if the user churns,
    marks them as churned and returns None.
    """
    # churned users generate no events
    if user.churned:
        return None

    # check if user churns this tick
    if should_churn(user, ticks_per_day):
        user.churned         = True
        user.churn_timestamp = int(time.time())
        return None

    # check if an event fires this tick
    event_type = select_event_type(user, ticks_per_day)
    if event_type is None:
        return None

    # build the event
    timestamp = int(time.time())
    event = {
        "event_id":   str(uuid.uuid4()),
        "user_id":    user.user_id,
        "event_type": event_type,
        "timestamp":  timestamp,
        "metadata":   build_metadata(event_type, user),
    }

    # update simulator's internal state
    update_user_state(user, event_type, timestamp)

    return event