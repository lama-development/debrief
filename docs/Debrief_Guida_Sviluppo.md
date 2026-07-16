# Debrief — Guida operativa di sviluppo

Questa guida serve per installare, eseguire, verificare ed estendere la versione
`0.1.0` del repository. Per motivazioni e trade-off consulta la
[documentazione tecnica](Debrief_Documentazione_Tecnica.md).

Il codice è la fonte primaria. In particolare:

- dipendenze e versione Python: `pyproject.toml` e `uv.lock`;
- dipendenze frontend: `frontend/package.json` e `frontend/package-lock.json`;
- modelli e soglie: `src/debrief/config.py`;
- contratti dati: `src/debrief/schemas.py` e `frontend/src/lib/types.ts`;
- endpoint: `src/debrief/api/routes_*.py`;
- dati dimostrativi: `seed/`;
- casi di valutazione: `eval/cases.json` e `eval/run_eval.py`.

Esegui i comandi backend dalla **root del repository**: `.env` e i percorsi
predefiniti dei database dipendono dalla working directory.

## 1. Requisiti

| Strumento | Requisito                                                                   |
| --------- | --------------------------------------------------------------------------- |
| Python    | `>=3.11`                                                                    |
| uv        | necessario per ambiente, lockfile e script Python                           |
| Node.js   | `^20.19.0` oppure `>=22.12.0`, requisito di Vite 8                          |
| npm       | usa il lockfile v3 incluso                                                  |
| Groq      | chiave API per router e agenti LLM                                          |
| Rete      | necessaria per installazione, primo download dell'embedding e chiamate Groq |

SQLite è incluso in Python. LanceDB usa una directory locale e non richiede un
server separato.

## 2. Setup iniziale

### 2.1 Backend

```bash
git clone https://github.com/lama-development/debrief.git
cd debrief
cp .env.example .env
uv sync
```

In PowerShell:

```powershell
Copy-Item .env.example .env
```

Configura `.env`:

```dotenv
GROQ_API_KEY=your_groq_api_key_here
```

Non versionare `.env`.

### 2.2 Dati demo

```bash
uv run seed
```

Questo passaggio è necessario per una demo completa: il solo startup FastAPI crea
le tabelle vuote, ma non carica il catalogo team né le collezioni RAG. Senza seed
la registrazione non ha team utilizzabili e le ricerche semantiche non hanno dati.

Al primo avvio Sentence Transformers scarica il modello configurato; gli avvii
successivi usano la cache locale.

### 2.3 Frontend

```bash
cd frontend
npm ci
```

`npm ci` è preferibile a `npm install` per riprodurre esattamente il lockfile.

## 3. Avvio in sviluppo

Terminale 1, dalla root:

```bash
uv run dev
```

- API: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- health check: `http://127.0.0.1:8000/health`
- reload automatico attivo

Terminale 2:

```bash
cd frontend
npm run dev
```

- SPA: `http://localhost:5173`

Non esistono credenziali predefinite. Registra un utente dalla UI scegliendo uno
dei team caricati dal seed.

Per avviare l'ASGI server senza l'entry point di sviluppo:

```bash
uv run uvicorn debrief.api.app:app --host 0.0.0.0 --port 8000
```

Questo comando non trasforma da solo l'applicazione in un deployment di
produzione: CORS, URL frontend, sessioni e persistenza restano configurati per il
prototipo.

## 4. Comandi

### 4.1 Root

| Comando                                        | Uso                                                   |
| ---------------------------------------------- | ----------------------------------------------------- |
| `uv sync`                                      | sincronizza dipendenze e ambiente                     |
| `uv lock --check`                              | verifica che il lockfile sia aggiornato               |
| `uv run seed`                                  | aggiorna seed SQLite e rigenera le collezioni LanceDB |
| `uv run dev`                                   | avvia FastAPI con reload                              |
| `uv run eval`                                  | esegue l'harness AI                                   |
| `uv run python -m compileall -q src seed eval` | controlla la sintassi Python                          |

### 4.2 `frontend/`

| Comando          | Uso                                 |
| ---------------- | ----------------------------------- |
| `npm ci`         | installazione riproducibile         |
| `npm run dev`    | server Vite                         |
| `npm run lint`   | ESLint                              |
| `npm run build`  | TypeScript + bundle Vite in `dist/` |
| `npm run format` | applica Prettier; modifica i file   |

Non sono definiti script frontend `test`, `typecheck`, `preview` o `start`. Il
controllo TypeScript fa parte di `npm run build`.

Il repository include `pytest` e `httpx` nel gruppo di sviluppo, ma non contiene
ancora test pytest. `uv run eval` misura capacità AI specifiche e non sostituisce
test unitari o di integrazione.

