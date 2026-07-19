"""Configurazione centralizzata dell'applicazione."""

from dotenv import load_dotenv

load_dotenv()

# Modelli Groq
# Il router privilegia la velocità; gli specialisti la capacità.
MODELS = {
    "orchestrator": "openai/gpt-oss-20b",
    "triage": "openai/gpt-oss-20b",
    "investigator": "openai/gpt-oss-20b",
    "resolver": "openai/gpt-oss-120b",
}

# Embedding (locale)
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# Database
SQLITE_PATH = "data/debrief.db"
LANCEDB_PATH = "data/lancedb"

# RAG
KNOWLEDGE_BASE_SIMILARITY_THRESHOLD = 0.35
INCIDENT_SIMILARITY_THRESHOLD = 0.55
TOP_K_INCIDENTS = 3
TOP_K_KB = 3

# LLM
TEMPERATURE = {
    "orchestrator": 0.5,
    "triage": 0.5,
    "investigator": 0.5,
    "resolver": 0.6,
}

REASONING_EFFORT = {
    "orchestrator": "low",
    "triage": "medium",
    "investigator": "medium",
    "resolver": "medium",
}
