"""Embedding locale con sentence-transformers."""

import os

# Evita barre di avanzamento rumorose negli script CLI.
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import logging
from sentence_transformers import SentenceTransformer

from debrief.config import EMBEDDING_MODEL

logger = logging.getLogger(__name__)

# Il modello viene caricato solo al primo utilizzo e poi riusato.
_model = None


def get_model() -> SentenceTransformer:
    """Carica il modello di embedding (una sola volta)."""
    global _model
    if _model is None:
        model_name = os.getenv("EMBEDDING_MODEL", EMBEDDING_MODEL)
        logger.info("Loading embedding model: %s", model_name)
        _model = SentenceTransformer(model_name)
        logger.info("Embedding model loaded (dimension=%s)", _model.get_embedding_dimension())
    return _model


def embed_text(text: str) -> list[float]:
    """Calcola l'embedding di un testo."""
    model = get_model()
    # La normalizzazione permette di derivare la similarità dalla distanza L2.
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Calcola più embedding in un'unica operazione."""
    model = get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()


if __name__ == "__main__":
    test = embed_text("PLC fermo in produzione, linea bloccata")
    print(f"Embedding computed: {len(test)} dimensions")
    print(f"First 5 values: {test[:5]}")
