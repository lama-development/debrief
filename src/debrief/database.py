"""
database.py - Setup e accesso al database SQLite.

SQLite è un database "in un file": non serve un server, tutto il DB è il file
data/debrief.db. È incluso in Python (modulo `sqlite3`), quindi zero dipendenze.

Questo file ha due responsabilità:
1. Creare le tabelle e caricare i dati di seed (incidenti/team iniziali).
2. Offrire funzioni di lettura/scrittura usate a runtime dall'app.

Convenzione importante delle funzioni runtime: ognuna APRE e CHIUDE la propria
connessione ed è atomica (fa il commit da sola). Il chiamante non deve gestire
transazioni: chiama la funzione e ottiene il risultato già salvato.
"""

import sqlite3   # driver SQLite incluso in Python
import os         # per creare cartelle / leggere env
import re         # espressioni regolari (regex), qui per estrarre il numero dall'ID
import json       # per serializzare/deserializzare i post-mortem come testo JSON
from datetime import datetime


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Restituisce una connessione al database SQLite.
    Crea la cartella 'data/' se non esiste."""
    # `db_path: str | None = None` → parametro opzionale: se non passato vale None e
    # allora leggiamo il percorso dalle env (con un default).
    if db_path is None:
        db_path = os.getenv("SQLITE_PATH", "data/debrief.db")

    # os.path.dirname("data/debrief.db") = "data". exist_ok=True → non errore se
    # la cartella c'è già. Così un clone pulito del progetto parte senza errori.
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    # row_factory = sqlite3.Row: fa sì che le righe lette si possano leggere per
    # NOME di colonna (row["title"]) e non solo per indice (row[1]). Più leggibile.
    conn.row_factory = sqlite3.Row
    # PRAGMA = comando di configurazione di SQLite. WAL (Write-Ahead Logging)
    # migliora le prestazioni e permette letture concorrenti durante le scritture.
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def create_tables(conn: sqlite3.Connection):
    """Crea tutte le tabelle. Idempotente (IF NOT EXISTS)."""
    # executescript esegue più istruzioni SQL in una volta. "IF NOT EXISTS"
    # significa che richiamare questa funzione più volte è sicuro: le tabelle
    # già presenti non vengono ricreate né cancellate (= idempotente).
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          TEXT PRIMARY KEY,
            username    TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token       TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS teams (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            description TEXT,
            contact_info TEXT
        );

        CREATE TABLE IF NOT EXISTS incidents (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            description TEXT NOT NULL,
            category    TEXT,
            severity    TEXT,
            status      TEXT DEFAULT 'declared',
            created_by  TEXT,
            session_id  TEXT,
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now')),
            resolved_at TEXT
        );

        CREATE TABLE IF NOT EXISTS timeline_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            timestamp   TEXT DEFAULT (datetime('now')),
            event_type  TEXT NOT NULL,
            actor       TEXT,
            content     TEXT,
            FOREIGN KEY (incident_id) REFERENCES incidents(id)
        );

        CREATE TABLE IF NOT EXISTS remediation_steps (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            description TEXT NOT NULL,
            completed   INTEGER DEFAULT 0,
            source      TEXT,
            FOREIGN KEY (incident_id) REFERENCES incidents(id)
        );

        CREATE TABLE IF NOT EXISTS post_mortems (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT UNIQUE NOT NULL,
            content_json TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (incident_id) REFERENCES incidents(id)
        );
    """)
    # SQLite richiede commit() per rendere PERMANENTI le modifiche sul file.
    conn.commit()


def load_teams(conn: sqlite3.Connection, teams_path: str):
    """Carica il catalogo team da un file JSON."""
    # `with open(...) as f` apre il file e lo CHIUDE automaticamente alla fine
    # del blocco (anche in caso di errore). encoding="utf-8" per gli accenti.
    with open(teams_path, encoding="utf-8") as f:
        teams = json.load(f)   # legge il JSON e lo trasforma in lista di dict

    for team in teams:
        # I "?" sono placeholder: SQLite sostituisce i valori della tupla in modo
        # sicuro (previene SQL injection). MAI costruire SQL con f-string sui dati.
        # INSERT OR REPLACE: se l'id esiste già, sovrascrive (utile per re-seed).
        conn.execute(
            "INSERT OR REPLACE INTO teams (id, name, description, contact_info) VALUES (?, ?, ?, ?)",
            # team.get("contact_info", "") → se la chiave manca, usa "" invece di errore.
            (team["id"], team["name"], team["description"], team.get("contact_info", ""))
        )
    conn.commit()
    return len(teams)   # numero di team caricati


