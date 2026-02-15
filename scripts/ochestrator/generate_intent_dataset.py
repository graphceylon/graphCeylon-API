import random
import csv
from pathlib import Path

# -----------------------------
# Config
# -----------------------------
SEED = 42
OUT_PATH = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/script_generated_intents.csv")

# Set how many NEW rows you want per intent (edit these numbers)
COUNTS = {
    "generic_fact_query": 120,
    "info_attraction": 120,
    "forecast_price": 100,
    "smalltalk": 90,
    "cancel_booking": 70,
    "check_availability": 70,
    "book_hotel": 70,
    "modify_booking": 70,
    "modify_itinerary": 70,
    "forecast_weather": 65,
    "forecast_sustainability": 55,
    "info_accommodation": 45,
    "out_of_scope": 40,

    # optional / later
    "info_transport": 30,
    "info_visa_policy": 40,
    "update_preferences": 40,
    "explanation_request": 70,
}

# Split ratio for generated samples
SPLIT_WEIGHTS = [("train", 0.80), ("val", 0.10), ("test", 0.10)]

random.seed(SEED)

# -----------------------------
# Helper utilities
# -----------------------------
def pick_split():
    r = random.random()
    cum = 0.0
    for name, w in SPLIT_WEIGHTS:
        cum += w
        if r <= cum:
            return name
    return SPLIT_WEIGHTS[-1][0]

def uniq_generate(gen_func, n, seen, max_tries=500000):
    """Generate n unique texts using gen_func."""
    out = []
    tries = 0
    while len(out) < n and tries < max_tries:
        tries += 1
        t = gen_func().strip()
        # Normalize a bit for duplicate checking
        key = " ".join(t.lower().split())
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    if len(out) < n:
        print(f"[WARN] Only generated {len(out)}/{n} unique samples for {gen_func.__name__}")
    return out

# -----------------------------
# Phrase banks
# -----------------------------
CITIES = [
    "Colombo", "Kandy", "Galle", "Ella", "Nuwara Eliya", "Sigiriya", "Mirissa",
    "Hikkaduwa", "Arugam Bay", "Trincomalee", "Jaffna", "Anuradhapura", "Polonnaruwa",
    "Bentota", "Negombo", "Haputale", "Badulla", "Matara", "Kalutara"
]

ATTRACTIONS = [
    "Sigiriya Rock Fortress", "Temple of the Tooth", "Galle Fort", "Nine Arches Bridge",
    "Yala National Park", "Udawalawe National Park", "Horton Plains", "Adam's Peak",
    "Pinnawala Elephant Orphanage", "Dambulla Cave Temple", "Royal Botanic Gardens Peradeniya",
    "Mirissa Whale Watching", "Nilaveli Beach", "Ravana Falls"
]

BUDGETS = ["low budget", "mid-range", "luxury", "under 30,000 LKR per day", "under 50,000 LKR per day"]
TRAVELERS = ["solo traveler", "family", "group of friends", "couple", "elderly parents", "family with kids"]
DURATIONS = ["2-day", "3-day", "4-day", "5-day", "7-day"]
TIME_HINTS = ["next week", "next month", "this weekend", "in March", "in April", "during school holidays"]
PREFERENCES = ["eco friendly", "family-friendly", "vegetarian-friendly", "quiet places", "beach + mountains", "cultural + nature"]

HOTEL_TYPES = ["boutique hotel", "resort", "villa", "guesthouse", "hostel", "homestay"]
ROOM_TYPES = ["single room", "double room", "family room", "suite"]
AMENITIES = ["pool", "wifi", "breakfast", "AC", "parking", "gym", "spa"]
TRANSPORT = ["train", "bus", "private car", "tuk-tuk", "taxi", "domestic flight"]

# -----------------------------
# Intent template generators
# -----------------------------
def gen_plan_itinerary_like():
    # (Not used in COUNTS by default, but kept if you want to generate more)
    d = random.choice(DURATIONS)
    c1 = random.choice(CITIES)
    c2 = random.choice([c for c in CITIES if c != c1])
    traveler = random.choice(TRAVELERS)
    budget = random.choice(BUDGETS)
    pref = random.choice(PREFERENCES)
    timeh = random.choice(TIME_HINTS)
    forms = [
        f"Plan a {d} trip to {c1} for a {traveler} with a {budget}",
        f"Create a {d} itinerary covering {c1} and {c2} for {traveler}",
        f"I need a {d} {pref} itinerary in {c1} {timeh}",
        f"Design a {d} Sri Lanka trip starting in {c1} for a {traveler}",
        f"Build a {d} plan for {c1} with {pref} options and {budget}",
    ]
    return random.choice(forms)

