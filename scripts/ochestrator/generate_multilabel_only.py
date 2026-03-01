# generate_multilabel_only.py
# Generates ONLY NEW multi-intent rows (no reading any existing CSV).
#
# Output columns:
# id,text,intent,split,labels,num_labels
#
# Usage example:
# python scripts/ochestrator/generate_multilabel_only.py \
#   --out data/orchestrator/raw/intents_multilabel_new_only.csv \
#   --start-id 5270 \
#   --n-per-pair 40 \
#   --include-triples 120 \
#   --seed 42

import argparse
import random
import re
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd


INTENT_LABELS = [
    "plan_itinerary","recommend_pois","modify_itinerary",
    "crowd_forecast","forecast_weather","forecast_price","forecast_sustainability",
    "info_attraction","info_accommodation","info_transport","info_visa_policy",
    "check_availability","book_hotel","modify_booking","cancel_booking",
    "update_preferences","explanation_request",
    "generic_fact_query","recommend_restaurants",
    "smalltalk",
    "out_of_scope"
]

# You can tune which intents you want to generate multi-intents for.
# Usually you DON'T want smalltalk/out_of_scope as multi-label.
DEFAULT_EXCLUDE_FROM_MULTI = {"smalltalk", "out_of_scope"}

CITIES = [
    "Kandy", "Colombo", "Galle", "Ella", "Nuwara Eliya", "Sigiriya",
    "Matara", "Jaffna", "Negombo", "Trincomalee", "Mirissa", "Bentota",
    "Anuradhapura", "Polonnaruwa", "Haputale", "Badulla", "Arugam Bay",
    "Dambulla", "Hikkaduwa", "Kalpitiya"
]

TIME_PHRASES = [
    "today", "tomorrow", "this weekend", "next 3 days", "next 5 days",
    "for the next few days", "for this week", "for the next week",
    "in March", "in April", "during my trip", "this month", "next month"
]

CONNECTORS = ["and", "plus", "as well as", "along with", "also", "together with"]