def load_incidents(conn: sqlite3.Connection, incidents_path: str):
    """Carica gli incidenti seed nel database SQLite.
    Li mette tutti in stato 'archived' perchè sono incidenti passati."""
    with open(incidents_path, encoding="utf-8") as f:
        incidents = json.load(f)

    for inc in incidents:
        conn.execute(
            """INSERT OR REPLACE INTO incidents
            (id, title, description, category, severity, status, created_at, resolved_at)
            VALUES (?, ?, ?, ?, ?, 'archived', ?, ?)""",
            (inc["id"], inc["title"], inc["description"],
            inc["category"], inc["severity"],
            inc["created_at"], inc.get("resolved_at", ""))
        )

        # Salva anche il post-mortem come JSON.
        # Costruiamo un dict con i campi del post-mortem e lo serializziamo come
        # testo (json.dumps) per salvarlo in una sola colonna TEXT.
        post_mortem = {
            "incident_id": inc["id"],
            "title": inc["title"],
            "severity": inc["severity"],
            "impact": inc.get("impact", ""),
            "detection": inc.get("detection", ""),
            "root_cause": inc.get("root_cause", ""),
            "resolution_steps": inc.get("resolution_steps", []),
        }
        conn.execute(
            "INSERT OR REPLACE INTO post_mortems (incident_id, content_json) VALUES (?, ?)",
            # ensure_ascii=False → mantiene gli accenti italiani leggibili nel JSON
            # invece di trasformarli in sequenze tipo è.
            (inc["id"], json.dumps(post_mortem, ensure_ascii=False))
        )

    conn.commit()
    return len(incidents)


# ---------------------------------------------------------------------------
# Data-access runtime
# ---------------------------------------------------------------------------
# Funzioni usate dall'app (service layer e route) per leggere/scrivere durante
# l'esecuzione. A differenza dei loader di seed, ognuna apre e chiude la propria
# connessione ed è atomica: il chiamante non deve gestire transazioni.

def _next_incident_id(conn: sqlite3.Connection) -> str:
    """Genera il prossimo ID incidente nel formato INC-NNN (3 cifre come il seed).
    Prende il massimo suffisso numerico esistente e incrementa."""
    # Il prefisso "_" nel nome (per convenzione) segnala una funzione "privata",
    # cioè un helper interno non pensato per essere usato da fuori il modulo.
    # LIKE 'INC-%' → '%' è il jolly SQL: prende tutti gli id che iniziano con INC-.
    rows = conn.execute("SELECT id FROM incidents WHERE id LIKE 'INC-%'").fetchall()
    max_n = 0
    for r in rows:
        # re.search(r"(\d+)$", testo): cerca una o più cifre (\d+) alla FINE ($)
        # della stringa. La `r"..."` è una "raw string": i backslash restano
        # letterali (necessario nelle regex).
        m = re.search(r"(\d+)$", r["id"])
        if m:
            # m.group(1) = il pezzo catturato tra parentesi (le cifre). max() tiene
            # il valore più alto trovato finora.
            max_n = max(max_n, int(m.group(1)))
    # f-string con format: :03d formatta l'intero con almeno 3 cifre e zeri davanti
    # (es. 7 -> "007"). Risultato: "INC-008" dopo "INC-007".
    return f"INC-{max_n + 1:03d}"


def create_incident(description: str, created_by: str, title: str | None = None,
                    db_path: str | None = None) -> dict:
    """Crea un nuovo incidente in stato 'declared' e registra il primo evento
    in timeline (il messaggio dell'utente). Restituisce l'incidente creato."""
    conn = get_connection(db_path)
    # try/finally: qualunque cosa accada nel try (anche un errore), il blocco
    # finally viene SEMPRE eseguito → garantiamo che la connessione si chiuda.
    try:
        inc_id = _next_incident_id(conn)
        # `title or "..."` → se title è None o stringa vuota (entrambi "falsy"),
        # usa il testo di default. Idioma Python molto comune.
        title = title or "(in attesa di classificazione)"
        conn.execute(
            """INSERT INTO incidents (id, title, description, status, created_by)
               VALUES (?, ?, ?, 'declared', ?)""",
            (inc_id, title, description, created_by),
        )
        # Registriamo subito il messaggio dell'utente come primo evento di timeline.
        conn.execute(
            """INSERT INTO timeline_events (incident_id, event_type, actor, content)
               VALUES (?, 'message', ?, ?)""",
            (inc_id, created_by, description),
        )
        conn.commit()
        # Rileggiamo la riga appena creata per restituirla completa (con i default).
        row = conn.execute("SELECT * FROM incidents WHERE id = ?", (inc_id,)).fetchone()
        return dict(row)   # converte la Row in un normale dizionario Python
    finally:
        conn.close()


