<div align="center">
  <img src="frontend/public/Debrief-Light.png" alt="Logo di Debrief" width="120" />

# Debrief

**Piattaforma AI-assisted per la gestione collaborativa degli incidenti IT**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

## Perché esiste

Durante un incidente tecnico, una parte rilevante del tempo viene spesa per
classificare il problema, coinvolgere le persone giuste, recuperare casi simili e
documentare la soluzione. Debrief riunisce queste attività in uno spazio condiviso
e usa agenti specializzati per assistere il team senza sostituire le decisioni
umane.

Il progetto dimostra quattro capacità principali:

- triage da una descrizione in linguaggio naturale, con severità `SEV1`–`SEV4`,
  team suggeriti e richieste di chiarimento;
- indagine su incidenti storici tramite ricerca semantica locale;
- proposta di remediation che usa incidenti risolti e runbook quando disponibili,
  altrimenti best practice esplicitamente etichettate;
- capitalizzazione della conoscenza attraverso timeline persistenti, soluzioni
  umane e debriefing alla chiusura.

## Funzionalità implementate

- registrazione e login con password hashate e sessioni Bearer revocabili;
- visibilità degli incidenti in base a creatore, partecipazione e team coinvolto;
- dashboard con filtri, conteggi e MTTR degli incidenti accessibili all'utente;
- creazione, classificazione, modifica manuale, risoluzione e riapertura;
- chat multi-utente persistente; lo streaming Server-Sent Events trasporta la
  risposta agentica del singolo turno, non sincronizza i browser in realtime;
- attivazione esplicita degli agenti con `@debrief` dopo il triage iniziale;
- conferma umana per gli override di severità e team;
- escalation quando il resolver non trova evidenze applicabili;
- RAG su incidenti risolti, contributi umani e knowledge base, con embedding
  eseguiti in locale;
- indicizzazione best-effort tentata subito per rendere le nuove soluzioni
  recuperabili in casi futuri;
- tema chiaro/scuro e interfaccia responsive.

## Flusso principale

1. L'utente si registra scegliendo il proprio team.
2. Dichiara un incidente con una descrizione libera.
3. Il frontend apre la conversazione e avvia automaticamente il triage.
4. Il team continua a collaborare in chat; su un incidente attivo, una menzione
   `@debrief` richiama investigator, resolver o il flusso di override.
5. Una persona conferma eventuali modifiche e inserisce il riepilogo finale della
   risoluzione.
6. Il backend salva il debriefing strutturato e tenta di aggiornare la memoria
   semantica.

## Architettura

| Area              | Tecnologia                              | Ruolo                                              |
| ----------------- | --------------------------------------- | -------------------------------------------------- |
| Frontend          | React, TypeScript, Vite, Tailwind CSS   | Dashboard e chat                                   |
| API               | FastAPI, Uvicorn                        | REST, autenticazione e streaming SSE               |
| Agenti            | Agno + modelli Groq                     | routing, triage, indagine e remediation            |
| Stato applicativo | SQLite                                  | utenti, sessioni, incidenti, timeline e debriefing |
| Ricerca semantica | LanceDB                                 | incidenti risolti e knowledge base                 |
| Embedding         | `paraphrase-multilingual-MiniLM-L12-v2` | vettori normalizzati calcolati localmente          |
| Package manager   | uv, npm                                 | ambiente Python e frontend riproducibili           |

## Avvio locale

### Prerequisiti

- [Python](https://www.python.org/) `>=3.11`;
- [uv](https://docs.astral.sh/uv/);
- [Node.js](https://nodejs.org/) `^20.19.0` oppure `>=22.12.0`;
- una chiave API [Groq](https://groq.com/) per le funzioni basate su LLM.

### Installazione

```bash
git clone https://github.com/lama-development/debrief.git
cd debrief
cp .env.example .env
```

In PowerShell usa `Copy-Item .env.example .env` al posto di `cp`.

Inserisci la chiave nel file `.env` senza versionarlo:

```dotenv
GROQ_API_KEY=your_groq_api_key_here
```

Installa il backend e prepara i dati dimostrativi:

```bash
uv sync
uv run seed
```

Il seed carica 7 team e 15 incidenti in SQLite, indicizza i 15 incidenti risolti
e 7 runbook in LanceDB ed esegue uno smoke test del retrieval. Al primo utilizzo,
il modello di embedding viene scaricato e poi mantenuto nella cache locale.

### Esecuzione

Avvia i due processi da terminali separati.

**Terminale 1** - Backend su `http://localhost:8000`:

```bash
uv run dev
```

**Terminale 2** - Frontend su `http://localhost:5173`:

```bash
cd frontend
npm ci
npm run dev
```

Apri `http://localhost:5173`. Non esistono utenti predefiniti: crea il primo
account dalla schermata di registrazione. La documentazione interattiva dell'API
è disponibile su `http://localhost:8000/docs`; il controllo di salute è
`GET http://localhost:8000/health`.

> [!TIP]
> Il frontend usa attualmente `http://localhost:8000` come URL API fisso.
> Per un host diverso è necessario modificarlo in `frontend/src/lib/api.ts`.

## Comandi utili

| Directory   | Comando          | Effetto                                               |
| ----------- | ---------------- | ----------------------------------------------------- |
| root        | `uv sync`        | sincronizza l'ambiente Python dal lockfile            |
| root        | `uv run seed`    | aggiorna i dati demo e rigenera gli indici vettoriali |
| root        | `uv run dev`     | avvia FastAPI in modalità reload sulla porta 8000     |
| root        | `uv run eval`    | esegue la suite di autovalutazione                    |
| `frontend/` | `npm ci`         | installa le dipendenze dal lockfile                   |
| `frontend/` | `npm run dev`    | avvia Vite sulla porta 5173                           |
| `frontend/` | `npm run lint`   | esegue ESLint                                         |
| `frontend/` | `npm run build`  | verifica TypeScript e produce il bundle               |
| `frontend/` | `npm run format` | formatta i file con Prettier                          |

Le suite `triage`, `routing`, `resolver` e `injection` richiedono Groq. Senza
`GROQ_API_KEY`, il runner le segnala come saltate ed esegue comunque `retrieval`.

## Documentazione

- [Documentazione tecnica](docs/Debrief_Documentazione_Tecnica.md)
- [Guida operativa di sviluppo](docs/Debrief_Guida_Sviluppo.md)
- [Dataset e runbook usati dal RAG](seed/knowledge_base/)

## Autore

**Davide La Marca** (20054157) per il corso
_Programmazione di Applicazioni Intelligenti_ (MF0781).

Il codice è distribuito con licenza [MIT](LICENSE).
