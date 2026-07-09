"""
search.py - Tool di ricerca per gli agenti.

Queste funzioni vengono passate ad Agno come "tools" (strumenti). Un tool è una
funzione che l'LLM può decidere di CHIAMARE da solo quando gli serve: l'agente
"ragiona", capisce che deve cercare incidenti passati, e invoca search_past_incidents.

Agno legge automaticamente il DOCSTRING e i TYPE HINTS di ogni funzione per
costruire lo schema del tool (nome, descrizione, parametri) da mostrare all'LLM.
Per questo i docstring qui sono in inglese e molto descrittivi: li "legge" il modello.
Ogni funzione restituisce una STRINGA leggibile che l'agente usa nella sua risposta.
"""

from debrief.rag.retriever import (
    retrieve_knowledge,
    retrieve_similar_incidents,
)


def search_past_incidents(query: str) -> str:
    """Search past incidents for cases similar to the given query.
    Use this tool when you need to find incidents that happened before,
    identify recurring patterns, or check if something similar has occurred.

    Args:
        query: Description of symptoms, error messages, or the situation to search for.

    Returns:
        Up to three past incidents above the similarity threshold. If only one
        incident is truly similar, only one is returned. Never assume the list
        must be filled to three results.
    """
    # 1. Trasforma la query in vettore. 2. Apre il DB vettoriale. 3. Cerca i k più
    # simili sopra la soglia.
    results = retrieve_similar_incidents(query)

    # `if not results` → vero se la lista è vuota. Importante: diciamo all'agente
    # che non c'è nulla, così NON inventa incidenti (regola anti-allucinazione).
    if not results:
        return "No similar past incidents found above the similarity threshold."

    # Costruiamo la risposta come lista di pezzi di testo, poi li uniamo. Più
    # efficiente che concatenare stringhe in un loop.
    output_parts = [
        f"Found {len(results)} past incident(s) above the similarity threshold. "
        "Do not treat this as a mandatory top-3 list; cite only the incidents that are actually useful.\n"
    ]
    for r in results:
        # _distance è la distanza L2 restituita da LanceDB; con vettori normalizzati
        # similarità coseno = 1 - distanza/2. (Vedi spiegazione in indexer.search.)
        similarity = r["similarity"]
        output_parts.append(
            f"--- Incident {r['id']} (similarity: {similarity:.0%}) ---\n"
            f"Title: {r['title']}\n"
            f"Severity: {r['severity']}\n"
            f"Resolution: {r.get('resolution', 'N/A')}\n"
        )

    # "\n".join(lista) → unisce i pezzi separandoli con un a-capo.
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
    results = retrieve_knowledge(query)

    if not results:
        return "No relevant knowledge base articles found."

    output_parts = [f"Found {len(results)} relevant article(s):\n"]
    for r in results:
        similarity = r["similarity"]
        # Tronca il testo a 1500 caratteri per non esplodere il contesto: i
        # runbook possono essere lunghi e l'LLM ha un limite di token.
        text = r.get("text", "")
        if len(text) > 1500:
            text = text[:1500] + "... [truncated]"
        output_parts.append(
            f"--- {r.get('title', r['id'])} (relevance: {similarity:.0%}) ---\n"
            f"{text}\n"
        )

    return "\n".join(output_parts)


