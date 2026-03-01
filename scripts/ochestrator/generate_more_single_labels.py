import random
import csv
from pathlib import Path

# -----------------
# CONFIG
# -----------------
OUT_PATH = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/single_intents_more.csv")

START_ID = 9692        # <-- change this to where you want to start
RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# Goal: add ~1800 single-intent rows total (to push single% up)
# Adjust counts if you want more/less.
TARGET_NEW = {
    "plan_itinerary": 120,
    "recommend_pois": 90,
    "generic_fact_query": 90,
    "recommend_restaurants": 90,
    "info_attraction": 90,
    "info_transport": 90,
    "forecast_price": 90,
    "forecast_sustainability": 90,
    "info_accommodation": 90,
    "book_hotel": 90,
    "forecast_weather": 90,
    "check_availability": 90,
    "info_visa_policy": 80,
    "modify_itinerary": 80,
    "update_preferences": 80,
    "crowd_forecast": 90,
    "cancel_booking": 60,
    "explanation_request": 60,
    "modify_booking": 60,
    "info_event_activity": 90,
    "smalltalk": 120,
    "out_of_scope": 120,
}

# Split ratio
SPLIT_WEIGHTS = {"train": 0.80, "val": 0.10, "test": 0.10}

# -----------------
# DATA BANKS
# -----------------
CITIES = [
    "Colombo","Kandy","Galle","Ella","Sigiriya","Nuwara Eliya","Matara","Jaffna",
    "Anuradhapura","Polonnaruwa","Trincomalee","Batticaloa","Negombo","Haputale",
    "Mirissa","Unawatuna","Hikkaduwa","Arugam Bay","Dambulla","Bentota"
]

ATTRACTIONS = [
    "Temple of the Tooth","Sigiriya Rock Fortress","Galle Fort","Dambulla Cave Temple",
    "Nine Arches Bridge","Yala National Park","Udawalawe National Park",
    "Horton Plains","Adam’s Peak","Pinnawala Elephant Orphanage"
]

HOTEL_AREAS = ["Kandy", "Colombo", "Ella", "Galle", "Nuwara Eliya", "Negombo"]
CUISINES = ["Sri Lankan", "seafood", "veg", "halal", "Chinese", "Indian", "Italian"]
BUDGETS = ["low budget", "mid-range", "luxury"]
TRAVELERS = ["solo traveler", "couple", "family", "elderly parents", "group of friends"]
TRANSPORT_MODES = ["bus", "train", "tuk-tuk", "taxi", "private car"]

EVENT_TYPES = ["cultural show", "music festival", "food festival", "night market", "temple ceremony", "art exhibition"]
TIME_HINTS = ["today", "tomorrow", "this weekend", "next weekend", "tonight"]

# -----------------
# HELPERS
# -----------------
def pick_split() -> str:
    splits = list(SPLIT_WEIGHTS.keys())
    weights = list(SPLIT_WEIGHTS.values())
    return random.choices(splits, weights=weights, k=1)[0]

def norm_key(text: str) -> str:
    return " ".join(text.lower().split())