## 5. Struttura del repository

```text
debrief/
├── pyproject.toml              # package Python, dipendenze e script
├── uv.lock                     # lockfile Python
├── .env.example               # esempio del solo segreto richiesto
├── README.md                   # onboarding del progetto
├── docs/
│   ├── README.md
│   ├── Debrief_Documentazione_Tecnica.md
│   └── Debrief_Guida_Sviluppo.md
├── src/debrief/
│   ├── config.py               # modelli, soglie e path predefiniti
│   ├── schemas.py              # output Pydantic
│   ├── database.py             # schema e data access SQLite
│   ├── auth.py                 # bcrypt e sessioni Bearer
│   ├── agents/
│   │   ├── orchestrator.py
│   │   ├── triage.py
│   │   ├── investigator.py
│   │   └── resolver.py
│   ├── api/
│   │   ├── app.py
│   │   ├── lifecycle.py
│   │   ├── service.py
│   │   ├── routes_auth.py
│   │   ├── routes_incidents.py
│   │   ├── routes_chat.py
│   │   └── routes_metrics.py
│   ├── rag/
│   │   ├── indexer.py
│   │   └── retriever.py
│   └── tools/
│       ├── embedding.py
│       └── search.py
├── seed/
│   ├── teams.json
│   ├── incidents.json
│   ├── knowledge_base/         # 7 runbook Markdown
│   └── run_seed.py
├── eval/
│   ├── cases.json
│   └── run_eval.py
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.ts
│   ├── public/
│   └── src/
│       ├── auth/
│       ├── components/
│       ├── hooks/
│       ├── lib/
│       └── pages/
└── data/                       # generato a runtime, ignorato da Git
    ├── debrief.db
    └── lancedb/
```

## 6. Configurazione

### 6.1 Variabili d'ambiente

| Variabile         | Default                                 | Uso                           |
| ----------------- | --------------------------------------- | ----------------------------- |
| `GROQ_API_KEY`    | nessuno                                 | richiesta dalle funzioni LLM  |
| `SQLITE_PATH`     | `data/debrief.db`                       | file SQLite                   |
| `LANCEDB_PATH`    | `data/lancedb`                          | directory LanceDB             |
| `EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | modello Sentence Transformers |

`GROQ_API_KEY` è l'unico valore attivo in `.env.example`; gli override opzionali
sono riportati come righe commentate.

La chiave Groq non serve per creare le tabelle, eseguire il seed o usare il
retrieval locale. Serve a router, triage, investigator, resolver e alle suite LLM.

### 6.2 Configurazione nel codice

`src/debrief/config.py` contiene:

| Componente            | Valore corrente                        |
| --------------------- | -------------------------------------- |
| router                | `openai/gpt-oss-20b`, temperatura 0    |
| triage                | `openai/gpt-oss-120b`, temperatura 0   |
| investigator          | `openai/gpt-oss-120b`, temperatura 0,2 |
| resolver              | `openai/gpt-oss-120b`, temperatura 0,3 |
| top-k incidenti       | 3                                      |
| top-k knowledge base  | 3                                      |
| soglia incidenti      | 0,55                                   |
| soglia knowledge base | 0,35                                   |

I nomi dei modelli e le soglie non sono configurabili via `.env` nella versione
corrente: modifica `config.py` e riesegui le verifiche pertinenti.

### 6.3 Frontend e CORS

Il client usa un URL fisso:

```ts
// frontend/src/lib/api.ts
export const API_URL = "http://localhost:8000";
```

FastAPI consente in sviluppo `http://localhost:5173` e
`http://localhost:3000`. Per un ambiente diverso occorre allineare `API_URL` e
`CORS_ORIGINS`.

Una build servita dietro un web server deve inoltrare le rotte client-side, come
`/incidents/INC-001`, a `index.html`.

## 7. Modello funzionale

### 7.1 Stati

| Evento                       | Stato iniziale    | Stato finale |
| ---------------------------- | ----------------- | ------------ |
| `TRIAGE_NEEDS_CLARIFICATION` | `open`            | `open`       |
| `TRIAGE_CLASSIFIED`          | `open`            | `active`     |
| `RESOLUTION_STARTED`         | `open` o `active` | `active`     |
| `RESOLVED`                   | `open` o `active` | `resolved`   |
| `REOPENED`                   | `resolved`        | `active`     |

Non implementare nuovi stati soltanto nel frontend: il contratto coinvolge
`lifecycle.py`, database, tipi TypeScript, badge, filtri, route e test.

### 7.2 Regola della chat

