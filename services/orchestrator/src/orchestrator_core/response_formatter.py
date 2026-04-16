from __future__ import annotations

from asyncio import tasks
from typing import Any, Dict, Optional, List
import os
import json
from pandas import date_range
import requests
import re

from ..utils.smalltalk_detector import SmalltalkSubtypeDetector
from .agentic.output_patch import patch_agentic_text


class ResponseFormatter:
    """
    Formats orchestrator results into a chat-friendly message.

    Behavior:
      - smalltalk: templates (fast, cheap, deterministic)
      - everything else: Groq (if enabled + key present), fallback to templates

    Debugging:
      - Set FORMATTER_DEBUG=1 to print which path is used and Groq response snippets.
    """

    # def __init__(self) -> None:
    #     self.provider = os.getenv("RESPONSE_LLM_PROVIDER", "template").lower().strip()
    #     self.groq_key = os.getenv("GROQ_API_KEY", "").strip()
    #     self.groq_model = os.getenv("RESPONSE_LLM_MODEL", "llama-3.1-8b-instant").strip()

    #     # Debug flag
    #     self.debug = os.getenv("FORMATTER_DEBUG", "0").strip() == "1"

    def __init__(self, llm_client=None) -> None:
        self.llm_client = llm_client
        self.provider = os.getenv("LLM_PROVIDER", "template").lower().strip()
        self.debug = os.getenv("FORMATTER_DEBUG", "0").strip() == "1"

        self.llm_intents = set(
            i.strip().lower()
            for i in os.getenv("RESPONSE_LLM_INTENTS", "").split(",")
            if i.strip()
        )

        self.smalltalk = SmalltalkSubtypeDetector(
            model_name=os.getenv("SMALLTALK_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
            threshold=float(os.getenv("SMALLTALK_THRESHOLD", "0.45")),
        )

        if self.debug:
            print("[ResponseFormatter:init] provider =", self.provider)
            print("[ResponseFormatter:init] llm_client_set =", self.llm_client is not None)
            print("[ResponseFormatter:init] llm_intents =", sorted(list(self.llm_intents)) if self.llm_intents else "(all non-smalltalk)")
    def _derive_activity_label(self, parsed_intent: Dict[str, Any]) -> str:
        ents = parsed_intent.get("entities") or {}
        activity = ents.get("activity_type") or ents.get("activity_preference")
        if isinstance(activity, str) and activity.strip():
            return activity.strip().lower()
        tags = ents.get("tags") or []
        for t in tags:
            if isinstance(t, str) and t.strip():
                return t.strip().lower()
        return "trip"
    def _format_followup_with_llm(
        self,
        *,
        user_text: str,
        parsed_intent: Dict[str, Any],
        followup: Dict[str, Any],
        missing_fields: List[str],
    ) -> Dict[str, Any]:
        system = (
            "You are a RESPONSE FORMATTER for a Sri Lanka travel assistant.\n"
            "You MUST NOT invent facts.\n"
            "You ONLY rewrite the follow-up question to sound natural.\n\n"
            "You MAY adapt the trip type word using activity_label.\n"
            "You MUST ask ONLY for the missing_fields provided.\n"
            "Do NOT add new questions beyond missing_fields.\n"
            "Do NOT add new options beyond the provided options list.\n\n"
            "OUTPUT FORMAT (strict): JSON with EXACT keys: text, followups.\n"
            "- text: one friendly message (max 60 words)\n"
            "- followups: use the given options ONLY (max 8)\n"
        )

        label = self._derive_activity_label(parsed_intent)
        ents = parsed_intent.get("entities") or {}
        prefs = parsed_intent.get("preference_overrides") or {}

        payload = {
            "user_text": user_text,
            "intent": (parsed_intent.get("intent") or ""),
            "missing_fields": missing_fields,
            "activity_label": label,
            "tags": ents.get("tags") or [],
            "days": ents.get("days"),
            "preferences": {
                "activity_preference": prefs.get("activity_preference"),
                "travel_style": prefs.get("travel_style"),
                "budget_level": prefs.get("budget_level"),
                "adventure_level": prefs.get("adventure_level"),
                "pace_preference": prefs.get("pace_preference"),
            },
            "question": followup.get("question") or "",
            "options": followup.get("options") or [],
        }

        try:
            out = self.llm_client.chat_json(
                system_prompt=system,
                user_prompt=f"JSON:\n{json.dumps(payload, ensure_ascii=False)}\nReturn ONLY the JSON object."
            )
            return {"text": out.get("text", ""), "followups": out.get("followups", [])}
        except Exception:
            return {
                "text": (followup.get("question") or "I need a bit more info to plan this.").strip(),
                "followups": followup.get("options") or [],
            }
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
            "debug": {...optional...}
        }
        """
        intent = self._pick_effective_intent_with_results(parsed_intent, results)
        
        present_keys = self._collect_present_result_keys(results)

        # ✅ NEW: Follow-up short-circuit (MUST be early)
        followup = (results or {}).get("followup")
        missing_fields = (results or {}).get("missing_fields") or []
        if followup and missing_fields:
            # If Groq enabled, use it to rewrite/beautify the followup (NO hallucinations)
            use_llm = self.llm_client is not None
            if self.llm_intents:
                # allow followup formatting when plan_itinerary is enabled
                intent0 = (parsed_intent.get("intent") or "").strip().lower()
                use_llm = use_llm and (intent0 in self.llm_intents)

            if use_llm:
                out = self._format_followup_with_llm(
                    user_text=user_text,
                    parsed_intent=parsed_intent,
                    followup=followup,
                    missing_fields=missing_fields,
                )
                out = self._sanitize_output(out)
                section = "pois" if intent == "recommend_pois" else intent
                out = self._append_why_to_text(out, results, section=section)
                out = patch_agentic_text(out, results)
                ui = self._format_explainability_ui_with_llm(results, effective_intent=intent)
                if not ui:
                    ui = self._build_explainability_ui(results, effective_intent=intent)
                out["explainability_ui"] = ui
                return out

            out = {
                "text": followup.get("question") or "I need a bit more info to plan this.",
                "followups": followup.get("options") or [],
            }
            out = self._sanitize_output(out)
            out = patch_agentic_text(out, results)
            ui = self._format_explainability_ui_with_llm(results, effective_intent=intent)
            if not ui:
                ui = self._build_explainability_ui(results, effective_intent=intent)
            out["explainability_ui"] = ui
            return out

        # If nothing to format (no *_result), use LLM general answer for fact/out_of_scope
        has_any_result = any(
            (k.endswith("_result") and results.get(k) is not None)
            for k in (results or {}).keys()
        )
        # ✅ Visa short-circuit — always use structured template (never Groq for visa)
        if results.get("visa_result"):
            vr = results["visa_result"]
            vr_dict = vr.model_dump(mode="json") if hasattr(vr, "model_dump") else dict(vr or {})

            formatted_text = self._format_visa(vr)

            # Build structured sources for explainability_ui
            sources = []
            seen = set()
            for rule in (vr_dict.get("rules") or []):
                for ev in (rule.get("evidence") or []):
                    url = (ev.get("url") or "").strip()
                    source = (ev.get("source") or "").strip()
                    if url and url not in seen:
                        seen.add(url)
                        label = source.replace("_", " ").replace(".json", "").title() if source else "Official Source"
                        sources.append({"label": label, "url": url})

            explainability_ui = ""
            if sources:
                src_lines = "\n".join(f"• {s['label']}: {s['url']}" for s in sources)
                explainability_ui = f"Sources verified from official Sri Lanka Immigration authorities:\n{src_lines}"

            return {
                "text": formatted_text,
                "followups": ["Tourist visa", "Visa fee", "Processing time", "Required documents"],
                "explainability_ui": explainability_ui,
                "sources": sources,  # Flutter renders these as tappable links
            }

        if not has_any_result:
            # ALWAYS use LLM for smooth conversation
            if self.llm_client is not None:
                return self._answer_general_with_llm(user_text, parsed_intent)

            # fallback only if LLM fails
            return {
                "text": "I can help you explore Sri Lanka, plan trips, find hotels, transport, and travel tips. What would you like to do?",
                "followups": ["Plan a trip", "Find hotels", "Explore places", "Travel tips"],
            }

        if self.debug:
            print(f"[ResponseFormatter:format] effective_intent={intent!r}")

        # Always keep smalltalk local
        if intent == "smalltalk":
            out = self._format_with_templates(user_text, parsed_intent, results, tasks)
            out = self._sanitize_output(out)
            section = "pois" if intent == "recommend_pois" else intent
            out = self._append_why_to_text(out, results, section=section)

            out = patch_agentic_text(out, results)
            ui = self._format_explainability_ui_with_llm(results, effective_intent=intent)
            if not ui:
                ui = self._build_explainability_ui(results, effective_intent=intent)
            out["explainability_ui"] = ui
            return out
            # return patch_agentic_text(out, results)

        use_llm = self.llm_client is not None
        if self.llm_intents:
            use_llm = use_llm and (intent in self.llm_intents)

        if use_llm:
            out = self._format_with_llm(user_text, parsed_intent, results, tasks, effective_intent=intent)
            out = self._sanitize_output(out)
            if out.get("text", "").strip():
                out = patch_agentic_text(out, results)
                ui = self._format_explainability_ui_with_llm(results, effective_intent=intent)
                if not ui:
                    ui = self._build_explainability_ui(results, effective_intent=intent)
                out["explainability_ui"] = ui
                return out

        out = self._format_with_templates(user_text, parsed_intent, results, tasks)
        out = self._sanitize_output(out)
        out = patch_agentic_text(out, results)
        ui = self._format_explainability_ui_with_llm(results, effective_intent=intent)
        if not ui:
            ui = self._build_explainability_ui(results, effective_intent=intent)
        out["explainability_ui"] = ui
        return out
    
    def _collect_present_result_keys(self, results: Dict[str, Any]) -> List[str]:
        """Return result keys that are present and meaningful."""
        order = [
            "weather_result",
            "itinerary_result",
            "pois_result",
            "attraction_result",
            "transport_result",
            "accommodation_result",
            "visa_result",
            "price_result",
            "crowd_result",
            "modify_result",
            "restaurant_result",
        ]

        present = []
        for k in order:
            v = results.get(k)
            if v is None:
                continue
            # if result has items list, ensure it's non-empty
            if isinstance(v, dict) and "items" in v:
                if v.get("items"):
                    present.append(k)
                continue
            # otherwise accept non-null objects/dicts
            present.append(k)

        return present
    def _answer_general_with_llm(self, user_text, parsed_intent):
        system = (
            "You are GraphCeylon, a friendly Sri Lanka travel assistant.\n"
            "Keep conversations natural and engaging.\n"
            "Help with trips, hotels, transport, weather, food, and places.\n"
            "If the user is vague, still respond helpfully and ask ONE follow-up.\n"
            "Never say you failed. Never mention tools or intents.\n"
            "Return ONLY JSON.\n"
            "FORMAT:\n"
            "{\n"
            '  "text": "your answer",\n'
            '  "followups": ["option1", "option2", "option3"]\n'
            "}"
        )

        try:
            out = self.llm_client.chat_json(
                system_prompt=system,
                user_prompt=f"User: {user_text}\nReturn JSON only."
            )

            return {
                "text": str(out.get("text", "")).strip(),
                "followups": out.get("followups", []) or [],
            }

        except Exception:
            return {
                "text": "I can help you plan trips, find places, hotels, transport, or travel tips in Sri Lanka. What would you like to do?",
                "followups": ["Plan a trip", "Find hotels", "Explore places", "Travel tips"],
            }

    def _as_dict(self, obj: Any) -> Dict[str, Any]:
        if obj is None:
            return {}
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, "model_dump"):   # pydantic v2
            return obj.model_dump(mode="json")
        if hasattr(obj, "dict"):         # pydantic v1
            return obj.dict()
        return {}

    def _compact_itinerary_result(self, it: Any) -> Dict[str, Any]:
        it = self._as_dict(it)

        meta = it.get("meta") or {}
        plans = it.get("plans") or {}
        plans = self._as_dict(plans)

        route_plan = plans.get("route_plan")
        route_plan = self._as_dict(route_plan) if route_plan else {}

        days_out = []
        for day in (it.get("itinerary") or [])[:7]:
            items_out = []
            for item in (day.get("items") or [])[:3]:
                items_out.append({
                    "slot": item.get("slot"),
                    "title": item.get("title"),
                    "district": item.get("district"),
                    "kind": item.get("kind"),
                })
            days_out.append({
                "date": day.get("date"),
                "district": day.get("district"),
                "city": day.get("city"),
                "items": items_out,
            })

        compact = {
            "status": it.get("status"),
            "meta": {
                "destination": meta.get("destination"),
                "origin_city": meta.get("origin_city"),
                "days": meta.get("days"),
                "start_date": meta.get("start_date"),
            },
            "itinerary": days_out,
        }

        # include route question if present (useful for followups chips)
        if route_plan.get("question"):
            compact["route_plan"] = {
                "status": route_plan.get("status"),
                "reason": route_plan.get("reason"),
                "question": route_plan.get("question"),
                "options": (route_plan.get("options") or [])[:4],
            }

        return compact


    def _pick_effective_intent(self, parsed_intent: Dict[str, Any], results: Dict[str, Any]) -> str:
        # Read the *original* intent directly (no recursion)
        intent = (parsed_intent.get("intent") or "").strip().lower()
        domain = (parsed_intent.get("domain_category") or "").strip().lower()
        entities = parsed_intent.get("entities") or {}

        # If not smalltalk, keep it
        if intent != "smalltalk":
            return intent

        # If we actually have real attraction results, override smalltalk
        atr = results.get("attraction_result") or {}
        items = atr.get("items") or []
        if atr.get("ok") and items:
            return "info_attraction"

        # If smalltalk but we have travel signals, prefer secondary intents
        secondary = [s.strip().lower() for s in (parsed_intent.get("secondary_intents") or [])]
        has_city = bool(entities.get("city"))

        if (has_city or domain) and secondary:
            for s in secondary:
                if s != "smalltalk":
                    return s

        return intent
    def _build_explainability_ui(self, results: Dict[str, Any], *, effective_intent: str) -> Optional[str]:
        ctx = self._explainability_relevant_context(results, effective_intent=effective_intent)
        if not ctx:
            return None

        prefs = ctx.get("relevant_prefs") or {}
        city = (ctx.get("context") or {}).get("city") or "this area"

        # Now use prefs (already filtered by intent)
        ts = prefs.get("travel_style") or []
        tags = ", ".join(ts[:2]) if ts else None

        avoid = prefs.get("avoid_crowds")
        food = (prefs.get("food_preferences") or [])
        budget = prefs.get("budget_per_night_lkr")

        parts = []
        if tags:
            parts.append(f"your interests in {tags}")
        if food:
            parts.append(f"your {food[0]} preference")
        if avoid is True:
            parts.append("your preference to avoid crowds")
        if isinstance(budget, (int, float)) and budget > 0:
            parts.append(f"your budget (~LKR {int(budget)}/night)")

        if parts:
            return f"Picked these for {city} based on " + ", ".join(parts) + "."
        return f"Picked these for {city} using your saved profile preferences."
    def _explainability_relevant_context(self, results: Dict[str, Any], *, effective_intent: str) -> Dict[str, Any]:
        xp = (results or {}).get("explainability")
        if not isinstance(xp, dict) or not xp:
            return {}

        prefs = xp.get("effective_prefs") or {}
        ents = xp.get("entities") or {}

        city = ents.get("city")
        country = ents.get("country")

        # Define relevance per intent (you can tweak anytime)
        if effective_intent in {"recommend_pois", "info_attraction", "plan_itinerary", "modify_itinerary"}:
            relevant_prefs = {
                "travel_style": prefs.get("travel_style") or [],
                "activity_preference": prefs.get("activity_preference"),
                "pace_preference": prefs.get("pace_preference"),
                "adventure_level": prefs.get("adventure_level"),
                "avoid_crowds": prefs.get("avoid_crowds"),
                "preferred_transport": prefs.get("preferred_transport") or [],
                "rain_preference": prefs.get("rain_preference"),
                "temperature_preference": prefs.get("temperature_preference"),
            }

        elif effective_intent in {"recommend_restaurants"}:
            relevant_prefs = {
                "food_preferences": prefs.get("food_preferences") or [],
                # "budget_level": prefs.get("budget_level"),
                # "avoid_crowds": prefs.get("avoid_crowds"),
                # "preferred_transport": prefs.get("preferred_transport") or [],
            }

        elif effective_intent in {"book_hotel", "info_accommodation", "check_availability"}:
            relevant_prefs = {
                "budget_per_night_lkr": prefs.get("budget_per_night_lkr"),
                "budget_level": prefs.get("budget_level"),
                "must_have_amenities": prefs.get("must_have_amenities") or [],
                # "preferred_transport": prefs.get("preferred_transport") or [],
                # "avoid_crowds": prefs.get("avoid_crowds"),
            }

        # elif effective_intent in {"forecast_weather"}:
        #     relevant_prefs = {
        #         "rain_preference": prefs.get("rain_preference"),
        #         "temperature_preference": prefs.get("temperature_preference"),
        #     }

        else:
            # generic safe fallback
            relevant_prefs = {
                "travel_style": prefs.get("travel_style") or [],
                "food_preferences": prefs.get("food_preferences") or [],
                "avoid_crowds": prefs.get("avoid_crowds"),
            }

        # remove empty values
        cleaned = {}
        for k, v in relevant_prefs.items():
            if v is None:
                continue
            if isinstance(v, list) and not v:
                continue
            if isinstance(v, str) and not v.strip():
                continue
            cleaned[k] = v

        return {
            "intent": xp.get("intent"),
            "domain": xp.get("domain"),
            "summary": xp.get("summary"),
            "context": {"city": city, "country": country},
            "relevant_prefs": cleaned,
        }


    def _format_explainability_ui_with_llm(self, results: Dict[str, Any], *, effective_intent: str) -> Optional[str]:
        if self.llm_client is None:
            return None

        ctx = self._explainability_relevant_context(results, effective_intent=effective_intent)
        if not ctx:
            return None

        system = (
            "You are generating ONE short explainability sentence for a travel assistant UI.\n"
            "RULES:\n"
            "- Output MUST be a single sentence.\n"
            "- Use ONLY the provided JSON fields.\n"
            "- Do NOT invent facts.\n"
            "- Mention the city if present.\n"
            "- If relevant_prefs is empty, paraphrase summary.\n"
            "Return ONLY plain text.\n"
        )

        try:
            s = self.llm_client.chat_text(
                system_prompt=system,
                user_prompt=f"JSON:\n{json.dumps(ctx, ensure_ascii=False)}\n"
            )
            s = re.sub(r"\s+", " ", s).strip()
            return s if s else None
        except Exception:
            return None
    def _sanitize_output(self, out: Any) -> Dict[str, Any]:
        """
        Guarantee formatter output shape:
        - text: plain string (never JSON string, never dict)
        - followups: list[str]
        """
        if not isinstance(out, dict):
            return {"text": str(out), "followups": []}

        text = out.get("text", "")
        followups = out.get("followups", [])

        # 1) text must be string
        if text is None:
            text = ""
        if not isinstance(text, str):
            text = str(text)

        # 2) if text looks like JSON string with {"text": "..."} unwrap it
        t = text.strip()
        if t.startswith("{") and t.endswith("}") and '"text"' in t:
            try:
                j = json.loads(t)
                if isinstance(j, dict) and isinstance(j.get("text"), str):
                    text = j["text"].strip()
                    fu = j.get("followups")
                    if isinstance(fu, list):
                        followups = fu
            except Exception:
                pass

        # 3) followups must be list[str]
        if not isinstance(followups, list):
            followups = []
        followups = [str(x) for x in followups if isinstance(x, (str, int, float))]

        return {"text": text.strip(), "followups": followups}
    def _render_why_block(self, results: Dict[str, Any], *, section: str) -> str:
        """
        section: "pois" | "attraction" | "itinerary" | ...
        Returns a small explanation block using results["explainability"] ONLY.
        """
        xp = (results or {}).get("explainability") or {}
        if not isinstance(xp, dict) or not xp:
            return ""

        summary = (xp.get("summary") or "").strip()
        prefs = xp.get("effective_prefs") or {}
        ents = xp.get("entities") or {}

        lines = []
        if summary:
            lines.append(summary)

        # small preference highlights (keep short)
        highlights = []
        ts = prefs.get("travel_style") or []
        if ts:
            highlights.append(f"interests: {', '.join(ts[:3])}")
        if prefs.get("avoid_crowds") is not None:
            highlights.append(f"avoid crowds: {prefs.get('avoid_crowds')}")
        if prefs.get("budget_per_night_lkr"):
            highlights.append(f"budget/night: LKR {prefs.get('budget_per_night_lkr')}")
        fp = prefs.get("food_preferences") or []
        if fp:
            highlights.append(f"food: {', '.join(fp[:3])}")

        if highlights:
            lines.append("Based on: " + " • ".join(highlights))

        # light context
        if ents.get("city"):
            lines.append(f"Context: city = {ents.get('city')}")

        if not lines:
            return ""

        return "\n\nWhy these recommendations:\n- " + "\n- ".join(lines)

    def _append_why_to_text(self, out: Dict[str, Any], results: Dict[str, Any], *, section: str) -> Dict[str, Any]:
        why = self._render_why_block(results, section=section)
        if not why:
            return out
        out["text"] = (out.get("text") or "").rstrip() + why
        return out
    def _pick_effective_intent_with_results(self, parsed_intent: Dict[str, Any], results: Dict[str, Any]) -> str:
        """
        Pick an intent that matches available results.
        Example: intent=forecast_price but price_result is None, while transport_result exists -> use info_transport.
        """
        primary = self._pick_effective_intent(parsed_intent, results)

        # map intent -> expected result key
        intent_to_result_key = {
            "info_attraction": "attraction_result",
            "recommend_pois": "pois_result", 
            "info_accommodation": "accommodation_result",
            "info_transport": "transport_result",
            "forecast_weather": "weather_result",
            "info_visa_policy": "visa_result",
            "forecast_price": "price_result",
            "crowd_forecast": "crowd_result",
            "modify_itinerary": "modify_result",
            "plan_itinerary": "itinerary_result",
            "recommend_restaurants":"restaurant_result",
        }

        expected_key = intent_to_result_key.get(primary)
        expected_val = results.get(expected_key) if expected_key else None

        # if expected result exists, keep primary
        if expected_val is not None:
            return primary

        # Otherwise: try secondary intents (if any) that have results
        secondary = [s.strip().lower() for s in (parsed_intent.get("secondary_intents") or [])]
        for s in secondary:
            k = intent_to_result_key.get(s)
            if k and results.get(k) is not None:
                return s

        # Finally: pick ANY available result key (priority order)
        for fallback_intent, k in [
            ("plan_itinerary", "itinerary_result"),
            ("recommend_pois", "pois_result"), 
            ("info_attraction", "attraction_result"),
            ("info_transport", "transport_result"),
            ("forecast_weather", "weather_result"),
            ("info_accommodation", "accommodation_result"),
            ("info_visa_policy", "visa_result"),
            ("forecast_price", "price_result"),
            ("crowd_forecast", "crowd_result"),
            ("modify_itinerary", "modify_result"),
            
        ]:
            if results.get(k) is not None:
                return fallback_intent

        return primary


    def _format_with_templates(self, user_text, parsed_intent, results, tasks):
        intent = self._pick_effective_intent_with_results(parsed_intent, results)


        city = (parsed_intent.get("entities") or {}).get("city") or "Sri Lanka"
        stage = (results.get("meta", {}) or {}).get("conversation_stage", "idle")

                # ---- plan_itinerary template fallback (Day 1/2/3 + chips) ----
        if intent == "plan_itinerary":
            it_raw = results.get("itinerary_result") or {}
            # convert Pydantic model to dict if needed
            if hasattr(it_raw, "model_dump"):
                it = it_raw.model_dump(mode="json")
            elif hasattr(it_raw, "dict"):
                it = it_raw.dict()
            else:
                it = dict(it_raw) if it_raw else {}

            parsed_intent_dict = parsed_intent if isinstance(parsed_intent, dict) else (
                parsed_intent.model_dump(mode="json") if hasattr(parsed_intent, "model_dump") else {}
            )
            days = it.get("days") or ((parsed_intent_dict.get("entities") or {}).get("days") or 0) or 0

            itinerary = it.get("itinerary") or []
            if not itinerary:
                # try nested structure: plans.destination_plan.itinerary
                dp = ((it.get("plans") or {}).get("destination_plan") or {})
                itinerary = dp.get("itinerary") or []

            if not itinerary:
                return {
                    "text": "I couldn’t generate an itinerary from the current data. Can you share your start city (e.g., Colombo) or are you already in Sri Lanka?",
                    "followups": ["Starting from Colombo", "Already in Sri Lanka", "Other"],
                }

            # Detect day request from user_text (Day 1/Day 2/Day 3)
            m = re.search(r"\bday\s*(\d+)\b", (user_text or "").lower())
            day_idx = None
            if m:
                try:
                    day_idx = int(m.group(1)) - 1
                except Exception:
                    day_idx = None

            def format_one_day(d, label):
                date = d.get("date") or ""
                district = d.get("district") or d.get("city") or "Hill Country"
                
                # weather from first attraction if available
                attractions = d.get("attractions") or d.get("items") or []
                weather_str = ""
                if attractions:
                    w = attractions[0].get("weather") or {}
                    if w.get("temp_c") is not None and w.get("rain_risk"):
                        weather_str = f"Weather: {int(w['temp_c'])}C, {w['rain_risk'].lower()} rain risk"
                district = d.get("district") or d.get("city") or "Hill Country"

                lines = [f"{label} — {date} | {district}"]
                if weather_str:
                    lines.append(weather_str)

                for attr in attractions:
                    slot = (attr.get("slot") or "").capitalize()
                    title = attr.get("title") or "Activity"
                    desc = (attr.get("description") or "").strip()
                    rating = attr.get("rating")
                    if desc and "." in desc:
                        desc = desc.split(".")[0].strip() + "."
                    rating_str = f" Rated {rating}." if rating else ""
                    desc_str = f" — {desc}{rating_str}" if desc else (f" — Rated {rating}." if rating else "")
                    lines.append(f"- {title} ({slot}){desc_str}")

                return "\n".join(lines)

            # If specific day requested, show only that day
            if day_idx is not None and 0 <= day_idx < len(itinerary):
                text = format_one_day(itinerary[day_idx], f"Day {day_idx+1}")
                # chips: All days + nearby days (max 4)
                chips = ["All days"]
                if day_idx - 1 >= 0:
                    chips.append(f"Day {day_idx}")
                chips.append(f"Day {day_idx+1}")
                if day_idx + 1 < len(itinerary):
                    chips.append(f"Day {day_idx+2}")
                return {"text": text, "followups": chips[:4]}

            # Otherwise show all days (max 3 shown; you have 3 anyway)
            # Build header
            origin = (parsed_intent.get("entities") or {}).get("origin_city") or "Colombo"
            dest = (parsed_intent.get("entities") or {}).get("city") or "Kandy"
            start = (parsed_intent.get("entities") or {}).get("start_date") or ""
            end = (parsed_intent.get("entities") or {}).get("end_date") or ""
            date_range = f"{start} – {end}" if start and end else start
            n = days or len(itinerary)
            header = f" {n}-Day Itinerary | {date_range}"

            out_lines = [header, ""]

            for i, d in enumerate(itinerary[:3], start=1):
                out_lines.append(format_one_day(d, f"Day {i}"))
                out_lines.append("")

            # Hotels — deduplicate, pull from first day
            first_day = itinerary[0] if itinerary else {}
            hotels = first_day.get("hotel_options") or []
            if hotels:
                out_lines.append("Where to Stay")
                for h in hotels:
                    name = h.get("name") or "Hotel"
                    price = h.get("price_range_lkr") or {}
                    price_str = f"LKR {int(price['min']):,}–{int(price['max']):,}/night" if price.get("min") and price.get("max") else ""
                    amenities = h.get("amenities") or []
                    amenities_str = ", ".join(amenities[:4]) if amenities else ""
                    parts = [p for p in [price_str, amenities_str] if p]
                    detail = " | ".join(parts)
                    out_lines.append(f"- {name}" + (f" — {detail}" if detail else ""))
                out_lines.append("")

            # Restaurants — collect unique across all days
            seen_restaurants = set()
            all_restaurants = []
            for d in itinerary:
                for r in (d.get("restaurants") or []):
                    title = r.get("title") or ""
                    if title and title not in seen_restaurants:
                        seen_restaurants.add(title)
                        all_restaurants.append(r)

            if all_restaurants:
                out_lines.append("Where to Eat")
                for r in all_restaurants:
                    title = r.get("title") or "Restaurant"
                    rating = r.get("rating")
                    category = (r.get("category") or "").replace("_", " ").capitalize()
                    rating_str = f", rated {rating}" if rating else ""
                    out_lines.append(f"- {title} — {category}{rating_str}")
                out_lines.append("")
            outbound_stops = it.get("outbound_stops") or []
            if outbound_stops:
                meta = it.get("meta") or {}
                origin = meta.get("origin_city") or "Origin"
                destination = meta.get("destination") or "Destination"
                out_lines.append(f"On the Way to {destination} ({origin} → {destination})")
                for i, stop in enumerate(outbound_stops, start=1):
                    title = stop.get("title") or "Stop"
                    city = stop.get("city") or ""
                    district = stop.get("district") or ""
                    rating = stop.get("rating")
                    location = f"{city}, {district}".strip(", ") if city or district else ""
                    rating_str = f" — Rated {rating}" if rating else ""
                    location_str = f" | {location}" if location else ""
                    out_lines.append(f"- {i}. {title}{location_str}{rating_str}")
                out_lines.append("")

            # ── ADD THIS: Return stops ────────────────────────────────────
            return_stops = it.get("return_stops") or []
            if return_stops:
                meta = it.get("meta") or {}
                origin = meta.get("origin_city") or "Origin"
                destination = meta.get("destination") or "Destination"
                out_lines.append(f"On the Way Back ({destination} → {origin})")
                for i, stop in enumerate(return_stops, start=1):
                    title = stop.get("title") or "Stop"
                    city = stop.get("city") or ""
                    district = stop.get("district") or ""
                    rating = stop.get("rating")
                    location = f"{city}, {district}".strip(", ") if city or district else ""
                    rating_str = f" — Rated {rating}" if rating else ""
                    location_str = f" | {location}" if location else ""
                    out_lines.append(f"- {i}. {title}{location_str}{rating_str}")
                out_lines.append("")

            # n = days or len(itinerary)
            chips = []

            days = n

            if days > 1:
                chips.append(f"Make it {days-1} day trip")

            chips.append(f"Extend to {days+1} days")

            if days >= 2:
                chips.append("Swap day 1 and day 2")
            else:
                chips.append("Change activities for day 1")
            return {"text": "\n".join(out_lines).strip(), "followups": chips}


        # ---- smalltalk ----
        # if intent == "smalltalk":
        #     st = self.smalltalk.predict(user_text)

        #     if st.subtype == "greeting":
        #         if stage != "idle":
        #             return {
        #                 "text": "Hi 👋 Want to continue from where we left off?",
        #                 "followups": ["Continue", "Change days", "Change budget"],
        #             }
        #         return {
        #             "text": "Hi 👋 What would you like to do?",
        #             "followups": ["Plan an itinerary", "Recommend places", "Visa info", "Find hotels"],
        #         }

        #     if st.subtype == "how_are_you":
        #         if stage != "idle":
        #             return {"text": "I’m doing well, thanks 😊 Want to continue?", "followups": ["Continue", "Adjust itinerary"]}
        #         return {"text": "I’m doing great 😊 How can I help with Sri Lanka travel?", "followups": ["Plan an itinerary", "Recommend places"]}

        #     if st.subtype == "thanks":
        #         if stage != "idle":
        #             return {"text": "You’re welcome 😊 Want me to tweak anything?", "followups": ["Budget", "Days", "Pace", "Avoid crowds"]}
        #         return {"text": "You’re welcome 😊", "followups": []}

        #     if st.subtype == "farewell":
        #         return {"text": "Bye 👋 Come back anytime!", "followups": []}

        #     if st.subtype == "ack":
        #         if stage != "idle":
        #             return {"text": "Got it 👍 What do you want to change next?", "followups": ["Change dates", "Change budget", "Add activities"]}
        #         return {"text": "Got it 👍 What would you like to do?", "followups": []}


        # ---- smalltalk ----
        if intent == "smalltalk":
            st = self.smalltalk.predict(user_text)

            if st.subtype == "greeting":
                if stage != "idle":
                    return {
                        "text": "Welcome back! Want to continue planning your trip?",
                        "followups": ["Continue", "Change days", "Change destination", "Change budget"],
                    }
                return {
                    "text": "Hi! I'm GraphCeylon, your Sri Lanka travel assistant. How can I help you today?",
                    "followups": ["Plan a trip", "Find hotels", "Check weather", "Visa info"],
                }

            if st.subtype == "how_are_you":
                if stage != "idle":
                    return {"text": "Doing well, thanks for asking! Want to continue with your trip plan?", "followups": ["Continue", "Adjust itinerary"]}
                return {"text": "Doing well! Ready to help you plan your Sri Lanka trip. Where would you like to go?", "followups": ["Plan a trip", "Recommend places"]}

            if st.subtype == "thanks":
                if stage != "idle":
                    return {"text": "Happy to help! Would you like to adjust anything?", "followups": ["Change budget", "Change days", "Change pace", "Avoid crowds"]}
                return {"text": "Happy to help!", "followups": []}

            if st.subtype == "farewell":
                return {"text": "Goodbye! Have a great trip to Sri Lanka. Come back anytime.", "followups": []}

            if st.subtype == "ack":
                if stage != "idle":
                    return {"text": "Got it. What would you like to change?", "followups": ["Change dates", "Change budget", "Add activities"]}
                return {"text": "Got it. What would you like to do?", "followups": []}

            return {"text": "How can I help you with your Sri Lanka trip?", "followups": ["Plan a trip", "Find hotels", "Check weather", "Visa info"]}

        # ---- info_attraction template fallback (cleaner) ----
        if intent == "modify_itinerary":
            mod_raw = results.get("modify_result")
            if mod_raw:
                mod = mod_raw if isinstance(mod_raw, dict) else (
                    mod_raw.model_dump(mode="json") if hasattr(mod_raw, "model_dump") else dict(mod_raw)
                )
                meta = mod.get("meta") or {}
                destination = meta.get("destination") or "your destination"
                num_days = meta.get("days")
                start_date = meta.get("start_date")

                # Build date string
                date_str = ""
                if start_date and num_days:
                    try:
                        from datetime import datetime, timedelta
                        start = datetime.strptime(start_date, "%Y-%m-%d")
                        end = start + timedelta(days=int(num_days) - 1)
                        if int(num_days) == 1:
                            date_str = start.strftime('%b %-d')
                        else:
                            date_str = f"{start.strftime('%b %-d')}–{end.strftime('%-d')}"
                    except Exception:
                        date_str = start_date

                days_label = f"{num_days} day{'s' if int(num_days) != 1 else ''}" if num_days else "updated"
                date_part = f" ({date_str})" if date_str else ""

                # Build header
                out_lines = [
                    f"Your {destination} trip has been updated to {days_label}{date_part}.",
                    "",
                ]

                # Pull itinerary from plan (only show days up to num_days)
                plan = mod.get("plan") or {}
                itinerary = plan.get("itinerary") or []
                num_days_int = int(num_days) if num_days else len(itinerary)
                itinerary = itinerary[:num_days_int]

                for i, day in enumerate(itinerary, start=1):
                    date = day.get("date") or ""
                    district = day.get("district") or day.get("city") or destination
                    out_lines.append(f"Day {i} — {date} | {district}")

                    # Weather from first attraction
                    attractions = day.get("attractions") or []
                    if attractions:
                        w = attractions[0].get("weather") or {}
                        if w.get("temp_c") is not None and w.get("rain_risk"):
                            out_lines.append(f"Weather: {int(w['temp_c'])}°C, {w['rain_risk'].lower()} rain risk")

                    for attr in attractions:
                        slot = (attr.get("slot") or "").capitalize()
                        title = attr.get("title") or "Activity"
                        desc = (attr.get("description") or "").strip()
                        rating = attr.get("rating")
                        if desc and "." in desc:
                            desc = desc.split(".")[0].strip() + "."
                        rating_str = f" Rated {rating}." if rating else ""
                        desc_str = f" — {desc}{rating_str}" if desc else (f" — Rated {rating}." if rating else "")
                        out_lines.append(f"- {title} ({slot}){desc_str}")

                    out_lines.append("")

                # Hotels from first day only
                first_day = itinerary[0] if itinerary else {}
                hotels = first_day.get("hotel_options") or []
                if hotels:
                    out_lines.append("Where to Stay")
                    for h in hotels[:3]:
                        name = h.get("name") or "Hotel"
                        price = h.get("price_range_lkr") or {}
                        price_str = f"LKR {int(price['min']):,}–{int(price['max']):,}/night" if price.get("min") and price.get("max") else ""
                        amenities = h.get("amenities") or []
                        amenities_str = ", ".join(amenities[:3]) if amenities else ""
                        parts = [p for p in [price_str, amenities_str] if p]
                        detail = " | ".join(parts)
                        out_lines.append(f"- {name}" + (f" — {detail}" if detail else ""))
                    out_lines.append("")

                # Restaurants — unique across all days, in-destination only
                seen_restaurants = set()
                all_restaurants = []
                for day in itinerary:
                    for r in (day.get("restaurants") or []):
                        title = r.get("title") or ""
                        r_city = (r.get("city") or "").lower()
                        dest_lower = destination.lower()
                        # skip restaurants clearly from a different city (e.g. Colombo KFC showing in Kandy)
                        if title and title not in seen_restaurants and (r_city == dest_lower or not r_city):
                            seen_restaurants.add(title)
                            all_restaurants.append(r)

                if all_restaurants:
                    out_lines.append("Where to Eat")
                    for r in all_restaurants[:4]:
                        title = r.get("title") or "Restaurant"
                        rating = r.get("rating")
                        category = (r.get("category") or "").replace("_", " ").capitalize()
                        rating_str = f", rated {rating}" if rating else ""
                        out_lines.append(f"- {title} — {category}{rating_str}")
                    out_lines.append("")

                chips = []

                days = num_days_int

                if days > 1:
                    chips.append(f"Make it {days-1} day trip")

                chips.append(f"Extend to {days+1} days")

                # ✅ Keep this instead of swap
                chips.append("Show hotels")

                chips = chips[:3]

                return {
                    "text": "\n".join(out_lines).strip(),
                    "followups": chips[:4],
                }

                # generic fallback
                return {"text": "I got your request. What would you like to do next?", "followups": []}
        # if intent == "info_transport":
        #     ents = (parsed_intent.get("entities") or {})
        #     origin = ents.get("origin") or ents.get("city") or "your starting point"
        #     destination = ents.get("destination") or "your destination"
        #     route_str = f"from {origin} to {destination}" if origin and destination and origin != destination else "around Sri Lanka"
        #     return {
        #         "text": f"Getting {route_str}:\n• Train — scenic and affordable, book at eservices.railway.gov.lk\n• Bus — frequent departures, most budget-friendly option\n• Taxi — approximately LKR 5,000-8,000 depending on distance\n• Private hire — most comfortable for families and groups\n\nWould you like to plan a full trip?",
        #         "followups": ["Plan a trip", "Hotels in Kandy", "Places to visit", "Weather forecast"],
        #     }
        if intent == "info_transport":
            ents = (parsed_intent.get("entities") or {})
            origin      = ents.get("origin") or ents.get("city") or "your starting point"
            destination = ents.get("destination") or "your destination"
            route_str   = f"from {origin} to {destination}" if origin != destination else f"around {origin}"

            transport_result = results.get("transport_result") or {}

            # ── Normalize to dict immediately — used by ALL branches below ───
            transport_dict = (
                transport_result.model_dump(mode="json")
                if hasattr(transport_result, "model_dump")
                else dict(transport_result) if transport_result else {}
            )

            transport_mode = transport_dict.get("_transport_mode")

            # ── ok:false from downstream — give a useful human answer ────────
            if transport_dict.get("ok") is False:
                scenic_note = ""
                if "colombo" in origin.lower() and "galle" in destination.lower():
                    scenic_note = " This is a popular 2.5-hour coastal scenic route."
                elif "colombo" in origin.lower() and any(
                    x in destination.lower() for x in ["kandy", "ella", "badulla", "nuwara"]
                ):
                    scenic_note = " This is a scenic hill country route."

                return {
                    "text": (
                        f"Trains from {origin} to {destination}:{scenic_note}\n\n"
                        "• Several express trains run daily on this route.\n"
                        "• Book tickets at eservices.railway.gov.lk or at the Colombo Fort station counter.\n"
                        "• Call 0112 421 281 for live schedule info.\n"
                        "• 2nd class reserved seats recommended for longer journeys."
                    ),
                    "followups": [
                        "Bus instead",
                        "How long does it take?",
                        "Plan a full trip",
                        f"Hotels in {destination}",
                    ],
                }

            # ── BUS ONLY ─────────────────────────────────────────────────
            # ── BUS ONLY ─────────────────────────────────────────────────
            if transport_mode == "bus" or (
                isinstance(transport_dict, dict)
                and transport_dict.get("ok") is True
                and "items" in transport_dict
                and "_transport_mode" not in transport_dict
            ):
                schedules = transport_dict.get("items") or []
                lines = [f"Buses from {origin} to {destination}:\n"]

                if schedules:
                    for i, s in enumerate(schedules[:5]):
                        if hasattr(s, "model_dump"):
                            s = s.model_dump()
                        open_hours = s.get("open_hours") or ""
                        parts_time = open_hours.split("→") if "→" in open_hours else []
                        dep  = parts_time[0].strip() if parts_time else ""
                        arr  = parts_time[1].strip() if len(parts_time) > 1 else ""
                        fare = s.get("entry_fee_lkr")
                        desc = s.get("description") or ""
                        link = s.get("website") or ""

                        fare_str = f" | LKR {int(fare)}" if fare else ""
                        time_str = f"departs {dep} → arrives {arr}" if dep and arr else dep or ""
                        lines.append(f"• {time_str}{fare_str}")

                        # Extract seats note from description
                        if "seats available" in desc:
                            for part in desc.split("."):
                                if "seats available" in part:
                                    lines.append(f"  ↳ {part.strip()}")
                                    break

                        # Show booking link
                        if link:
                            lines.append(f"  ↳ Book: {link}")

                    # Fare summary
                    fares = [s.get("entry_fee_lkr") for s in schedules if s.get("entry_fee_lkr")]
                    if fares:
                        lines.append(f"\nFares from LKR {int(min(fares))} – LKR {int(max(fares))}")
                    lines.append("Book at sltb.eseat.lk or Central Bus Stand, Colombo.")
                else:
                    lines.append("• Frequent SLTB buses on this route — buy tickets at the terminal.")
                    lines.append("• Book online at sltb.eseat.lk")

                return {
                    "text": "\n".join(lines),
                    "followups": [
                        "Train instead",
                        f"Hotels in {destination}",
                        f"Plan a full trip to {destination}",
                        "What time is the first bus?",
                    ],
                }

            # ── TRAIN ONLY ───────────────────────────────────────────────
            # ── TRAIN ONLY ───────────────────────────────────────────────
            # Inside _format_with_templates, the TRAIN ONLY section:

            if transport_mode == "train" or (
                isinstance(transport_dict, dict)
                and "options" in transport_dict
                and "_transport_mode" not in transport_dict
            ):
                train_options = transport_dict.get("options") or []
                lines = [f"Trains from {origin} to {destination}:\n"]

                if train_options:
                    for i, t in enumerate(train_options):
                        if hasattr(t, "model_dump"):
                            t = t.model_dump()
                        summary  = t.get("summary") or ""
                        cost     = t.get("estimated_cost_lkr")
                        duration = t.get("estimated_time_min")
                        tips     = (t.get("tips") or "").strip()

                        cost_str = f" | LKR {int(cost)}" if cost else ""
                        dur_str  = f" | ~{int(duration//60)}h {int(duration%60)}m" if duration else ""
                        lines.append(f"• {summary}{dur_str}{cost_str}")

                        # Only show first/last train info on first and last items
                        if tips and i == 0:
                            for part in tips.split("."):
                                part = part.strip()
                                if "first train" in part.lower():
                                    lines.append(f"  ↳ {part}")
                                    break
                        elif tips and i == len(train_options) - 1:
                            for part in tips.split("."):
                                part = part.strip()
                                if "last train" in part.lower():
                                    lines.append(f"  ↳ {part}")
                                    break

                    # Add booking note once at the bottom
                    lines.append("\nBook at eservices.railway.gov.lk or Colombo Fort station counter.")
                    lines.append("Call 0112 421 281 for schedule info.")
                else:
                    lines.append("• Several trains run daily on this coastal route.")
                    lines.append("• Book at eservices.railway.gov.lk")

                return {
                    "text": "\n".join(lines),
                    "followups": [
                        "Bus instead",
                        f"How long is the journey?",
                        "Plan a full trip to Galle",
                        f"Hotels in {destination}",
                    ],
                }

            # ── BOTH (generic query) ──────────────────────────────────────
            # ── BOTH ──────────────────────────────────────────────────────────
            # ── BOTH (IMPROVED UX FORMAT) ──────────────────────────────────────
            bus_data   = transport_dict.get("bus")   or {}
            train_data = transport_dict.get("train") or {}

            bus_items = bus_data.get("items", []) if isinstance(bus_data, dict) else []
            train_options = train_data.get("options", []) if isinstance(train_data, dict) else []
            # graceful fallback when both modes have no results
            if not train_options and not bus_items:
                return {
                    "text": (
                        f"I couldn’t find direct train or bus options from {origin} to {destination} right now.\n\n"
                        "You can try another date, check the reverse route, or ask for nearby transport hubs."
                    ),
                    "followups": [
                        "Try another date",
                        f"{destination} to {origin}",
                        "Nearby transport hubs",
                        "Plan a full trip",
                    ],
                }

            # ===== TRAIN SECTION =====
            train_section = "No train options available."

            if train_options:
                t = train_options[0]

                train_section = (
                    f"Best train option\n"
                    f"• {t.get('summary', 'Colombo → Kandy')} "
                )

                if t.get("estimated_time_min"):
                    duration = t["estimated_time_min"]
                    train_section += f"| ~{int(duration//60)}h {int(duration%60)}m "

                if t.get("estimated_cost_lkr"):
                    train_section += f"| from LKR {int(t['estimated_cost_lkr'])}"

                train_section += "\n"

                tips = t.get("tips", "")

                for part in tips.split("."):
                    part = part.strip()

                    if "first train" in part.lower():
                        cleaned = part.replace("the first train is at", "").strip()
                        cleaned = cleaned.replace("am", "AM").replace("pm", "PM")
                        train_section += f"  ↳ First train: {cleaned}\n"
                        break
                if "eservices.railway.gov.lk" in tips.lower():
                    train_section += "  ↳ Book at eservices.railway.gov.lk\n"



            # ===== BUS SECTION =====
            bus_section = "No bus options available."

            if bus_items:
                lines = []
                for b in bus_items[:3]:
                    dep = b.get("departure_time") or b.get("open_hours") or ""
                    fare = b.get("entry_fee_lkr") or b.get("fare")

                    line = f"• {dep}"
                    if fare:
                        line += f" | LKR {int(fare)}"

                    desc = (b.get("description") or "").lower()
                    if "seats available" in desc:
                        for part in desc.split("."):
                            if "seats available" in part:
                                line += f"\n  ↳ {part.strip()}"
                                break

                    lines.append(line)

                bus_section = "Best bus options\n" + "\n".join(lines)


            # ===== COMPARISON =====
            comparison_lines = []

            train_price = train_options[0].get("estimated_cost_lkr") if train_options else None
            bus_prices = [b.get("entry_fee_lkr") for b in bus_items if b.get("entry_fee_lkr")]

            if train_options and bus_items:
                cheapest = "Train"
                if train_price and bus_prices and min(bus_prices) < train_price:
                    cheapest = "Bus"

                comparison_lines = [
                    "Quick comparison",
                    f"• Cheapest: {cheapest}",
                    "• More departures: Bus",
                    "• Scenic option: Train",
                ]
            elif train_options:
                comparison_lines = [
                    "Quick comparison",
                    "• Train option available",
                    "• Scenic option: Train",
                ]
            elif bus_items:
                comparison_lines = [
                    "Quick comparison",
                    "• Bus options available",
                    "• More departures: Bus",
                ]

            comparison = "\n".join(comparison_lines)

            # ===== FINAL TEXT =====
            text_parts = [
                f"Getting {route_str}",
                train_section,
                bus_section,
            ]

            if comparison:
                text_parts.append(comparison)

            text_parts.append("What would you like next?")

            text = "\n\n".join(text_parts)

            return {
                "text": text,
                "followups": [
                    "Cheapest option",
                    "Fastest option",
                    "Show more buses",
                    "Train booking link"
                ],
            }

            # # ---- catch-all: use Groq for anything unhandled ----
            # if self.provider == "groq" and self.groq_key:
            #     return self._answer_general_with_groq(user_text, parsed_intent)

            # return {
            #     "text": "I can help you plan your Sri Lanka trip. What would you like to know?",
            #     "followups": ["Plan a trip", "Find hotels", "Check weather", "Visa info"],
            # }
        # return {"text": "I got your request. What would you like to do next?", "followups": []}
    def _format_visa(self, visa_result: Any) -> str:
        if not visa_result:
            return ""

        vr = visa_result.model_dump(mode="json") if hasattr(visa_result, "model_dump") else dict(visa_result or {})

        if vr.get("status") != "ok":
            return "Visa information is currently unavailable."

        dest = vr.get("destination_country") or "Sri Lanka"
        lines = [f"Visa & Entry Requirements — {dest}\n"]

        # ── Group rules by their title ─────────────────────────────────────
        rules = vr.get("rules") or []
        seen_details = set()
        seen_urls = {}   # url -> source label (from the data itself)
        grouped = {}     # title -> list of clean bullets

        for rule in rules:
            details = (rule.get("details") or "").strip()
            if not details or details in seen_details:
                continue
            seen_details.add(details)

            # Use actual title from data, fallback to rule_type
            title = (rule.get("title") or rule.get("rule_type") or "Information").strip()

            # Collect URLs + labels FROM the evidence itself (not hardcoded)
            for ev in (rule.get("evidence") or []):
                url = (ev.get("url") or "").strip()
                source = (ev.get("source") or "").strip()
                if url and url not in seen_urls:
                    # derive readable label from source filename
                    label = (
                        source
                        .replace("_data.json", "")
                        .replace("_", " ")
                        .title()
                    ) if source else url
                    seen_urls[url] = label

            # ── Clean raw text into readable sentences ─────────────────────
            sentences = re.split(r'\n{2,}|\.\s+(?=[A-Z])', details)
            for sentence in sentences:
                s = sentence.strip().strip(".")
                if not s or len(s) < 20:
                    continue
                if re.match(r'^\d+\.?\s', s):
                    continue
                if s.lower().startswith("where can i") or s.lower().startswith("how can i"):
                    continue
                if "dependents" in s.lower() and "diplomat" in s.lower():
                    continue
                if s in seen_details:
                    continue
                seen_details.add(s)

                if len(s) > 200:
                    s = s[:200].rsplit(" ", 1)[0] + "..."

                grouped.setdefault(title, [])
                if s not in grouped[title]:
                    grouped[title].append(s)

        # ── Render grouped sections ────────────────────────────────────────
        for title, bullets in grouped.items():
            if not bullets:
                continue
            lines.append(f"{title}:")
            for b in bullets[:6]:
                lines.append(f"• {b}")
            lines.append("")

        # ── Warnings ──────────────────────────────────────────────────────
        for w in (vr.get("warnings") or []):
            lines.append(f"⚠ {w}")
        if vr.get("warnings"):
            lines.append("")

        # ── Sources — labels derived from data, not hardcoded ─────────────
        # if seen_urls:
        #     lines.append("Official Sources:")
        #     for url, label in seen_urls.items():
        #         lines.append(f"  • {label}")
        #         lines.append(f"    {url}")

        return "\n".join(lines)
    def _format_with_llm(self, user_text, parsed_intent, results, tasks, *, effective_intent: str):
        if effective_intent in {"plan_itinerary", "modify_itinerary", "info_transport"}:
            return self._format_with_templates(user_text, parsed_intent, results, tasks)

        if self.llm_client is None:
            if self.debug:
                print("[ResponseFormatter:llm] llm_client missing -> templates")
            out = self._format_with_templates(user_text, parsed_intent, results, tasks)
            return self._sanitize_output(out)

        intent = effective_intent

                # IMPORTANT: use effective_intent (already passed in) instead of parsed intent
        # IMPORTANT: compact itinerary only (keep)
        it_raw = results.get("itinerary_result")
        compact_it = self._compact_itinerary_result(it_raw) if it_raw else None

        # build results payload
        results_payload: Dict[str, Any] = {}

        # 1) itinerary -> compact
        if compact_it:
            results_payload["itinerary_result"] = compact_it

        # 2) everything else -> normal (no compact)
        # only include non-null results so payload stays clean
        for k in [
            "pois_result",
            "attraction_result",
            "accommodation_result",
            "transport_result",
            "weather_result",
            "visa_result",
            "price_result",
            "crowd_result",
            "modify_result",
            "restaurant_result",
        ]:
            v = results.get(k)
            if v is not None:
                results_payload[k] = self._as_dict(v)

        compact = {
            "user_text": user_text,
            "intent": {
                "primary": effective_intent,
                "confidence": parsed_intent.get("confidence"),
                "secondary": parsed_intent.get("secondary_intents", []),
                "domain_category": parsed_intent.get("domain_category"),
            },
            "entities": parsed_intent.get("entities", {}),
            "results": results_payload,
        }



        
        

        



        # Strong “format-only” contract to prevent hallucination
        system = (
            "You are a RESPONSE FORMATTER for a Sri Lanka travel assistant.\n"
            "Your job is ONLY to format the answer using the provided JSON.\n\n"

            "HARD RULES (no hallucinations):\n"
            "- Use ONLY facts present in the JSON.\n"
            "- Do NOT invent new places, hotels, prices, distances, opening hours, phone numbers, URLs, or any details.\n"
            "- If the JSON is missing key details, say so clearly and ask ONE short follow-up question.\n"
            "- If a field is empty/unknown, do not guess.\n\n"

            "WHAT TO FORMAT:\n"
            "- Determine which result is present by checking JSON.results keys.\n"
            "- Prefer the most relevant non-null result based on intent.primary.\n"
            "- If JSON.results has a key that ends with '_result' and contains a non-empty 'items' list, format that list.\n"
            "- Do NOT say \"nothing found\" if items exist.\n"
            "- Check JSON.results for all keys that end with '_result'.\n"
            "- If multiple results exist, format ALL relevant ones as separate sections.\n"
            "- Limit to max 2 sections unless user asks for more.\n"
            "- If weather_result and itinerary_result both exist: show Weather first, then Itinerary.\n"
            "- If a result has an 'items' list, show up to 5 bullets.\n"
            "- If only one item exists, still show it (don’t discard it).\n\n"

            "FORMATTING STYLE:\n"
            "- Keep the output friendly and natural, but concise.\n"
            "- Max ~120 words.\n"
            "- If there is a list of items/options: show up to 5 bullets.\n"
            "- Each bullet: one line only.\n\n"

            "ITINERARY RULES (when JSON.results.itinerary_result exists):\n"
            "- The itinerary is under: JSON.results.itinerary_result.itinerary (list of days).\n"
            "- If the user_text mentions a specific day (e.g., 'Day 2' / 'day 2'), output ONLY that day.\n"
            "- Otherwise, output ALL days.\n"
            "- Day format must be:\n"
            "  Day X (YYYY-MM-DD) — District\n"
            "  - morning: title\n"
            "  - afternoon: title\n"
            "  - evening: title\n"
            "- If a slot does not exist in JSON for that day, omit that slot (do NOT create it).\n"
            "- Show up to 3 items per day.\n\n"

            "FOLLOWUPS (chips):\n"
            "- For itineraries: include ['Day 1','Day 2',... up to N] plus optionally 'All days'.\n"
            "- Max 4 followups total.\n"
            "- If you returned a single day, include 'All days' + nearby days (e.g., Day 1, Day 3).\n"
            "- For attractions: suggest up to 4 of ['More history spots','Beaches nearby','Family-friendly','Food places'].\n"
            "- For hotels: suggest up to 4 of ['Set budget','Only with AC','Near center','Luxury'].\n"
            "- For visa: suggest up to 4 of ['Tourist visa','Visa fee','Processing time','Required documents'].\n"
            "- Otherwise: return [].\n"



            "OUTPUT FORMAT (strict):\n"
            "- Output MUST be valid JSON with EXACTLY these keys: text, followups\n"
            "- 'text' must be a string.\n"
            "- 'followups' must be a JSON array of strings.\n"
        )


        



        prompt = (
            f"{system}\n"
            f"JSON:\n{json.dumps(compact, ensure_ascii=False, default=str)}\n\n"
            "Return ONLY the JSON object."
        )

        if self.debug:
            print("[ResponseFormatter:llm] >>> ENTERING LLM FORMATTER")
            print(f"[ResponseFormatter:llm] provider={self.provider}")
            print(f"[ResponseFormatter:llm] client={type(self.llm_client).__name__ if self.llm_client else 'None'}")
            print(f"[ResponseFormatter:llm] model={getattr(self.llm_client, 'model', 'unknown')}")

        try:
            out = self.llm_client.chat_json(
                system_prompt=system,
                user_prompt=f"JSON:\n{json.dumps(compact, ensure_ascii=False, default=str)}\n\nReturn ONLY the JSON object."
            )
        except Exception as e:
            if self.debug:
                print("[ResponseFormatter:llm] request failed:", repr(e))
            return self._format_with_templates(user_text, parsed_intent, results, tasks)

        if isinstance(out, dict) and "text" in out:
            return {
                "text": str(out.get("text", "")).strip(),
                "followups": out.get("followups", []) or [],
            }

        return self._format_with_templates(user_text, parsed_intent, results, tasks)


            
