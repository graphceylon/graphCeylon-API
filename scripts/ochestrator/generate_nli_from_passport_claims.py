import re
import random
import pandas as pd
from pathlib import Path

BASE_PATH = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/base_claims_passport_clean.txt")
OUT_PATH  = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/nli_passport.csv")

random.seed(42)

lines = [l.strip() for l in BASE_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]

# ---------- regex patterns ----------
re_fee      = re.compile(r"LKR\.?\s?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)", re.I)
re_days     = re.compile(r"(\d+)\s+working\s+days", re.I)
re_same_day = re.compile(r"\bsame\s+day\b", re.I)
re_age      = re.compile(r"above\s+(\d+)\s+years.*below\s+(\d+)\s+years", re.I)
re_validity = re.compile(r"valid\s+(\d+)\s+years", re.I)
re_must     = re.compile(r"\b(must|required|should|will)\b", re.I)
re_no_longer = re.compile(r"no\s+longer\s+be\s+accepted", re.I)

def flip_fee(text):
    m = re_fee.search(text)
    if not m: return None
    val = m.group(1)
    other = ["5,000","15,000","20,000","25,000"]
    other = [o for o in other if o != val]
    return text.replace(val, random.choice(other), 1)

def flip_days(text):
    m = re_days.search(text)
    if not m: return None
    d = int(m.group(1))
    other = random.choice([1,3,7,14,60])
    return text.replace(f"{d} working days", f"{other} working days", 1)

def flip_same_day(text):
    if re_same_day.search(text):
        return re_same_day.sub("30 working days", text)
    return None

def flip_age(text):
    m = re_age.search(text)
    if not m: return None
    lo, hi = int(m.group(1)), int(m.group(2))
    return re_age.sub(f"above {lo+5} years and below {hi-5} years", text)

def flip_validity(text):
    m = re_validity.search(text)
    if not m: return None
    yrs = int(m.group(1))
    other = random.choice([1,2,3,5])
    return text.replace(f"valid {yrs} years", f"valid {other} years")

def negate_rule(text):
    if re_no_longer.search(text):
        return text.replace("no longer be accepted", "will be accepted")
    if m := re_must.search(text):
        return text[:m.start()] + "does not have to" + text[m.end():]
    return "It is not true that " + text[0].lower() + text[1:]

def make_entailment(text):
    return text.replace("must", "is required to").replace("should", "is expected to")

def make_contradiction(text):
    for f in [flip_fee, flip_days, flip_same_day, flip_age, flip_validity]:
        out = f(text)
        if out and out != text:
            return out
    return negate_rule(text)

pairs = []
TARGET = 1200

while len(pairs) < TARGET:
    premise = random.choice(lines)
    r = random.random()

    if r < 0.4:
        hyp = make_entailment(premise)
        label = "entailment"
    elif r < 0.8:
        hyp = make_contradiction(premise)
        label = "contradiction"
    else:
        other = random.choice(lines)
        if other == premise:
            continue
        hyp = other
        label = "neutral"

    if premise != hyp:
        pairs.append((premise, hyp, label))

df = pd.DataFrame(pairs, columns=["premise","hypothesis","label"])
df.to_csv(OUT_PATH, index=False)
print("Wrote:", OUT_PATH, "rows:", len(df))
print(df["label"].value_counts())