- su un incidente `open`, ogni messaggio può completare il triage;
- il frontend invia automaticamente la descrizione iniziale quando apre un nuovo
  incidente non ancora gestito;
- su un incidente `active`, tutti i messaggi vengono salvati, ma gli agenti
  rispondono solo alla menzione `@debrief`;
- su `resolved`, la UI blocca l'input finché l'incidente non viene riaperto;
- il router sceglie un solo ruolo per turno.

La regex backend per la menzione è case-insensitive e non accetta la menzione
come parte di un'altra parola.

### 7.3 Accesso agli incidenti

`database.user_can_access_incident()` autorizza:

1. il creatore;
2. un partecipante;
3. un utente il cui team è coinvolto e non è stato rimosso successivamente.

L'apertura del dettaglio e della chat aggiunge l'utente ai partecipanti. Non
esistono permessi differenziati: chi ha accesso può anche chiudere, riaprire,
modificare la classificazione e aggiungere una soluzione umana.

## 8. Agenti e contratti

| Ruolo        | Input principale                         | Output / tool                                    |
| ------------ | ---------------------------------------- | ------------------------------------------------ |
| router       | stato, descrizione troncata, messaggio   | `RoutingDecision`                                |
| triage       | descrizione e contesto recente           | `TriageOutput`; nessun tool RAG                  |
| investigator | domanda, descrizione e contesto          | `search_past_incidents`                          |
| resolver     | incidente, richiesta e contesto          | `search_past_incidents`, `search_knowledge_base` |
| override     | intent estratto dal router               | proposta da confermare, non agente autonomo      |
| none         | richiesta fuori scope o incidente chiuso | testo di aiuto standard                          |

Gli agenti hanno `num_history_messages=0`. Il service ricostruisce gli ultimi 12
eventi rilevanti e li passa esplicitamente.

### 8.1 Schemi Pydantic principali

`TriageOutput`:

```text
title
severity: SEV1 | SEV2 | SEV3 | SEV4
suggested_teams[]
summary
needs_clarification
clarifying_questions[]
confidence: 0..1
```

`RoutingDecision`:

```text
agent: triage | investigator | resolver | override | none
reason
override_params?
```

`DebriefReport`:

```text
incident_id
title
severity
timeline[]
resolution
```

Il debrief viene assemblato dal service usando il riepilogo umano; non è una
generazione LLM del resolver.

I report creati a runtime includono la timeline. I report storici caricati dal
seed contengono soltanto `incident_id`, `title`, `severity` e `resolution`: il
tipo frontend rende per questo la timeline opzionale.

### 8.2 Aggiungere un evento SSE

Aggiorna insieme:

1. il produttore in `src/debrief/api/service.py`;
2. il contratto `ChatEvent` in `frontend/src/lib/types.ts`;
3. lo switch in `frontend/src/components/ChatPanel.tsx`;
4. la documentazione API;
5. i test di contratto, quando disponibili.

Il frame attuale è sempre:

```text
data: {"type":"..."}\n\n
```

Tipi prodotti dal backend: `routing`, `tool`, `token`, `triage`,
`override_proposed`, `human_help_required`, `done`, `error`.

## 9. API REST

Tutte le route incidenti e metriche richiedono:

```http
Authorization: Bearer <token>
```

| Metodo | Path                              | Body o query                                          |
| ------ | --------------------------------- | ----------------------------------------------------- |
| GET    | `/health`                         | —                                                     |
| GET    | `/auth/teams`                     | —                                                     |
| POST   | `/auth/register`                  | `username`, `password`, `team_id`                     |
| POST   | `/auth/login`                     | `username`, `password`                                |
| POST   | `/auth/logout`                    | —                                                     |
| GET    | `/auth/me`                        | —                                                     |
| POST   | `/incidents`                      | `description`                                         |
| GET    | `/incidents`                      | `status?`, `limit=100`                                |
| GET    | `/incidents/{id}`                 | —                                                     |
| POST   | `/incidents/{id}/chat`            | `message`                                             |
| PATCH  | `/incidents/{id}/classification`  | `severity?`, `add_teams?`, `remove_teams?`, `reason?` |
| POST   | `/incidents/{id}/resolve`         | `resolution_summary`                                  |
| POST   | `/incidents/{id}/reopen`          | —                                                     |
| POST   | `/incidents/{id}/human-solutions` | `solution`                                            |
| GET    | `/metrics`                        | —                                                     |

Usa `/docs` per payload, codici di stato e prove manuali. Le route non hanno
version prefix; una futura API pubblica dovrebbe introdurre versioning.

## 10. SQLite

