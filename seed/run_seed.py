"""Rigenera SQLite e LanceDB dai dati dimostrativi; non è una migrazione."""

import os
import sys
import json
import glob

from debrief.database import get_connection, create_tables, load_teams, load_incidents
from debrief.tools.embedding import embed_text, embed_texts
from debrief.rag.indexer import (
    get_db,
    index_incidents,
    index_knowledge_base,
    search,
    _build_incident_text,
)


def main():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")

    print("\n================================================")
    print(" Debrief - Database seed")
    print("================================================")

    seed_dir = os.path.join(os.path.dirname(__file__))
    incidents_path = os.path.join(seed_dir, "incidents.json")
    teams_path = os.path.join(seed_dir, "teams.json")
    kb_dir = os.path.join(seed_dir, "knowledge_base")

    # SQLite
    print("\n== SQLite ==")
    print("[INFO] Preparing database")
    conn = get_connection()
    create_tables(conn)
    print("[OK] Tables created")

    n_teams = load_teams(conn, teams_path)
    print(f"[OK] {n_teams} teams loaded")

    n_incidents = load_incidents(conn, incidents_path)
    print(f"[OK] {n_incidents} incidents loaded")

    conn.close()

    # Dati per l'indicizzazione
    print("\n== LanceDB source data ==")
    print("[INFO] Preparing documents")
    with open(incidents_path, encoding="utf-8") as f:
        incidents = json.load(f)

    # Solo i casi risolti contengono conoscenza riutilizzabile.
    rag_incidents = [inc for inc in incidents if inc.get("status", "resolved") == "resolved"]

    kb_docs = []
    for filepath in sorted(glob.glob(os.path.join(kb_dir, "*.md"))):
        with open(filepath, encoding="utf-8") as f:
            text = f.read()
        filename = os.path.basename(filepath)
        kb_docs.append({
            "id": filename.replace(".md", ""),
            "title": filename.replace("_", " ").replace(".md", "").title(),
            "text": text,
        })

    print(
        "[OK] "
        f"{len(incidents)} incidents ({len(rag_incidents)} risolti -> RAG), "
        f"{len(kb_docs)} runbooks ready"
    )

    # Rende le procedure indicizzate autonome dai segnaposto dei team.
    with open(teams_path, encoding="utf-8") as f:
        teams = json.load(f)
    team_map = {team["id"]: team["name"] for team in teams}

    placeholders_resolved = 0
    for doc in kb_docs:
        for team_id, team_name in team_map.items():
            placeholder = "{{" + team_id + "}}"
            if placeholder in doc["text"]:
                count = doc["text"].count(placeholder)
                doc["text"] = doc["text"].replace(placeholder, team_name)
                placeholders_resolved += count

    print(f"[OK] {placeholders_resolved} team placeholders resolved in runbooks")

    # Embedding
    print("\n== Embeddings ==")

    incident_texts = [_build_incident_text(inc) for inc in rag_incidents]
    kb_texts = [doc["text"] for doc in kb_docs]
    print(f"[INFO] Computing {len(incident_texts) + len(kb_texts)} embeddings")

    # Un'unica elaborazione in blocco riduce il costo di inferenza.
    all_texts = incident_texts + kb_texts
    all_vectors = embed_texts(all_texts)

    # Mantiene lo stesso ordine usato nel batch.
    idx = 0
    incident_vectors = all_vectors[idx:idx + len(rag_incidents)]
    idx += len(rag_incidents)
    kb_vectors = all_vectors[idx:idx + len(kb_docs)]

    # Indicizzazione
    print("\n== Indexing ==")
    print("[INFO] Writing LanceDB tables")
    db = get_db()

    n = index_incidents(db, rag_incidents, incident_vectors)
    print(f"[OK] {n} incidents indexed in 'past_incidents'")

    n = index_knowledge_base(db, kb_docs, kb_vectors)
    print(f"[OK] {n} runbooks indexed in 'knowledge_base'")

    # Verifica rapida del recupero semantico
    print("\n== Semantic search smoke test ==")

    test_queries = [
        ("TSPlus Remote App disconnette subito dopo il login", "past_incidents"),
        ("timbratore alimentato ma non raggiungibile sulla VLAN corretta", "past_incidents"),
        ("come gestire un errore del PLC", "knowledge_base"),
    ]

    for query, table in test_queries:
        query_vec = embed_text(query)
        results = search(db, table, query_vec, k=3, threshold=0.3)

        print(f"[QUERY] \"{query}\" [{table}]")
        if results:
            for r in results:
                similarity = 1 - r["_distance"] / 2  # Da distanza L2 a similarità coseno
                id_field = r.get("id", "?")
                title_field = r.get("title", r.get("text", "")[:60])
                print(f"   [HIT] {id_field} score={similarity:.2f} {title_field}")
        else:
            print("   [MISS] No results above threshold")
        print()

    print("[DONE] Seed complete. The database is ready.")


if __name__ == "__main__":
    main()
