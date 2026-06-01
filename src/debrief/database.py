"""
database.py - Setup del database SQLite.

Crea le tabelle necessarie e fornisce funzioni per leggere/scrivere.
Questo file viene usato sia dal seed (per popolare) sia dall'app (per operare).
"""

import sqlite3
import os
import json
from datetime import datetime


def get_connection(db_path: str = None) -> sqlite3.Connection:
    """Restituisce una connessione al database SQLite.
    Crea la cartella 'data/' se non esiste."""
    if db_path is None:
        db_path = os.getenv("SQLITE_PATH", "data/debrief.db")

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # per accedere alle colonne per nome
    conn.execute("PRAGMA journal_mode=WAL")  # performance migliori
    return conn


def create_tables(conn: sqlite3.Connection):
    """Crea tutte le tabelle. Idempotente (IF NOT EXISTS)."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          TEXT PRIMARY KEY,
            username    TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now'))
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

        # Salva anche il post-mortem come JSON
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
            (inc["id"], json.dumps(post_mortem, ensure_ascii=False))
        )

    conn.commit()
    return len(incidents)


# Se esegui questo file direttamente, crea il database vuoto
if __name__ == "__main__":
    conn = get_connection()
    create_tables(conn)
    print("✓ Tabelle SQLite create")
    conn.close()
