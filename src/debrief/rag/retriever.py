"""Retrieval strutturato usato dall'applicazione e dalla valutazione."""

import logging

from debrief.config import (
    INCIDENT_SIMILARITY_THRESHOLD,
    SIMILARITY_THRESHOLD,
    TOP_K_INCIDENTS,
    TOP_K_KB,
)
from debrief.rag.indexer import get_db, search
from debrief.tools.embedding import embed_text

logger = logging.getLogger(__name__)


def _retrieve(query: str, table: str, k: int, threshold: float) -> list[dict]:
    """Esegue la pipeline comune embedding → LanceDB → risultati strutturati."""
    try:
        results = search(get_db(), table, embed_text(query), k=k, threshold=threshold)
        return [
            {**result, "similarity": round(1 - result["_distance"] / 2, 4)}
            for result in results
        ]
    except Exception:
        logger.exception("Retrieval failed on table %s", table)
        return []


def retrieve_similar_incidents(
    query: str,
    k: int = TOP_K_INCIDENTS,
    threshold: float = INCIDENT_SIMILARITY_THRESHOLD,
) -> list[dict]:
    """Recupera incidenti passati semanticamente simili."""
    return _retrieve(query, "past_incidents", k, threshold)


def retrieve_knowledge(
    query: str,
    k: int = TOP_K_KB,
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[dict]:
    """Recupera articoli e runbook dalla knowledge base."""
    return _retrieve(query, "knowledge_base", k, threshold)