def get_incident(incident_id: str, db_path: str | None = None) -> dict | None:
    """Restituisce l'incidente come dict, o None se non esiste."""
    # Il tipo di ritorno `dict | None` significa "un dict OPPURE None".
    conn = get_connection(db_path)
    try:
        # fetchone() prende UNA riga (o None se la query non trova nulla).
        row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        # Espressione condizionale "a if cond else b": se row esiste la converte
        # in dict, altrimenti restituisce None.
        return dict(row) if row else None
    finally:
        conn.close()


def list_incidents(status: str | None = None, limit: int = 100, db_path: str | None = None) -> list[dict]:
    """Elenca gli incidenti, opzionalmente filtrati per status. Più recenti prima."""
    conn = get_connection(db_path)
    try:
        if status:
            # ORDER BY ... DESC = ordina dal più recente. LIMIT = max risultati.
            rows = conn.execute(
                "SELECT * FROM incidents WHERE status = ? ORDER BY created_at DESC, id DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM incidents ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        # List comprehension: crea una lista convertendo ogni Row in dict.
        # Equivale a un for che fa append, ma più compatto: [f(x) for x in lista].
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_incident_classification(incident_id: str, title: str, category: str,
                                severity: str, db_path: str | None = None):
    """Aggiorna i campi prodotti dal triage (titolo, categoria, severità)."""
    conn = get_connection(db_path)
    try:
        # datetime('now') è una funzione SQL di SQLite: scrive il timestamp corrente.
        conn.execute(
            """UPDATE incidents
               SET title = ?, category = ?, severity = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (title, category, severity, incident_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_incident_status(incident_id: str, status: str, resolved_at: str | None = None,
                        db_path: str | None = None):
    """Aggiorna lo status di un incidente (e resolved_at se fornito)."""
    conn = get_connection(db_path)
    try:
        # Due query diverse a seconda che resolved_at sia stato passato o meno:
        # quando chiudiamo l'incidente vogliamo registrare anche QUANDO è stato risolto.
        if resolved_at is not None:
            conn.execute(
                "UPDATE incidents SET status = ?, updated_at = datetime('now'), resolved_at = ? WHERE id = ?",
                (status, resolved_at, incident_id),
            )
        else:
            conn.execute(
                "UPDATE incidents SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (status, incident_id),
            )
        conn.commit()
    finally:
        conn.close()


def add_timeline_event(incident_id: str, event_type: str, actor: str, content: str,
                    db_path: str | None = None) -> int:
    """Aggiunge un evento alla timeline dell'incidente. Restituisce l'id dell'evento."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            """INSERT INTO timeline_events (incident_id, event_type, actor, content)
               VALUES (?, ?, ?, ?)""",
            (incident_id, event_type, actor, content),
        )
        conn.commit()
        # lastrowid = l'id auto-incrementato che SQLite ha assegnato alla riga
        # appena inserita. Dopo una INSERT è sempre valorizzato; il `or 0` serve
        # solo a soddisfare il type-checker (lastrowid è tipato "int | None").
        return cur.lastrowid or 0
    finally:
        conn.close()


def get_timeline(incident_id: str, db_path: str | None = None) -> list[dict]:
    """Restituisce gli eventi della timeline in ordine cronologico."""
    conn = get_connection(db_path)
    try:
        # ORDER BY id ASC → ordine crescente = cronologico (l'id auto-incrementa).
        rows = conn.execute(
            "SELECT * FROM timeline_events WHERE incident_id = ? ORDER BY id ASC",
            (incident_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def add_remediation_steps(incident_id: str, steps: list[dict], db_path: str | None = None):
    """Inserisce passi di remediation. Ogni step: {description, completed?, source?}."""
    conn = get_connection(db_path)
    try:
        for step in steps:
            conn.execute(
                """INSERT INTO remediation_steps (incident_id, description, completed, source)
                   VALUES (?, ?, ?, ?)""",
                # int(bool) → SQLite non ha un vero booleano: True diventa 1, False 0.
                (incident_id, step["description"],
                int(step.get("completed", False)), step.get("source", "general")),
            )
        conn.commit()
    finally:
        conn.close()


def get_remediation(incident_id: str, db_path: str | None = None) -> list[dict]:
    """Restituisce i passi di remediation di un incidente."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM remediation_steps WHERE incident_id = ? ORDER BY id ASC",
            (incident_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_post_mortem(incident_id: str, content_json: str, db_path: str | None = None):
    """Salva (o sostituisce) il post-mortem di un incidente come JSON."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO post_mortems (incident_id, content_json) VALUES (?, ?)",
            (incident_id, content_json),
        )
        conn.commit()
    finally:
        conn.close()


def get_post_mortem(incident_id: str, db_path: str | None = None) -> dict | None:
    """Restituisce il post-mortem (parsato da JSON) di un incidente, o None."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT content_json FROM post_mortems WHERE incident_id = ?",
            (incident_id,),
        ).fetchone()
        # json.loads = da testo JSON a dict Python. Lo facciamo solo se row esiste.
        return json.loads(row["content_json"]) if row else None
    finally:
        conn.close()


def get_teams(db_path: str | None = None) -> tuple[list[dict], set[str]]:
    """Carica il catalogo team. Restituisce (lista di team, set di id validi).
    Usato sia dal triage (lista nel prompt) sia per validare i suggerimenti."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT id, name, description FROM teams").fetchall()
        teams = [dict(r) for r in rows]
        # Restituiamo una tupla con DUE cose: la lista completa e un `set` dei soli
        # id. Il set serve per controllare velocemente "questo id esiste?" (la
        # ricerca in un set è O(1), istantanea). `{t["id"] for t in teams}` è una
        # "set comprehension".
        return teams, {t["id"] for t in teams}
    finally:
        conn.close()


# --- Utenti e sessioni (auth) ---

def create_user(user_id: str, username: str, password_hash: str, db_path: str | None = None) -> dict:
    """Crea un utente. Solleva ValueError se lo username è già preso."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)",
            (user_id, username, password_hash),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row)
    except sqlite3.IntegrityError:
        # Lo username ha il vincolo UNIQUE nella tabella: se è duplicato SQLite
        # lancia IntegrityError. Lo "traduciamo" in un ValueError più chiaro che
        # il layer superiore (route) trasformerà in un HTTP 409.
        raise ValueError(f"Username '{username}' already taken")
    finally:
        conn.close()


def get_user_by_username(username: str, db_path: str | None = None) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id: str, db_path: str | None = None) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_session(token: str, user_id: str, db_path: str | None = None):
    """Registra un token di sessione per un utente."""
    conn = get_connection(db_path)
    try:
        conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
        conn.commit()
    finally:
        conn.close()


