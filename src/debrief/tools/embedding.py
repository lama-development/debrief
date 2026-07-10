"""
embedding.py - Embedding locale con sentence-transformers.

"Embedding" = trasformare un testo in un vettore di numeri (una lista di float)
che ne rappresenta il SIGNIFICATO. Testi con senso simile producono vettori
vicini nello spazio: è questo che permette la ricerca "semantica" (per concetto,
non per parole esatte).

Tutto avviene in locale, senza usare API, costi aggiuntivi, o rate limit.
"""

import os

# Evita progress bar rumorose negli script CLI (`uv run seed`, `uv run eval`).
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import logging
from sentence_transformers import SentenceTransformer

from debrief.config import EMBEDDING_MODEL

logger = logging.getLogger(__name__)

# Il modello viene caricato UNA volta e riusato (pattern "singleton").
# Caricare il modello è lento; tenerlo in questa variabile globale evita di
# ricaricarlo a ogni chiamata. La prima volta scarica ~80MB, poi usa la cache.
_model = None


def get_model() -> SentenceTransformer:
    """Carica il modello di embedding (una sola volta)."""
    # `global _model` dice a Python: dentro questa funzione voglio MODIFICARE la
    # variabile globale _model, non crearne una locale con lo stesso nome.
    global _model
    # Carichiamo solo se non è ancora stato caricato (lazy loading).
    if _model is None:
        model_name = os.getenv("EMBEDDING_MODEL", EMBEDDING_MODEL)
        logger.info("Loading embedding model: %s", model_name)
        # Al primo uso il modello viene scaricato; poi Sentence Transformers usa
        # la propria cache locale.
        _model = SentenceTransformer(model_name)
        logger.info("Embedding model loaded (dimension=%s)", _model.get_embedding_dimension())
    return _model


def embed_text(text: str) -> list[float]:
    """Calcola l'embedding di un singolo testo. Restituisce una lista di float."""
    model = get_model()
    # normalize_embeddings=True → i vettori hanno lunghezza 1. Questo semplifica
    # il confronto di similarità (vedi indexer.search: la distanza si converte
    # facilmente in similarità coseno).
    vector = model.encode(text, normalize_embeddings=True)
    # encode restituisce un array NumPy; .tolist() lo converte in una normale
    # lista Python, più comoda da serializzare e salvare.
    return vector.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Calcola gli embedding di più testi in batch (più efficiente)."""
    # Passare TUTTI i testi insieme è molto più veloce che chiamare embed_text in
    # un loop: il modello li elabora in parallelo. Usato dal seed.
    model = get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()


# Test rapido se esegui il file direttamente (vedi nota su __main__ in database.py).
if __name__ == "__main__":
    test = embed_text("PLC fermo in produzione, linea bloccata")
    print(f"Embedding computed: {len(test)} dimensions")
    print(f"First 5 values: {test[:5]}")   # test[:5] = i primi 5 elementi (slicing)