| Tabella                 | Colonne                                                                                                     |
| ----------------------- | ----------------------------------------------------------------------------------------------------------- |
| `teams`                 | `id`, `name`, `description`, `contact_info`                                                                 |
| `users`                 | `id`, `username`, `password_hash`, `team_id`, `created_at`                                                  |
| `sessions`              | `token`, `user_id`, `created_at`                                                                            |
| `incidents`             | `id`, `title`, `description`, `severity`, `status`, `created_by`, `created_at`, `updated_at`, `resolved_at` |
| `incident_participants` | `incident_id`, `user_id`, `joined_at`, `last_activity_at`                                                   |
| `timeline_events`       | `id`, `incident_id`, `timestamp`, `event_type`, `actor`, `content`                                          |
| `debrief_reports`       | `id`, `incident_id`, `content_json`, `created_at`                                                           |

Lo schema non usa un migration framework. Una modifica strutturale deve quindi
prevedere una migrazione esplicita prima di poter essere considerata compatibile
con database esistenti. `CREATE TABLE IF NOT EXISTS` non modifica tabelle già
create.

Gli eventi di coinvolgimento e rimozione sono append-only a runtime; il set
corrente dei team viene ricostruito dalla timeline. Il seed elimina e ricrea
questi eventi per i propri incidenti, così una nuova esecuzione resta ripetibile.

## 11. RAG e learning loop

### 11.1 Collezioni

| Tabella LanceDB  | Campi                                                     | Ricerca                 |
| ---------------- | --------------------------------------------------------- | ----------------------- |
| `past_incidents` | `id`, `title`, `severity`, `text`, `resolution`, `vector` | investigator e resolver |
| `knowledge_base` | `id`, `title`, `text`, `vector`                           | resolver                |

Testo incidente incorporato:

```text
title + description + resolution
```

I runbook sono indicizzati interamente, senza chunking. Il tool limita a 1.500
caratteri il testo di ogni articolo passato al resolver.

### 11.2 Chiusura e soluzione umana

`resolve_incident()` salva prima lo stato in SQLite e poi tenta l'upsert
vettoriale. Un guasto LanceDB non annulla la chiusura.

`capture_human_solution()`:

1. registra un evento `human_solution`;
2. usa il testo come `resolution` del record indicizzato;
3. inserisce o sostituisce l'incidente in `past_incidents`.

Non c'è moderazione, versione o collezione separata. Un nuovo contributo sullo
stesso incidente sostituisce il precedente record vettoriale.

### 11.3 Estendere i dati

Per aggiungere un team:

1. modifica `seed/teams.json`;
2. usa il nuovo ID negli incidenti o nei placeholder dei runbook;
3. aggiungi sempre l'ID all'elenco valido hardcoded nel prompt del router e, se
   necessario, al mapping dai nomi naturali;
4. esegui `uv run seed`;
5. verifica registrazione, accesso e routing.

Per aggiungere un runbook:

1. crea un file `.md` in `seed/knowledge_base/`;
2. usa placeholder `{{TEAM_ID}}` solo per ID presenti nel catalogo;
3. esegui `uv run seed`;
4. prova una query pertinente nel retrieval.

Per aggiungere incidenti seed:

1. usa un ID `INC-NNN` univoco;
2. assegna team esistenti;
3. fornisci `severity`, `resolution` e `resolved_at` per i casi `resolved`;
4. aggiorna la ground truth in `eval/cases.json` quando il corpus cambia;
5. riesegui seed ed eval.

## 12. Seed

Il dataset corrente contiene:

- 7 team;
- 15 incidenti `resolved`;
- 7 runbook;
- 15 record iniziali in `past_incidents`.

`uv run seed`:

- crea le tabelle SQLite mancanti;
- inserisce o sostituisce team e incidenti seed;
- rigenera `past_incidents` e `knowledge_base`;
- esegue tre smoke query.

Non è un reset totale: utenti, sessioni e incidenti runtime non collidenti restano
nel file SQLite. Su un ambiente con dati importanti esegui prima un backup e non
usare il seed come migrazione.

## 13. Valutazione

`uv run eval` esegue:

| Suite     | Casi effettivamente selezionati | Richiede Groq |
| --------- | ------------------------------: | ------------- |
| triage    |                          2 di 5 | sì            |
| routing   |                          3 di 5 | sì            |
| resolver  |                          1 di 5 | sì            |
| retrieval |                          5 di 5 | no            |
| learning  |           1 scenario nel codice | no            |
| injection |                          1 di 3 | sì            |

Senza chiave, le suite LLM sono marcate `SKIP`; retrieval e learning restano
eseguibili. Esegui prima il seed.

