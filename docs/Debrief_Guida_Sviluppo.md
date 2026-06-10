# Debrief – Guida Operativa di Sviluppo

Riferimento compatto da tenere aperto accanto all'editor.
La documentazione completa con le motivazioni è nel PDF (23 pagine).

## Struttura del repo

```
debrief/
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
├── src/debrief/
│   ├── __init__.py
│   ├── config.py                # modelli, soglie, path DB
│   ├── schemas.py               # Pydantic: TriageOutput, PostMortem, VerifiedSolution
│   ├── database.py              # setup SQLite + tabelle
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── triage.py
│   │   ├── investigator.py
│   │   ├── resolver.py
│   │   └── orchestrator.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── search.py            # search_past_incidents, search_kb, search_verified
│   │   ├── db_read.py           # get_teams_catalog, get_incident_timeline
│   │   └── embedding.py         # sentence-transformers locale
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── indexer.py           # scrittura in LanceDB
│   │   └── retriever.py         # ricerca + soglia
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py               # FastAPI app (lifespan, CORS, router, /health)
│   │   ├── service.py           # macchina a stati + lifecycle + chat streaming + learning loop
│   │   ├── routes_incidents.py  # CRUD incidenti + resolve/archive/reopen
│   │   ├── routes_chat.py       # chat con SSE streaming
│   │   ├── routes_metrics.py    # MTTR, conteggi
│   │   └── routes_auth.py       # register/login/logout/me
│   └── auth.py                  # hashing bcrypt, token di sessione, current_user
├── seed/
│   ├── incidents.json           # incidenti mock con cluster
│   ├── verified_solutions.json  # soluzioni umane di esempio
│   ├── teams.json               # catalogo team
│   ├── knowledge_base/          # runbook markdown
│   │   ├── db_failover.md
│   │   ├── network_troubleshooting.md
│   │   ├── plc_error_handling.md
│   │   ├── email_client_issues.md
│   │   └── disk_space_management.md
│   ├── cluster_map.json         # GROUND TRUTH: quale incidente appartiene a quale cluster
│   └── run_seed.py              # popola SQLite + LanceDB
├── eval/
│   ├── test_triage.json         # descrizioni con severità/categoria attese
│   ├── test_routing.json        # messaggi con agente atteso
│   ├── test_retrieval.json      # query con incidenti simili attesi (da cluster_map)
│   ├── test_injection.json      # input ostili (red-team)
│   └── run_eval.py              # uv run eval
├── frontend/                    # React + shadcn (ULTIMO)
└── data/                        # generato a runtime, in .gitignore
    ├── debrief.db               # SQLite
    └── lancedb/                 # LanceDB
```

## Schemi Pydantic (src/debrief/schemas.py)

```python
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime

class Category(str, Enum):
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    DATABASE = "database"
    NETWORK = "network"
    SECURITY = "security"
    DEPLOYMENT = "deployment"
    HARDWARE = "hardware"        # PLC, macchinari
    HELPDESK = "helpdesk"        # posta, postazioni
    THIRD_PARTY = "third_party"
    OTHER = "other"

class Severity(str, Enum):
    SEV1 = "SEV1"  # critico: linea ferma, impatto su produzione/clienti
    SEV2 = "SEV2"  # alto: degrado significativo
    SEV3 = "SEV3"  # moderato: workaround disponibile
    SEV4 = "SEV4"  # basso: impatto minimo/cosmetico

class IncidentStatus(str, Enum):
    DECLARED = "declared"
    TRIAGE = "triage"
    AWAITING_DETAILS = "awaiting_details"
    ACTIVE = "active"
    IN_RESOLUTION = "in_resolution"
    RESOLVED = "resolved"
    ARCHIVED = "archived"

class TriageOutput(BaseModel):
    title: str
    category: Category
    severity: Severity
    affected_systems: list[str]
    suggested_teams: list[str]       # SOLO valori dal catalogo team
    summary: str
    needs_clarification: bool
    clarifying_questions: list[str]
    confidence: float = Field(ge=0, le=1)

class TimelineEvent(BaseModel):
    timestamp: datetime
    event_type: str                  # "message", "triage", "escalation", "resolution", "involvement"
    actor: str                       # user_id o agent name
    content: str

class PostMortem(BaseModel):
    incident_id: str
    title: str
    severity: Severity
    timeline: list[TimelineEvent]
    impact: str
    detection: str
    root_cause: str
    resolution_steps: list[str]
    action_items: list[str]
    references: list[str]            # id di incidenti/KB citati

class VerifiedSolution(BaseModel):
    incident_id: str
    problem_context: str
    solution: str
    provided_by: str
    created_at: datetime

class RemediationStep(BaseModel):
    description: str
    completed: bool = False
    source: str                      # "verified_solution:#id" | "past_incident:#id" | "knowledge_base" | "general"
```

## Schema SQLite (src/debrief/database.py)

