"""
indexer.py - Indicizzazione e ricerca in LanceDB.

LanceDB è un database VETTORIALE: invece di righe con colonne classiche, salva
vettori (gli embedding) e sa trovare velocemente i più "vicini" a un vettore di
query. È il motore del RAG.

Gestisce le tre collezioni (tabelle):
- past_incidents: incidenti chiusi con post-mortem
- knowledge_base: runbook e documentazione
- verified_solutions: soluzioni fornite da umani (priorità alta)
"""

import os
import json
import lancedb
import pyarrow as pa   # pyarrow è il formato dati su cui si appoggia LanceDB

# Dimensione del vettore (paraphrase-multilingual-MiniLM-L12-v2 = 384 numeri).
# Tutti i vettori in una tabella devono avere la stessa dimensione.
VECTOR_DIM = 384


def get_db(db_path: str | None = None) -> lancedb.DBConnection:
    """Apre (o crea) il database LanceDB."""
    if db_path is None:
        db_path = os.getenv("LANCEDB_PATH", "data/lancedb")
    os.makedirs(db_path, exist_ok=True)
    # connect apre la cartella come database; crea i file necessari se mancano.
    return lancedb.connect(db_path)


def _incident_record(inc: dict, vec: list[float]) -> dict:
    """Costruisce il record LanceDB per un incidente passato.
    Usato sia dall'indicizzazione batch (seed) sia dall'append a runtime."""
    # Centralizzare qui la "forma" del record garantisce che seed e runtime
    # scrivano ESATTAMENTE le stesse colonne (altrimenti LanceDB darebbe errore
    # di schema). DRY: una sola definizione, riusata.
    return {
        "id": inc["id"],
        "title": inc["title"],
        "severity": inc.get("severity", ""),
        "text": _build_incident_text(inc),  # il testo che è stato incorporato
        "root_cause": inc.get("root_cause", ""),
        # resolution_steps è una lista; LanceDB qui salva una stringa, quindi la
        # serializziamo in JSON (e la ri-parseremo alla lettura se serve).
        "resolution_steps": json.dumps(inc.get("resolution_steps", []), ensure_ascii=False),
        "vector": vec,   # l'embedding: è la colonna su cui avviene la ricerca
    }


def _solution_record(sol: dict, vec: list[float]) -> dict:
    """Costruisce il record LanceDB per una soluzione verificata.
    Usato sia dall'indicizzazione batch (seed) sia dall'append a runtime."""
    return {
        "id": sol["id"],
        "incident_id": sol.get("incident_id", ""),
        "problem_context": sol["problem_context"],
        "solution": sol["solution"],
        "provided_by": sol.get("provided_by", ""),
        "text": sol["problem_context"] + " " + sol["solution"],  # testo incorporato
        "vector": vec,
    }


def index_incidents(db: lancedb.DBConnection, incidents: list[dict], vectors: list[list[float]]):
    """Indicizza gli incidenti passati in LanceDB.

    Per ogni incidente, il testo incorporato è:
    descrizione + root_cause + resolution_steps
    (così l'investigator può cercare sia per sintomi che per soluzioni)
    """
    # zip(a, b) accoppia gli elementi delle due liste: (inc1, vec1), (inc2, vec2)...
    # La list comprehension costruisce un record per ogni coppia.
    records = [_incident_record(inc, vec) for inc, vec in zip(incidents, vectors)]

    # mode="overwrite" → ricrea la tabella da zero. Lo usa SOLO il seed; a runtime
    # invece si fa .add() per APPENDERE senza cancellare (vedi add_past_incident).
    db.create_table("past_incidents", data=records, mode="overwrite")
    return len(records)


def index_knowledge_base(db: lancedb.DBConnection, docs: list[dict], vectors: list[list[float]]):
    """Indicizza i documenti della knowledge base (runbook)."""
    records = []
    for doc, vec in zip(docs, vectors):
        records.append({
            "id": doc["id"],
            "title": doc["title"],
            "text": doc["text"],
            "vector": vec,
        })

    db.create_table("knowledge_base", data=records, mode="overwrite")
    return len(records)


