"""
run_seed.py - Popola SQLite e LanceDB da zero con i dati di seed.

Uso:
    uv run seed

Cosa fa:
1. Crea le tabelle SQLite
2. Carica team, incidenti e soluzioni verificate in SQLite
3. Calcola gli embedding localmente
4. Indicizza tutto in LanceDB (3 collezioni)
5. Esegue un test di ricerca semantica per verificare che funzioni
"""

import os
import sys
import json
import glob

# Aggiungi la cartella src al path per poter importare i moduli
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from debrief.database import get_connection, create_tables, load_teams, load_incidents
from debrief.tools.embedding import embed_text, embed_texts
from debrief.rag.indexer import get_db, index_incidents, index_knowledge_base, index_verified_solutions, search, _build_incident_text


def main():
    print("\n🟣 Starting database seed\n")

    # Percorsi (relativi alla root del progetto)
    seed_dir = os.path.join(os.path.dirname(__file__))
    incidents_path = os.path.join(seed_dir, "incidents.json")
    teams_path = os.path.join(seed_dir, "teams.json")
    solutions_path = os.path.join(seed_dir, "verified_solutions.json")
    kb_dir = os.path.join(seed_dir, "knowledge_base")

    # --- 1. SQLite ---
    print("🔵 Setting up SQLite...")
    conn = get_connection()
    create_tables(conn)
    print("🟢 Tables created")

    n_teams = load_teams(conn, teams_path)
    print(f"🟢 {n_teams} teams loaded")

    n_incidents = load_incidents(conn, incidents_path)
    print(f"🟢 {n_incidents} incidents loaded")

    conn.close()
    print()

    # --- 2. Carica i dati per l'indicizzazione ---
    print("🔵 Preparing data for LanceDB...")
    with open(incidents_path, encoding="utf-8") as f:
        incidents = json.load(f)

    with open(solutions_path, encoding="utf-8") as f:
        solutions = json.load(f)

    # Carica i runbook della knowledge base
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

    print(f"🟢 {len(incidents)} incidents, {len(solutions)} solutions, {len(kb_docs)} runbooks ready")

    # Risolvi i placeholder {{TEAM_ID}} nei runbook con i nomi reali dal catalogo team.
    # Il testo indicizzato in LanceDB sarà leggibile e autocontenuto,
    # ma nel sorgente markdown cambi il nome in un posto solo (teams.json).
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

    print(f"🟢 {placeholders_resolved} team placeholders resolved in runbooks")
    print()

    # --- 3. Calcola gli embedding ---
    print("🔵 Computing embeddings...")

    # Testi da incorporare per ogni tipo
    incident_texts = [_build_incident_text(inc) for inc in incidents]
    solution_texts = [s["problem_context"] + " " + s["solution"] for s in solutions]
    kb_texts = [doc["text"] for doc in kb_docs]

    # Calcola tutti gli embedding in batch
    all_texts = incident_texts + solution_texts + kb_texts
    all_vectors = embed_texts(all_texts)

    # Dividi i vettori per tipo
    idx = 0
    incident_vectors = all_vectors[idx:idx + len(incidents)]; idx += len(incidents)
    solution_vectors = all_vectors[idx:idx + len(solutions)]; idx += len(solutions)
    kb_vectors = all_vectors[idx:idx + len(kb_docs)]

    print()

    # --- 4. Indicizza in LanceDB ---
    print("🔵 Indexing into LanceDB...")
    db = get_db()

    n = index_incidents(db, incidents, incident_vectors)
    print(f"🟢 {n} incidents indexed in 'past_incidents'")

    n = index_verified_solutions(db, solutions, solution_vectors)
    print(f"🟢 {n} solutions indexed in 'verified_solutions'")

    n = index_knowledge_base(db, kb_docs, kb_vectors)
    print(f"🟢 {n} runbooks indexed in 'knowledge_base'")
    print()

    # --- 5. Test di ricerca ---
    print("🔵 Semantic search test...")
    print()

    test_queries = [
        ("il disco del server è pieno", "past_incidents"),
        ("come gestire un errore del PLC", "knowledge_base"),
        ("sensore di temperatura guasto sul macchinario", "verified_solutions"),
    ]

    for query, table in test_queries:
        query_vec = embed_text(query)
        results = search(db, table, query_vec, k=3, threshold=0.3)

        print(f"🔵 Query: \"{query}\" [{table}]")
        if results:
            for r in results:
                similarity = 1 - r["_distance"] / 2  # distanza L2 -> coseno
                id_field = r.get("id", "?")
                title_field = r.get("title", r.get("problem_context", "")[:60])
                print(f"🟢 {id_field} ({similarity:.2f}) {title_field}")
        else:
            print(f"🔴 No results above threshold")
        print()

    print("🟣 Seed complete! The database is ready.\n")


if __name__ == "__main__":
    main()