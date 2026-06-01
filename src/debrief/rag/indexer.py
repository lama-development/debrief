"""
indexer.py - Indicizzazione e ricerca in LanceDB.

Gestisce le tre collezioni:
- past_incidents: incidenti chiusi con post-mortem
- knowledge_base: runbook e documentazione
- verified_solutions: soluzioni fornite da umani (priorità alta)
"""

import os
import json
import lancedb
import pyarrow as pa

# Dimensione del vettore (all-MiniLM-L6-v2 = 384)
VECTOR_DIM = 384


def get_db(db_path: str = None) -> lancedb.DBConnection:
    """Apre (o crea) il database LanceDB."""
    if db_path is None:
        db_path = os.getenv("LANCEDB_PATH", "data/lancedb")
    os.makedirs(db_path, exist_ok=True)
    return lancedb.connect(db_path)


def index_incidents(db: lancedb.DBConnection, incidents: list[dict], vectors: list[list[float]]):
    """Indicizza gli incidenti passati in LanceDB.

    Per ogni incidente, il testo incorporato è:
    descrizione + root_cause + resolution_steps
    (così l'investigator può cercare sia per sintomi che per soluzioni)
    """
    records = []
    for inc, vec in zip(incidents, vectors):
        records.append({
            "id": inc["id"],
            "title": inc["title"],
            "category": inc["category"],
            "severity": inc["severity"],
            "text": _build_incident_text(inc),  # il testo che è stato incorporato
            "root_cause": inc.get("root_cause", ""),
            "resolution_steps": json.dumps(inc.get("resolution_steps", []), ensure_ascii=False),
            "vector": vec,
        })

    # Crea o sovrascrive la tabella
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
    records = []
    for sol, vec in zip(solutions, vectors):
        records.append({
            "id": sol["id"],
            "incident_id": sol["incident_id"],
            "problem_context": sol["problem_context"],
            "solution": sol["solution"],
            "provided_by": sol.get("provided_by", ""),
            "text": sol["problem_context"] + " " + sol["solution"],  # testo incorporato
            "vector": vec,
        })

    db.create_table("verified_solutions", data=records, mode="overwrite")
    return len(records)


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

    results = (
        table.search(query_vector)
        .limit(k)
        .to_list()
    )

    # Filtra per soglia se richiesto
    # Con vettori normalizzati (come i nostri), distanza L2 = 2*(1-coseno)
    # Quindi coseno = 1 - distanza/2
    if threshold > 0:
        results = [
            r for r in results
            if (1 - r["_distance"] / 2) >= threshold
        ]

    return results


def _build_incident_text(incident: dict) -> str:
    """Costruisce il testo da incorporare per un incidente.
    Combina descrizione, root cause e risoluzione per massimizzare il retrieval."""
    parts = [
        incident.get("description", ""),
        incident.get("root_cause", ""),
    ]
    steps = incident.get("resolution_steps", [])
    if steps:
        parts.append(" ".join(steps))
    return " ".join(parts)
