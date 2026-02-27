import random
import re
import pandas as pd

# -----------------
# CONFIG
# -----------------
CSV_PATH = "/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/intents_multilabel copy.csv"
OUT_PATH = "/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/intents_multilabel_aug_single.csv"

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# ✅ Add new intent here
INTENT_LABELS = [
    "plan_itinerary","recommend_pois","modify_itinerary",
    "crowd_forecast","forecast_weather","forecast_price","forecast_sustainability",
    "info_attraction","info_accommodation","info_transport","info_visa_policy",
    "check_availability","book_hotel","modify_booking","cancel_booking",
    "update_preferences","explanation_request",
    "generic_fact_query","recommend_restaurants",
    "info_event_activity",      # ✅ NEW
    "smalltalk","out_of_scope"
]
allowed = set(INTENT_LABELS)

# How many NEW single-intent rows to generate per intent
TARGET_NEW = {
    "plan_itinerary": 80,
    "recommend_pois": 60,
    "generic_fact_query": 60,
    "recommend_restaurants": 60,
    "info_attraction": 60,
    "info_transport": 60,
    "forecast_price": 60,
    "forecast_sustainability": 60,
    "info_accommodation": 60,
    "book_hotel": 60,
    "forecast_weather": 60,
    "check_availability": 60,
    "info_visa_policy": 50,
    "modify_itinerary": 50,
    "update_preferences": 50,
    "crowd_forecast": 60,
    "cancel_booking": 40,
    "explanation_request": 40,
    "modify_booking": 40,
    "info_event_activity": 80,   # ✅ NEW
    "out_of_scope": 80,
    "smalltalk": 80,
}

# -----------------
# VOCAB / LOOKUPS
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
BUDGETS = ["budget", "mid-range", "luxury"]
TRANSPORT_MODES = ["bus", "train", "tuk-tuk", "taxi", "private car"]

EVENT_TYPES = [
    "cultural show", "music festival", "food festival", "night market",
    "temple ceremony", "beach party", "street parade", "art exhibition"
]
TIME_HINTS = ["today", "tomorrow", "this weekend", "next weekend", "tonight"]

# -----------------
# LABEL PARSING + 0-LABEL FIX
# -----------------
def normalize(s: str) -> str:
    return " ".join(str(s).lower().strip().split())

def parse_labels(label_str) -> list:
    """Parse label string into list of allowed labels."""
    if pd.isna(label_str):
        return []
    s = str(label_str).strip()
    if not s:
        return []
    parts = re.split(r"[;|,]+", s)
    labs = [p.strip() for p in parts if p.strip()]
    labs = [l for l in labs if l in allowed]
    return labs

