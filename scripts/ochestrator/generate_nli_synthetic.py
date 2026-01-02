import re
import random
import pandas as pd
from pathlib import Path

BASE_PATH = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/base_claims_pruned.txt")
OUT_PATH  = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/nli_synthetic.csv")

random.seed(42)

lines = [l.strip() for l in BASE_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]

# --- regex patterns ---
re_checkin = re.compile(r"^(?P<ent>.+?) has check-in time at (?P<time>.+?)\.$", re.I)
re_star    = re.compile(r"^(?P<ent>.+?) is a (?P<stars>\d)-star hotel\.$", re.I)
re_rating  = re.compile(r"^(?P<ent>.+?) has an overall rating of (?P<r>\d+(\.\d+)?)\.$", re.I)
re_locprov = re.compile(r"^(?P<place>.+?) is located in the (?P<prov>.+?) of Sri Lanka\.$", re.I)
re_nearcat = re.compile(r"^(?P<name>.+?) is a (?P<cat>.+?) near (?P<anchor>.+?)\.$", re.I)
re_address = re.compile(r"^(?P<ent>.+?) is located at (?P<addr>.+?)\.$", re.I)

CATS = [
    "Restaurant", "Family restaurant", "Seafood restaurant", "Sri Lankan restaurant",
    "Train station", "Bus station", "Point of interest"
]
TIMES = ["11:00 AM","11:30 AM","12:00 PM","1:00 PM","2:00 PM","3:00 PM","4:00 PM"]
PROVS = ["Western Province","Central Province","Southern Province","Eastern Province",
         "North Central Province","Northern Province","North Western Province","Uva Province","Sabaragamuwa Province"]

def flip_star(s):
    other = [2,3,4,5]
    other.remove(int(s))
    return str(random.choice(other))

def flip_time(t):
    t = t.strip()
    choices = [x for x in TIMES if x != t]
    return random.choice(choices) if choices else "3:00 PM"

def flip_rating(r):
    r = float(r)
    # shift rating enough to be contradictory
    candidates = [1.5,2.5,3.0,3.5,4.0,4.5,4.8,5.0]
    candidates = [c for c in candidates if abs(c - r) >= 0.5]
    return str(random.choice(candidates)) if candidates else str(max(1.0, min(5.0, r-1.0)))

def flip_province(p):
    p = p.strip()
    choices = [x for x in PROVS if x.lower() != p.lower()]
    return random.choice(choices) if choices else "Western Province"

def flip_category(c):
    c = c.strip()
    choices = [x for x in CATS if x.lower() != c.lower()]
    return random.choice(choices) if choices else "Point of interest"

def negate(sentence):
    # simple negation templates based on your patterns
    if " has check-in time at " in sentence:
        return sentence.replace(" has check-in time at ", " does not have check-in time at ")
    if " has an overall rating of " in sentence:
        return sentence.replace(" has an overall rating of ", " does not have an overall rating of ")
    if " is a " in sentence and " near " in sentence:
        return sentence.replace(" is a ", " is not a ", 1)
    if " is a " in sentence and "star hotel" in sentence:
        return sentence.replace(" is a ", " is not a ", 1)
    if " is located in the " in sentence:
        return sentence.replace(" is located in the ", " is not located in the ", 1)
    if " is located at " in sentence:
        return sentence.replace(" is located at ", " is not located at ", 1)
    return "It is not true that " + sentence[0].lower() + sentence[1:]

def make_entailment(sentence):
    # safe paraphrases (avoid changing meaning)
    if m := re_checkin.match(sentence):
        ent, t = m.group("ent"), m.group("time")
        return f"Check-in at {ent} is at {t}."
    if m := re_star.match(sentence):
        ent, s = m.group("ent"), m.group("stars")
        return f"{ent} is rated as a {s}-star hotel."
    if m := re_rating.match(sentence):
        ent, r = m.group("ent"), m.group("r")
        return f"{ent} has a customer rating of {r}."
    if m := re_locprov.match(sentence):
        place, prov = m.group("place"), m.group("prov")
        return f"{place} is in Sri Lanka's {prov}."
    if m := re_nearcat.match(sentence):
        name, cat, anchor = m.group("name"), m.group("cat"), m.group("anchor")
        return f"{name} is a {cat} close to {anchor}."
    return sentence  # fallback

def make_contradiction(sentence):
    # change one key attribute or negate
    if m := re_checkin.match(sentence):
        ent, t = m.group("ent"), m.group("time")
        return f"{ent} has check-in time at {flip_time(t)}."
    if m := re_star.match(sentence):
        ent, s = m.group("ent"), m.group("stars")
        return f"{ent} is a {flip_star(s)}-star hotel."
    if m := re_rating.match(sentence):
        ent, r = m.group("ent"), m.group("r")
        return f"{ent} has an overall rating of {flip_rating(r)}."
    if m := re_locprov.match(sentence):
        place, prov = m.group("place"), m.group("prov")
        return f"{place} is located in the {flip_province(prov)} of Sri Lanka."
    if m := re_nearcat.match(sentence):
        name, cat, anchor = m.group("name"), m.group("cat"), m.group("anchor")
        return f"{name} is a {flip_category(cat)} near {anchor}."
    # address claims: contradiction via negation (safer than making fake addresses)
    if re_address.match(sentence):
        return negate(sentence)
    return negate(sentence)

# Build pools for neutral pairing (avoid same entity)
entities = []
for s in lines:
    # rough entity extraction: left side before " is " or " has "
    ent = s.split(" is ")[0].split(" has ")[0].strip()
    entities.append(ent)

pairs = []
N_TARGET = 4500  # adjust 3000-5000

while len(pairs) < N_TARGET:
    premise = random.choice(lines)

    # 40% entailment, 40% contradiction, 20% neutral
    r = random.random()
    if r < 0.40:
        hyp = make_entailment(premise)
        label = "entailment"
    elif r < 0.80:
        hyp = make_contradiction(premise)
        label = "contradiction"
    else:
        # neutral: pair with a different claim from different entity
        p_ent = premise.split(" is ")[0].split(" has ")[0].strip()
        cand = random.choice(lines)
        c_ent = cand.split(" is ")[0].split(" has ")[0].strip()
        tries = 0
        while c_ent == p_ent and tries < 10:
            cand = random.choice(lines)
            c_ent = cand.split(" is ")[0].split(" has ")[0].strip()
            tries += 1
        hyp = cand
        label = "neutral"

    if premise != hyp:
        pairs.append((premise, hyp, label))

df = pd.DataFrame(pairs, columns=["premise","hypothesis","label"])
df.to_csv(OUT_PATH, index=False)
print("Wrote:", OUT_PATH, "rows:", len(df))
print(df["label"].value_counts())
