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
from debrief.schemas import ClassificationOverrideRequest

router = APIRouter(prefix="/incidents", tags=["incidents"])


class CreateIncidentRequest(BaseModel):
    description: str = Field(min_length=1)


class ResolveRequest(BaseModel):
    resolution_summary: str = Field(min_length=1)


class HumanSolutionRequest(BaseModel):
    solution: str = Field(min_length=3)


def _require_incident(incident_id: str, user_id: str | None = None) -> dict:
    """Restituisce il dettaglio dell'incidente o solleva 404."""
    # Helper riusato da più route: centralizza il controllo "esiste?" → 404.
    detail = service.get_incident_detail(incident_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    if user_id is not None:
        service.join_incident(incident_id, user_id)
        detail = service.get_incident_detail(incident_id)
        assert detail is not None
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
    return service.list_incidents(user["id"], status=status, limit=limit)


@router.get("/{incident_id}")
def detail(incident_id: str, user: dict = Depends(auth.current_user)):
    """Dettaglio completo: incidente + timeline + remediation + debriefing."""
    # {incident_id} nel path → FastAPI lo passa come argomento omonimo.
    return _require_incident(incident_id, user["id"])


@router.post("/{incident_id}/resolve")
def resolve(incident_id: str, body: ResolveRequest, user: dict = Depends(auth.current_user)):
    """Chiude l'incidente e lancia il loop di apprendimento."""
    _require_incident(incident_id, user["id"])
    try:
        return service.resolve_incident(incident_id, body.resolution_summary, user["username"])
    except ValueError as e:
        # Il service solleva ValueError se la transizione di stato non è valida → 409.
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{incident_id}/reopen")
def reopen(incident_id: str, user: dict = Depends(auth.current_user)):
    """Riapre un incidente risolto (torna 'active')."""
    _require_incident(incident_id, user["id"])
    try:
        return service.reopen_incident(incident_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{incident_id}/human-solutions", status_code=201)
def add_human_solution(
    incident_id: str,
    body: HumanSolutionRequest,
    user: dict = Depends(auth.current_user),
):
    """Cattura un contributo umano e lo rende riutilizzabile dal RAG."""
    _require_incident(incident_id, user["id"])
    return service.capture_human_solution(incident_id, body.solution, user["username"])


@router.patch("/{incident_id}/classification")
def override_classification(
    incident_id: str,
    body: ClassificationOverrideRequest,
    user: dict = Depends(auth.current_user),
):
    """Override umano di severità e/o team. Loga la modifica in timeline."""
    _require_incident(incident_id, user["id"])
    try:
        return service.override_classification(incident_id, body, user["username"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
