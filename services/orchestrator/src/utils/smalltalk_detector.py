from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer


@dataclass
class SmalltalkResult:
    subtype: str
    score: float


class SmalltalkSubtypeDetector:
    """
    Detects smalltalk subtype by embedding similarity against anchor phrases.
    No training required.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        threshold: float = 0.45,   # tune this on your logs
    ) -> None:
        self.model = SentenceTransformer(model_name)
        self.threshold = threshold

        # Anchor phrases per subtype (add Sinhala later if you want)
        self.anchors: Dict[str, List[str]] = {
            "greeting": [
                "hello", "hi", "hey", "good morning", "good evening",
            ],
            "how_are_you": [
                "how are you", "how is it going", "how are things",
                "you good", "how you doing",
            ],
            "thanks": [
                "thank you", "thanks", "much appreciated",
                "thank you so much", "appreciate it",
            ],
            "farewell": [
                "bye", "goodbye", "see you", "talk later", "catch you later",
            ],
            "ack": [
                "ok", "okay", "sure", "alright", "cool",
            ],
        }

        # Pre-compute (cache) normalized embeddings for all anchor phrases
        self._labels: List[str] = []
        self._phrases: List[str] = []
        for label, phrases in self.anchors.items():
            for p in phrases:
                self._labels.append(label)
                self._phrases.append(p)

        emb = self.model.encode(self._phrases, convert_to_numpy=True, normalize_embeddings=True)
        self._anchor_emb = emb  # shape: (N, D)

    def predict(self, text: str) -> SmalltalkResult:
        t = (text or "").strip()
        if not t:
            return SmalltalkResult(subtype="unknown", score=0.0)

        q = self.model.encode([t], convert_to_numpy=True, normalize_embeddings=True)[0]  # (D,)
        sims = self._anchor_emb @ q  # cosine similarity since vectors are normalized
        idx = int(np.argmax(sims))
        best_score = float(sims[idx])
        best_label = self._labels[idx]

        if best_score < self.threshold:
            return SmalltalkResult(subtype="unknown", score=best_score)

        return SmalltalkResult(subtype=best_label, score=best_score)
