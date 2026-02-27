from __future__ import annotations

from typing import Any, Dict, Optional, List
import os
import json
import requests
import re

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
        intent = self._pick_effective_intent_with_results(parsed_intent, results)
        present_keys = self._collect_present_result_keys(results)

        # If nothing to format (no *_result), use LLM general answer for fact/out_of_scope
        has_any_result = any(
            (k.endswith("_result") and results.get(k) is not None)
            for k in (results or {}).keys()
        )

        if not has_any_result and intent in {"out_of_scope", "generic_fact_query"}:
            # if groq enabled, answer directly (general knowledge)
            if self.provider == "groq" and self.groq_key:
                return self._answer_general_with_groq(user_text, parsed_intent)
            # else template fallback
            return {
                "text": "I can help with Sri Lanka travel planning (places, routes, hotels, visa). What do you want to do?",
                "followups": ["Plan an itinerary", "Recommend places", "Transport info", "Visa info"],
            }


        if self.debug:
            print(f"[ResponseFormatter:format] effective_intent={intent!r}")

        # Only keep smalltalk local if it is STILL smalltalk after override
        # if intent == "smalltalk":
        #     return self._format_with_templates(user_text, parsed_intent, results, tasks)


        # if self.debug:
        #     print(f"[ResponseFormatter:format] intent={intent!r}")

        # # Always keep smalltalk local
        # if intent == "smalltalk":
        #     if self.debug:
        #         print("[ResponseFormatter:format] path=templates (reason=smalltalk)")
        #     return self._format_with_templates(user_text, parsed_intent, results, tasks)

        if self.debug:
            print(f"[ResponseFormatter:format] effective_intent={intent!r}")

        # Always keep smalltalk local
        if intent == "smalltalk":
            if self.debug:
                print("[ResponseFormatter:format] path=templates (reason=smalltalk)")
            return self._format_with_templates(user_text, parsed_intent, results, tasks)

        # Determine whether to use LLM
        use_llm = (self.provider == "groq" and bool(self.groq_key))

        # If RESPONSE_LLM_INTENTS is set, restrict to those intents.
        # If it's empty, Groq applies to ALL non-smalltalk intents.
        if self.llm_intents:
            use_llm = use_llm and (intent in self.llm_intents)

        if self.debug:
            print(f"[ResponseFormatter:format] provider={self.provider} groq_key_set={bool(self.groq_key)} use_llm={use_llm}")

        if use_llm:
            out = self._format_with_groq(user_text, parsed_intent, results, tasks, effective_intent=intent)

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
    def _answer_general_with_groq(self, user_text: str, parsed_intent: Dict[str, Any]) -> Dict[str, Any]:
        system = (
            "You are a helpful assistant.\n"
            "Answer the user's question using general knowledge.\n"
            "Keep it short and clear.\n"
            "If the question is unclear, ask ONE short follow-up.\n"
            "OUTPUT FORMAT (strict): Return valid JSON with EXACTLY: text, followups.\n"
        )

        prompt = (
            f"{system}\n"
            f"User: {user_text}\n\n"
            "Return ONLY the JSON object."
        )

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
                timeout=15,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            out = json.loads(content)
            return {
                "text": str(out.get("text", "")).strip(),
                "followups": out.get("followups", []) or [],
            }
        except Exception:
            # safe fallback if LLM fails
            return {"text": "Sri Lanka’s capital is Sri Jayawardenepura Kotte.", "followups": []}

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
            it = results.get("itinerary_result") or {}
            days = it.get("days") or ((parsed_intent.get("entities") or {}).get("days") or 0) or 0

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
                lines = [f"{label} ({date}) — {district}"]
                items = d.get("items") or []
                # group by slot
                slot_order = ["morning", "afternoon", "evening"]
                by_slot = {s: [] for s in slot_order}
                for itx in items:
                    slot = (itx.get("slot") or "").lower()
                    title = itx.get("title") or itx.get("name") or "Activity"
                    if slot in by_slot and len(by_slot[slot]) < 1:
                        by_slot[slot].append(title)

                for s in slot_order:
                    if by_slot[s]:
                        lines.append(f"- {s}: {by_slot[s][0]}")
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
            out_lines = []
            for i, d in enumerate(itinerary[:3], start=1):
                out_lines.append(format_one_day(d, f"Day {i}"))
                out_lines.append("")  # spacing

            # chips Day 1..Day N (max 4)
            n = days or len(itinerary)
            chips = [f"Day {i}" for i in range(1, min(n, 4) + 1)]
            return {"text": "\n".join(out_lines).strip(), "followups": chips}


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

    def _format_with_groq(self, user_text, parsed_intent, results, tasks, *, effective_intent: str):
        # If key missing, fallback safely
        if not self.groq_key:
            if self.debug:
                print("[ResponseFormatter:groq] groq_key missing -> templates")
            return self._format_with_templates(user_text, parsed_intent, results, tasks)

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
                # Try strict JSON parse
                # Try strict JSON parse
        try:
            out = json.loads(content)
        except Exception:
            # Try to extract the first JSON object from the text
            m = re.search(r"\{.*\}", content, re.DOTALL)
            if not m:
                return {"text": content.strip(), "followups": []}
            try:
                out = json.loads(m.group(0))
            except Exception:
                return {"text": content.strip(), "followups": []}

        if isinstance(out, dict) and "text" in out:
            return {
                "text": str(out.get("text", "")).strip(),
                "followups": out.get("followups", []) or [],
            }

        # Soft fallback: if model returned something unexpected, still show it
        if content:
            return {"text": content.strip(), "followups": []}

        return self._format_with_templates(user_text, parsed_intent, results, tasks)


        
