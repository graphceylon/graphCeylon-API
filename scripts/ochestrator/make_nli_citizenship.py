import re
import random
import pandas as pd
from pathlib import Path

BASE_CSV = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/base_claims_citizenship_clean.csv")
OUT_CSV  = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/nli_citizenship.csv")

random.seed(42)

df_base = pd.read_csv(BASE_CSV)
lines = [str(x).strip() for x in df_base["claim"].tolist() if str(x).strip()]

# -------------------
# Patterns / helpers
# -------------------
re_working_hours2 = re.compile(r"^Working Hours:\s*(?P<days>.+?) Applications are accepted from (?P<from>.+?) to (?P<to>.+?)\.$", re.I)
re_accept_time_rng = re.compile(r"^Applications .*accepted from (?P<from>.+?) to (?P<to>.+?)\.$", re.I)
re_years = re.compile(r"(?P<n>\d+)\s+years?", re.I)
re_usd  = re.compile(r"USD\s*(?P<amt>\d+(?:,\d{3})*(?:\.\d+)?)", re.I)
re_age  = re.compile(r"above\s+(?P<n>\d+)\s+years", re.I)

TIMES = ["08.30 a.m.", "09.00 a.m.", "10.00 a.m.", "11.00 a.m.", "12.00 p.m.", "01.00 p.m.", "02.30 p.m.", "03.00 p.m.", "04.00 p.m."]

def pick_other(seq, current):
    opts = [x for x in seq if x.lower() != (current or "").lower()]
    return random.choice(opts) if opts else random.choice(seq)

def flip_year(n: str) -> str:
    n_i = int(n)
    choices = [1,2,3,4,5,7,10]
    choices = [c for c in choices if c != n_i]
    return str(random.choice(choices)) if choices else str(max(1, n_i-1))

def negate(sentence: str) -> str:
    if " will be " in sentence:
        return sentence.replace(" will be ", " will not be ", 1)
    if " are " in sentence:
        return sentence.replace(" are ", " are not ", 1)
    if " is " in sentence:
        return sentence.replace(" is ", " is not ", 1)
    if " should be " in sentence:
        return sentence.replace(" should be ", " should not be ", 1)
    if " must be " in sentence:
        return sentence.replace(" must be ", " must not be ", 1)
    return "It is not true that: " + sentence

def make_entailment(sentence: str) -> str:
    # Conservative paraphrases, otherwise add entailment wrapper (never equal)
    if m := re_working_hours2.match(sentence):
        days, t1, t2 = m.group("days"), m.group("from"), m.group("to")
        return f"Applications are accepted on {days} between {t1} and {t2}."
    if m := re_accept_time_rng.match(sentence):
        t1, t2 = m.group("from"), m.group("to")
        return f"Applications are received between {t1} and {t2}."
    # Guaranteed entailment but not identical
    return f"It is true that: {sentence}"

def make_contradiction(sentence: str) -> str:
    # Flip time range if present
    if m := re_working_hours2.match(sentence):
        days, t1, t2 = m.group("days"), m.group("from"), m.group("to")
        return f"Applications are accepted on {days} from {pick_other(TIMES,t1)} to {pick_other(TIMES,t2)}."
    if m := re_accept_time_rng.match(sentence):
        t1, t2 = m.group("from"), m.group("to")
        return f"Applications are accepted from {pick_other(TIMES,t1)} to {pick_other(TIMES,t2)}."

    # Flip a number (years / USD / age) if possible
    if re_years.search(sentence):
        return re_years.sub(lambda mm: f"{flip_year(mm.group('n'))} years", sentence, count=1)
    if re_usd.search(sentence):
        candidates = ["10,000","15,000","20,000","25,000","30,000","50,000","100,000"]
        return re_usd.sub(lambda mm: f"USD {pick_other(candidates, mm.group('amt'))}", sentence, count=1)
    if re_age.search(sentence):
        candidates = ["12","14","16","18","21","55","60"]
        return re_age.sub(lambda mm: f"above {pick_other(candidates, mm.group('n'))} years", sentence, count=1)

    return negate(sentence)

def topic_key(s: str) -> str:
    s = s.lower()
    if "dual citizenship" in s:
        return "dual"
    if "citizenship division" in s or "indo" in s:
        return "office"
    if "act" in s:
        return "act"
    if "working" in s or "hours" in s:
        return "hours"
    if "document" in s:
        return "docs"
    return "misc"

def make_neutral(premise: str) -> str:
    p_key = topic_key(premise)
    cand = random.choice(lines)
    tries = 0
    while topic_key(cand) == p_key and tries < 30:
        cand = random.choice(lines)
        tries += 1
    return cand

# -------------------
# Exact balancing
# -------------------
N_ENTAIL = 1000
N_CONTR = 1000
N_NEUT  = 500

pairs = []

for _ in range(N_ENTAIL):
    p = random.choice(lines)
    h = make_entailment(p)
    pairs.append((p, h, "entailment"))

for _ in range(N_CONTR):
    p = random.choice(lines)
    h = make_contradiction(p)
    pairs.append((p, h, "contradiction"))

for _ in range(N_NEUT):
    p = random.choice(lines)
    h = make_neutral(p)
    pairs.append((p, h, "neutral"))

random.shuffle(pairs)

df_out = pd.DataFrame(pairs, columns=["premise", "hypothesis", "label"])
df_out.to_csv(OUT_CSV, index=False)

print("Wrote:", OUT_CSV, "rows:", len(df_out))
print(df_out["label"].value_counts())
