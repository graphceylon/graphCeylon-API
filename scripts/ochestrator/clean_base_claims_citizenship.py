#!/usr/bin/env python3
"""
Clean base_claims_citizenship.csv -> base_claims_citizenship_clean.csv

Usage:
  python clean_base_claims_citizenship.py \
    --in /Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/base_claims_citizenship.csv \
    --out /Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/base_claims_citizenship_clean.csv
"""

from __future__ import annotations

import argparse
import pandas as pd
import re


WS = re.compile(r"\s+")

def norm(s: str) -> str:
    s = (s or "").replace("\u00a0", " ").strip()
    s = WS.sub(" ", s)
    return s

def is_bad(s: str) -> bool:
    if not s:
        return True
    if len(s) < 20:
        return True
    low = s.lower()

    bad_contains = [
        "for more information",
        "click here",
        "see note",
        "download",
        "pdf",
        "not relevant",   # form instruction
        "block capitals", # form instruction
    ]
    if any(x in low for x in bad_contains):
        return True

    # Too many non-letter chars -> often scraped menu/artifacts
    letters = sum(ch.isalpha() for ch in s)
    if letters / max(len(s), 1) < 0.55:
        return True

    return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    args = ap.parse_args()

    df = pd.read_csv(args.inp)
    df["claim"] = df["claim"].astype(str).map(norm)

    before = len(df)
    df = df[~df["claim"].map(is_bad)].copy()

    # Dedup on (service_key, claim)
    df = df.drop_duplicates(subset=["service_key", "claim"])

    df.to_csv(args.out, index=False)
    print(f"[ok] cleaned: {before} -> {len(df)} rows, wrote {args.out}")

if __name__ == "__main__":
    main()
