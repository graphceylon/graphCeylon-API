#!/usr/bin/env python3
from __future__ import annotations
import re
from pathlib import Path

# Split rough sentences (good enough for your content)
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\s+\|\s+|(?<=\.)\s+(?=[A-Z0-9])")

# Remove obvious noise
NOISE_PATTERNS = [
    r"^\s*where can i\b",                 # questions
    r"^\s*what are the\b",
    r"^\s*how can i\b",
    r"^\s*how do i\b",
    r"^\s*when can i\b",
    r"^\s*see circular\b",
    r"^\s*see table\b",
    r"^\s*download\b.*application form\b",
    r"^\s*more information\b",
    r"^\s*operators are available\b",
    r"^\s*nb:\b",
]
NOISE_RE = re.compile("|".join(f"(?:{p})" for p in NOISE_PATTERNS), re.IGNORECASE)

# Keep only fact-like sentences (tune if needed)
FACTY_RE = re.compile(
    r"\b(must|required|should|will|valid|fee|fees|lkr|working days|urgent|normal|fingerprints|photograph|application|passport|issued|submit|accepted|only|cannot|no longer|destroyed)\b",
    re.IGNORECASE
)

def normalize(s: str) -> str:
    s = s.strip()
    s = s.strip('"').strip("'").strip()
    s = re.sub(r"\s+", " ", s)
    return s

def is_too_short(s: str) -> bool:
    return len(s) < 30

def main():
    inp = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/base_claims_passport.txt")
    out = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/base_claims_passport_clean.txt")
    out.parent.mkdir(parents=True, exist_ok=True)

    raw = inp.read_text(encoding="utf-8").splitlines()

    cleaned = []
    for line in raw:
        line = normalize(line)
        if not line:
            continue

        # split merged lines into sentence-ish chunks
        chunks = [normalize(x) for x in SENT_SPLIT.split(line) if normalize(x)]

        for c in chunks:
            # drop pure questions / noise
            if NOISE_RE.search(c):
                continue
            # drop sentences ending with '?'
            if c.endswith("?"):
                continue
            # keep only fact-like content
            if not FACTY_RE.search(c):
                continue
            if is_too_short(c):
                continue

            # ensure punctuation ending
            if c[-1] not in ".!?":
                c += "."
            cleaned.append(c)

    # dedupe with normalized key
    seen = set()
    final = []
    for c in cleaned:
        key = normalize(c).lower()
        if key in seen:
            continue
        seen.add(key)
        final.append(c)

    out.write_text("\n".join(final) + "\n", encoding="utf-8")

    print("IN :", len(raw))
    print("OUT:", len(final))
    print("Wrote:", out)

if __name__ == "__main__":
    main()
