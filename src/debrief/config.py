"""Configurazione centralizzata dell'applicazione."""

from dotenv import load_dotenv

load_dotenv()

# Modelli Groq
# Il router privilegia la velocità; gli specialisti la capacità.
MODELS = {
    "orchestrator": "openai/gpt-oss-20b",
    "triage": "openai/gpt-oss-120b",
    "investigator": "openai/gpt-oss-120b",
    "resolver": "openai/gpt-oss-120b",
}

# Embedding (locale)
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# Database
SQLITE_PATH = "data/debrief.db"
LANCEDB_PATH = "data/lancedb"

# RAG
SIMILARITY_THRESHOLD = 0.35
INCIDENT_SIMILARITY_THRESHOLD = 0.55
TOP_K_INCIDENTS = 3
TOP_K_KB = 3

# LLM
# Routing e triage restano deterministici.
TEMPERATURE = {
    "orchestrator": 0.0,
    "triage": 0.0,
    "investigator": 0.2,
    "resolver": 0.3,
}
