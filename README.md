<div align="center">
  <img src="frontend/public/logo.png" alt="Debrief Logo" width="120" />

# Debrief

**Incident Response Multi-Agent Platform**

[![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

## Come funziona

Debrief sposta il valore cognitivo del triage dall'essere umano agli agenti: classificazione in linguaggio naturale, recall semantico degli incidenti passati via RAG, e post-mortem generato automaticamente alla chiusura.

### Agenti

| Agente           | Ruolo                                                            |
| ---------------- | ---------------------------------------------------------------- |
| **Triage**       | Classifica severity, priorità e team coinvolti dal testo libero  |
| **Investigator** | Cerca incidenti simili via RAG (embedding semantico)             |
| **Resolver**     | Propone remediation, traccia la chiusura e genera il post-mortem |

## Stack

| Livello               | Tecnologia                                                                 |
| --------------------- | -------------------------------------------------------------------------- |
| Orchestrazione agenti | [Agno](https://agno.com)                                                   |
| Vector DB             | [LanceDB](https://lancedb.com)                                             |
| Embedding             | sentence-transformers (locale)                                             |
| LLM                   | [Groq](https://groq.com)                                                   |
| Backend               | [FastAPI](https://fastapi.tiangolo.com) + [uv](https://docs.astral.sh/uv/) |
| Frontend              | [React](https://react.dev) + [shadcn/ui](https://ui.shadcn.com)            |
| Database              | SQLite                                                                     |

## Quick start

### 1. Clona e configura

```bash
git clone https://github.com/lama-development/debrief && cd debrief
cp .env.example .env
# Inserisci la tua GROQ_API_KEY in .env
```

### 2. Installa le dipendenze Python

```bash
uv sync
```

### 3. Popola il database con dati di seed

```bash
uv run python seed/run_seed.py
```

### 4. Avvia backend e frontend

**Terminale 1** — Backend su `http://localhost:8000`:

```bash
uv run dev
```

**Terminale 2** — Frontend su `http://localhost:5173`:

```bash
cd frontend
npm install # solo la prima volta
npm run dev
```

Apri `http://localhost:5173`, registra un utente, dichiara un incidente e chatta con gli agenti.

> [!TIP]
> Per puntare a un backend diverso, modifica `API_URL` in `frontend/src/lib/api.ts`.

### 5. (Opzionale) Esegui la valutazione

```bash
uv run eval
```

## Documentazione

La documentazione tecnica completa — motivazioni architetturali, scelte di design e valutazione — è in [`docs/Debrief_Documentazione_Tecnica.md`](docs/Debrief_Documentazione_Tecnica.md).

## Autore

**Davide La Marca** (20054157) — Programmazione di Applicazioni Intelligenti MF0781
