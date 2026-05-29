"""Configurazione centralizzata. Nessun segreto qui - quelli stanno in .env."""

import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys (da .env, MAI qui) ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "dev-secret-change-me")

# --- Modelli Groq (verificare disponibilità su console.groq.com) ---
MODELS = {
    "orchestrator": "llama-3.1-8b-instant",
    "triage": "gpt-oss-20b",
    "investigator": "llama-3.3-70b-versatile",
    "resolver": "llama-3.3-70b-versatile",
}

# --- Embedding (locale, nessuna API) ---
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# --- Database ---
SQLITE_PATH = os.getenv("SQLITE_PATH", "data/debrief.db")
LANCEDB_PATH = os.getenv("LANCEDB_PATH", "data/lancedb")

# --- RAG ---
SIMILARITY_THRESHOLD = 0.65       # soglia minima per considerare un match "simile"
TOP_K_INCIDENTS = 5               # risultati per past_incidents
TOP_K_VERIFIED = 3                # risultati per verified_solutions
TOP_K_KB = 3                      # risultati per knowledge_base

# --- LLM ---
TEMPERATURE = {
    "orchestrator": 0.0,          # deterministico
    "triage": 0.0,                # deterministico
    "investigator": 0.2,          # minima variabilità
    "resolver": 0.3,              # creatività controllata
}
MAX_REPAIR_RETRIES = 2            # tentativi di repair su JSON malformato
