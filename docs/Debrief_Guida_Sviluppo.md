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
│   ├── teams.json               # catalogo team
│   ├── knowledge_base/          # runbook markdown
│   │   ├── db_failover.md
│   │   ├── network_troubleshooting.md
│   │   ├── plc_error_handling.md
│   │   ├── email_client_issues.md
│   │   └── disk_space_management.md
│   └── run_seed.py              # popola SQLite + LanceDB
├── eval/
│   ├── cases.json               # pochi casi rappresentativi per tutte le suite AI
│   ├── smoke_demo.py            # demo end-to-end su database temporanei
│   ├── run_eval.py              # unico runner delle metriche AI (`uv run eval`)
│   └── __init__.py
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

class Severity(str, Enum):
    SEV1 = "SEV1"  # critico: linea ferma, impatto su produzione/clienti
    SEV2 = "SEV2"  # alto: degrado significativo
    SEV3 = "SEV3"  # moderato: workaround disponibile
    SEV4 = "SEV4"  # basso: impatto minimo/cosmetico

class IncidentStatus(str, Enum):
    OPEN = "open"          # dichiarato / in triage / in attesa di dettagli
    ACTIVE = "active"      # classificato e in lavorazione (inclusa la risoluzione)
    RESOLVED = "resolved"  # chiuso (riapribile)

class TriageOutput(BaseModel):
    title: str
    severity: Severity
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
    resolution: str

class VerifiedSolution(BaseModel):
    id: str
    incident_id: str
    problem_context: str
    solution: str
    provided_by: str
    created_at: datetime
```

## Schema SQLite (src/debrief/database.py)

```
users           (id, username, password_hash, created_at)
incidents       (id, title, description, severity, status, created_by, created_at, updated_at)
incident_participants (incident_id, user_id, joined_at, last_activity_at)
verified_solutions    (id, incident_id, problem_context, solution, provided_by, created_at)
timeline_events (id, incident_id, timestamp, event_type, actor, content)
teams           (id, name, description, contact_info)
post_mortems    (id, incident_id, content_json, created_at)
```

## Collezioni LanceDB

| Collezione           | Contenuto                      | Testo incorporato                     | Priorità retrieval |
| -------------------- | ------------------------------ | ------------------------------------- | ------------------ |
| `verified_solutions` | Soluzioni fornite da umani     | problem_context + solution            | ALTA               |
| `past_incidents`     | Incidenti chiusi + post-mortem | description + root_cause + resolution | MEDIA              |
| `knowledge_base`     | Runbook/playbook               | testo completo (chunked se lungo)     | BASE               |

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

| Componente    | Modello                     | Motivazione                                          |
| ------------- | --------------------------- | ---------------------------------------------------- |
| Orchestratore | `llama-3.1-8b-instant`      | veloce, output cortissimo                            |
| Triage        | `gpt-oss-20b`               | buon rapporto velocità/capacità per JSON strutturato |
| Investigator  | `llama-3.3-70b-versatile`   | ragionamento su evidenze                             |
| Resolver      | `llama-3.3-70b-versatile`   | output lungo e ragionato                             |
| Embedding     | `all-MiniLM-L6-v2` (locale) | costo zero                                           |

Verifica disponibilità su console.groq.com prima di iniziare. I nomi stanno in `config.py`, MAI hardcoded altrove.

## Ground truth del retrieval

Dataset seed compatto: **11 incidenti** che coprono tutti i casi (3 stati + severità
SEV1-SEV4 + categorie varie). Solo gli incidenti **risolti** finiscono nel RAG; di
questi, i gruppi di incidenti simili fanno da ground truth del retrieval. I relativi
ID attesi sono dichiarati direttamente in `eval/cases.json`, evitando una seconda
mappa duplicata. Gli incidenti `active`/`open` mostrano gli altri stati in dashboard.

| Cluster (risolti)    | Categoria | Incidenti                 |
| -------------------- | --------- | ------------------------- |
| `plc_error`          | HARDWARE  | INC-001, INC-002, INC-003 |
| `db_connection_pool` | DATABASE  | INC-004, INC-005, INC-006 |

Risolti standalone: INC-007 (infrastructure), INC-008 (network).
Attivi: INC-009 (helpdesk SEV4), INC-010 (network SEV3). Da classificare: INC-011.

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
