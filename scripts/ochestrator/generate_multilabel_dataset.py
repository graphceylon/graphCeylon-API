from __future__ import annotations
import csv, random
from pathlib import Path
from typing import List, Dict

random.seed(42)

START_ID = 2827

CITIES = ["Kandy", "Ella", "Nuwara Eliya", "Galle", "Sigiriya", "Colombo"]
DAYS = [2, 3, 4, 5]

JOINERS = [
    "and also",
    "and",
    "plus",
    "along with",
    "as well as",
]

TEMPLATES = [
    {
        "labels": ["plan_itinerary", "crowd_forecast"],
        "patterns": [
            "Plan a {days}-day itinerary in {city} {j} show me the crowd forecast for each day",
            "Build a {days}-day trip plan to {city} {j} include daily crowd levels",
            "Create an itinerary for {city} for {days} days {j} provide crowd prediction",
        ],
    },
    {
        "labels": ["plan_itinerary", "forecast_weather"],
        "patterns": [
            "Plan a {days}-day itinerary in {city} {j} show the weather forecast for each day",
            "Make a travel plan for {city} for {days} days {j} include rain and temperature forecast",
        ],
    },
    {
        "labels": ["recommend_pois", "crowd_forecast"],
        "patterns": [
            "Recommend places to visit in {city} {j} show the crowd forecast",
            "Suggest attractions in {city} {j} include expected crowd levels",
        ],
    },
]

def render(pattern: str):
    city = random.choice(CITIES)
    days = random.choice(DAYS)
    j = random.choice(JOINERS)
    return pattern.format(city=city, days=days, j=j)

def main():
    out_path = Path("data/orchestrator/raw/intent_multilabel_synth.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    idx = START_ID

    for t in TEMPLATES:
        for _ in range(300):
            text = render(random.choice(t["patterns"]))
            labels = "|".join(t["labels"])
            rows.append({
                "id": idx,
                "text": text,
                "intent": t["labels"][0],
                "split": "train",
                "labels": labels,
                "num_labels": len(t["labels"])
            })
            idx += 1

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id","text","intent","split","labels","num_labels"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} rows starting from ID {START_ID}")
    print(f"Saved to: {out_path}")

if __name__ == "__main__":
    main()
