from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from .settings import EMBED_MODEL, EMBED_DIM

_model = None

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL)
    return _model

def embed_texts(texts: List[str]) -> List[List[float]]:
    vecs = get_model().encode(texts, normalize_embeddings=True, show_progress_bar=False)
    vecs = np.asarray(vecs, dtype=np.float32)
    if vecs.shape[1] != EMBED_DIM:
        raise RuntimeError(f"Embedding dim mismatch: got {vecs.shape[1]} expected {EMBED_DIM}")
    return vecs.tolist()

def vector_literal(v: List[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in v) + "]"
