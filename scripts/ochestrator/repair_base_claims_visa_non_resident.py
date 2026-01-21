import argparse
import re
import pandas as pd

WS = re.compile(r"\s+")
QMARK = re.compile(r"\?\s*$")

def norm(s: str) -> str:
    s = (s or "").replace("\u00a0", " ").strip()
    s = WS.sub(" ", s)
    return s

def is_question(s: str) -> bool:
    s = s.strip()
    if QMARK.search(s):
        return True
    low = s.lower()
    return low.startswith(("what ", "how ", "when ", "where ", "why ", "who "))

def too_listy(s: str) -> bool:
    low = s.lower()
    # big multi-fact blobs
    if "allowed activities:" in low or "not allowed activities:" in low:
        return True
    if "required documents:" in low and len(s) > 120:
        return True
    return False

def is_too_short(s: str) -> bool:
    return len(s.strip()) < 18

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    args = ap.parse_args()

    df = pd.read_csv(args.inp)
    df["claim"] = df["claim"].astype(str).map(norm)

    before = len(df)

    # drop questions + very short fragments + list blobs
    df = df[~df["claim"].map(is_question)].copy()
    df = df[~df["claim"].map(is_too_short)].copy()
    df = df[~df["claim"].map(too_listy)].copy()

    # de-dup on claim
    df = df.drop_duplicates(subset=["claim"])

    df.to_csv(args.out, index=False)
    print(f"[ok] repaired visa base claims: {before} -> {len(df)} rows -> {args.out}")

if __name__ == "__main__":
    main()