def gen_generic_fact_query():
    h1 = random.choice(HOTEL_TYPES)
    h2 = random.choice([x for x in HOTEL_TYPES if x != h1])
    a = random.choice(AMENITIES)
    c = random.choice(CITIES)
    forms = [
        f"What’s the difference between {h1} and {h2}?",
        f"Is it better to book a {h1} or {h2} in {c}?",
        f"What does ‘half board’ mean in hotels?",
        f"Do hotels in Sri Lanka usually include {a}?",
        f"What is the best time to visit {c}?",
        f"Is {c} safe for tourists?",
        f"What should I pack for a trip to {c}?",
        f"How far is {c} from Colombo by road?",
        f"What’s the typical check-in and check-out time in hotels?",
        f"Explain what a cancellation policy usually means.",
    ]
    return random.choice(forms)

def gen_info_attraction():
    att = random.choice(ATTRACTIONS)
    c = random.choice(CITIES)
    forms = [
        f"Tell me about {att}",
        f"What are the opening hours for {att}?",
        f"How much time should I allocate for {att}?",
        f"Is {att} suitable for kids?",
        f"What is the best time of day to visit {att}?",
        f"How do I get to {att} from {c}?",
        f"Give me 5 things to do near {att}",
        f"Is {att} crowded on weekends?",
        f"Any tips for visiting {att}?",
    ]
    return random.choice(forms)

def gen_forecast_price():
    c = random.choice(CITIES)
    hotel = random.choice(HOTEL_TYPES)
    timeh = random.choice(TIME_HINTS)
    forms = [
        f"Will hotel prices in {c} go up {timeh}?",
        f"Forecast accommodation prices in {c} for {timeh}",
        f"Are {hotel} rates in {c} cheaper {timeh} or later?",
        f"Estimate the average room price in {c} for {timeh}",
        f"Is it cheaper to book {timeh} or last minute in {c}?",
        f"Predict price trends for hotels in {c} this season",
    ]
    return random.choice(forms)

def gen_smalltalk():
    forms = [
        "Hi!", "Hello", "Good morning", "Good evening",
        "How are you?", "Can you help me?", "Thanks!", "Thank you so much",
        "What can you do?", "Who are you?", "That’s helpful, nice!",
        "Ok cool", "Great", "Awesome", "Can we start?",
    ]
    # add slight variations
    extra = ["🙂", "!", "!!", ""]
    return random.choice(forms) + random.choice(extra)

def gen_cancel_booking():
    forms = [
        "I want to cancel my booking",
        "Cancel my hotel reservation please",
        "How do I cancel my booking for tomorrow?",
        "I need to cancel this reservation immediately",
        "Can you cancel the booking under my name?",
        "I booked by mistake, cancel it",
        "Cancel my room booking and confirm",
    ]
    return random.choice(forms)

def gen_check_availability():
    c = random.choice(CITIES)
    room = random.choice(ROOM_TYPES)
    timeh = random.choice(TIME_HINTS)
    forms = [
        f"Check availability for a {room} in {c} {timeh}",
        f"Are there any rooms available in {c} {timeh}?",
        f"Can you see if a {room} is available in {c}?",
        f"I need to know room availability in {c} for {timeh}",
        f"Any available hotels in {c} {timeh}?",
    ]
    return random.choice(forms)

def gen_book_hotel():
    c = random.choice(CITIES)
    room = random.choice(ROOM_TYPES)
    a = random.choice(AMENITIES)
    timeh = random.choice(TIME_HINTS)
    forms = [
        f"Book a {room} in {c} {timeh}",
        f"I want to book a hotel in {c} with {a}",
        f"Reserve a {room} in {c} for {timeh}",
        f"Can you book me a hotel in {c}?",
        f"Please book accommodation in {c} {timeh}",
    ]
    return random.choice(forms)

def gen_modify_booking():
    forms = [
        "Change my booking dates",
        "I need to update my reservation",
        "Can you modify my booking to add one more night?",
        "Change the room type in my booking",
        "Update my booking details please",
        "I want to shift my booking to next week",
        "Can you change the guest name on the reservation?",
    ]
    return random.choice(forms)

def gen_modify_itinerary():
    c = random.choice(CITIES)
    att = random.choice(ATTRACTIONS)
    forms = [
        f"Modify my itinerary to include {att}",
        f"Can you change day 2 to be in {c} instead?",
        "Remove one destination and make it more relaxed",
        "Adjust the plan to reduce travel time",
        "Swap the order of activities in my itinerary",
        "Make the itinerary more budget friendly",
        "Add more cultural places and fewer beaches",
    ]
    return random.choice(forms)

def gen_forecast_weather():
    c = random.choice(CITIES)
    timeh = random.choice(TIME_HINTS)
    forms = [
        f"What will the weather be like in {c} {timeh}?",
        f"Forecast rain chances in {c} {timeh}",
        f"Is it likely to rain in {c} {timeh}?",
        f"Predict temperature in {c} {timeh}",
        f"Will {c} be sunny {timeh}?",
    ]
    return random.choice(forms)

