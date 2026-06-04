"""
embedding.py - Embedding locale con sentence-transformers.

Calcola i vettori per la ricerca semantica.
Tutto avviene in locale, senza usare API, costi aggiuntivi, o rate limit.
"""

import os
from sentence_transformers import SentenceTransformer

# Il modello viene caricato UNA volta e riusato.
# La prima volta scarica ~80MB, poi usa la cache locale.
_model = None


def get_model() -> SentenceTransformer:
    """Carica il modello di embedding."""
    global _model
    if _model is None:
        model_name = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
        print(f"🔵 Loading embedding model: {model_name}...")
        _model = SentenceTransformer(model_name)
        print(f"🟢 Model loaded (vector dimension: {_model.get_embedding_dimension()})")
    return _model


def embed_text(text: str) -> list[float]:
    """Calcola l'embedding di un singolo testo. Restituisce una lista di float."""
    model = get_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Calcola gli embedding di più testi in batch (più efficiente)."""
    model = get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    return vectors.tolist()


# Test rapido se esegui il file direttamente
if __name__ == "__main__":
    test = embed_text("PLC fermo in produzione, linea bloccata")
    print(f"🟢 Embedding computed: {len(test)} dimensions")
    print(f"First 5 values: {test[:5]}")
