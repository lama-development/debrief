# Debrief

Incident response multi-agent platform per team IT.

Tre agenti orchestrati da un router LLM gestiscono il ciclo di vita di un incidente: **triage** (classificazione e prioritizzazione), **investigator** (ricerca di incidenti simili via RAG), **resolver** (remediation e post-mortem automatico). Il sistema impara da ogni incidente risolto e dalle soluzioni fornite dagli umani.

## Quick start

```bash
# 1. Clona e installa
git clone <repo-url> && cd debrief
cp .env.example .env
# Inserisci la tua GROQ_API_KEY in .env

# 2. Installa dipendenze
uv sync

# 3. Popola il database con i dati di seed
uv run seed

# 4. Avvia il backend
uv run uvicorn src.debrief.api.app:app --reload

# 5. (opzionale) Esegui la valutazione
uv run eval
```

## Stack

| Livello | Scelta |
|---|---|
| Orchestrazione agenti | Agno |
| Vector DB | LanceDB |
| Embedding | sentence-transformers (locale) |
| LLM | Groq (modelli open-source) |
| Backend | FastAPI + uv |
| Frontend | React + shadcn/ui |
| Database | SQLite |

## Documentazione

La documentazione tecnica completa (23 pagine) con le motivazioni architetturali e la valutazione e' nel file `Debrief_Documentazione_Tecnica.pdf`.

## Autore

Davide La Marca (20054157)
Programmazione di Applicazioni Intelligenti