def gen_forecast_sustainability():
    c = random.choice(CITIES)
    timeh = random.choice(TIME_HINTS)
    forms = [
        f"Is {c} likely to be crowded {timeh}?",
        f"Forecast crowd levels in {c} {timeh}",
        f"Which places are less crowded than {c} {timeh}?",
        f"Predict sustainability risk for {c} {timeh}",
        "Suggest low-impact travel options for my trip",
        "How can I travel more sustainably in Sri Lanka?",
    ]
    return random.choice(forms)

def gen_info_accommodation():
    c = random.choice(CITIES)
    h = random.choice(HOTEL_TYPES)
    a = random.choice(AMENITIES)
    forms = [
        f"Suggest {h} options in {c}",
        f"What are good hotels in {c}?",
        f"Find accommodations in {c} with {a}",
        f"Any family-friendly hotels in {c}?",
        f"Show me budget stays in {c}",
        f"Which area in {c} is best to stay?",
    ]
    return random.choice(forms)

def gen_out_of_scope():
    forms = [
        "Can you do my math homework for me?",
        "Write a full essay for my exam",
        "Hack a website for me",
        "Generate a fake passport photo",
        "Tell me how to break into an account",
        "Can you help me cheat on a test?",
        "Make a deepfake video",
    ]
    return random.choice(forms)

def gen_info_transport():
    c1 = random.choice(CITIES)
    c2 = random.choice([c for c in CITIES if c != c1])
    mode = random.choice(TRANSPORT)
    forms = [
        f"How do I travel from {c1} to {c2}?",
        f"Is there a {mode} option from {c1} to {c2}?",
        f"What’s the best way to go from {c1} to {c2}?",
        f"How long does it take to get from {c1} to {c2}?",
        f"Is train travel between {c1} and {c2} scenic?",
    ]
    return random.choice(forms)

def gen_info_visa_policy():
    forms = [
        "Do I need a visa to visit Sri Lanka?",
        "How do I apply for a tourist visa for Sri Lanka?",
        "What documents are needed for a Sri Lanka tourist visa?",
        "Can I extend my tourist visa in Sri Lanka?",
        "What is the visa fee for Sri Lanka?",
        "Is visa on arrival available?",
    ]
    return random.choice(forms)

def gen_update_preferences():
    forms = [
        "Update my preferences to be more budget friendly",
        "Set my travel style to eco friendly",
        "I prefer vegetarian food, update my profile",
        "Change my accommodation preference to hotels only",
        "I want more nature and less nightlife",
        "Set my pace to relaxed",
        "Update my language preference to Sinhala",
    ]
    return random.choice(forms)

def gen_explanation_request():
    forms = [
        "Why did you recommend that hotel?",
        "Explain your reasoning for this itinerary",
        "How did you choose these places?",
        "What criteria did you use to rank these options?",
        "Why is this option better than the other one?",
        "Can you justify this recommendation?",
        "How did you decide the travel order?",
    ]
    return random.choice(forms)

GENS = {
    "generic_fact_query": gen_generic_fact_query,
    "info_attraction": gen_info_attraction,
    "forecast_price": gen_forecast_price,
    "smalltalk": gen_smalltalk,
    "cancel_booking": gen_cancel_booking,
    "check_availability": gen_check_availability,
    "book_hotel": gen_book_hotel,
    "modify_booking": gen_modify_booking,
    "modify_itinerary": gen_modify_itinerary,
    "forecast_weather": gen_forecast_weather,
    "forecast_sustainability": gen_forecast_sustainability,
    "info_accommodation": gen_info_accommodation,
    "out_of_scope": gen_out_of_scope,
    "info_transport": gen_info_transport,
    "info_visa_policy": gen_info_visa_policy,
    "update_preferences": gen_update_preferences,
    "explanation_request": gen_explanation_request,

    # optional
    "plan_itinerary": gen_plan_itinerary_like,
}

# -----------------------------
# Generate dataset
# -----------------------------
def build_rows(start_id=1):
    seen = set()
    rows = []
    idx = start_id

    for intent, n in COUNTS.items():
        gen = GENS[intent]
        texts = uniq_generate(gen, n, seen)

        for t in texts:
            split = pick_split()
            rows.append({
                "id": idx,
                "text": t,
                "intent": intent,
                "split": split,
                "labels": intent,
                "num_labels": 1,
            })
            idx += 1

    return rows

def write_csv(rows, path: Path):
    fieldnames = ["id", "text", "intent", "split", "labels", "num_labels"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

def main():
    rows = build_rows(start_id=4306)
    write_csv(rows, OUT_PATH)
    print(f"Saved {len(rows)} rows → {OUT_PATH.resolve()}")

if __name__ == "__main__":
    main()
