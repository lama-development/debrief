"""Indicizzazione e ricerca vettoriale in LanceDB."""

import os
import lancedb
from debrief.config import LANCEDB_PATH


def get_db(db_path: str | None = None) -> lancedb.DBConnection:
    """Apre (o crea) il database LanceDB."""
    if db_path is None:
        db_path = os.getenv("LANCEDB_PATH", LANCEDB_PATH)
    os.makedirs(db_path, exist_ok=True)
    return lancedb.connect(db_path)


def _incident_record(inc: dict, vec: list[float]) -> dict:
    """Costruisce il record condiviso da caricamento e aggiornamenti."""
    return {
        "id": inc["id"],
        "title": inc["title"],
        "severity": inc.get("severity", ""),
        "text": _build_incident_text(inc),
        "resolution": inc.get("resolution", ""),
        "vector": vec,
    }


def index_incidents(db: lancedb.DBConnection, incidents: list[dict], vectors: list[list[float]]):
    """Ricrea l'indice degli incidenti passati."""
    records = [_incident_record(inc, vec) for inc, vec in zip(incidents, vectors)]

    # Solo il caricamento iniziale sovrascrive l'intero indice.
    db.create_table("past_incidents", data=records, mode="overwrite")
    return len(records)


def index_knowledge_base(db: lancedb.DBConnection, docs: list[dict], vectors: list[list[float]]):
    """Indicizza le procedure della base di conoscenza."""
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


def upsert_past_incident(db: lancedb.DBConnection, incident: dict, vector: list[float]) -> str:
    """Inserisce o aggiorna un incidente senza duplicarlo."""
    record = _incident_record(incident, vector)
    try:
        table = db.open_table("past_incidents")
    except ValueError:
        db.create_table("past_incidents", data=[record])
        return record["id"]
    safe_id = record["id"].replace("'", "''")
    table.delete(f"id = '{safe_id}'")
    table.add([record])
    return record["id"]


def search(db: lancedb.DBConnection, table_name: str, query_vector: list[float],
        k: int = 5, threshold: float = 0.0) -> list[dict]:
    """Cerca fino a k record sopra la soglia di similarità coseno."""
    table = db.open_table(table_name)

    results = (
        table.search(query_vector)
        .limit(k)
        .to_list()
    )

    # Per vettori normalizzati: similarità coseno = 1 - distanza L2 / 2.
    if threshold > 0:
        results = [
            r for r in results
            if (1 - r["_distance"] / 2) >= threshold
        ]

    return results


def _build_incident_text(incident: dict) -> str:
    """Combina i campi indicizzati per il recupero semantico."""
    parts = [
        incident.get("title", ""),
        incident.get("description", ""),
        incident.get("resolution", ""),
    ]
    return " ".join(p for p in parts if p)
