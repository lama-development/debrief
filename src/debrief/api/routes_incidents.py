"""
routes_incidents.py - CRUD incidenti + azioni di ciclo di vita.

Route sottili sopra il service layer. Tutte richiedono autenticazione.
Mappatura errori: risorsa assente -> 404; transizione di stato non valida
(il service solleva ValueError) -> 409.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from debrief import auth
from debrief.api import service

router = APIRouter(prefix="/incidents", tags=["incidents"])


class CreateIncidentRequest(BaseModel):
    description: str = Field(min_length=1)


class ResolveRequest(BaseModel):
    resolution_summary: str = Field(min_length=1)
    # `str | None = None` → campo OPZIONALE: può essere una stringa o assente (None).
    verified_solution: str | None = None


def _require_incident(incident_id: str) -> dict:
    """Restituisce il dettaglio dell'incidente o solleva 404."""
    # Helper riusato da più route: centralizza il controllo "esiste?" → 404.
    detail = service.get_incident_detail(incident_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return detail


@router.post("", status_code=201)   # 201 Created: una risorsa nuova è stata creata
def create(body: CreateIncidentRequest, user: dict = Depends(auth.current_user)):
    """Dichiara un nuovo incidente (stato 'open'). La classificazione avviene
    al primo messaggio in chat (il router instrada open -> triage)."""
    # user["id"] arriva dalla dependency: l'incidente è legato a chi lo dichiara.
    return service.create_incident(body.description, user["id"])


@router.get("")
def list_all(status: str | None = None, limit: int = 100,
            user: dict = Depends(auth.current_user)):
    """Elenca gli incidenti, opzionalmente filtrati per status."""
    # status e limit NON sono nel path: FastAPI li legge come query string
    # (es. /incidents?status=active&limit=20). I default valgono se omessi.
    return service.list_incidents(status=status, limit=limit)


@router.get("/{incident_id}")
def detail(incident_id: str, user: dict = Depends(auth.current_user)):
    """Dettaglio completo: incidente + timeline + remediation + post-mortem."""
    # {incident_id} nel path → FastAPI lo passa come argomento omonimo.
    return _require_incident(incident_id)


@router.post("/{incident_id}/resolve")
def resolve(incident_id: str, body: ResolveRequest, user: dict = Depends(auth.current_user)):
    """Chiude l'incidente e lancia il loop di apprendimento."""
    _require_incident(incident_id)   # prima un 404 pulito se non esiste
    try:
        return service.resolve_incident(
            incident_id, body.resolution_summary, user["username"], body.verified_solution
        )
    except ValueError as e:
        # Il service solleva ValueError se la transizione di stato non è valida → 409.
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{incident_id}/reopen")
def reopen(incident_id: str, user: dict = Depends(auth.current_user)):
    """Riapre un incidente risolto (torna 'active')."""
    _require_incident(incident_id)
    try:
        return service.reopen_incident(incident_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
