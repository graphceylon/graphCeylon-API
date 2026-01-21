import re
import random
from pathlib import Path
import pandas as pd

IN_PATH  = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/processed/nli_v2/cleaned_full_v2.csv")
OUT_PATH = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/processed/nli_v2/augmented_full_v3.csv")

random.seed(42)

CITY_POOL = ["Colombo","Kandy","Galle","Nuwara Eliya","Ella","Sigiriya","Negombo","Jaffna","Matara","Trincomalee"]
TIME_POOL = ["6 AM","7 AM","8 AM","9 AM","10 AM","11 AM","12 PM","1 PM","2 PM","3 PM","4 PM","5 PM","6 PM","7 PM","8 PM"]
PRICE_POOL = ["LKR 500","LKR 1000","LKR 1500","LKR 2000","LKR 2500","LKR 3000","LKR 3500","LKR 4000"]

time_pat  = re.compile(r"\b([1-9]|1[0-2])\s?(AM|PM)\b")
price_pat = re.compile(r"\b(LKR|Rs\.?)\s?\d{2,6}\b", re.IGNORECASE)
num_pat = re.compile(r"\b(\d{1,3})\b")
time2_pat = re.compile(r"\b([01]?\d|2[0-3]):[0-5]\d\b")
ampm_pat  = re.compile(r"\b([1-9]|1[0-2])\s?(AM|PM)\b", re.IGNORECASE)
AMENITIES = ["wifi","parking","pool","spa","gym","restaurant","breakfast","air conditioning","ac","bar"]

def flip_amenity(text: str):
    lower = text.lower()
    for a in AMENITIES:
        if a in lower:
            choices = [x for x in AMENITIES if x != a]
            newa = random.choice(choices)
            # replace preserving original casing as best effort
            return re.sub(re.escape(a), newa, text, flags=re.IGNORECASE, count=1)
    return None


def flip_time_any(text: str):
    m = time2_pat.search(text)
    if m:
        old = m.group(0)
        hh, mm = old.split(":")
        hh = int(hh)
        new_hh = (hh + random.choice([1,2,3,4,6])) % 24
        new = f"{new_hh:02d}:{mm}"
        return text[:m.start()] + new + text[m.end():]
    m = ampm_pat.search(text)
    if m:
        old = m.group(0)
        choices = [t for t in TIME_POOL if t.lower() != old.lower()]
        new = random.choice(choices)
        return text[:m.start()] + new + text[m.end():]
    return None


def flip_number(text: str):
    m = num_pat.search(text)
    if not m: return None
    old = int(m.group(1))
    # avoid 0 and keep reasonable range
    candidates = [old+1, old+2, max(1, old-1), max(1, old-2)]
    new = str(random.choice([c for c in candidates if c != old]))
    return text[:m.start()] + new + text[m.end():]


def flip_time(text: str):
    m = time_pat.search(text)
    if not m: return None
    old = m.group(0)
    choices = [t for t in TIME_POOL if t.lower() != old.lower()]
    new = random.choice(choices)
    return text[:m.start()] + new + text[m.end():]

def flip_price(text: str):
    m = price_pat.search(text)
    if not m: return None
    old = m.group(0)
    new = random.choice(PRICE_POOL)
    # keep currency style if possible
    if old.lower().startswith("rs"):
        new = new.replace("LKR", "Rs.")
    return text[:m.start()] + new + text[m.end():]

def flip_location(text: str):
    # swap first city mention
    for c in CITY_POOL:
        if re.search(rf"\b{re.escape(c)}\b", text):
            choices = [x for x in CITY_POOL if x != c]
            newc = random.choice(choices)
            return re.sub(rf"\b{re.escape(c)}\b", newc, text, count=1)
    return None

def make_contra(row):
    hyp = str(row["hypothesis"])
    prem = str(row["premise"])

    # 1) try flipping hypothesis first
    for fn, ptype in [
        (flip_time_any, "hard_time_contra"),
        (flip_price,    "hard_price_contra"),
        (flip_number,   "hard_number_contra"),
        (flip_location, "hard_location_contra"),
        (flip_amenity,  "hard_amenity_contra"),
    ]:
        new_h = fn(hyp)
        if new_h and new_h != hyp:
            return prem, new_h, ptype

    # 2) if hypothesis couldn't be flipped, flip premise
    for fn, ptype in [
        (flip_time_any, "hard_time_contra"),
        (flip_price,    "hard_price_contra"),
        (flip_number,   "hard_number_contra"),
        (flip_location, "hard_location_contra"),
        (flip_amenity,  "hard_amenity_contra"),
    ]:
        new_p = fn(prem)
        if new_p and new_p != prem:
            return new_p, hyp, ptype

    return None


def main():
    df = pd.read_csv(IN_PATH)
    aug_rows = []

    # sample from entailment/neutral/other pairs to create contradictions
    base = df.sample(n=min(2500, len(df)), random_state=42)

    for _, r in base.iterrows():
        out = make_contra(r)
        if out is None:
            continue
        prem, hyp, ptype = out
        aug_rows.append({
            "premise": prem,
            "hypothesis": hyp,
            "label": "contradiction",
            "negation": False,
            "overlap": None,
            "domain": r.get("domain","unknown"),
            "pair_type": ptype
        })

    aug_df = pd.DataFrame(aug_rows)
    print("Generated:", len(aug_df), "non-negation contradictions")
    df2 = pd.concat([df, aug_df], ignore_index=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df2.to_csv(OUT_PATH, index=False)
    print("Saved:", OUT_PATH, "rows=", len(df2))
    print("Label dist:", df2["label"].value_counts().to_dict())
    print("New pair types:", aug_df["pair_type"].value_counts().to_dict())

if __name__ == "__main__":
    main()
