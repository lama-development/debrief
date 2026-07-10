"""
routes_metrics.py - Metriche aggregate per la dashboard.
"""

from datetime import datetime

from fastapi import APIRouter, Depends

from debrief import auth
from debrief.api import service

# Niente prefix qui: la route è semplicemente /metrics.
router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def metrics(user: dict = Depends(auth.current_user)):
    """Conteggi (per status/severity), totale e MTTR (secondi)."""
    # Route sottile: delega tutto il calcolo al service layer e restituisce il dict.
    incidents = service.list_incidents(user["id"], limit=10000)
    by_status: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    durations: list[float] = []
    for incident in incidents:
        by_status[incident["status"]] = by_status.get(incident["status"], 0) + 1
        if incident.get("severity"):
            severity = incident["severity"]
            by_severity[severity] = by_severity.get(severity, 0) + 1
        if incident.get("resolved_at"):
            created = datetime.fromisoformat(incident["created_at"])
            resolved = datetime.fromisoformat(incident["resolved_at"])
            durations.append((resolved - created).total_seconds())
    return {
        "by_status": by_status,
        "by_severity": by_severity,
        "mttr_seconds": sum(durations) / len(durations) if durations else None,
        "total": len(incidents),
    }
