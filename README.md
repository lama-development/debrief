# Debrief

_Incident Response Multi-Agent Platform_

Tre agenti orchestrati da un router LLM gestiscono il ciclo di vita di un incidente:

1. **Triage**: classificazione e prioritizzazione;
2. **Investigator**: ricerca di incidenti simili via RAG;
3. **Resolver**: remediation e post-mortem automatico.

Il sistema impara da ogni incidente risolto e dalle soluzioni fornite dagli umani.

## Quick start

### 1. Clona e installa

```bash
git clone https://github.com/lama-development/debrief && cd debrief
cp .env.example .env
# Inserisci la tua GROQ_API_KEY in .env
```

### 2. Installa dipendenze

```bash
uv sync
```

### 3. Popola il database con i dati di seed

```bash
uv run python seed/run_seed.py
```

### 4. Avvia backend e frontend

Terminale 1 - Backend (porta 8000):

```bash
uv run dev
```

Terminale 2 - Frontend (porta 5173):

```bash
cd frontend
npm install # solo la prima volta
npm run dev
```

L'interfaccia è su `http://localhost:5173`. Registra un utente, dichiara un
incidente e chatta con gli agenti (triage → investigator → resolver). Per
puntare a un backend diverso, modifica `API_URL` in `frontend/src/lib/api.ts`.

### 5. (_opzionale_) Esegui la valutazione

```bash
uv run eval
```

## Stack

| Livello               | Scelta                         |
| --------------------- | ------------------------------ |
| Orchestrazione agenti | Agno                           |
| Vector DB             | LanceDB                        |
| Embedding             | sentence-transformers (locale) |
| LLM                   | Groq (modelli open-source)     |
| Backend               | FastAPI + uv                   |
| Frontend              | React + shadcn/ui              |
| Database              | SQLite                         |

## Documentazione

La documentazione tecnica completa con le motivazioni architetturali e la valutazione è in `docs/Debrief_Documentazione_Tecnica.md`.

## Autore

Davide La Marca (20054157) -
Programmazione di Applicazioni Intelligenti