```
users           (id, username, password_hash, created_at)
incidents       (id, title, description, category, severity, status, created_by, created_at, updated_at, session_id)
timeline_events (id, incident_id, timestamp, event_type, actor, content)
teams           (id, name, description, contact_info)
remediation     (id, incident_id, description, completed, source)
post_mortems    (id, incident_id, content_json, created_at)
```

## Collezioni LanceDB

| Collezione | Contenuto | Testo incorporato | Priorità retrieval |
|---|---|---|---|
| `verified_solutions` | Soluzioni fornite da umani | problem_context + solution | ALTA |
| `past_incidents` | Incidenti chiusi + post-mortem | description + root_cause + resolution | MEDIA |
| `knowledge_base` | Runbook/playbook | testo completo (chunked se lungo) | BASE |

## Tool per agente

**Triage:**
- `get_teams_catalog()` – sola lettura, restituisce lista team da seed

**Investigator:**
- `search_past_incidents(query: str, k: int = 5)` – LanceDB, sola lettura
- `get_incident_timeline(incident_id: str)` – SQLite, sola lettura

**Resolver:**
- `search_verified_solutions(query: str, k: int = 3)` – LanceDB, sola lettura
- `search_knowledge_base(query: str, k: int = 3)` – LanceDB, sola lettura
- `search_past_incidents(query: str, k: int = 5)` – LanceDB, sola lettura

**Orchestratore:**
- nessun tool, solo routing (output: enum agente)

Tutti gli output strutturati passano per validazione Pydantic nel livello applicativo PRIMA della scrittura nel DB.

## Modelli Groq (da config.py)

| Componente | Modello | Motivazione |
|---|---|---|
| Orchestratore | `llama-3.1-8b-instant` | veloce, output cortissimo |
| Triage | `gpt-oss-20b` | buon rapporto velocità/capacità per JSON strutturato |
| Investigator | `llama-3.3-70b-versatile` | ragionamento su evidenze |
| Resolver | `llama-3.3-70b-versatile` | output lungo e ragionato |
| Embedding | `all-MiniLM-L6-v2` (locale) | costo zero |

Verifica disponibilità su console.groq.com prima di iniziare. I nomi stanno in `config.py`, MAI hardcoded altrove.

## Mappa cluster per il seed

Ogni cluster = 3-4 incidenti dello stesso tipo descritti con parole diverse.
Segnare in `cluster_map.json` per la ground truth del retrieval.

| Cluster | Categoria | Esempi di varianti |
|---|---|---|
| `db_connection_pool` | DATABASE | "pool esaurito", "troppe connessioni", "timeout query sotto carico" |
| `network_latency` | NETWORK | "latenza anomala", "pacchetti persi", "switch instabile" |
| `plc_error` | HARDWARE | "PLC fermo linea 2", "errore comunicazione PLC", "allarme macchinario" |
| `disk_full` | INFRASTRUCTURE | "disco pieno /var", "spazio esaurito DB", "log non ruotati" |
| `email_client` | HELPDESK | "Outlook non sincronizza", "posta bloccata", "allegati non si aprono" |
| `deploy_failure` | DEPLOYMENT | "deploy rotto in prod", "rollback fallito", "container non parte" |
| `vpn_access` | NETWORK | "VPN non si connette", "timeout VPN remoto", "certificato VPN scaduto" |

## Checklist di sviluppo

- [x] Scheletro repo + `uv sync`
- [x] Seed: scrivere `incidents.json` con cluster + `cluster_map.json`
- [x] Seed: `teams.json`, `verified_solutions.json`, runbook markdown
- [x] Seed: `run_seed.py` (popola SQLite + LanceDB)
- [x] Embedding: caricamento modello locale, funzione `embed(text)`
- [x] RAG retriever: `search(collection, query, k, threshold)` con soglia
- [x] Agente triage: system prompt + output TriageOutput + validazione
- [x] Agente investigator: system prompt + grounded + provenance
- [x] Agente resolver: system prompt + ibrido + escalation HITL + cattura VerifiedSolution
- [x] Orchestratore: routing LLM su modello piccolo
- [x] API: CRUD incidenti + endpoint metriche
- [x] API: chat con SSE streaming
- [x] API: auth (register/login, hashing bcrypt)
- [x] Service layer: macchina a stati + lifecycle + learning loop (`api/service.py`)
- [ ] Eval: dataset di test (triage, routing, retrieval, injection)
- [ ] Eval: `run_eval.py` con metriche per agente
- [ ] Frontend: dashboard + dettaglio incidente + chat (3 schermate)
- [ ] Demo: happy path end-to-end + dimostrazione loop apprendimento
- [ ] Relazione finale

## Comandi chiave

```bash
uv sync                    # installa dipendenze
uv run seed                # popola DB da zero
uv run dev                 # avvia backend (FastAPI)
uv run eval                # esegue valutazione
```

## Soglie da calibrare

- Similarità minima retrieval: partire da 0.65, regolare osservando i risultati
- Top-k retrieval: 5 per past_incidents, 3 per verified_solutions e KB
- Retry su JSON malformato: max 2 tentativi
- Temperatura LLM: 0 per triage/routing (deterministico), 0.3-0.5 per resolver (creatività controllata)
