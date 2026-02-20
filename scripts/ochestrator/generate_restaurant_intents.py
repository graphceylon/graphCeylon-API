import random
import csv

# ---------- CONFIG ----------
START_ID = 5120
N = 150
OUT_FILE = "synthetic_recommend_restaurants_150.csv"
SPLIT = "train"
INTENT = "recommend_restaurants"
WEIGHT = 1
SEED = 42
# ---------------------------

random.seed(SEED)

cities = [
    "Colombo", "Colombo Fort", "Kandy", "Galle", "Negombo", "Ella", "Nuwara Eliya",
    "Sigiriya", "Hikkaduwa", "Mirissa", "Unawatuna", "Bentota", "Jaffna", "Trincomalee",
    "Arugam Bay", "Anuradhapura", "Polonnaruwa", "Matara", "Haputale", "Badulla",
    "Dambulla", "Kalutara", "Weligama", "Tangalle", "Batticaloa", "Kurunegala"
]

cuisines = [
    "Sri Lankan", "seafood", "Italian", "Indian", "Chinese", "Japanese", "Thai",
    "Middle Eastern", "kottu", "rice and curry", "street food", "burgers", "pizza",
    "vegetarian", "vegan", "halal"
]

preferences = [
    "cheap", "budget-friendly", "mid-range", "fine dining", "family-friendly",
    "romantic", "quiet", "near the beach", "near the station", "near the city center",
    "with good reviews", "with AC", "outdoor seating", "nice view", "open late"
]

dietary = [
    "vegetarian options", "vegan options", "halal options", "gluten-free options",
    "no spicy food", "spicy food", "kid-friendly menu"
]

times = ["breakfast", "brunch", "lunch", "dinner", "late night"]

question_templates = [
    "Recommend some {pref} {cuisine} restaurants in {city}.",
    "Where can I find {cuisine} food in {city}?",
    "Best places to eat {cuisine} in {city}?",
    "Suggest {pref} food places in {city}.",
    "Any good {cuisine} spots near {city}?",
    "Can you recommend restaurants in {city} for {time}?",
    "Top {pref} restaurants in {city} for {diet}?",
    "Good cafes or restaurants in {city} with {pref}?",
    "Where should I eat in {city} if I want {cuisine}?",
    "Find me a {pref} place to eat in {city}.",
    "Any restaurants in {city} that have {diet}?",
    "Best seafood places in {city}?",
    "Suggest a nice restaurant in {city} for {time}.",
    "Recommend street food places in {city}.",
    "What are some must-try food places in {city}?",
    "Where can I get a good {cuisine} meal in {city}?",
    "Any {pref} restaurants in {city} that are open late?",
    "Suggest a place to eat near {city} station.",
    "Recommend a restaurant in {city} with {pref} and {diet}.",
    "Can you give me 3 restaurant suggestions in {city}?"
]

def generate_unique_examples(n: int):
    seen = set()
    examples = []
    tries = 0
    max_tries = n * 30

    while len(examples) < n and tries < max_tries:
        tries += 1
        city = random.choice(cities)
        cuisine = random.choice(cuisines)
        pref = random.choice(preferences)
        diet = random.choice(dietary)
        time = random.choice(times)
        template = random.choice(question_templates)

        text = template.format(city=city, cuisine=cuisine, pref=pref, diet=diet, time=time)

        # light cleanup for awkward combos
        text = text.replace("vegetarian vegetarian", "vegetarian").replace("vegan vegan", "vegan")

        key = text.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        examples.append(text)

    return examples

examples = generate_unique_examples(N)

# Write CSV
with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    # Header optional: comment out if your dataset has no header
    writer.writerow(["id", "text", "intent", "split", "label", "weight"])

    cur_id = START_ID
    for text in examples:
        writer.writerow([cur_id, text, INTENT, SPLIT, INTENT, WEIGHT])
        cur_id += 1

print(f"✅ Wrote {len(examples)} rows to {OUT_FILE} (IDs {START_ID}..{START_ID+len(examples)-1})")
