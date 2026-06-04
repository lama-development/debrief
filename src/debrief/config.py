import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Modelli Groq
MODELS = {
    "orchestrator": "llama-3.1-8b-instant",
    "triage": "llama-3.3-70b-versatile",
    "investigator": "llama-3.3-70b-versatile",
    "resolver": "llama-3.3-70b-versatile",
}

# Embedding (locale)
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# Database
SQLITE_PATH = "data/debrief.db"
LANCEDB_PATH = "data/lancedb"

# RAG
SIMILARITY_THRESHOLD = 0.35       # soglia minima per considerare un match "simile"
TOP_K_INCIDENTS = 3               # risultati per past_incidents
TOP_K_VERIFIED = 3                # risultati per verified_solutions
TOP_K_KB = 3                      # risultati per knowledge_base

# LLM
TEMPERATURE = {
    "orchestrator": 0.0,          # deterministico
    "triage": 0.0,                # deterministico
    "investigator": 0.2,          # minima variabilità
    "resolver": 0.3,              # creatività controllata
}
MAX_REPAIR_RETRIES = 2            # tentativi di repair su JSON malformato
