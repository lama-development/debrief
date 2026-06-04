"""
search.py - Tool di ricerca per gli agenti.

Queste funzioni vengono passate ad Agno come tools.
Agno usa il docstring e i type hints per creare lo schema del tool automaticamente.
Ogni funzione restituisce una stringa leggibile che l'agente usa nella sua risposta.
"""

from debrief.tools.embedding import embed_text
from debrief.rag.indexer import get_db, search
from debrief.config import SIMILARITY_THRESHOLD, TOP_K_INCIDENTS, TOP_K_VERIFIED, TOP_K_KB


def search_past_incidents(query: str) -> str:
    """Search past incidents for cases similar to the given query.
    Use this tool when you need to find incidents that happened before,
    identify recurring patterns, or check if something similar has occurred.
    
    Args:
        query: Description of symptoms, error messages, or the situation to search for.
    
    Returns:
        A formatted list of similar past incidents with their details, or a message
        saying no similar incidents were found.
    """
    query_vector = embed_text(query)
    db = get_db()
    results = search(db, "past_incidents", query_vector, k=TOP_K_INCIDENTS, threshold=SIMILARITY_THRESHOLD)

    if not results:
        return "No similar past incidents found above the similarity threshold."

    output_parts = [f"Found {len(results)} similar past incident(s):\n"]
    for r in results:
        similarity = 1 - r["_distance"] / 2
        output_parts.append(
            f"--- Incident {r['id']} (similarity: {similarity:.0%}) ---\n"
            f"Title: {r['title']}\n"
            f"Category: {r['category']} | Severity: {r['severity']}\n"
            f"Root cause: {r.get('root_cause', 'N/A')}\n"
            f"Resolution: {r.get('resolution_steps', 'N/A')}\n"
        )

    return "\n".join(output_parts)


def search_knowledge_base(query: str) -> str:
    """Search the knowledge base for runbooks, procedures, and best practices.
    Use this tool when you need operational procedures, troubleshooting guides,
    or general best practices for handling a type of incident.
    
    Args:
        query: The topic or problem type to search for in the knowledge base.
    
    Returns:
        Relevant knowledge base articles, or a message saying nothing was found.
    """
    query_vector = embed_text(query)
    db = get_db()
    results = search(db, "knowledge_base", query_vector, k=TOP_K_KB, threshold=SIMILARITY_THRESHOLD)

    if not results:
        return "No relevant knowledge base articles found."

    output_parts = [f"Found {len(results)} relevant article(s):\n"]
    for r in results:
        similarity = 1 - r["_distance"] / 2
        # Tronca il testo a 1500 caratteri per non esplodere il contesto
        text = r.get("text", "")
        if len(text) > 1500:
            text = text[:1500] + "... [truncated]"
        output_parts.append(
            f"--- {r.get('title', r['id'])} (relevance: {similarity:.0%}) ---\n"
            f"{text}\n"
        )

    return "\n".join(output_parts)


def search_verified_solutions(query: str) -> str:
    """Search for human-verified solutions to past problems.
    These are solutions that were provided by human experts when the system
    couldn't solve a problem autonomously. They have the highest reliability.
    
    Args:
        query: Description of the problem to find verified solutions for.
    
    Returns:
        Verified solutions with their context, or a message saying none were found.
    """
    query_vector = embed_text(query)
    db = get_db()
    results = search(db, "verified_solutions", query_vector, k=TOP_K_VERIFIED, threshold=SIMILARITY_THRESHOLD)

    if not results:
        return "No verified human solutions found for this type of problem."

    output_parts = [f"Found {len(results)} verified solution(s):\n"]
    for r in results:
        similarity = 1 - r["_distance"] / 2
        output_parts.append(
            f"--- Solution {r['id']} (relevance: {similarity:.0%}) ---\n"
            f"Problem context: {r.get('problem_context', 'N/A')}\n"
            f"Solution: {r.get('solution', 'N/A')}\n"
            f"Provided by: {r.get('provided_by', 'N/A')}\n"
        )

    return "\n".join(output_parts)