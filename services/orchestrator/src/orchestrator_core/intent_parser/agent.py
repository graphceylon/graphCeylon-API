# orchestrator_core/intent_parser/agent.py

from typing import Dict, List
import numpy as np
import torch
from scipy.special import expit
from transformers import AutoTokenizer, AutoModelForSequenceClassification


from orchestrator_core.entity_extractor import extract_entities_and_prefs


# Keep this synced with your training code
INTENT_LABELS: List[str] = [
    "plan_itinerary",
    "recommend_pois",
    "modify_itinerary",

    # Forecasting-related intents (NEW)
    "crowd_forecast",
    "forecast_weather",
    "forecast_price",
    "forecast_sustainability",

    # Information-based intents
    "info_attraction",
    "info_accommodation",
    "info_transport",
    "info_visa_policy",

    # Preference & meta intents
    "update_preferences",
    "explanation_request",

    # General fallback
    "generic_fact_query"
]

id2label = {i: lbl for i, lbl in enumerate(INTENT_LABELS)}


class IntentParserAgent:
    """
    Wraps the DistilBERT multi-label model used for intent parsing.
    - Predicts primary + secondary intents
    - Applies rule-based boost for obvious recommendation queries
    - Optionally extracts entities + preference_overrides via Ollama + rules
    """

    def __init__(
        self,
        model_dir: str = "intent_multilabel_final",
        threshold: float = 0.2,
        top_k_if_empty: int = 2,
        enable_entity_extraction: bool = True,
    ) -> None:
        """
        :param model_dir: Folder where you saved the final model
                          (SAVE_DIR = 'intent_multilabel_final')
        :param threshold: Probability threshold for selecting labels
        :param top_k_if_empty: Fallback number of labels if none exceed threshold
        :param enable_entity_extraction: If True, call LLM+rules to fill entities and preference_overrides
        """
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir)
        self.model.eval()

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

        self.threshold = threshold
        self.top_k_if_empty = top_k_if_empty
        self.enable_entity_extraction = enable_entity_extraction

    def parse(self, text: str) -> Dict:
        """
        Run DistilBERT multi-label model, apply rule-based tweaks,
        then (optionally) run entity + preference extraction.

        Returns:
          {
            "primary_intent": str,
            "secondary_intents": [str],
            "scores": {intent: prob},
            "raw_text": str,
            "entities": {...},
            "preference_overrides": {...}
          }
        """
        # ---- 1) Intent classification (DistilBERT) ----
        with torch.no_grad():
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                padding=True,
                max_length=128,
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            outputs = self.model(**inputs)
            logits = outputs.logits.detach().cpu().numpy()
            probs = expit(logits)[0]

        # Thresholding
        pred_indices = np.where(probs >= self.threshold)[0]

        # Fallback: top-k if nothing passes threshold
        if len(pred_indices) == 0 and self.top_k_if_empty is not None:
            top_indices = probs.argsort()[-self.top_k_if_empty:][::-1]
            pred_indices = top_indices

        # Sort by probability desc
        pred_indices = sorted(pred_indices, key=lambda i: probs[i], reverse=True)

        labels = [id2label[i] for i in pred_indices]
        scores = {id2label[i]: float(probs[i]) for i in range(len(probs))}

        # ---- 2) RULE-BASED BOOST: enforce recommend_pois in obvious recommendation queries ----
        text_lower = text.lower()
        recommend_triggers = [
            "suggest the best places",
            "best places to visit",
            "recommend places",
            "recommend some places",
            "recommend some nature spots",
            "show me places to visit",
            "show me family-friendly places",
            "suggest some places",
            "can you suggest the best places",
            "where should i go",
        ]

        has_reco_phrase = any(p in text_lower for p in recommend_triggers)

        # If it clearly looks like a recommendation query, make sure recommend_pois is present
        if has_reco_phrase and "recommend_pois" not in labels:
            labels.append("recommend_pois")

        # ---- 3) Choose primary intent (with small priority tweak) ----
        primary_intent = "generic_fact_query"
        if labels:
            # If it's a reco-style query and recommend_pois is present, make it primary
            if has_reco_phrase and "recommend_pois" in labels:
                primary_intent = "recommend_pois"
            else:
                # Default: highest-probability label
                primary_intent = labels[0]

        # Secondary intents = everything else except primary
        secondary_intents = [lbl for lbl in labels if lbl != primary_intent]

        # ---- 4) Entity + preference extraction (LLM + rules) ----
        entities: Dict = {}
        preference_overrides: Dict = {}

        if self.enable_entity_extraction:
            extracted = extract_entities_and_prefs(text)
            domain_category = extracted.get("domain_category")
            entities = extracted.get("entities", {})
            preference_overrides = extracted.get("preference_overrides", {})

        return {
            "primary_intent": primary_intent,
            "secondary_intents": secondary_intents,
            "scores": scores,
            "raw_text": text,
            "domain_category": domain_category,
            "entities": entities,
            "preference_overrides": preference_overrides,
        }