def make_text(intent: str) -> str:
    city = random.choice(CITIES)
    city2 = random.choice([c for c in CITIES if c != city])
    attr = random.choice(ATTRACTIONS)
    area = random.choice(HOTEL_AREAS)
    cuisine = random.choice(CUISINES)
    budget = random.choice(BUDGETS)
    traveler = random.choice(TRAVELERS)
    mode = random.choice(TRANSPORT_MODES)
    days = random.randint(2, 7)

    ev_type = random.choice(EVENT_TYPES)
    when = random.choice(TIME_HINTS)

    templates = {
        "plan_itinerary": [
            f"Plan a {days}-day trip to {city} for a {traveler} with a {budget}.",
            f"Create a {days}-day itinerary covering {city} and {city2} for a {traveler}.",
            f"I need a {days}-day eco friendly itinerary in {city} next month.",
            f"Can you design a {days}-day Sri Lanka trip starting in {city} for a {traveler}?",
        ],
        "recommend_pois": [
            f"Recommend places to visit in {city}.",
            f"What are the best tourist spots in {city}?",
            f"Suggest attractions I should see in {city}.",
        ],
        "generic_fact_query": [
            f"Tell me about {attr}.",
            f"What is special about {attr}?",
            f"Give me a short description of {attr}.",
        ],
        "recommend_restaurants": [
            f"Recommend {cuisine} restaurants in {city}.",
            f"Best places to eat in {city} for {cuisine} food.",
            f"Suggest good {budget} restaurants in {city}.",
        ],
        "info_attraction": [
            f"Give details about {attr}.",
            f"How much time should I spend at {attr}?",
            f"What are the opening hours of {attr}?",
        ],
        "info_transport": [
            f"How can I travel around {city} using {mode}?",
            f"Best way to travel from Colombo to {city}.",
            f"Tell me transport options to reach {city}.",
        ],
        "forecast_price": [
            f"Estimate travel costs for a {days}-day trip to {city}.",
            f"Give a budget estimate for visiting {city}.",
            f"How expensive is it to travel in {city} for {days} days?",
        ],
        "forecast_sustainability": [
            f"Suggest eco-friendly activities in {city}.",
            f"How can I travel sustainably in {city}?",
            f"Give sustainable tourism tips for visiting {city}.",
        ],
        "info_accommodation": [
            f"Tell me about accommodation options in {area}.",
            f"Where should I stay in {area} for a {budget} trip?",
            f"Recommend areas to book hotels in {area}.",
        ],
        "book_hotel": [
            f"Book a {budget} hotel in {area} for {days} nights.",
            f"I want to book a hotel in {area} for this weekend.",
            f"Reserve a hotel room in {area} for tomorrow.",
        ],
        "forecast_weather": [
            f"What’s the weather in {city} today?",
            f"Weather forecast for {city} tomorrow.",
            f"Will it rain in {city} this weekend?",
        ],
        "check_availability": [
            f"Check hotel availability in {area} for next weekend.",
            f"Are there available hotels in {area} for {days} nights?",
            f"Check availability for a {budget} hotel in {area}.",
        ],
        "info_visa_policy": [
            "Do I need a visa to visit Sri Lanka?",
            "What are the Sri Lanka tourist visa requirements?",
            "Explain Sri Lanka visa rules for tourists.",
        ],
        "modify_itinerary": [
            f"Modify my itinerary to include {attr}.",
            f"Remove one day from my {city} itinerary.",
            f"Swap day 2 and day 3 in my {city} trip plan.",
        ],
        "update_preferences": [
            f"Update my preferences to {budget} travel.",
            f"I prefer {cuisine} food, update my preferences.",
            "Update my preferences to include nature and culture.",
        ],
        "crowd_forecast": [
            f"How crowded is {attr} today?",
            f"Crowd level forecast for {attr} this weekend.",
            f"Is {city} crowded right now?",
        ],
        "cancel_booking": [
            "Cancel my hotel booking.",
            f"Please cancel my booking in {area}.",
            "I want to cancel my reservation.",
        ],
        "explanation_request": [
            "Why did you recommend these places?",
            "Explain how you created this itinerary.",
            "Why is this route suggested?",
        ],
        "modify_booking": [
            "Change my hotel booking dates.",
            f"Modify my booking in {area} to {days} nights.",
            "Update my reservation details.",
        ],
        "info_event_activity": [
            f"What events are happening in {city} {when}?",
            f"Any {ev_type} in {city} {when}?",
            f"Things to do in {city} {when}.",
        ],
        "smalltalk": [
            "Hi!",
            "Hello!",
            "Thanks!",
            "Good morning!",
            "How are you?",
        ],
        # safe out-of-scope (no harmful requests)
        "out_of_scope": [
            "Help me solve a calculus question.",
            "Tell me about the solar system.",
            "Write a short poem about rain.",
            "Explain how cryptocurrency works.",
        ],
    }

    return random.choice(templates[intent])

# -----------------
# GENERATE
# -----------------
rows = []
seen = set()
cur_id = START_ID

for intent, n in TARGET_NEW.items():
    created = 0
    guard = 0
    while created < n and guard < n * 60:
        guard += 1
        text = make_text(intent)
        key = norm_key(text)
        if key in seen:
            continue
        seen.add(key)

        split = pick_split()
        rows.append({
            "id": cur_id,
            "text": text,
            "intent": intent,
            "split": split,
            "labels": intent,
            "num_labels": 1,
        })
        cur_id += 1
        created += 1

    print(f"{intent}: generated {created}/{n}")

# -----------------
# SAVE
# -----------------
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["id","text","intent","split","labels","num_labels"])
    writer.writeheader()
    writer.writerows(rows)

print("\nSaved:", OUT_PATH)
print("Total generated:", len(rows))
print("ID range:", START_ID, "->", cur_id - 1)