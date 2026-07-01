"""Macchina a stati dell'incidente, isolata dalle dipendenze AI e di persistenza."""

TRANSITIONS: dict[str, dict[str, str]] = {
    "TRIAGE_CLASSIFIED": {"open": "active"},
    "TRIAGE_NEEDS_CLARIFICATION": {"open": "open"},
    "RESOLUTION_STARTED": {"open": "active", "active": "active"},
    "RESOLVED": {"open": "resolved", "active": "resolved"},
    "REOPENED": {"resolved": "active"},
}


def advance_status(current: str, event: str) -> str:
    """Applica una transizione valida; altrimenti mantiene lo stato corrente."""
    return TRANSITIONS.get(event, {}).get(current, current)
