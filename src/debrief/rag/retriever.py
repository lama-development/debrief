"""
retriever.py - Recupero a livello applicativo e indicizzazione a runtime.

Differenza chiave con tools/search.py:
  tools/search.py  →  per gli AGENTI: restituisce STRINGHE formattate (Agno tool)
  rag/retriever.py →  per l'APP / API: restituisce DICT strutturati (dati grezzi)

Stessa ricerca sotto, due "vestiti" diversi a seconda di chi consuma il risultato:
un LLM vuole testo leggibile, il codice applicativo vuole dati strutturati.

Gestisce anche il "loop chiuso": riaggiungere a LanceDB gli incidenti risolti e
le soluzioni verificate, così il sistema IMPARA col tempo.
"""

import json

from debrief.config import (
    SIMILARITY_THRESHOLD,
    TOP_K_INCIDENTS,
    TOP_K_KB,
    TOP_K_VERIFIED,
)
from debrief.rag.indexer import _build_incident_text, get_db, search
from debrief.tools.embedding import embed_text


def retrieve_similar_incidents(
    query: str,
    k: int = TOP_K_INCIDENTS,
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[dict]:
    """Cerca incidenti passati simili alla query.

    Returns:
        Lista di record con i campi originali più 'similarity' (0-1, coseno).
        Lista vuota se nessun match supera la soglia o in caso di errore.
    """
    # try/except: se qualcosa va storto (DB assente, ecc.) NON facciamo crashare
    # l'app: logghiamo e restituiamo lista vuota. Il chiamante gestisce "nessun
    # risultato" allo stesso modo di un errore.
    try:
        vector = embed_text(query)
        db = get_db()
        results = search(db, "past_incidents", vector, k=k, threshold=threshold)
        # Aggiungiamo un campo 'similarity' leggibile (0-1) a ogni risultato, così
        # il layer applicativo non deve conoscere la formula distanza→similarità.
        for r in results:
            r["similarity"] = round(1 - r["_distance"] / 2, 4)
        return results
    except Exception as e:
        print(f"🔴 retrieve_similar_incidents failed: {e}")
        return []


def retrieve_knowledge(
    query: str,
    k: int = TOP_K_KB,
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[dict]:
    """Cerca documenti nella knowledge base (runbook, procedure).

    Returns:
        Lista di record con 'similarity' aggiunto. Lista vuota su errore.
    """
    try:
        vector = embed_text(query)
        db = get_db()
        results = search(db, "knowledge_base", vector, k=k, threshold=threshold)
        for r in results:
            r["similarity"] = round(1 - r["_distance"] / 2, 4)
        return results
    except Exception as e:
        print(f"🔴 retrieve_knowledge failed: {e}")
        return []


def retrieve_verified_solutions(
    query: str,
    k: int = TOP_K_VERIFIED,
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[dict]:
    """Cerca soluzioni verificate da umani (fonte ad alta priorità).

    Returns:
        Lista di record con 'similarity' aggiunto. Lista vuota su errore.
    """
    try:
        vector = embed_text(query)
        db = get_db()
        results = search(db, "verified_solutions", vector, k=k, threshold=threshold)
        for r in results:
            r["similarity"] = round(1 - r["_distance"] / 2, 4)
        return results
    except Exception as e:
        print(f"🔴 retrieve_verified_solutions failed: {e}")
        return []


def index_new_incident(incident: dict) -> None:
    """Aggiunge un post-mortem risolto alla collezione past_incidents (loop chiuso).

    Chiamato quando un incidente passa a 'resolved'.
    Il record viene appeso alla tabella esistente senza sovrascriverla.

    Args:
        incident: dict con almeno id, title, category, severity, root_cause,
                  resolution_steps (list[str]). 'description' o 'text' per l'embedding.

    Raises:
        Exception: se l'aggiunta fallisce (es. schema mismatch). Il chiamante decide
                   se ritentare o loggare.
    """
    try:
        # `A or B` → se _build_incident_text restituisce stringa vuota (falsy),
        # ripiega su incident["text"]. Garantiamo di avere SEMPRE del testo da embeddare.
        text = _build_incident_text(incident) or incident.get("text", "")
        vector = embed_text(text)
        record = {
            "id": incident["id"],
            "title": incident["title"],
            "category": incident.get("category", "other"),
            "severity": incident.get("severity", "SEV4"),
            "text": text,
            "root_cause": incident.get("root_cause", ""),
            "resolution_steps": json.dumps(
                incident.get("resolution_steps", []), ensure_ascii=False
            ),
            "vector": vector,
        }
        db = get_db()
        # open_table(...).add([record]) → appende il record alla tabella esistente.
        db.open_table("past_incidents").add([record])
        print(f"🟢 Indexed new incident: {incident['id']}")
    except Exception as e:
        print(f"🔴 index_new_incident failed for {incident.get('id', '?')}: {e}")
        # `raise` senza argomenti ri-solleva l'eccezione appena catturata: la
        # logghiamo ma lasciamo decidere al chiamante cosa farne.
        raise


def index_new_verified_solution(solution: dict) -> None:
    """Aggiunge una soluzione verificata da umano a LanceDB (learning loop).

    Chiamato quando un umano fornisce una soluzione durante l'escalation del resolver.
    La soluzione diventa immediatamente recuperabile per incidenti futuri simili.

    Args:
        solution: dict con id, incident_id, problem_context, solution, provided_by.

    Raises:
        Exception: se l'aggiunta fallisce. Il chiamante decide se ritentare.
    """
    try:
        # Embeddiamo contesto + soluzione insieme: così la ricerca trova la soluzione
        # sia partendo dalla descrizione del problema sia dal testo della soluzione.
        text = solution["problem_context"] + " " + solution["solution"]
        vector = embed_text(text)
        record = {
            "id": solution["id"],
            "incident_id": solution["incident_id"],
            "problem_context": solution["problem_context"],
            "solution": solution["solution"],
            "provided_by": solution.get("provided_by", ""),
            "text": text,
            "vector": vector,
        }
        db = get_db()
        db.open_table("verified_solutions").add([record])
        print(f"🟢 Indexed verified solution: {solution['id']}")
    except Exception as e:
        print(f"🔴 index_new_verified_solution failed for {solution.get('id', '?')}: {e}")
        raise
