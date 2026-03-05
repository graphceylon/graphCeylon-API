from dataclasses import dataclass
from typing import Dict, List, Tuple
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

@dataclass
class NLIResult:
    entailment: float
    neutral: float
    contradiction: float
    label: str  # "entailment" | "neutral" | "contradiction"

class DebertaNLIWrapper:
    """
    Loads your fine-tuned DeBERTa NLI model from a local folder.
    Expects the folder to contain config.json + model weights.
    """
    def __init__(self, model_dir: str, device: str | None = None):
        self.model_dir = model_dir
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        self.tokenizer = AutoTokenizer.from_pretrained(model_dir, use_fast=True)

        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_dir,
            torch_dtype=torch.float32,          # ✅ force fp32
            low_cpu_mem_usage=False,            # ✅ safer on some setups
        )

        self.model.to(self.device)

        # ✅ If on CPU, force model weights to fp32 explicitly
        if self.device == "cpu":
            self.model = self.model.float()

        self.model.eval()

        print("[NLI] device:", self.device)
        print("[NLI] config.torch_dtype:", getattr(self.model.config, "torch_dtype", None))
        print("[NLI] param dtype:", next(self.model.parameters()).dtype)

        # check if any parameter tensor has NaN/Inf
        bad = 0
        for p in self.model.parameters():
            if torch.isnan(p).any() or torch.isinf(p).any():
                bad += 1
        print("[NLI] bad parameter tensors:", bad)

        # If your label mapping differs, adjust this:
        # You previously used: {'contradiction': 0, 'entailment': 1, 'neutral': 2}
        self.id2label = {0: "contradiction", 1: "entailment", 2: "neutral"}

    @torch.no_grad()
    def score(self, premise: str, hypothesis: str) -> NLIResult:
        inputs = self.tokenizer(
            premise,
            hypothesis,
            truncation=True,
            padding=True,
            return_tensors="pt",
            max_length=256,
        ).to(self.device)

        logits = self.model(**inputs).logits[0].float()
        probs = torch.softmax(logits, dim=-1).detach().cpu().tolist()

        # order must match your training label ids
        contradiction, entailment, neutral = probs[0], probs[1], probs[2]

        best_id = int(torch.argmax(torch.tensor(probs)))
        label = self.id2label.get(best_id, "neutral")

        return NLIResult(
            entailment=float(entailment),
            neutral=float(neutral),
            contradiction=float(contradiction),
            label=label,
        )

    def best_evidence(
        self,
        claim: str,
        evidence_snippets: List[str],
        min_entail: float = 0.70,
        min_contra: float = 0.60,
    ) -> Tuple[str, Dict]:
        """
        Finds best supporting/contradicting evidence among snippets.
        Returns: (verdict, debug)
        verdict: "SUPPORTED" | "UNSUPPORTED" | "NEED_MORE_INFO"
        """
        best = None
        best_entail = -1.0
        best_contra = -1.0

        for ev in evidence_snippets[:6]:
            r = self.score(premise=ev, hypothesis=claim)
            best_entail = max(best_entail, r.entailment)
            best_contra = max(best_contra, r.contradiction)

            if best is None or r.entailment > best.entailment:
                best = r

        if best_contra >= min_contra:
            return "UNSUPPORTED", {"best": best, "best_contradiction": best_contra}
        if best_entail >= min_entail:
            return "SUPPORTED", {"best": best, "best_entailment": best_entail}

        return "NEED_MORE_INFO", {"best": best, "best_entailment": best_entail, "best_contradiction": best_contra}