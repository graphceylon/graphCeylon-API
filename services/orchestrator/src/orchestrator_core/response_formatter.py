from __future__ import annotations

from typing import Any, Dict, Optional, List
import os
import json
import requests

from ..utils.smalltalk_detector import SmalltalkSubtypeDetector


class ResponseFormatter:
    """
    Formats orchestrator results into a chat-friendly message.

    Behavior:
      - smalltalk: templates (fast, cheap, deterministic)
      - everything else: Groq (if enabled + key present), fallback to templates

    Debugging:
      - Set FORMATTER_DEBUG=1 to print which path is used and Groq response snippets.
    """

    def __init__(self) -> None:
        self.provider = os.getenv("RESPONSE_LLM_PROVIDER", "template").lower().strip()
        self.groq_key = os.getenv("GROQ_API_KEY", "").strip()
        self.groq_model = os.getenv("RESPONSE_LLM_MODEL", "llama-3.1-8b-instant").strip()

        # Debug flag
        self.debug = os.getenv("FORMATTER_DEBUG", "0").strip() == "1"

        # Which intents should use LLM formatting (if empty => all non-smalltalk)
        self.llm_intents = set(
            i.strip().lower()
            for i in os.getenv("RESPONSE_LLM_INTENTS", "").split(",")
            if i.strip()
        )

        # smalltalk subtype detector (no training)
        self.smalltalk = SmalltalkSubtypeDetector(
            model_name=os.getenv("SMALLTALK_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
            threshold=float(os.getenv("SMALLTALK_THRESHOLD", "0.45")),
        )

        if self.debug:
            print("[ResponseFormatter:init] provider =", self.provider)
            print("[ResponseFormatter:init] groq_key_set =", bool(self.groq_key))
            print("[ResponseFormatter:init] groq_model =", self.groq_model)
            print("[ResponseFormatter:init] llm_intents =", sorted(list(self.llm_intents)) if self.llm_intents else "(all non-smalltalk)")

    def format(
        self,
        *,
        user_text: str,
        parsed_intent: Dict[str, Any],
        results: Dict[str, Any],
        tasks: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Returns:
          {
            "text": "...final answer for UI...",
            "followups": [...optional questions...],
            "debug": {...optional...}   # not used here, but you can add if needed
          }
        """
        intent = (parsed_intent.get("intent") or "").strip().lower()

        if self.debug:
            print(f"[ResponseFormatter:format] intent={intent!r}")

        # Always keep smalltalk local
        if intent == "smalltalk":
            if self.debug:
                print("[ResponseFormatter:format] path=templates (reason=smalltalk)")
            return self._format_with_templates(user_text, parsed_intent, results, tasks)

        # Determine whether to use LLM
        use_llm = (self.provider == "groq" and bool(self.groq_key))

        # If RESPONSE_LLM_INTENTS is provided, only use LLM for those intents
        if use_llm and self.llm_intents:
            use_llm = intent in self.llm_intents

        if self.debug:
            print(f"[ResponseFormatter:format] provider={self.provider} groq_key_set={bool(self.groq_key)} use_llm={use_llm}")

        if use_llm:
            out = self._format_with_groq(user_text, parsed_intent, results, tasks)
            # If Groq failed and returned empty, fallback to templates
            if out and out.get("text"):
                if self.debug:
                    print("[ResponseFormatter:format] path=groq (success)")
                return out
            if self.debug:
                print("[ResponseFormatter:format] path=groq (empty/failed) -> fallback templates")

        if self.debug:
            print("[ResponseFormatter:format] path=templates (default/fallback)")
        return self._format_with_templates(user_text, parsed_intent, results, tasks)

    def _format_with_templates(self, user_text, parsed_intent, results, tasks):
        intent = (parsed_intent.get("intent") or "").strip().lower()
        city = (parsed_intent.get("entities") or {}).get("city") or "Sri Lanka"
        stage = (results.get("meta", {}) or {}).get("conversation_stage", "idle")

        # ---- smalltalk ----
        if intent == "smalltalk":
            st = self.smalltalk.predict(user_text)

            if st.subtype == "greeting":
                if stage != "idle":
                    return {
                        "text": "Hi 👋 Want to continue from where we left off?",
                        "followups": ["Continue", "Change days", "Change budget"],
                    }
                return {
                    "text": "Hi 👋 What would you like to do?",
                    "followups": ["Plan an itinerary", "Recommend places", "Visa info", "Find hotels"],
                }

            if st.subtype == "how_are_you":
                if stage != "idle":
                    return {"text": "I’m doing well, thanks 😊 Want to continue?", "followups": ["Continue", "Adjust itinerary"]}
                return {"text": "I’m doing great 😊 How can I help with Sri Lanka travel?", "followups": ["Plan an itinerary", "Recommend places"]}

            if st.subtype == "thanks":
                if stage != "idle":
                    return {"text": "You’re welcome 😊 Want me to tweak anything?", "followups": ["Budget", "Days", "Pace", "Avoid crowds"]}
                return {"text": "You’re welcome 😊", "followups": []}

            if st.subtype == "farewell":
                return {"text": "Bye 👋 Come back anytime!", "followups": []}

            if st.subtype == "ack":
                if stage != "idle":
                    return {"text": "Got it 👍 What do you want to change next?", "followups": ["Change dates", "Change budget", "Add activities"]}
                return {"text": "Got it 👍 What would you like to do?", "followups": []}

            return {"text": "😊 How can I help?", "followups": ["Plan an itinerary", "Recommend places"]}

        # ---- info_attraction template fallback (cleaner) ----
        if intent == "info_attraction":
            atr = results.get("attraction_result") or {}
            items = atr.get("items") or []

            if not items:
                return {
                    "text": f"I couldn’t find attractions for **{city}** from my current data. What type of places do you prefer?",
                    "followups": ["Culture", "Nature", "Viewpoints", "Museums"],
                }

            lines = [f"Here are some places to explore in **{city}**:\n"]
            for it in items[:5]:
                name = it.get("name") or "Attraction"
                desc = (it.get("description") or "").strip()

                # nicer shortening: first sentence only
                if "." in desc:
                    desc = desc.split(".")[0].strip() + "."

                lines.append(f"📍 **{name}**\n{desc}\n")

            lines.append("Want me to narrow it down (culture / nature / family-friendly / short visit)?")
            return {"text": "\n".join(lines).strip(), "followups": []}

        # generic fallback
        return {"text": "I got your request. What would you like to do next?", "followups": []}

    def _format_with_groq(self, user_text, parsed_intent, results, tasks):
        # If key missing, fallback safely
        if not self.groq_key:
            if self.debug:
                print("[ResponseFormatter:groq] groq_key missing -> templates")
            return self._format_with_templates(user_text, parsed_intent, results, tasks)

        intent = (parsed_intent.get("intent") or "").strip().lower()

        # Keep payload small + consistent
        compact = {
            "user_text": user_text,
            "intent": {
                "primary": intent,
                "confidence": parsed_intent.get("confidence"),
                "secondary": parsed_intent.get("secondary_intents", []),
                "domain_category": parsed_intent.get("domain_category"),
            },
            "entities": parsed_intent.get("entities", {}),
            "results": {k: v for k, v in results.items() if v is not None and k.endswith("_result")},
        }

        # Strong “format-only” contract to prevent hallucination
        system = (
            "You are a response formatter for a Sri Lanka travel assistant.\n"
            "You MUST ONLY use facts present in the provided JSON.\n"
            "Do NOT add new attractions, prices, distances, hours, or any facts not in JSON.\n"
            "If the JSON has only generic/low-quality items, say so politely and ask 1 short follow-up question.\n"
            "Write clean, friendly, ChatGPT-style output.\n"
            "Output MUST be valid JSON with exactly keys: text, followups.\n"
            "followups must be a JSON array of short strings.\n"
        )

        prompt = (
            f"{system}\n"
            f"JSON:\n{json.dumps(compact, ensure_ascii=False)}\n\n"
            "Return ONLY the JSON object."
        )

        if self.debug:
            print("[ResponseFormatter:groq] >>> ENTERING GROQ FORMATTER")
            print(f"[ResponseFormatter:groq] model={self.groq_model}")

        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.groq_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.groq_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                },
                timeout=20,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()

            if self.debug:
                print("[ResponseFormatter:groq] raw_content_preview =", content[:300].replace("\n", "\\n"))

        except Exception as e:
            if self.debug:
                print("[ResponseFormatter:groq] request failed:", repr(e))
            return self._format_with_templates(user_text, parsed_intent, results, tasks)

        # Try strict JSON parse
        try:
            out = json.loads(content)
            if isinstance(out, dict) and "text" in out:
                return {
                    "text": str(out.get("text", "")).strip(),
                    "followups": out.get("followups", []) or [],
                }
        except Exception as e:
            if self.debug:
                print("[ResponseFormatter:groq] JSON parse failed:", repr(e))

            # Soft fallback: if model returned plain text, still show it
            if content:
                return {"text": content, "followups": []}

        return self._format_with_templates(user_text, parsed_intent, results, tasks)
