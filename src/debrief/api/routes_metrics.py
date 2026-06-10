"""
routes_metrics.py - Metriche aggregate per la dashboard.
"""

from fastapi import APIRouter, Depends

from debrief import auth
from debrief.api import service

# Niente prefix qui: la route è semplicemente /metrics.
router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def metrics(user: dict = Depends(auth.current_user)):
    """Conteggi (per status/severity/category), totale e MTTR (secondi)."""
    # Route sottile: delega tutto il calcolo al service layer e restituisce il dict.
    return service.get_metrics()
