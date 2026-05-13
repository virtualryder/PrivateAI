"""
Thin wrapper around database.add_audit_event for convenience.
Import and call log() anywhere in the app to record an audit event.
"""

from core.database import add_audit_event


def log(
    event_type: str,
    user_id: str,
    details: dict | None = None,
    model_used: str | None = None,
    local_only: bool = True,
) -> None:
    """
    Log an event to the audit trail.

    event_type: "query" | "ingest" | "key_load" | "settings_change" | "error"
    details: arbitrary dict (will be JSON-serialized)
    model_used: e.g. "ollama/llama3" or "openai/gpt-4o"
    local_only: False if the event sent data to an external API
    user_id: the authenticated user's ID
    """
    try:
        add_audit_event(
            event_type=event_type,
            user_id=user_id,
            details=details,
            model_used=model_used,
            local_only=local_only,
        )
    except Exception:
        pass  # Audit log failures must never crash the main app