def index_verified_solutions(db: lancedb.DBConnection, solutions: list[dict], vectors: list[list[float]]):
    """Indicizza le soluzioni verificate da umani."""
    records = [_solution_record(sol, vec) for sol, vec in zip(solutions, vectors)]

    db.create_table("verified_solutions", data=records, mode="overwrite")
    return len(records)


def add_past_incident(db: lancedb.DBConnection, incident: dict, vector: list[float]) -> str:
    """Aggiunge UN incidente risolto a 'past_incidents' (append, non overwrite).
    È il cuore del loop di apprendimento: ogni incidente chiuso diventa
    immediatamente ricercabile dall'investigator e dal resolver.
    Crea la tabella se non esiste ancora (DB senza seed)."""
    record = _incident_record(incident, vector)
    try:
        # open_table fallisce con ValueError se la tabella non esiste ancora.
        table = db.open_table("past_incidents")
    except ValueError:
        # Primo incidente su un DB mai seedato: creiamo la tabella con questo record.
        db.create_table("past_incidents", data=[record])
        return record["id"]
    # .add() appende il nuovo record SENZA toccare quelli esistenti.
    table.add([record])
    return record["id"]


def add_verified_solution(db: lancedb.DBConnection, solution: dict, vector: list[float]) -> str:
    """Aggiunge UNA soluzione verificata da umano a 'verified_solutions' (append).
    Metà human-feedback del loop di apprendimento: quando una persona fornisce
    una soluzione, diventa una fonte ad alta priorità per i casi futuri.
    Crea la tabella se non esiste ancora."""
    record = _solution_record(solution, vector)
    try:
        table = db.open_table("verified_solutions")
    except ValueError:
        db.create_table("verified_solutions", data=[record])  # tabella assente (DB senza seed)
        return record["id"]
    table.add([record])
    return record["id"]


def search(db: lancedb.DBConnection, table_name: str, query_vector: list[float],
        k: int = 5, threshold: float = 0.0) -> list[dict]:
    """Cerca i record più simili in una tabella LanceDB.

    Args:
        table_name: "past_incidents", "knowledge_base", o "verified_solutions"
        query_vector: il vettore della query
        k: numero massimo di risultati
        threshold: soglia minima di similarità (0-1, coseno). Sotto questa, il risultato viene scartato.

    Returns:
        Lista di dizionari con i campi del record + "_distance" (distanza, non similarità)
        Nota: LanceDB restituisce distanza L2 per default. Con vettori normalizzati,
        distanza = 2*(1-coseno), quindi threshold va convertita.
    """
    table = db.open_table(table_name)

    # API "a catena" (fluent): cerca i vicini al vettore, limita a k, e converte
    # il risultato in una lista di dict. Ogni dict ha anche "_distance".
    results = (
        table.search(query_vector)
        .limit(k)
        .to_list()
    )

    # Filtra per soglia se richiesto.
    # Con vettori normalizzati (come i nostri), distanza L2 = 2*(1-coseno),
    # quindi coseno (= similarità) = 1 - distanza/2. Teniamo solo i risultati
    # abbastanza simili da superare la soglia.
    if threshold > 0:
        results = [
            r for r in results
            if (1 - r["_distance"] / 2) >= threshold
        ]

    return results


def _build_incident_text(incident: dict) -> str:
    """Costruisce il testo da incorporare per un incidente.
    Combina descrizione, root cause e risoluzione per massimizzare il retrieval."""
    # Mettiamo insieme più campi così la ricerca funziona sia se l'utente descrive
    # i SINTOMI (description) sia se cerca per CAUSA o SOLUZIONE.
    parts = [
        incident.get("description", ""),
        incident.get("root_cause", ""),
    ]
    steps = incident.get("resolution_steps", [])
    if steps:
        # I passi sono una lista: li uniamo in un'unica stringa prima di aggiungerli.
        parts.append(" ".join(steps))
    # Uniamo tutti i pezzi con uno spazio: è questo il testo che verrà embeddato.
    return " ".join(parts)