def fix_zero_label_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure every row has at least 1 valid label.
    If a row has 0 valid labels -> map to out_of_scope.
    """
    df["label_list"] = df["labels"].apply(parse_labels)

    zero_mask = df["label_list"].apply(len) == 0
    zero_count = int(zero_mask.sum())
    if zero_count > 0:
        print(f"⚠️ Found {zero_count} rows with 0 valid labels. Mapping them to 'out_of_scope'.")
        df.loc[zero_mask, "labels"] = "out_of_scope"
        df.loc[zero_mask, "intent"] = "out_of_scope"
        df.loc[zero_mask, "label_list"] = [["out_of_scope"]] * zero_count

    return df

# -----------------
# TEXT GENERATION
# -----------------
def make_text(intent: str) -> str:
    city = random.choice(CITIES)
    attr = random.choice(ATTRACTIONS)
    area = random.choice(HOTEL_AREAS)
    cuisine = random.choice(CUISINES)
    budget = random.choice(BUDGETS)
    mode = random.choice(TRANSPORT_MODES)

    ev_type = random.choice(EVENT_TYPES)
    when = random.choice(TIME_HINTS)

    templates = {
        "plan_itinerary": [
            f"Plan a 3 day itinerary to {city}.",
            f"Create a 2-day trip plan for {city}.",
            f"Build a 5-day travel itinerary in {city}.",
            f"Make me a weekend itinerary for {city}.",
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
            f"What are the opening hours for {attr}?",
        ],
        "info_transport": [
            f"How can I travel around {city} using {mode}?",
            f"Best way to travel from Colombo to {city}.",
            f"Tell me transport options to reach {city}.",
        ],
        "forecast_price": [
            f"Estimate travel costs for a 3 day trip to {city}.",
            f"How expensive is it to visit {city}?",
            f"Give a budget estimate for visiting {city}.",
        ],
        "forecast_sustainability": [
            f"Suggest eco-friendly activities in {city}.",
            f"How can I travel sustainably in {city}?",
            f"Give sustainable tourism tips for visiting {city}.",
        ],
        "info_accommodation": [
            f"Tell me about accommodation options in {area}.",
            f"Where should I stay in {area}?",
            f"Recommend areas to book hotels in {area}.",
        ],
        "book_hotel": [
            f"Book a {budget} hotel in {area} for 2 nights.",
            f"I want to book a hotel in {area}.",
            f"Reserve a hotel room in {area} for tomorrow.",
        ],
        "forecast_weather": [
            f"What’s the weather in {city} today?",
            f"Weather forecast for {city} tomorrow.",
            f"Will it rain in {city} this weekend?",
        ],
        "check_availability": [
            f"Check hotel availability in {area} for next weekend.",
            f"Are there available hotels in {area} for 2 nights?",
            f"Check availability for a {budget} hotel in {area}.",
        ],
        "info_visa_policy": [
            "Do I need a visa to visit Sri Lanka?",
            "What are the Sri Lanka visa requirements?",
            "Explain Sri Lanka tourist visa rules.",
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
            "Explain how you built this itinerary.",
            "Why is this route suggested?",
        ],
        "modify_booking": [
            "Change my hotel booking dates.",
            f"Modify my booking in {area} to 3 nights.",
            "Update my reservation details.",
        ],
        # ✅ NEW: event/activity intent
        "info_event_activity": [
            f"What events are happening in {city} {when}?",
            f"Any {ev_type} in {city} {when}?",
            f"Things to do in {city} {when}.",
            f"Is there any festival in {city} {when}?",
        ],
        # ✅ safer out-of-scope (no harmful instructions)
        "out_of_scope": [
            "Help me with my math homework about calculus.",
            "Can you write a love song for me?",
            "Tell me the latest cricket scores.",
            "Explain how cryptocurrency works.",
        ],
        "smalltalk": [
            "Hi!",
            "How are you?",
            "Thank you!",
            "Good morning!",
        ],
    }

    return random.choice(templates[intent])

# -----------------
# LOAD + FIX + DEDUP
# -----------------
df = pd.read_csv(CSV_PATH)

for col in ["text", "labels", "intent"]:
    if col not in df.columns:
        raise ValueError(f"Missing required column: {col}")

df = fix_zero_label_rows(df)

df["text_norm"] = df["text"].apply(normalize)
existing = set(df["text_norm"].tolist())

# -----------------
# GENERATE NEW ROWS
# -----------------
new_rows = []
next_id = int(df["id"].max()) + 1 if "id" in df.columns else 100000

for intent, n_new in TARGET_NEW.items():
    created = 0
    guard = 0
    while created < n_new and guard < n_new * 40:
        guard += 1
        text = make_text(intent)
        key = normalize(text)
        if key in existing:
            continue
        existing.add(key)
        new_rows.append({
            "id": next_id,
            "text": text,
            "labels": intent,     # single-intent label
            "intent": intent,
            "source": "aug_single"
        })
        next_id += 1
        created += 1

    print(f"{intent}: generated {created}/{n_new}")

aug_df = pd.DataFrame(new_rows)

# -----------------
# MERGE + SAVE
# -----------------
out = pd.concat([df.drop(columns=["text_norm"]), aug_df], ignore_index=True)
out.to_csv(OUT_PATH, index=False)

print("\nSaved:", OUT_PATH)
print("Original:", len(df), "Augmented:", len(out), "Added:", len(aug_df))