"""Schemi Pydantic condivisi dall'applicazione."""

from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class Severity(str, Enum):
    SEV1 = "SEV1"
    SEV2 = "SEV2"
    SEV3 = "SEV3"
    SEV4 = "SEV4"


class AgentRole(str, Enum):
    """Risposta dell'orchestratore: quale agente attivare."""
    TRIAGE = "triage"
    INVESTIGATOR = "investigator"
    RESOLVER = "resolver"
    OVERRIDE = "override"
    NONE = "none"


class TriageOutput(BaseModel):
    """Risposta del triage, validata prima della scrittura nel database."""
    title: str
    severity: Severity
    suggested_teams: list[str] = []
    summary: str
    needs_clarification: bool = False
    clarifying_questions: list[str] = []
    confidence: float = Field(ge=0.0, le=1.0)


class TimelineEvent(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: str
    actor: str
    content: str


class DebriefReport(BaseModel):
    """Report generato dal Resolver e salvato come JSON alla chiusura."""
    incident_id: str
    title: str
    severity: Severity
    timeline: list[TimelineEvent]
    resolution: str = ""



class ClassificationOverrideRequest(BaseModel):
    """Richiesta di modifica manuale a severità e team coinvolti."""
    severity: Severity | None = None
    add_teams: list[str] = []
    remove_teams: list[str] = []


class OverrideParams(BaseModel):
    """Parametri estratti quando l'orchestratore riconosce una modifica manuale."""
    severity: Severity | None = None
    add_teams: list[str] = []
    remove_teams: list[str] = []
    description: str = ""


class RoutingDecision(BaseModel):
    """Decisione strutturata dell'orchestratore."""
    agent: AgentRole
    reason: str = ""
    override_params: OverrideParams | None = None
