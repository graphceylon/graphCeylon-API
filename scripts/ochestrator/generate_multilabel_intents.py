# generate_multilabel_intents.py
# Creates synthetic multi-intent training rows for your intents_multilabel.csv
# Focus: weak pairs like recommend_pois+forecast_weather, info_attraction+forecast_weather,
# plus optional triple-intent recommend_pois+forecast_weather+plan_itinerary.
#
# Usage:
#   python generate_multilabel_intents.py \
#     --csv /Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/intents_multilabel.csv \
#     --out /Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/intents_multilabel_aug.csv \
#     --start-id 5270 \
#     --n-rp-fw 150 \
#     --n-ia-fw 80 \
#     --n-rp-fw-pi 50 \
#     --seed 42
#
# Notes:
# - Does NOT call any LLM. Pure template + variation generation.
# - Ensures unique IDs, and will bump start-id if it clashes with existing max id.
# - Adds diverse phrasing, different date/period expressions, and optional day counts.

import argparse
import random
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import pandas as pd


CITIES = [
    "Kandy", "Colombo", "Galle", "Ella", "Nuwara Eliya", "Sigiriya",
    "Matara", "Jaffna", "Negombo", "Trincomalee", "Mirissa", "Bentota",
    "Anuradhapura", "Polonnaruwa", "Haputale", "Badulla", "Arugam Bay",
]

TIME_PHRASES = [
    "today", "tomorrow", "this weekend", "next 3 days", "next 5 days",
    "for the next few days", "for this week", "for the next week",
    "this month", "in March", "in April", "during my trip",
]

ATTRACTION_WORDS = [
    "top attractions", "must-see places", "best places to visit",
    "things to do", "popular spots", "main sights", "tourist attractions",
    "places to explore", "best viewpoints and sites", "recommended places",
]

WEATHER_WORDS = [
    "weather", "forecast", "weather forecast", "rain chance", "temperature forecast",
    "is it rainy", "is it sunny", "will it rain", "how’s the weather",
]

CONNECTORS = [
    "and", "plus", "as well as", "along with", "also", "together with",
]

REQUEST_STYLES = [
    "Can you {ask_pois} in {city}, {connector} tell me the {ask_weather} {time}?",
    "What are the {pois_word} in {city}, {connector} what’s the {ask_weather} {time}?",
    "Suggest {pois_word} around {city} {connector} give me the {ask_weather} {time}.",
    "I’m visiting {city}. {ask_pois_cap}. {connector_cap} {ask_weather_cap} {time}.",
    "Need {pois_word} for {city} {connector} {ask_weather} {time}.",
]

# More “info”-style attraction prompts (slightly different tone)
INFO_STYLES = [
    "Tell me about {pois_word} in {city}, {connector} the {ask_weather} {time}.",
    "Give details on {pois_word} in {city} {connector} share the {ask_weather} {time}.",
    "Explain {pois_word} in {city} {connector} what’s the {ask_weather} {time}?",
    "In {city}, what are {pois_word}? {connector_cap} what’s the {ask_weather} {time}?",
]

# Triple intent: recommend_pois + forecast_weather + plan_itinerary
TRIPLE_STYLES = [
    "Plan a {days}-day trip to {city} and include {pois_word} {connector} the {ask_weather} {time}.",
    "Create a {days}-day itinerary for {city} {connector} list {pois_word} {connector} share the {ask_weather} {time}.",
    "I need a {days}-day itinerary for {city}. Include {pois_word}, {connector} tell me the {ask_weather} {time}.",
    "Build a {days}-day plan for {city} with {pois_word} {connector} what’s the {ask_weather} {time}?",
]


