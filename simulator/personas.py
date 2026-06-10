# simulator/personas.py

from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────────────────────
# PERSONA DEFINITION
# ─────────────────────────────────────────────────────────────

@dataclass
class Persona:
    """
    A complete behavioral profile for a user type.

    Attributes:
        name:
            Unique identifier for this persona.

        weight:
            Proportion of users assigned this persona.
            All weights across all personas must sum to 1.0.

        event_weights:
            Probability distribution over event types.
            Higher weight = more likely to generate that event.
            Does not need to sum to 1.0 — Python normalizes automatically.

        base_event_rate:
            Average number of events this persona generates per day.
            Controls how active this user type is overall.

        churn_probability_base:
            Starting churn risk for this persona (0.0 to 1.0).
            Modified by behavior over time.

        churn_triggers:
            Events that accelerate churn risk for this persona.
            A price_sensitive user churns faster after seeing prices.
            A trial_user churns faster as trial_end approaches.

        intervention_sensitivity:
            How likely each intervention is to prevent churn.
            Used by the simulator to decide if an intervention succeeded.
            Also used to generate realistic proxy reward signals.
    """
    name:                     str
    weight:                   float
    event_weights:            dict[str, float]
    base_event_rate:          float
    churn_probability_base:   float
    churn_triggers:           list[str]
    intervention_sensitivity: dict[str, float]


# ─────────────────────────────────────────────────────────────
# THE FIVE PERSONAS
# ─────────────────────────────────────────────────────────────

PERSONAS = [

    Persona(
        name="price_sensitive",
        weight=0.30,

        event_weights={
            "login":               0.15,
            "page_view":           0.20,
            "purchase":            0.20,
            "discount_used":       0.25,
            "email_open":          0.10,
            "support_ticket":      0.05,
            "feedback_submitted":  0.02,
            "settings_change":     0.02,
            "password_reset":      0.01,
        },

        # moderately active — engages mainly around deals
        base_event_rate=4.0,

        # moderate baseline churn risk
        churn_probability_base=0.35,

        # churns when pricing feels unfair
        churn_triggers=["support_ticket", "password_reset"],

        # responds strongly to discounts, weakly to education
        intervention_sensitivity={
            "discount":         0.80,
            "feedback_survey":  0.20,
            "education_email":  0.30,
        },
    ),

    Persona(
        name="feature_lover",
        weight=0.25,

        event_weights={
            "login":               0.15,
            "page_view":           0.25,
            "purchase":            0.10,
            "settings_change":     0.20,
            "feedback_submitted":  0.12,
            "support_ticket":      0.10,
            "email_open":          0.05,
            "discount_used":       0.02,
            "password_reset":      0.01,
        },

        # highly active — explores the product deeply
        base_event_rate=7.0,

        # lower baseline churn risk — invested in the product
        churn_probability_base=0.20,

        # churns when product doesn't meet expectations
        churn_triggers=["support_ticket", "feedback_submitted"],

        # responds strongly to education, weakly to discounts
        intervention_sensitivity={
            "discount":         0.30,
            "feedback_survey":  0.40,
            "education_email":  0.70,
        },
    ),

    Persona(
        name="casual_user",
        weight=0.25,

        event_weights={
            "login":               0.20,
            "page_view":           0.35,
            "purchase":            0.15,
            "email_open":          0.15,
            "discount_used":       0.08,
            "support_ticket":      0.04,
            "feedback_submitted":  0.02,
            "settings_change":     0.01,
            "password_reset":      0.00,
        },

        # low activity — dips in and out
        base_event_rate=2.0,

        # high baseline churn risk — shallow engagement
        churn_probability_base=0.50,

        # churns from neglect and friction
        churn_triggers=["password_reset", "support_ticket"],

        # responds moderately to everything
        intervention_sensitivity={
            "discount":         0.50,
            "feedback_survey":  0.30,
            "education_email":  0.50,
        },
    ),

    Persona(
        name="power_user",
        weight=0.15,

        event_weights={
            "login":               0.15,
            "page_view":           0.20,
            "purchase":            0.15,
            "settings_change":     0.20,
            "feedback_submitted":  0.12,
            "support_ticket":      0.10,
            "email_open":          0.05,
            "discount_used":       0.02,
            "password_reset":      0.01,
        },

        # very active — uses the product daily
        base_event_rate=10.0,

        # lowest baseline churn risk — deeply invested
        churn_probability_base=0.15,

        # churns only when product fundamentally fails them
        churn_triggers=["support_ticket", "feedback_submitted"],

        # responds to education and feedback, not discounts
        intervention_sensitivity={
            "discount":         0.20,
            "feedback_survey":  0.50,
            "education_email":  0.60,
        },
    ),

    Persona(
        name="trial_user",
        weight=0.05,

        event_weights={
            "login":               0.15,
            "page_view":           0.35,
            "purchase":            0.05,
            "trial_start":         0.10,
            "trial_end":           0.10,
            "email_open":          0.15,
            "discount_used":       0.05,
            "support_ticket":      0.03,
            "feedback_submitted":  0.01,
            "settings_change":     0.01,
            "password_reset":      0.00,
        },

        # moderate activity during trial, drops sharply after
        base_event_rate=3.0,

        # highest baseline churn risk — hasn't committed yet
        churn_probability_base=0.65,

        # churns when trial ends without seeing value
        churn_triggers=["trial_end", "support_ticket"],

        # responds strongly to education and discounts
        intervention_sensitivity={
            "discount":         0.60,
            "feedback_survey":  0.40,
            "education_email":  0.80,
        },
    ),

]


# ─────────────────────────────────────────────────────────────
# DERIVED LOOKUPS
# ─────────────────────────────────────────────────────────────

# Keyed by name for fast lookup
PERSONA_MAP: dict[str, Persona] = {
    p.name: p for p in PERSONAS
}

# Names and weights for random assignment
PERSONA_NAMES:   list[str]   = [p.name   for p in PERSONAS]
PERSONA_WEIGHTS: list[float] = [p.weight for p in PERSONAS]