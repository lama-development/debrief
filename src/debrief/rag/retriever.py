"""Retrieval strutturato usato dall'applicazione e dalla valutazione."""

import logging

from debrief.config import SIMILARITY_THRESHOLD, TOP_K_INCIDENTS, TOP_K_KB, TOP_K_VERIFIED
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
    threshold: float = SIMILARITY_THRESHOLD,
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


def retrieve_verified_solutions(
    query: str,
    k: int = TOP_K_VERIFIED,
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[dict]:
    """Recupera soluzioni fornite e verificate da persone."""
    return _retrieve(query, "verified_solutions", k, threshold)
