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

È uno SCRIPT, non un modulo importato dall'app: si lancia una volta sola per
preparare il database iniziale (i dati passati su cui il RAG farà le ricerche).
"""

import os
import sys      # serve per manipolare il "path" di import (vedi sotto)
import json
import glob     # cerca file con un pattern (es. tutti i *.md in una cartella)

# Aggiungi la cartella src/ al path di Python così possiamo importare `debrief`.
# __file__ = percorso di questo script; dirname(__file__) = la sua cartella (seed/);
# ".." sale alla root del progetto e poi entra in "src". sys.path.insert(0, ...)
# mette questa cartella in cima alla lista dove Python cerca i moduli da importare.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Riusiamo le STESSE funzioni dell'app (DRY): seed e runtime scrivono in modo
# identico, così i dati di seed e quelli creati a runtime hanno la stessa forma.
from debrief.database import get_connection, create_tables, load_teams, load_incidents
from debrief.tools.embedding import embed_text, embed_texts
from debrief.rag.indexer import get_db, index_incidents, index_knowledge_base, index_verified_solutions, search, _build_incident_text


def main():
    print("\n🟣 Starting database seed\n")

    # Percorsi (relativi alla root del progetto). os.path.join unisce i pezzi con
    # il separatore giusto del sistema operativo (\ su Windows, / su Linux/Mac).
    seed_dir = os.path.join(os.path.dirname(__file__))
    incidents_path = os.path.join(seed_dir, "incidents.json")
    teams_path = os.path.join(seed_dir, "teams.json")
    solutions_path = os.path.join(seed_dir, "verified_solutions.json")
    kb_dir = os.path.join(seed_dir, "knowledge_base")

    # --- 1. SQLite ---
    print("🔵 Setting up SQLite...")
    conn = get_connection()
    create_tables(conn)              # idempotente: sicuro anche se le tabelle esistono già
    print("🟢 Tables created")

    # Ogni loader restituisce QUANTI record ha caricato: lo stampiamo come riscontro.
    n_teams = load_teams(conn, teams_path)
    print(f"🟢 {n_teams} teams loaded")

    n_incidents = load_incidents(conn, incidents_path)
    print(f"🟢 {n_incidents} incidents loaded")

    conn.close()
    print()

    # --- 2. Carica i dati per l'indicizzazione ---
    # Per il RAG ci servono i dati grezzi (gli stessi file JSON), che rileggiamo qui
    # perché ora dobbiamo calcolarne gli embedding, non solo salvarli in SQLite.
    print("🔵 Preparing data for LanceDB...")
    with open(incidents_path, encoding="utf-8") as f:
        incidents = json.load(f)

    with open(solutions_path, encoding="utf-8") as f:
        solutions = json.load(f)

    # Carica i runbook della knowledge base (file Markdown).
    kb_docs = []
    # glob("*.md") trova tutti i file .md; sorted() li ordina per nome (output stabile).
    for filepath in sorted(glob.glob(os.path.join(kb_dir, "*.md"))):
        with open(filepath, encoding="utf-8") as f:
            text = f.read()          # legge l'INTERO contenuto del file come stringa
        filename = os.path.basename(filepath)   # solo il nome file, senza il percorso
        kb_docs.append({
            # Dal nome file ricaviamo id e titolo: togliamo ".md" per l'id; per il
            # titolo sostituiamo "_" con spazi e .title() mette le iniziali maiuscole
            # (es. "vpn_forticlient.md" -> "Vpn Forticlient").
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
    # Dict comprehension: costruisce una mappa {id_team: nome_team} per la sostituzione.
    team_map = {team["id"]: team["name"] for team in teams}

    placeholders_resolved = 0   # contatore, solo per il messaggio di riepilogo finale
    for doc in kb_docs:
        # .items() itera la mappa dando coppie (chiave, valore) = (id, nome).
        for team_id, team_name in team_map.items():
            placeholder = "{{" + team_id + "}}"   # es. "{{T-NET}}"
            if placeholder in doc["text"]:
                count = doc["text"].count(placeholder)        # quante occorrenze
                doc["text"] = doc["text"].replace(placeholder, team_name)  # sostituisci tutte
                placeholders_resolved += count

    print(f"🟢 {placeholders_resolved} team placeholders resolved in runbooks")
    print()

    # --- 3. Calcola gli embedding ---
    print("🔵 Computing embeddings...")

    # Per ogni tipo costruiamo la lista dei testi DA incorporare. Devono coincidere
    # con il testo usato in fase di ricerca (vedi indexer._build_incident_text).
    incident_texts = [_build_incident_text(inc) for inc in incidents]
    solution_texts = [s["problem_context"] + " " + s["solution"] for s in solutions]
    kb_texts = [doc["text"] for doc in kb_docs]

    # Calcola TUTTI gli embedding in un'unica chiamata batch: molto più veloce che
    # farne una per testo. `+` tra liste le concatena in un'unica grande lista.
    all_texts = incident_texts + solution_texts + kb_texts
    all_vectors = embed_texts(all_texts)

    # Ora dividiamo il grande blocco di vettori nei tre gruppi, nello stesso ordine
    # in cui li abbiamo concatenati. Usiamo lo slicing [inizio:fine] e un indice
    # scorrevole `idx`. (Il `;` separa due istruzioni sulla stessa riga.)
    idx = 0
    incident_vectors = all_vectors[idx:idx + len(incidents)]; idx += len(incidents)
    solution_vectors = all_vectors[idx:idx + len(solutions)]; idx += len(solutions)
    kb_vectors = all_vectors[idx:idx + len(kb_docs)]

    print()

    # --- 4. Indicizza in LanceDB ---
    print("🔵 Indexing into LanceDB...")
    db = get_db()

    # Ogni funzione index_* crea/sovrascrive la sua collezione e restituisce il
    # numero di record indicizzati.
    n = index_incidents(db, incidents, incident_vectors)
    print(f"🟢 {n} incidents indexed in 'past_incidents'")

    n = index_verified_solutions(db, solutions, solution_vectors)
    print(f"🟢 {n} solutions indexed in 'verified_solutions'")

    n = index_knowledge_base(db, kb_docs, kb_vectors)
    print(f"🟢 {n} runbooks indexed in 'knowledge_base'")
    print()

    # --- 5. Test di ricerca ---
    # Verifica di sanità: cerchiamo qualche query di esempio e stampiamo i risultati,
    # così vediamo subito se la ricerca semantica funziona dopo il seed.
    print("🔵 Semantic search test...")
    print()

    # Lista di tuple (query, tabella_in_cui_cercare).
    test_queries = [
        ("il disco del server è pieno", "past_incidents"),
        ("come gestire un errore del PLC", "knowledge_base"),
        ("sensore di temperatura guasto sul macchinario", "verified_solutions"),
    ]

    # "for query, table in lista" spacchetta ogni tupla nelle due variabili.
    for query, table in test_queries:
        query_vec = embed_text(query)
        results = search(db, table, query_vec, k=3, threshold=0.3)

        print(f"🔵 Query: \"{query}\" [{table}]")
        if results:
            for r in results:
                similarity = 1 - r["_distance"] / 2  # distanza L2 -> coseno
                id_field = r.get("id", "?")
                # Prova "title"; se manca usa i primi 60 char di "problem_context"
                # (le soluzioni verificate non hanno un titolo).
                title_field = r.get("title", r.get("problem_context", "")[:60])
                print(f"🟢 {id_field} ({similarity:.2f}) {title_field}")
        else:
            print(f"🔴 No results above threshold")
        print()

    print("🟣 Seed complete! The database is ready.")


# Esegui main() solo se lo script è lanciato direttamente (non se importato).
if __name__ == "__main__":
    main()