Il runner misura accuratezza, fallback, ID di incidente citati rispetto alle
attese seed, precision/recall/MRR, learning loop e blocco di prompt injection.
Non verifica la provenance dei runbook o il trace completo delle tool call.
Stampa soltanto su console e non è un quality gate completo: non testa API, auth,
lifecycle, SSE, concorrenza o UI.

Quando aggiungi una capacità, preferisci:

- unit test per funzioni pure e lifecycle;
- integration test con SQLite/LanceDB temporanei;
- test API con `httpx`;
- test di contratto SSE;
- test frontend ed end-to-end;
- casi eval separati per qualità non deterministica.

## 14. Flussi di modifica comuni

### Modificare un output backend

1. aggiorna lo schema Pydantic o il response shape;
2. aggiorna `frontend/src/lib/types.ts`;
3. aggiorna il client in `frontend/src/lib/api.ts`;
4. aggiorna hook e componenti;
5. esegui compile, lint e build;
6. aggiorna questa guida se cambia un contratto pubblico.

### Modificare un prompt

1. cambia il file in `src/debrief/agents/`;
2. conserva i confini di ruolo e il trattamento dei dati utente come dati;
3. aggiorna o aggiungi casi in `eval/cases.json`;
4. esegui le suite coinvolte;
5. controlla che gli ID citati provengano dai tool.

### Modificare retrieval o embedding

1. cambia `config.py`, `tools/embedding.py` o `rag/`;
2. esegui nuovamente `uv run seed`, perché i vettori esistenti non si aggiornano
   automaticamente al cambio modello;
3. esegui retrieval, resolver e learning;
4. registra i risultati se il cambiamento deve essere confrontabile.

## 15. Troubleshooting

### La registrazione non mostra team o restituisce errore

Esegui dalla root:

```bash
uv run seed
```

### Il retrieval segnala tabelle mancanti

Il backend può avviarsi con il solo SQLite vuoto; LanceDB richiede il seed.

```bash
uv run seed
```

### Gli agenti falliscono ma `/health` risponde

`/health` verifica solo che FastAPI sia vivo. Controlla:

- `GROQ_API_KEY`;
- disponibilità dei modelli configurati;
- rete verso Groq;
- presenza delle collezioni LanceDB;
- log del backend.

### Il frontend non raggiunge l'API

Verifica:

- backend sulla porta 8000;
- `API_URL` in `frontend/src/lib/api.ts`;
- origine presente in `CORS_ORIGINS`;
- uso coerente di `localhost`/host remoto e protocollo HTTP/HTTPS.

### Un deep link frontend restituisce 404 dopo il deploy

Configura il server statico per servire `index.html` sulle rotte non corrispondenti
a un file.

### Lo stream arriva tutto insieme

Un reverse proxy può bufferizzare SSE. Mantieni `text/event-stream`, disabilita il
buffering e imposta timeout compatibili con risposte lunghe. Il backend invia già
`X-Accel-Buffering: no`.

### I file dati compaiono in una directory inattesa

Avvia i comandi dalla root oppure imposta `SQLITE_PATH` e `LANCEDB_PATH` con
percorsi espliciti.

## 16. Checklist prima di una modifica

```bash
uv lock --check
uv run python -m compileall -q src seed eval
```

```bash
cd frontend
npm run lint
npm run build
```

Esegui inoltre `uv run eval` quando tocchi agenti, prompt, embedding, retrieval,
seed o learning loop.

Il frontend non abilita attualmente React `StrictMode`: l'effetto che avvia
l'auto-triage invierebbe due POST in sviluppo. Prima di riattivarlo, rendi quel
flusso idempotente lato client e backend.

Controlla infine:

- nessun segreto nel diff;
- documentazione e tipi allineati;
- nessun file generato in Git;
- comportamento verificato sia con dati presenti sia con errori attesi;
- nuove capacità descritte come implementate solo dopo la loro verifica.

## 17. Limiti operativi da non dimenticare

- sessioni senza scadenza e token in `localStorage`;
- nessun ruolo o amministrazione dei team;
- nessuna migrazione DB;
- operazioni multi-step non transazionali;
- ID incidente non generato atomicamente;
- riapertura che conserva `resolved_at` e il debrief precedente;
- URL, CORS e server di sviluppo poco configurabili;
- nessun retry/backoff, rate limit o budget applicativo per agenti e LLM;
- nessun realtime globale tra più browser;
- nessun test di regressione convenzionale;
- nessun deployment, backup o recovery documentato come supportato.

Questi elementi appartengono alla roadmap professionale, non alle garanzie della
versione corrente.
