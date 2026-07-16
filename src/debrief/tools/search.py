"""Strumenti RAG esposti agli agenti Agno."""

from debrief.rag.retriever import (
    retrieve_knowledge,
    retrieve_similar_incidents,
)


def search_past_incidents(query: str) -> str:
    """Find relevant past incidents from symptoms or error messages."""
    results = retrieve_similar_incidents(query)

    if not results:
        return "No similar past incidents found above the similarity threshold."

    output_parts = [
        f"Found {len(results)} past incident(s) above the similarity threshold. "
        "Do not treat this as a mandatory top-3 list; cite only the incidents that are actually useful.\n"
    ]
    for r in results:
        similarity = r["similarity"]
        output_parts.append(
            f"--- Incident {r['id']} (similarity: {similarity:.0%}) ---\n"
            f"Title: {r['title']}\n"
            f"Severity: {r['severity']}\n"
            f"Resolution: {r.get('resolution', 'N/A')}\n"
        )

    return "\n".join(output_parts)


def search_knowledge_base(query: str) -> str:
    """Find relevant runbooks and operational procedures."""
    results = retrieve_knowledge(query)

    if not results:
        return "No relevant knowledge base articles found."

    output_parts = [f"Found {len(results)} relevant article(s):\n"]
    for r in results:
        similarity = r["similarity"]
        # Limita il contesto inviato al modello.
        text = r.get("text", "")
        if len(text) > 1500:
            text = text[:1500] + "... [truncated]"
        output_parts.append(
            f"--- {r.get('title', r['id'])} (relevance: {similarity:.0%}) ---\n"
            f"{text}\n"
        )

    return "\n".join(output_parts)


