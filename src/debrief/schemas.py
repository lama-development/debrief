"""Schemi Pydantic per tutti gli output strutturati del sistema.

Pydantic è la libreria che definisce la "forma" dei dati. Una classe che eredita
da BaseModel diventa un modello con campi tipizzati: Pydantic VALIDA i dati in
ingresso (tipi giusti? campi obbligatori presenti? valori nei range?) e li
converte automaticamente. È fondamentale qui perché gli LLM restituiscono testo
"libero": questi schemi sono il contratto che obbliga l'output ad avere una
struttura precisa, altrimenti viene scartato.
"""

# `Enum` = enumerazione: un insieme chiuso di valori ammessi (come un menu a
# tendina). Impedisce valori arbitrari: una Severity può essere SOLO una di queste.
from enum import Enum
from datetime import datetime
# BaseModel = la classe base di ogni schema. Field = serve a dare regole extra a
# un campo (default, vincoli come "deve essere tra 0 e 1", ecc.).
from pydantic import BaseModel, Field


# Enum
# Ereditare sia da `str` che da `Enum` (str, Enum) rende ogni valore al tempo
# stesso una stringa: comodo perché si serializza in JSON come testo ("SEV1")
# invece che come oggetto Python.
class Severity(str, Enum):
    # Scala di gravità: SEV1 = critico, SEV4 = basso impatto.
    SEV1 = "SEV1"
    SEV2 = "SEV2"
    SEV3 = "SEV3"
    SEV4 = "SEV4"


class AgentRole(str, Enum):
    """Output dell'orchestratore: quale agente attivare."""
    TRIAGE = "triage"
    INVESTIGATOR = "investigator"
    RESOLVER = "resolver"
    OVERRIDE = "override"
    NONE = "none"


# Output strutturati
class TriageOutput(BaseModel):
    """Output del triage agent. Validato prima della scrittura nel DB."""
    # Ogni riga è un campo con il suo tipo. Senza "= valore" il campo è OBBLIGATORIO.
    title: str
    severity: Severity        # deve essere uno dei valori dell'Enum Severity
    # `list[str]` = lista di stringhe. "= []" la rende opzionale, con lista vuota
    # come default. (Nota: in Pydantic v2 i default mutabili come [] sono gestiti
    # in modo sicuro, ogni istanza ottiene la propria lista.)
    suggested_teams: list[str] = []
    summary: str
    needs_clarification: bool = False          # serve chiedere chiarimenti all'utente?
    clarifying_questions: list[str] = []
    # Field(ge=0.0, le=1.0): vincolo di validazione. ge = "greater or equal",
    # le = "less or equal". La confidence DEVE stare tra 0.0 e 1.0.
    confidence: float = Field(ge=0.0, le=1.0)


class TimelineEvent(BaseModel):
    # default_factory=datetime.now: invece di un valore fisso, chiama la funzione
    # datetime.now al momento della creazione → ogni evento prende l'ora corrente.
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
    resolution: str = ""


class VerifiedSolution(BaseModel):
    """Soluzione fornita da un umano e catturata dal resolver.
    Indicizzata in LanceDB come fonte ad alta priorità."""
    id: str
    incident_id: str
    problem_context: str
    solution: str
    provided_by: str
    created_at: datetime = Field(default_factory=datetime.now)


class ClassificationOverrideRequest(BaseModel):
    """Richiesta di override umano su severità e/o team coinvolti."""
    severity: Severity | None = None
    add_teams: list[str] = []
    remove_teams: list[str] = []
    reason: str | None = None


class OverrideParams(BaseModel):
    """Parametri estratti dall'orchestratore quando riconosce un intent di override."""
    severity: Severity | None = None
    add_teams: list[str] = []
    remove_teams: list[str] = []
    description: str = ""


class RoutingDecision(BaseModel):
    """Output dell'orchestratore."""
    agent: AgentRole           # quale agente deve rispondere
    reason: str = ""           # motivazione (una frase), utile per debug/log
    override_params: OverrideParams | None = None  # valorizzato solo se agent == "override"
