import time
from dataclasses import dataclass
from typing import Optional

from features.contract import VALID_EVENT_TYPES

@dataclass
class ValidationResult:
    """
    Represents the result of a validation operation.

    is_valid: Indicates whether the validation was successful.
    error_type: The type of error encountered during validation, if any.
    error_message: A descriptive message providing details about the validation error, if any.
    """

    is_valid: bool
    error_type: Optional[str] = None
    error_message: Optional[str] = None

def valid() -> ValidationResult:
    """
    Returns a ValidationResult indicating a successful validation.
    """
    return ValidationResult(is_valid=True)

def invalid(error_type: str, error_message: str) -> ValidationResult:
    """
    Returns a ValidationResult indicating a failed validation.

    Args:
        error_type: The type of error encountered during validation.
        error_message: A descriptive message providing details about the validation error.

    Returns:
        ValidationResult: An instance representing the failed validation.
    """
    return ValidationResult(is_valid=False, error_type=error_type, error_message=error_message)

def validate_event(event: dict) -> ValidationResult:
    """
    Check an event against every validation rule.
    Returns on first failure
    """
    # Rule 0: Event must be a dict
    if not isinstance(event, dict):
        return invalid("invalid_type", "Event must be a JSON object")
    
    # Rule 1: Must have event_id (non-empty string)
    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not event_id.strip():
        return invalid("missing_event_id", "Event must have a non-empty string 'event_id' field")
    
    # Rule 2: Must have user_id (non-empty string)
    user_id = event.get("user_id")
    if not isinstance(user_id, str) or not user_id.strip():
        return invalid("missing_user_id", "Event must have a non-empty string 'user_id' field")
    
    # Rule 3: Must have event_type (string in VALID_EVENT_TYPES)
    event_type = event.get("event_type")
    if event_type not in VALID_EVENT_TYPES:
        return invalid("invalid_event_type", f"Event 'event_type' must be one of {VALID_EVENT_TYPES}")
    
    # Rule 4: Must have timestamp (positive integer)
    timestamp = event.get("timestamp")
    if not isinstance(timestamp, int) or isinstance(timestamp, bool) or timestamp <= 0:
        return invalid("invalid_timestamp", "Event 'timestamp' must be a positive integer")
    
    # Allow small clock skew but reject events with timestamps more than 24 hours in the future
    if timestamp > int(time.time()) + 86400:
        return invalid("timestamp_in_future", "Event 'timestamp' cannot be more than 24 hours in the future")
    
    # Rule 5: metadata must be a dict
    metadata = event.get("metadata")
    if not isinstance(metadata, dict):
        return invalid("invalid_metadata", "Event 'metadata' field must be a JSON object")
    
    return valid()

# DLQ Payload builder

def build_dlq_payload(raw_event: dict, result: ValidationResult, consumer_id: str) -> dict:
    """
    Builds a payload for the Dead Letter Queue (DLQ) containing the original event, validation result, and consumer ID.
    """
    return {
        "original_event": raw_event,
        "error_type": result.error_type,
        "error_message": result.error_message,
        "failed_at": int(time.time()),
        "consumer_id": consumer_id
    }