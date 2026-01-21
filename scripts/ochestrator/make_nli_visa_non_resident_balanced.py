import re
import random
import pandas as pd
from pathlib import Path

BASE_CSV = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/base_claims_visa_non_resident_atomic.csv")
OUT_CSV  = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/nli_visa_non_resident.csv")

random.seed(42)

df_base = pd.read_csv(BASE_CSV)
lines = [str(x).strip() for x in df_base["claim"].tolist() if str(x).strip()]

# --------- helpers ----------
WS = re.compile(r"\s+")
def norm(s: str) -> str:
    return WS.sub(" ", (s or "").replace("\u00a0", " ").strip())

# patterns for common visa facts
re_days = re.compile(r"(?P<n>\d+)\s*(?:day|days)", re.I)
re_months = re.compile(r"(?P<n>\d+)\s*(?:month|months)", re.I)
re_years = re.compile(r"(?P<n>\d+)\s*(?:year|years)", re.I)
re_usd = re.compile(r"USD\s*(?P<amt>\d+(?:,\d{3})*(?:\.\d+)?)", re.I)
re_rs  = re.compile(r"(?:Rs\.?|LKR)\s*(?P<amt>\d+(?:,\d{3})*(?:\.\d+)?)", re.I)

NUM_CHOICES = [1, 3, 7, 14, 21, 30, 60, 90, 180]
USD_CHOICES = ["10", "20", "25", "30", "35", "40", "50", "75", "100"]
RS_CHOICES  = ["500", "1000", "1500", "2000", "2500", "5000", "10000", "15000"]

def pick_other(seq, current):
    cur = str(current).strip()
    opts = [x for x in seq if str(x).strip() != cur]
    return random.choice(opts) if opts else random.choice(seq)

def negate(sentence: str) -> str:
    # conservative negation
    if " is " in sentence:
        return sentence.replace(" is ", " is not ", 1)
    if " are " in sentence:
        return sentence.replace(" are ", " are not ", 1)
    if " must " in sentence:
        return sentence.replace(" must ", " must not ", 1)
    if " should " in sentence:
        return sentence.replace(" should ", " should not ", 1)
    if " can " in sentence:
        return sentence.replace(" can ", " cannot ", 1)
    return "It is not true that: " + sentence

def flip_numbers(sentence: str) -> str:
    # days/months/years
    if (m := re_days.search(sentence)):
        n = m.group("n")
        new_n = str(pick_other(NUM_CHOICES, int(n)))
        return re_days.sub(f"{new_n} days", sentence, count=1)

    if (m := re_months.search(sentence)):
        n = m.group("n")
        new_n = str(pick_other([1,2,3,6,12], int(n)))
        return re_months.sub(f"{new_n} months", sentence, count=1)

    if (m := re_years.search(sentence)):
        n = m.group("n")
        new_n = str(pick_other([1,2,3,5,10], int(n)))
        return re_years.sub(f"{new_n} years", sentence, count=1)

    # USD / Rs amounts
    if (m := re_usd.search(sentence)):
        amt = m.group("amt")
        return re_usd.sub(f"USD {pick_other(USD_CHOICES, amt)}", sentence, count=1)

    if (m := re_rs.search(sentence)):
        amt = m.group("amt")
        return re_rs.sub(lambda mm: mm.group(0).split()[0] + " " + pick_other(RS_CHOICES, amt), sentence, count=1)

    return sentence

def make_entailment(sentence: str) -> str:
    # safe paraphrase wrappers so it never equals premise
    return f"It is true that: {sentence}"

def make_contradiction(sentence: str) -> str:
    # prefer numeric flip if possible, else negate
    flipped = flip_numbers(sentence)
    if flipped != sentence:
        return flipped
    return negate(sentence)

def topic_key(s: str) -> str:
    s = s.lower()
    if "tourist" in s:
        return "tourist"
    if "business" in s:
        return "business"
    if "free visa" in s or "free-visa" in s:
        return "free"
    if "extension" in s:
        return "extension"
    if "eta" in s:
        return "eta"
    if "document" in s or "passport" in s:
        return "docs"
    if "fee" in s or "usd" in s or "rs" in s or "lkr" in s:
        return "fees"
    return "misc"

def make_neutral(premise: str) -> str:
    pk = topic_key(premise)
    cand = random.choice(lines)
    tries = 0
    while topic_key(cand) == pk and tries < 30:
        cand = random.choice(lines)
        tries += 1
    return cand

# --------- exact balancing ----------
N_ENTAIL = 800
N_CONTR  = 800
N_NEUT   = 800   # you can set 500 if you want smaller neutral

pairs = []

for _ in range(N_ENTAIL):
    p = random.choice(lines)
    pairs.append((p, make_entailment(p), "entailment"))

for _ in range(N_CONTR):
    p = random.choice(lines)
    pairs.append((p, make_contradiction(p), "contradiction"))

for _ in range(N_NEUT):
    p = random.choice(lines)
    pairs.append((p, make_neutral(p), "neutral"))

random.shuffle(pairs)

df_out = pd.DataFrame(pairs, columns=["premise", "hypothesis", "label"])
df_out.to_csv(OUT_CSV, index=False)

print("Wrote:", OUT_CSV, "rows:", len(df_out))
print(df_out["label"].value_counts())