def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def cap_first(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s

def sample_days(rng: random.Random) -> int:
    return rng.choice([2, 3, 4, 5, 6, 7])

def chunk_for_intent(rng: random.Random, intent: str, city: str, origin: str, dest: str) -> str:
    t = rng.choice(TIME_PHRASES)
    days = sample_days(rng)

    # --- Travel planning / attractions ---
    if intent == "plan_itinerary":
        return rng.choice([
            f"plan a {days}-day itinerary for {city}",
            f"create a {days}-day trip plan to {city}",
            f"build a {days}-day itinerary in {city}",
        ])
    if intent == "recommend_pois":
        return rng.choice([
            f"suggest top attractions in {city}",
            f"recommend must-see places in {city}",
            f"list things to do in {city}",
        ])
    if intent == "info_attraction":
        return rng.choice([
            f"tell me about tourist attractions in {city}",
            f"give details about main sights in {city}",
            f"explain the best places to visit in {city}",
        ])

    # --- Forecasts ---
    if intent == "forecast_weather":
        return rng.choice([
            f"give me the weather forecast for {city} {t}",
            f"tell me if it will rain in {city} {t}",
            f"what’s the weather in {city} {t}",
        ])
    if intent == "forecast_price":
        return rng.choice([
            f"estimate the trip cost for {city}",
            f"give a budget estimate for visiting {city}",
            f"what will a {days}-day trip to {city} cost",
        ])
    if intent == "forecast_sustainability":
        return rng.choice([
            f"suggest eco-friendly travel options for {city}",
            f"give sustainable travel tips for {city}",
            f"how can I travel sustainably in {city}",
        ])
    if intent == "crowd_forecast":
        return rng.choice([
            f"predict crowd levels in {city} {t}",
            f"how busy will {city} be {t}",
            f"give a crowd forecast for {city} {t}",
        ])

    # --- Modify itinerary / info ---
    if intent == "modify_itinerary":
        return rng.choice([
            f"change my itinerary in {city} to reduce travel time",
            f"update my {city} itinerary and rearrange the days",
            f"modify my plan in {city} to include more rest time",
        ])
    if intent == "info_accommodation":
        return rng.choice([
            f"tell me about accommodation options in {city}",
            f"recommend good areas to stay in {city}",
            f"what are some hotels or stays in {city}",
        ])
    if intent == "info_transport":
        return rng.choice([
            f"explain transport options from {origin} to {dest}",
            f"how can I travel from {origin} to {dest}",
            f"tell me the best way to go from {origin} to {dest}",
        ])
    if intent == "info_visa_policy":
        return rng.choice([
            "explain Sri Lanka tourist visa requirements",
            "tell me the visa policy for Sri Lanka",
            "what are the visa rules for visiting Sri Lanka",
        ])

    # --- Booking ---
    if intent == "check_availability":
        return rng.choice([
            f"check hotel availability in {city} for {t}",
            f"are there hotels available in {city} {t}",
            f"find available stays in {city} {t}",
        ])
    if intent == "book_hotel":
        return rng.choice([
            f"book a hotel in {city} for {days} nights",
            f"help me reserve a hotel in {city}",
            f"make a hotel booking in {city}",
        ])
    if intent == "modify_booking":
        return rng.choice([
            f"change my hotel booking in {city}",
            f"modify my reservation in {city}",
            f"update my booking dates for {city}",
        ])
    if intent == "cancel_booking":
        return rng.choice([
            f"cancel my hotel booking in {city}",
            f"help me cancel my reservation in {city}",
            f"I want to cancel my booking for {city}",
        ])

    # --- Preferences / explain / facts / restaurants ---
    if intent == "update_preferences":
        return rng.choice([
            "update my preferences to prefer nature and low crowds",
            "set my preferences for budget travel and local food",
            "change my preferences to family-friendly places",
        ])
    if intent == "explanation_request":
        return rng.choice([
            "explain why you chose those options",
            "can you explain your reasoning",
            "why is that the best choice",
        ])
    if intent == "generic_fact_query":
        return rng.choice([
            f"give me a quick overview of {city}",
            f"what is {city} known for",
            f"tell me basic facts about {city}",
        ])
    if intent == "recommend_restaurants":
        return rng.choice([
            f"recommend good restaurants in {city}",
            f"suggest places to eat in {city}",
            f"list the best food spots in {city}",
        ])

    # Typically excluded, but keep safe fallback:
    if intent == "smalltalk":
        return rng.choice(["hi", "hello", "hey there"])
    if intent == "out_of_scope":
        return rng.choice(["do my homework", "tell me something unrelated"])

    return f"help me with {intent} in {city}"

def make_multi_prompt(rng: random.Random, intents: List[str]) -> str:
    city = rng.choice(CITIES)
    origin = rng.choice(CITIES)
    dest = rng.choice([c for c in CITIES if c != origin])

    connector = rng.choice(CONNECTORS)

    chunks = [chunk_for_intent(rng, it, city, origin, dest) for it in intents]

    # Join 2 or 3 intents naturally
    if len(chunks) == 2:
        a, b = chunks
        styles = [
            "{a} {connector} {b}.",
            "Can you {a}, {connector} {b}?",
            "I’m planning a trip. {a}. {Connector} {b}.",
            "{a}. {Connector} {b}.",
        ]
        tpl = rng.choice(styles)
        return normalize_spaces(tpl.format(a=a, b=b, connector=connector, Connector=cap_first(connector)))

    if len(chunks) == 3:
        a, b, c = chunks
        styles = [
            "{a} {connector} {b} {connector} {c}.",
            "Can you {a}, {connector} {b}, {connector} {c}?",
            "{a}. {Connector} {b}. {Connector} {c}.",
        ]
        tpl = rng.choice(styles)
        return normalize_spaces(tpl.format(a=a, b=b, c=c, connector=connector, Connector=cap_first(connector)))

    return normalize_spaces(" ".join(chunks))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Output CSV path (NEW rows only)")
    ap.add_argument("--start-id", type=int, default=5270)
    ap.add_argument("--seed", type=int, default=42)

    # How many rows per 2-intent pair
    ap.add_argument("--n-per-pair", type=int, default=20)

    # How many total triple-intent rows to generate (random triples)
    ap.add_argument("--include-triples", type=int, default=0)

    # Exclude these intents from multi-intent generation
    ap.add_argument("--exclude", nargs="*", default=list(DEFAULT_EXCLUDE_FROM_MULTI))

    args = ap.parse_args()

    rng = random.Random(args.seed)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Build intent list for multi-intents
    excluded = set(args.exclude or [])
    intents = [x for x in INTENT_LABELS if x not in excluded]

    rows = []
    seen_text = set()
    cur_id = args.start_id

    # Generate all unordered 2-intent pairs
    pairs: List[Tuple[str, str]] = []
    for i in range(len(intents)):
        for j in range(i + 1, len(intents)):
            pairs.append((intents[i], intents[j]))

    rng.shuffle(pairs)

    for a, b in pairs:
        for _ in range(args.n_per_pair):
            text = make_multi_prompt(rng, [a, b])
            if text in seen_text:
                continue
            seen_text.add(text)

            labels = f"{a};{b}"
            primary = rng.choice([a, b])  # balanced
            rows.append({
                "id": cur_id,
                "text": text,
                "intent": primary,
                "split": "train",
                "labels": labels,
                "num_labels": 2
            })
            cur_id += 1

    # Optional: generate some triple-intent rows (random triples)
    if args.include_triples > 0 and len(intents) >= 3:
        for _ in range(args.include_triples):
            triple = rng.sample(intents, 3)
            text = make_multi_prompt(rng, triple)
            if text in seen_text:
                continue
            seen_text.add(text)

            labels = ";".join(triple)
            primary = rng.choice(triple)
            rows.append({
                "id": cur_id,
                "text": text,
                "intent": primary,
                "split": "train",
                "labels": labels,
                "num_labels": 3
            })
            cur_id += 1

    df = pd.DataFrame(rows, columns=["id","text","intent","split","labels","num_labels"])
    df.to_csv(out_path, index=False)

    print("Generated NEW rows:", len(df))
    if len(df) > 0:
        print("New id range:", int(df["id"].min()), "->", int(df["id"].max()))
    print("Wrote:", str(out_path))
    print("\nSample:")
    print(df.head(10).to_string(index=False))

if __name__ == "__main__":
    main()