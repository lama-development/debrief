"""
config.py - Configurazione centralizzata di tutto il sistema.

Qui raccogliamo in un solo posto tutte le "manopole" del progetto: chiavi API,
nomi dei modelli, percorsi dei database, soglie del RAG e parametri degli LLM.
Avere tutto qui significa che per cambiare un comportamento (es. quale modello
usa il triage) si modifica UNA riga sola, senza cercare nel resto del codice.
"""

# `os` è il modulo standard di Python per dialogare con il sistema operativo:
# qui lo usiamo per leggere le variabili d'ambiente (le "env variables").
import os
# `load_dotenv` legge il file `.env` (non versionato su git, contiene i segreti)
# e ne carica il contenuto tra le variabili d'ambiente del processo.
from dotenv import load_dotenv

# Eseguita all'import del modulo: da qui in poi os.getenv() "vede" anche le
# variabili scritte nel file .env (es. GROQ_API_KEY=...).
load_dotenv()

# Modelli Groq
# Un dizionario (dict): struttura chiave -> valore. Associa a ogni agente il
# nome del modello LLM che deve usare. Il router (orchestrator) usa un modello
# piccolo e veloce; gli agenti "di sostanza" usano un modello più capace.
MODELS = {
    "orchestrator": "openai/gpt-oss-20b",
    "triage": "openai/gpt-oss-120b",
    "investigator": "openai/gpt-oss-120b",
    "resolver": "openai/gpt-oss-120b",
}

# Embedding (locale)
# Nome del modello che trasforma il testo in vettori numerici per la ricerca
# semantica. "multilingual" perché i nostri incidenti sono in italiano.
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# Database
# Percorsi su disco dei due database: SQLite (dati strutturati) e LanceDB
# (database vettoriale per il RAG).
SQLITE_PATH = "data/debrief.db"
LANCEDB_PATH = "data/lancedb"

# RAG (Retrieval-Augmented Generation)
SIMILARITY_THRESHOLD = 0.35       # soglia minima per considerare un match "simile"
TOP_K_INCIDENTS = 3               # quanti risultati restituire per past_incidents
TOP_K_VERIFIED = 3                # quanti risultati restituire per verified_solutions
TOP_K_KB = 3                      # quanti risultati restituire per knowledge_base

# LLM
# La "temperature" controlla quanto è creativa/casuale la risposta del modello:
# 0.0 = sempre la stessa risposta (deterministico), valori alti = più varietà.
TEMPERATURE = {
    "orchestrator": 0.0,          # deterministico: il routing deve essere stabile
    "triage": 0.0,                # deterministico: la classificazione deve essere stabile
    "investigator": 0.2,          # minima variabilità
    "resolver": 0.3,              # creatività controllata nel proporre soluzioni
}