def get_user_id_by_token(token: str, db_path: str | None = None) -> str | None:
    """Risolve un token di sessione nell'id utente, o None se non valido."""
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT user_id FROM sessions WHERE token = ?", (token,)).fetchone()
        return row["user_id"] if row else None
    finally:
        conn.close()


def delete_session(token: str, db_path: str | None = None):
    """Invalida un token di sessione (logout)."""
    conn = get_connection(db_path)
    try:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
    finally:
        conn.close()


# --- Metriche (per la dashboard / routes_metrics) ---

def count_by_column(column: str, db_path: str | None = None) -> dict[str, int]:
    """Conteggio incidenti raggruppati per una colonna (status/severity/category)."""
    # Controllo di sicurezza: il nome colonna finisce DENTRO la query (non come
    # placeholder ?, perché i ? valgono solo per i valori, non per i nomi di
    # colonna). Quindi accettiamo solo una "whitelist" fissa per evitare injection.
    if column not in {"status", "severity", "category"}:
        raise ValueError(f"Unsupported metric column: {column}")
    conn = get_connection(db_path)
    try:
        # GROUP BY raggruppa le righe per valore della colonna; COUNT(*) conta
        # quante righe per gruppo. "AS k"/"AS n" sono alias per le colonne risultato.
        rows = conn.execute(
            f"SELECT {column} AS k, COUNT(*) AS n FROM incidents GROUP BY {column}"
        ).fetchall()
        # Dict comprehension: costruisce {valore: conteggio}. `r["k"] or "unknown"`
        # mette "unknown" quando il valore è NULL/vuoto.
        return {(r["k"] or "unknown"): r["n"] for r in rows}
    finally:
        conn.close()


def mttr_seconds(db_path: str | None = None) -> float | None:
    """Mean Time To Resolution medio (secondi) sugli incidenti con resolved_at valorizzato.
    Restituisce None se non ci sono incidenti risolti."""
    conn = get_connection(db_path)
    try:
        # julianday() converte una data in un numero di giorni; la differenza tra
        # risoluzione e creazione * 86400 (secondi in un giorno) dà la durata in
        # secondi. AVG() ne fa la media su tutti gli incidenti risolti.
        row = conn.execute(
            """SELECT AVG((julianday(resolved_at) - julianday(created_at)) * 86400.0) AS mttr
               FROM incidents
               WHERE resolved_at IS NOT NULL AND resolved_at != ''"""
        ).fetchone()
        # Se non ci sono righe risolte, AVG restituisce NULL → ritorniamo None.
        return row["mttr"] if row and row["mttr"] is not None else None
    finally:
        conn.close()


# Se esegui questo file direttamente, crea il database vuoto.
# `__name__ == "__main__"` è vero SOLO quando lanci `python database.py` da
# terminale; è falso quando il file viene importato da un altro modulo. Serve a
# dare al file un comportamento da "script" oltre che da libreria.
if __name__ == "__main__":
    conn = get_connection()
    create_tables(conn)
    print("🟢 SQLite tables created")
    conn.close()