def cap_first(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def sample_days(rng: random.Random) -> int:
    # Common itinerary lengths
    return rng.choice([2, 3, 4, 5])


def make_prompt(
    rng: random.Random,
    *,
    city: str,
    style_pool: List[str],
    allow_days: bool = False,
) -> str:
    pois_word = rng.choice(ATTRACTION_WORDS)
    ask_weather = rng.choice(WEATHER_WORDS)
    connector = rng.choice(CONNECTORS)
    time = rng.choice(TIME_PHRASES)

    ask_pois = rng.choice([
        "recommend " + pois_word,
        "suggest " + pois_word,
        "list " + pois_word,
        "share " + pois_word,
    ])

    # Capitalized variants for some templates
    ask_pois_cap = cap_first(ask_pois)
    ask_weather_cap = cap_first(ask_weather)
    connector_cap = cap_first(connector)

    tpl = rng.choice(style_pool)
    data = dict(
        city=city,
        pois_word=pois_word,
        ask_weather=ask_weather,
        ask_weather_cap=ask_weather_cap,
        connector=connector,
        connector_cap=connector_cap,
        time=time,
        ask_pois=ask_pois,
        ask_pois_cap=ask_pois_cap,
    )

    if allow_days:
        data["days"] = sample_days(rng)

    text = tpl.format(**data)
    return normalize_spaces(text)


def build_rows(
    rng: random.Random,
    *,
    start_id: int,
    n: int,
    label_str: str,
    primary_intent: str,
    split: str = "train",
    style_pool: Optional[List[str]] = None,
    allow_days: bool = False,
) -> List[Dict]:
    style_pool = style_pool or REQUEST_STYLES
    rows: List[Dict] = []
    for i in range(n):
        city = rng.choice(CITIES)
        text = make_prompt(rng, city=city, style_pool=style_pool, allow_days=allow_days)
        rows.append(
            {
                "id": start_id + i,
                "text": text,
                "intent": primary_intent,
                "split": split,
                "labels": label_str,
                "num_labels": len([x for x in label_str.split(";") if x.strip()]),
            }
        )
    return rows


def ensure_start_id(csv_df: pd.DataFrame, requested_start: int) -> int:
    if "id" not in csv_df.columns:
        return requested_start
    try:
        max_id = int(pd.to_numeric(csv_df["id"], errors="coerce").max())
        if pd.isna(max_id):
            return requested_start
        if requested_start <= max_id:
            return max_id + 1
    except Exception:
        pass
    return requested_start


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to existing intents_multilabel.csv")
    ap.add_argument("--out", required=True, help="Output CSV path (augmented)")
    ap.add_argument("--start-id", type=int, default=5270)
    ap.add_argument("--seed", type=int, default=42)

    ap.add_argument("--n-rp-fw", type=int, default=150, help="recommend_pois + forecast_weather")
    ap.add_argument("--n-ia-fw", type=int, default=80, help="info_attraction + forecast_weather")
    ap.add_argument("--n-rp-fw-pi", type=int, default=50, help="recommend_pois + forecast_weather + plan_itinerary")

    args = ap.parse_args()

    rng = random.Random(args.seed)

    csv_path = Path(args.csv)
    out_path = Path(args.out)

    df = pd.read_csv(csv_path)

    start_id = ensure_start_id(df, args.start_id)
    cur_id = start_id

    new_rows: List[Dict] = []

    # A) recommend_pois + forecast_weather
    if args.n_rp_fw > 0:
        rows = build_rows(
            rng,
            start_id=cur_id,
            n=args.n_rp_fw,
            label_str="recommend_pois;forecast_weather",
            primary_intent="recommend_pois",
            style_pool=REQUEST_STYLES,
            allow_days=False,
        )
        new_rows.extend(rows)
        cur_id += len(rows)

    # B) info_attraction + forecast_weather
    if args.n_ia_fw > 0:
        rows = build_rows(
            rng,
            start_id=cur_id,
            n=args.n_ia_fw,
            label_str="info_attraction;forecast_weather",
            primary_intent="info_attraction",
            style_pool=INFO_STYLES,
            allow_days=False,
        )
        new_rows.extend(rows)
        cur_id += len(rows)

    # C) recommend_pois + forecast_weather + plan_itinerary
    if args.n_rp_fw_pi > 0:
        rows = build_rows(
            rng,
            start_id=cur_id,
            n=args.n_rp_fw_pi,
            label_str="recommend_pois;forecast_weather;plan_itinerary",
            primary_intent="plan_itinerary",  # optional: keep plan_itinerary as primary for these
            style_pool=TRIPLE_STYLES,
            allow_days=True,
        )
        new_rows.extend(rows)
        cur_id += len(rows)

    aug_df = pd.DataFrame(new_rows)

    # Quick sanity: avoid exact duplicate texts (rare, but possible)
    aug_df = aug_df.drop_duplicates(subset=["text"])

    df_out = pd.concat([df, aug_df], ignore_index=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(out_path, index=False)

    print("Loaded rows:", len(df))
    print("Generated rows (after de-dup):", len(aug_df))
    print("Wrote:", str(out_path))
    if len(aug_df) > 0:
        print("New id range:", int(aug_df["id"].min()), "->", int(aug_df["id"].max()))
        print("\nSample rows:")
        print(aug_df.head(5).to_string(index=False))


if __name__ == "__main__":
    main()