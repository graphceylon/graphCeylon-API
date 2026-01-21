#!/usr/bin/env python3
import argparse
import re
import pandas as pd

WS = re.compile(r"\s+")

BAD_CONTAINS = [
    "click here",
    "download",
    "online form",
    "apply online",
    "visa application",
    "immigration.gov.lk",
    "home",
    "back",
    "next",
    "print",
]

BAD_EXACT = {
    "tourist visa",
    "business visa",
    "free visa",
    "visit visa extension",
    "online tourist visa extension",
    "requirements",
    "documents required",
    "procedure",
    "general",
}

def norm(s: str) -> str:
    s = (s or "").replace("\u00a0", " ").strip()
    s = WS.sub(" ", s)
    # strip bullet/number prefixes
    s = re.sub(r"^\s*[-•\u2022]+\s*", "", s)
    s = re.sub(r"^\s*(?:\(?\d+[.)]|\(?[a-zA-Z][.)])\s*", "", s)
    return s.strip()

def is_bad(s: str) -> bool:
    if not s:
        return True
    low = s.lower().strip()

    if low in BAD_EXACT:
        return True
    if len(s) < 18:
        return True
    if any(x in low for x in BAD_CONTAINS):
        return True

    # too symbol-heavy -> menus / broken scrape
    letters = sum(ch.isalpha() for ch in s)
    if letters / max(len(s), 1) < 0.55:
        return True

    # very generic non-factual headings
    if low.endswith(":"):
        return True

    return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    args = ap.parse_args()

    df = pd.read_csv(args.inp)

    if "claim" not in df.columns:
        raise SystemExit("CSV must contain a 'claim' column.")

    df["claim"] = df["claim"].astype(str).map(norm)
    before = len(df)

    df = df[~df["claim"].map(is_bad)].copy()

    # de-dup on (service_key, claim) if exists, else just claim
    subset = ["claim"]
    if "service_key" in df.columns:
        subset = ["service_key", "claim"]

    df = df.drop_duplicates(subset=subset)

    df.to_csv(args.out, index=False)
    print(f"[ok] cleaned: {before} -> {len(df)} rows, wrote {args.out}")

if __name__ == "__main__":
    main()
