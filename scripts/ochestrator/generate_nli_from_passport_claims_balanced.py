import re
import random
import pandas as pd
from pathlib import Path

BASE_PATH = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/base_claims_passport_clean.txt")
OUT_PATH  = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/nli_passport_balanced.csv")

random.seed(42)
lines = [l.strip() for l in BASE_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]

# ---------- regex patterns ----------
re_fee       = re.compile(r"LKR\.?\s?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)", re.I)
re_days      = re.compile(r"(\d+)\s+working\s+days", re.I)
re_same_day  = re.compile(r"\bsame\s+day\b", re.I)
re_age       = re.compile(r"above\s+(\d+)\s+years.*below\s+(\d+)\s+years", re.I)
re_validity  = re.compile(r"valid\s+(\d+)\s+years", re.I)
re_mustlike  = re.compile(r"\b(must|required|should|will)\b", re.I)
re_no_longer = re.compile(r"no\s+longer\s+be\s+accepted", re.I)

FEES = ["1,200.00", "3,500.00", "5,000.00", "10,000.00", "15,000.00", "20,000.00", "25,000.00"]
DAYS = ["1 working days", "3 working days", "7 working days", "14 working days", "30 working days", "60 working days"]

def flip_fee(text: str) -> str | None:
    m = re_fee.search(text)
    if not m: return None
    val = m.group(1)
    choices = [f for f in FEES if f != val]
    if not choices: return None
    return re_fee.sub(lambda _m: _m.group(0).replace(val, random.choice(choices)), text, count=1)

def flip_days(text: str) -> str | None:
    m = re_days.search(text)
    if not m: return None
    orig = m.group(0)
    choices = [d for d in DAYS if d.lower() != orig.lower()]
    if not choices: return None
    return re_days.sub(lambda _m: random.choice(choices), text, count=1)

def flip_same_day(text: str) -> str | None:
    if not re_same_day.search(text): return None
    return re_same_day.sub("30 working days", text)

def flip_age(text: str) -> str | None:
    m = re_age.search(text)
    if not m: return None
    lo, hi = int(m.group(1)), int(m.group(2))
    # keep it plausible but contradictory
    new_lo = lo + random.choice([2, 5, 10])
    new_hi = hi - random.choice([2, 5, 10])
    if new_lo >= new_hi:  # fallback
        new_lo, new_hi = lo + 5, hi - 5
    return re_age.sub(f"above {new_lo} years of age and below {new_hi} years of age", text)

def flip_validity(text: str) -> str | None:
    m = re_validity.search(text)
    if not m: return None
    yrs = int(m.group(1))
    choices = [1,2,3,5,7,10]
    choices = [c for c in choices if c != yrs]
    if not choices: return None
    return re_validity.sub(f"valid {random.choice(choices)} years", text, count=1)

def negate_rule(text: str) -> str:
    if re_no_longer.search(text):
        return re_no_longer.sub("will be accepted", text)
    m = re_mustlike.search(text)
    if m:
        # only replace the first modal-like token
        start, end = m.span()
        return text[:start] + "is not required to" + text[end:]
    # fallback
    return "It is not true that " + text[0].lower() + text[1:]

def make_entailment(text: str) -> str:
    # conservative paraphrases (don’t change meaning)
    t = text
    t = re.sub(r"\bmust\b", "is required to", t, flags=re.I)
    t = re.sub(r"\bshould\b", "is expected to", t, flags=re.I)
    t = re.sub(r"\bno longer be accepted\b", "will not be accepted anymore", t, flags=re.I)
    return t

def make_contradiction(text: str) -> str:
    # try numeric flips first; if nothing changed, fall back to negation
    for f in (flip_fee, flip_days, flip_same_day, flip_age, flip_validity):
        out = f(text)
        if out and out != text:
            return out
    return negate_rule(text)

def entity_key(s: str) -> str:
    # heuristic for neutral: first ~6 words
    return " ".join(s.split()[:6]).lower()

def build_balanced(n_per_class: int = 400):
    entailments, contradictions, neutrals = [], [], []

    # --- entailments ---
    for p in random.sample(lines, k=min(len(lines), n_per_class)):
        h = make_entailment(p)
        if h != p:
            entailments.append((p, h, "entailment"))
        if len(entailments) >= n_per_class:
            break

    # --- contradictions ---
    tries = 0
    while len(contradictions) < n_per_class and tries < n_per_class * 50:
        p = random.choice(lines)
        h = make_contradiction(p)
        tries += 1
        if h != p:
            contradictions.append((p, h, "contradiction"))

    # --- neutrals ---
    tries = 0
    while len(neutrals) < n_per_class and tries < n_per_class * 80:
        p = random.choice(lines)
        h = random.choice(lines)
        tries += 1
        if p == h:
            continue
        if entity_key(p) == entity_key(h):
            continue
        neutrals.append((p, h, "neutral"))

    # trim to exact balance
    n = min(len(entailments), len(contradictions), len(neutrals), n_per_class)
    data = entailments[:n] + contradictions[:n] + neutrals[:n]
    random.shuffle(data)
    return data, n

pairs, n = build_balanced(n_per_class=400)

df = pd.DataFrame(pairs, columns=["premise","hypothesis","label"])
df.to_csv(OUT_PATH, index=False)

print("Wrote:", OUT_PATH)
print("Per-class:", n)
print(df["label"].value_counts())
