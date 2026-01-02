import re
from pathlib import Path

IN_PATH  = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/base_claims.txt")
OUT_PATH = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/base_claims_clean.txt")

text = IN_PATH.read_text(encoding="utf-8", errors="ignore")
lines = [l.strip() for l in text.splitlines() if l.strip()]

clean = []
seen = set()

def norm(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace(" ,", ",").replace(" .", ".")
    return s

for l in lines:
    # basic sanity filters
    if len(l) < 12:
        continue
    if len(l) > 220:              # avoid long messy sentences
        continue
    if l.count("http") > 0:
        continue
    if l.endswith(":"):
        continue

    # normalize quotes / whitespace
    l = re.sub(r"\s+", " ", l)
    l = l.replace("“", '"').replace("”", '"').replace("’", "'")

    k = norm(l)
    if k in seen:
        continue
    seen.add(k)
    clean.append(l)

OUT_PATH.write_text("\n".join(clean) + "\n", encoding="utf-8")
print(f"IN  : {len(lines)}")
print(f"OUT : {len(clean)}")
print("Wrote:", OUT_PATH)
