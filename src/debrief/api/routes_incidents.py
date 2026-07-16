"""Endpoint autenticati per incidenti e ciclo di vita."""

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
    if user_id is not None and not service.can_access_incident(incident_id, user_id):
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    detail = service.get_incident_detail(incident_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    if user_id is not None:
        service.join_incident(incident_id, user_id)
        detail = service.get_incident_detail(incident_id)
        assert detail is not None
    return detail


@router.post("", status_code=201)
def create(body: CreateIncidentRequest, user: dict = Depends(auth.current_user)):
    """Dichiara un incidente da classificare in chat."""
    return service.create_incident(body.description, user["id"])


@router.get("")
def list_all(status: str | None = None, limit: int = 100,
            user: dict = Depends(auth.current_user)):
    """Elenca gli incidenti, eventualmente filtrati per stato."""
    return service.list_incidents(user["id"], status=status, limit=limit)


@router.get("/{incident_id}")
def detail(incident_id: str, user: dict = Depends(auth.current_user)):
    """Restituisce incidente, timeline, soluzione e debriefing."""
    return _require_incident(incident_id, user["id"])


@router.post("/{incident_id}/resolve")
def resolve(incident_id: str, body: ResolveRequest, user: dict = Depends(auth.current_user)):
    """Chiude l'incidente e avvia il ciclo di apprendimento."""
    _require_incident(incident_id, user["id"])
    try:
        return service.resolve_incident(incident_id, body.resolution_summary, user["id"])
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{incident_id}/reopen")
def reopen(incident_id: str, user: dict = Depends(auth.current_user)):
    """Riapre un incidente risolto (torna 'active')."""
    _require_incident(incident_id, user["id"])
    try:
        return service.reopen_incident(incident_id, user["username"])
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
    """Applica una modifica manuale e la registra nella timeline."""
    _require_incident(incident_id, user["id"])
    try:
        return service.override_classification(incident_id, body, user["username"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
