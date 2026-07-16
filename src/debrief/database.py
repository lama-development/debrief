"""Configurazione SQLite, dati iniziali e accesso autonomo alle connessioni."""

import sqlite3
import os
import re
import json

from debrief.config import SQLITE_PATH


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Apre SQLite e crea la cartella dati se necessario."""
    if db_path is None:
        db_path = os.getenv("SQLITE_PATH", SQLITE_PATH)

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # WAL consente letture concorrenti durante le scritture.
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def create_tables(conn: sqlite3.Connection):
    """Crea tutte le tabelle. Idempotente (IF NOT EXISTS)."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS teams (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            description TEXT,
            contact_info TEXT
        );

        CREATE TABLE IF NOT EXISTS users (
            id          TEXT PRIMARY KEY,
            username    TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            team_id     TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (team_id) REFERENCES teams(id)
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token       TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS incidents (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            description TEXT NOT NULL,
            severity    TEXT,
            status      TEXT DEFAULT 'open',
            created_by  TEXT,
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now')),
            resolved_at TEXT
        );

        CREATE TABLE IF NOT EXISTS incident_participants (
            incident_id      TEXT NOT NULL,
            user_id          TEXT NOT NULL,
            joined_at        TEXT DEFAULT (datetime('now')),
            last_activity_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (incident_id, user_id),
            FOREIGN KEY (incident_id) REFERENCES incidents(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
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

        CREATE TABLE IF NOT EXISTS debrief_reports (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT UNIQUE NOT NULL,
            content_json TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (incident_id) REFERENCES incidents(id)
        );
    """)
    conn.commit()


def load_teams(conn: sqlite3.Connection, teams_path: str):
    """Carica il catalogo team da un file JSON."""
    with open(teams_path, encoding="utf-8") as f:
        teams = json.load(f)

    for team in teams:
        conn.execute(
            "INSERT OR REPLACE INTO teams (id, name, description, contact_info) VALUES (?, ?, ?, ?)",
            (team["id"], team["name"], team["description"], team.get("contact_info", ""))
        )
    conn.commit()
    return len(teams)


def load_incidents(conn: sqlite3.Connection, incidents_path: str):
    """Carica gli incidenti iniziali; lo stato predefinito è `resolved`."""
    with open(incidents_path, encoding="utf-8") as f:
        incidents = json.load(f)

    valid_team_ids = {
        row["id"] for row in conn.execute("SELECT id FROM teams").fetchall()
    }

    for inc in incidents:
        unknown_teams = set(inc.get("involved_teams", [])) - valid_team_ids
        if unknown_teams:
            raise ValueError(
                f"Incident {inc['id']} references unknown teams: {sorted(unknown_teams)}"
            )
        status = inc.get("status", "resolved")
        resolved_at = inc.get("resolved_at", "") if status == "resolved" else None
        conn.execute(
            """INSERT OR REPLACE INTO incidents
            (id, title, description, severity, status, created_at, resolved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (inc["id"], inc["title"], inc["description"],
            inc.get("severity"), status,
            inc["created_at"], resolved_at)
        )

        # Ricrea i coinvolgimenti per rendere idempotente il caricamento iniziale.
        conn.execute(
            """DELETE FROM timeline_events
               WHERE incident_id = ? AND event_type IN ('involvement', 'disinvolvement')""",
            (inc["id"],),
        )
        for team_id in inc.get("involved_teams", []):
            conn.execute(
                """INSERT INTO timeline_events (incident_id, event_type, actor, content)
                   VALUES (?, 'involvement', 'seed', ?)""",
                (inc["id"], team_id),
            )

        if status == "resolved":
            debrief_report = {
                "incident_id": inc["id"],
                "title": inc["title"],
                "severity": inc["severity"],
                "resolution": inc.get("resolution", ""),
            }
            conn.execute(
                "INSERT OR REPLACE INTO debrief_reports (incident_id, content_json) VALUES (?, ?)",
                (inc["id"], json.dumps(debrief_report, ensure_ascii=False))
            )

    conn.commit()
    return len(incidents)


# Ogni funzione gestisce autonomamente connessione e transazione.

def _next_incident_id(conn: sqlite3.Connection) -> str:
    """Genera il prossimo ID nel formato INC-NNN."""
    rows = conn.execute("SELECT id FROM incidents WHERE id LIKE 'INC-%'").fetchall()
    max_n = 0
    for r in rows:
        m = re.search(r"(\d+)$", r["id"])
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"INC-{max_n + 1:03d}"


def create_incident(description: str, created_by: str, title: str | None = None,
                    db_path: str | None = None) -> dict:
    """Crea un incidente `open` con il primo evento della timeline."""
    conn = get_connection(db_path)
    try:
        inc_id = _next_incident_id(conn)
        title = title or "(in attesa di classificazione)"
        conn.execute(
            """INSERT INTO incidents (id, title, description, status, created_by)
               VALUES (?, ?, ?, 'open', ?)""",
            (inc_id, title, description, created_by),
        )
        conn.execute(
            """INSERT INTO timeline_events (incident_id, event_type, actor, content)
               VALUES (?, 'message', ?, ?)""",
            (inc_id, created_by, description),
        )
        conn.execute(
            """INSERT INTO incident_participants (incident_id, user_id)
               VALUES (?, ?)""",
            (inc_id, created_by),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM incidents WHERE id = ?", (inc_id,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def get_incident(incident_id: str, db_path: str | None = None) -> dict | None:
    """Restituisce l'incidente come dizionario, oppure `None`."""
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_user_incidents(user_id: str, status: str | None = None, limit: int = 100,
                        db_path: str | None = None) -> list[dict]:
    """Elenca solo incidenti creati, partecipati o assegnati al team dell'utente."""
    conn = get_connection(db_path)
    try:
        # La visibilità deriva da proprietà, partecipazione o team ancora coinvolto.
        filters = ["""(p.user_id = ? OR i.created_by = ? OR EXISTS (
            SELECT 1 FROM users AS viewer
            JOIN timeline_events AS te ON te.incident_id = i.id
            WHERE viewer.id = ? AND viewer.team_id IS NOT NULL
              AND te.event_type = 'involvement' AND te.content = viewer.team_id
              AND NOT EXISTS (
                SELECT 1 FROM timeline_events AS removed
                WHERE removed.incident_id = i.id
                  AND removed.event_type = 'disinvolvement'
                  AND removed.content = viewer.team_id
                  AND removed.id > te.id
              )
        ))"""]
        params: list[object] = [user_id, user_id, user_id]
        if status:
            filters.append("i.status = ?")
            params.append(status)
        params.append(limit)
        rows = conn.execute(
            f"""SELECT DISTINCT i.*
                FROM incidents AS i
                LEFT JOIN incident_participants AS p ON p.incident_id = i.id
                WHERE {' AND '.join(filters)}
                ORDER BY i.updated_at DESC, i.id DESC
                LIMIT ?""",
            params,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def add_incident_participant(incident_id: str, user_id: str,
                             db_path: str | None = None) -> None:
    """Registra la partecipazione o aggiorna l'ultima attività dell'utente."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            """INSERT INTO incident_participants (incident_id, user_id)
               VALUES (?, ?)
               ON CONFLICT(incident_id, user_id) DO UPDATE SET
                   last_activity_at = datetime('now')""",
            (incident_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_incident_participants(incident_id: str, db_path: str | None = None) -> list[dict]:
    """Restituisce identità e attività dei partecipanti alla conversazione."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT u.id, u.username, u.team_id, t.name AS team_name,
                      p.joined_at, p.last_activity_at
               FROM incident_participants AS p
               JOIN users AS u ON u.id = p.user_id
               LEFT JOIN teams AS t ON t.id = u.team_id
               WHERE p.incident_id = ?
               ORDER BY p.joined_at ASC, u.username ASC""",
            (incident_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_incident_teams(incident_id: str, db_path: str | None = None) -> list[str]:
    """Ricostruisce i team applicando in ordine gli eventi di coinvolgimento."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT event_type, content FROM timeline_events
               WHERE incident_id = ? AND event_type IN ('involvement', 'disinvolvement')
               ORDER BY id ASC""",
            (incident_id,),
        ).fetchall()
        teams: set[str] = set()
        for r in rows:
            if r["event_type"] == "involvement":
                teams.add(r["content"])
            else:
                teams.discard(r["content"])
        return sorted(teams)
    finally:
        conn.close()


def update_incident_severity(incident_id: str, severity: str, db_path: str | None = None):
    """Aggiorna solo la severità manuale, senza modificare il titolo."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE incidents SET severity = ?, updated_at = datetime('now') WHERE id = ?",
            (severity, incident_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_incident_classification(incident_id: str, title: str,
                                severity: str, db_path: str | None = None):
    """Aggiorna i campi prodotti dal triage (titolo, severità)."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            """UPDATE incidents
               SET title = ?, severity = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (title, severity, incident_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_incident_status(incident_id: str, status: str, resolved_at: str | None = None,
                        db_path: str | None = None):
    """Aggiorna lo stato e, se fornito, il campo `resolved_at`."""
    conn = get_connection(db_path)
    try:
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
    """Aggiunge un evento alla timeline e ne restituisce l'ID."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            """INSERT INTO timeline_events (incident_id, event_type, actor, content)
               VALUES (?, ?, ?, ?)""",
            (incident_id, event_type, actor, content),
        )
        conn.commit()
        return cur.lastrowid or 0
    finally:
        conn.close()


def get_timeline(incident_id: str, db_path: str | None = None) -> list[dict]:
    """Restituisce gli eventi della timeline in ordine cronologico."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT e.*, u.id AS actor_user_id, u.username AS actor_username,
                      u.team_id AS actor_team_id,
                      t.name AS actor_team_name
               FROM timeline_events AS e
               LEFT JOIN users AS u
                 ON u.id = e.actor
                 OR (
                      u.username = e.actor
                      AND NOT EXISTS (SELECT 1 FROM users AS actor_by_id WHERE actor_by_id.id = e.actor)
                    )
               LEFT JOIN teams AS t ON t.id = u.team_id
               WHERE e.incident_id = ? ORDER BY e.id ASC""",
            (incident_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_debrief_report(incident_id: str, content_json: str, db_path: str | None = None):
    """Salva (o sostituisce) il debriefing di un incidente come JSON."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO debrief_reports (incident_id, content_json) VALUES (?, ?)",
            (incident_id, content_json),
        )
        conn.commit()
    finally:
        conn.close()


def get_debrief_report(incident_id: str, db_path: str | None = None) -> dict | None:
    """Restituisce il debriefing decodificato dal JSON, oppure `None`."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT content_json FROM debrief_reports WHERE incident_id = ?",
            (incident_id,),
        ).fetchone()
        return json.loads(row["content_json"]) if row else None
    finally:
        conn.close()


def get_teams(db_path: str | None = None) -> tuple[list[dict], set[str]]:
    """Restituisce il catalogo team e l'insieme degli ID validi."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT id, name, description FROM teams").fetchall()
        teams = [dict(r) for r in rows]
        return teams, {t["id"] for t in teams}
    finally:
        conn.close()


# Utenti e sessioni

def create_user(user_id: str, username: str, password_hash: str, team_id: str,
                db_path: str | None = None) -> dict:
    """Crea un utente. Solleva ValueError se lo username è già preso."""
    conn = get_connection(db_path)
    try:
        team = conn.execute("SELECT id FROM teams WHERE id = ?", (team_id,)).fetchone()
        if team is None:
            raise ValueError(f"Team '{team_id}' not found")
        conn.execute(
            "INSERT INTO users (id, username, password_hash, team_id) VALUES (?, ?, ?, ?)",
            (user_id, username, password_hash, team_id),
        )
        conn.commit()
        row = conn.execute(
            """SELECT u.*, t.name AS team_name FROM users u
               LEFT JOIN teams t ON t.id = u.team_id WHERE u.id = ?""",
            (user_id,),
        ).fetchone()
        return dict(row)
    except sqlite3.IntegrityError:
        # Espone la violazione UNIQUE come errore di dominio.
        raise ValueError(f"Username '{username}' already taken")
    finally:
        conn.close()


def get_user_by_username(username: str, db_path: str | None = None) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            """SELECT u.*, t.name AS team_name FROM users u
               LEFT JOIN teams t ON t.id = u.team_id WHERE u.username = ?""",
            (username,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id: str, db_path: str | None = None) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            """SELECT u.*, t.name AS team_name FROM users u
               LEFT JOIN teams t ON t.id = u.team_id WHERE u.id = ?""",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def user_can_access_incident(user_id: str, incident_id: str,
                             db_path: str | None = None) -> bool:
    """Autorizza creatore, partecipanti espliciti e membri di team coinvolti."""
    conn = get_connection(db_path)
    try:
        # Un evento successivo di disinvolvement revoca l'accesso ottenuto dal team.
        row = conn.execute(
            """SELECT 1
               FROM incidents AS i
               JOIN users AS u ON u.id = ?
               WHERE i.id = ? AND (
                 i.created_by = u.id OR
                 EXISTS (SELECT 1 FROM incident_participants p
                         WHERE p.incident_id = i.id AND p.user_id = u.id) OR
                 (u.team_id IS NOT NULL AND EXISTS (
                   SELECT 1 FROM timeline_events te
                   WHERE te.incident_id = i.id AND te.event_type = 'involvement'
                     AND te.content = u.team_id
                     AND NOT EXISTS (
                       SELECT 1 FROM timeline_events removed
                       WHERE removed.incident_id = i.id
                         AND removed.event_type = 'disinvolvement'
                         AND removed.content = u.team_id AND removed.id > te.id
                     )
                 ))
               )""",
            (user_id, incident_id),
        ).fetchone()
        return row is not None
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
    """Restituisce l'ID utente del token, oppure `None` se non valido."""
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


if __name__ == "__main__":
    conn = get_connection()
    create_tables(conn)
    print("SQLite tables created")
    conn.close()
