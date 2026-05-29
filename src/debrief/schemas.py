"""Schemi Pydantic per tutti gli output strutturati del sistema."""

from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


# --- Enum ---

class Category(str, Enum):
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    DATABASE = "database"
    NETWORK = "network"
    SECURITY = "security"
    DEPLOYMENT = "deployment"
    HARDWARE = "hardware"
    HELPDESK = "helpdesk"
    THIRD_PARTY = "third_party"
    OTHER = "other"


class Severity(str, Enum):
    SEV1 = "SEV1"
    SEV2 = "SEV2"
    SEV3 = "SEV3"
    SEV4 = "SEV4"


class IncidentStatus(str, Enum):
    DECLARED = "declared"
    TRIAGE = "triage"
    AWAITING_DETAILS = "awaiting_details"
    ACTIVE = "active"
    IN_RESOLUTION = "in_resolution"
    RESOLVED = "resolved"
    ARCHIVED = "archived"


class AgentRole(str, Enum):
    """Output dell'orchestratore: quale agente attivare."""
    TRIAGE = "triage"
    INVESTIGATOR = "investigator"
    RESOLVER = "resolver"
    NONE = "none"


# --- Output strutturati ---

class TriageOutput(BaseModel):
    """Output del triage agent. Validato prima della scrittura nel DB."""
    title: str
    category: Category
    severity: Severity
    affected_systems: list[str] = []
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


class PostMortem(BaseModel):
    """Generato dal resolver alla chiusura. Re-indicizzato in LanceDB."""
    incident_id: str
    title: str
    severity: Severity
    timeline: list[TimelineEvent]
    impact: str
    detection: str
    root_cause: str
    resolution_steps: list[str]
    action_items: list[str]
    references: list[str] = []


class VerifiedSolution(BaseModel):
    """Soluzione fornita da un umano e catturata dal resolver.
    Indicizzata in LanceDB come fonte ad alta priorità."""
    incident_id: str
    problem_context: str
    solution: str
    provided_by: str
    created_at: datetime = Field(default_factory=datetime.now)


class RemediationStep(BaseModel):
    description: str
    completed: bool = False
    source: str  # "verified_solution:#id" | "past_incident:#id" | "knowledge_base" | "general"


class RoutingDecision(BaseModel):
    """Output dell'orchestratore."""
    agent: AgentRole
    reason: str = ""
