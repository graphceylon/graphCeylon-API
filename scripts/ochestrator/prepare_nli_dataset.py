#!/usr/bin/env python3
"""
Prepare GraphCeylon domain-NLI dataset for training:

✅ What this script does (all in one):
1) Loads your merged dataset CSV (premise,hypothesis,label)
2) Cleans obvious artifacts (whitespace, "dayss/yearss", jpg image noise)
3) Adds metadata:
   - negation flag
   - overlap (Jaccard)
   - pair_type (heuristic: negation_contradiction / easy_neutral / etc.)
4) Creates "hard neutrals" (same-domain, same leading token, but different fact)
   - Keeps some easy neutrals, replaces a portion with hard neutrals
5) Splits WITHOUT leakage using GroupSplit by premise
6) Saves:
   - cleaned_full.csv
   - train.csv / val.csv / test.csv
   - stats.json

Run:
  python prepare_nli_dataset.py \
    --in /Users/dev/Desktop/graphCeylon-API/data/orchestrator/processed/nli_final_dataset.csv \
    --out_dir /Users/dev/Desktop/graphCeylon-API/data/orchestrator/processed/splits \
    --seed 42 \
    --hard_neutral_ratio 0.5

Notes:
- No GPU needed for this preprocessing.
- Pure pandas + sklearn only.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit


LABELS = ["entailment", "contradiction", "neutral"]


# -------------------------
# Helpers
# -------------------------
_NEG_PAT = re.compile(r"\b(not|no|never|cannot|can't|isn't|aren't|wasn't|weren't|won't|don't|doesn't|didn't)\b", re.I)

_ARTIFACT_PATTERNS = [
    re.compile(r"\bjpg image\b", re.I),
    re.compile(r"\bsection_(ul|ol|p|heading)\b", re.I),
    re.compile(r"\bcontent_text\b", re.I),
]

_TYPO_FIXES = [
    (re.compile(r"\bdayss\b", re.I), "days"),
    (re.compile(r"\byearss\b", re.I), "years"),
    (re.compile(r"\bmonthss\b", re.I), "months"),
]


def norm_text(s: str) -> str:
    if s is None:
        return ""
    s = str(s)
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    s = re.sub(r"\s+", " ", s).strip()
    for pat, repl in _TYPO_FIXES:
        s = pat.sub(repl, s)
    return s


def is_artifact_sentence(s: str) -> bool:
    s_low = s.lower()
    # very short junk like "jpg image of data page..."
    for pat in _ARTIFACT_PATTERNS:
        if pat.search(s_low):
            return True
    # low-information single fragments (optional heuristic)
    if len(s_low) < 8:
        return True
    return False


def has_negation(s: str) -> bool:
    return bool(_NEG_PAT.search(s or ""))


def jaccard_overlap(a: str, b: str) -> float:
    A = set((a or "").lower().split())
    B = set((b or "").lower().split())
    denom = max(len(A | B), 1)
    return len(A & B) / denom


def infer_domain(premise: str) -> str:
    """
    Heuristic domain tag based on keywords.
    You can refine later; it's for analysis + hard neutral sampling.
    """
    p = (premise or "").lower()

    visa_kw = ["visa", "eta", "immigration", "entry", "tourist", "business purpose", "battaramulla", "department of immigration"]
    passport_kw = ["passport", "fingerprint", "photo", "application", "travel document", "data page", "emergency certificate"]
    citizenship_kw = ["citizen", "citizenship", "dual", "naturalization", "minister", "registration"]
    hotel_kw = ["hotel", "check-in", "checkout", "breakfast", "room", "reservation"]

    def hit(kws):
        return sum(1 for k in kws if k in p)

    scores = {
        "visa": hit(visa_kw),
        "passport": hit(passport_kw),
        "citizenship": hit(citizenship_kw),
        "hotels": hit(hotel_kw),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "unknown"


@dataclass
class SplitStats:
    total_rows: int
    label_counts: Dict[str, int]
    negation_rate_overall: float
    negation_rate_by_label: Dict[str, float]
    overlap_mean_by_label: Dict[str, float]
    unique_premises: int
    unique_hypotheses: int
    duplicates_removed: int
    hard_neutrals_created: int


# -------------------------
# Hard neutral generation
# -------------------------
def build_hard_neutrals(df: pd.DataFrame, ratio: float, seed: int) -> Tuple[pd.DataFrame, int]:
    """
    Replace a portion of existing neutrals with "hard neutrals":
      - same domain
      - same first token (rough proxy for same entity/section style)
      - different premise (avoid identical)
      - label stays 'neutral'
    """
    rng = random.Random(seed)

    df = df.copy()
    neutral_idx = df.index[df["label"] == "neutral"].tolist()
    if not neutral_idx or ratio <= 0:
        return df, 0

    target_n = int(len(neutral_idx) * ratio)
    if target_n <= 0:
        return df, 0

    # pools by (domain, first_token)
    def first_token(s: str) -> str:
        toks = (s or "").split()
        return toks[0].lower() if toks else ""

    df["first_tok_p"] = df["premise"].map(first_token)
    df["first_tok_h"] = df["hypothesis"].map(first_token)

    # Build candidate sentences per bucket from premises (to use as hard-neutral hypotheses)
    buckets: Dict[Tuple[str, str], List[str]] = {}
    for p, dom, ft in zip(df["premise"], df["domain"], df["first_tok_p"]):
        if not p:
            continue
        buckets.setdefault((dom, ft), []).append(p)

    # choose neutrals to rewrite
    chosen = rng.sample(neutral_idx, k=min(target_n, len(neutral_idx)))

    created = 0
    for i in chosen:
        dom = df.at[i, "domain"]
        ft = df.at[i, "first_tok_p"]
        prem = df.at[i, "premise"]

        cand = buckets.get((dom, ft), [])
        if len(cand) < 2:
            continue

        # pick a different sentence from same bucket
        alt = prem
        for _ in range(10):
            alt = rng.choice(cand)
            if alt != prem:
                break
        if alt == prem:
            continue

        df.at[i, "hypothesis"] = alt
        df.at[i, "pair_type"] = "hard_neutral"
        created += 1

    # cleanup temp cols
    df = df.drop(columns=["first_tok_p", "first_tok_h"], errors="ignore")
    return df, created


# -------------------------
# Main
# -------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input CSV (premise,hypothesis,label)")
    ap.add_argument("--out_dir", required=True, help="Output directory for cleaned + splits")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--hard_neutral_ratio", type=float, default=0.5, help="Fraction of neutrals to turn into hard neutrals (0..1)")
    ap.add_argument("--train", type=float, default=0.8)
    ap.add_argument("--val", type=float, default=0.1)
    ap.add_argument("--test", type=float, default=0.1)
    args = ap.parse_args()

    if not (0.0 <= args.hard_neutral_ratio <= 1.0):
        raise SystemExit("--hard_neutral_ratio must be between 0 and 1")

    if abs((args.train + args.val + args.test) - 1.0) > 1e-6:
        raise SystemExit("train+val+test must sum to 1.0")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- load
    df = pd.read_csv(args.inp)
    required = {"premise", "hypothesis", "label"}
    if not required.issubset(df.columns):
        raise SystemExit(f"Input must contain columns {required}. Found: {list(df.columns)}")

    # ---- normalize / clean
    before = len(df)
    df["premise"] = df["premise"].map(norm_text)
    df["hypothesis"] = df["hypothesis"].map(norm_text)
    df["label"] = df["label"].astype(str).str.strip().str.lower()

    # drop empty
    df = df[(df["premise"] != "") & (df["hypothesis"] != "") & (df["label"] != "")]
    # keep valid labels
    df = df[df["label"].isin(LABELS)]

    # remove obvious artifacts rows (optional but recommended)
    art_mask = df["premise"].map(is_artifact_sentence) | df["hypothesis"].map(is_artifact_sentence)
    df = df[~art_mask].copy()

    # remove duplicates on (premise,hypothesis,label)
    df = df.drop_duplicates(subset=["premise", "hypothesis", "label"]).copy()
    dups_removed = before - len(df)

    # ---- metadata
    df["negation"] = df["hypothesis"].map(has_negation)
    df["overlap"] = [jaccard_overlap(a, b) for a, b in zip(df["premise"], df["hypothesis"])]
    df["domain"] = df["premise"].map(infer_domain)

    # pair_type heuristic
    def pair_type(row) -> str:
        if row["label"] == "contradiction" and row["negation"]:
            return "negation_contradiction"
        if row["label"] == "neutral":
            return "easy_neutral"
        return "other"

    df["pair_type"] = df.apply(pair_type, axis=1)

    # ---- make hard neutrals
    df, hard_created = build_hard_neutrals(df, ratio=args.hard_neutral_ratio, seed=args.seed)

    # recompute overlap (since we edited some hypotheses)
    df["overlap"] = [jaccard_overlap(a, b) for a, b in zip(df["premise"], df["hypothesis"])]

    # ---- group split by premise to avoid leakage
    groups = df["premise"].values
    idx = np.arange(len(df))

    gss1 = GroupShuffleSplit(n_splits=1, test_size=(1.0 - args.train), random_state=args.seed)
    train_idx, temp_idx = next(gss1.split(idx, groups=groups))

    temp_df = df.iloc[temp_idx].copy()
    temp_groups = temp_df["premise"].values
    temp_idx2 = np.arange(len(temp_df))

    # split temp into val/test proportionally
    val_frac_of_temp = args.val / (args.val + args.test)
    gss2 = GroupShuffleSplit(n_splits=1, test_size=(1.0 - val_frac_of_temp), random_state=args.seed)
    val_i, test_i = next(gss2.split(temp_idx2, groups=temp_groups))

    train_df = df.iloc[train_idx].copy()
    val_df = temp_df.iloc[val_i].copy()
    test_df = temp_df.iloc[test_i].copy()

    # ---- save
    cleaned_path = out_dir / "cleaned_full.csv"
    train_path = out_dir / "train.csv"
    val_path = out_dir / "val.csv"
    test_path = out_dir / "test.csv"
    stats_path = out_dir / "stats.json"

    df.to_csv(cleaned_path, index=False)
    train_df.to_csv(train_path, index=False)
    val_df.to_csv(val_path, index=False)
    test_df.to_csv(test_path, index=False)

    # ---- stats
    label_counts = df["label"].value_counts().to_dict()
    neg_rate = float(df["negation"].mean())
    neg_by_label = df.groupby("label")["negation"].mean().to_dict()
    overlap_by_label = df.groupby("label")["overlap"].mean().to_dict()

    stats = SplitStats(
        total_rows=int(len(df)),
        label_counts={k: int(v) for k, v in label_counts.items()},
        negation_rate_overall=neg_rate,
        negation_rate_by_label={k: float(v) for k, v in neg_by_label.items()},
        overlap_mean_by_label={k: float(v) for k, v in overlap_by_label.items()},
        unique_premises=int(df["premise"].nunique()),
        unique_hypotheses=int(df["hypothesis"].nunique()),
        duplicates_removed=int(dups_removed),
        hard_neutrals_created=int(hard_created),
    )

    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(asdict(stats), f, indent=2)

    # ---- print summary
    print("\n[ok] Wrote:")
    print(" ", cleaned_path)
    print(" ", train_path)
    print(" ", val_path)
    print(" ", test_path)
    print(" ", stats_path)

    print("\n[info] cleaned_full label counts:")
    print(df["label"].value_counts())
    print("\n[info] negation by label:")
    print(df.groupby("label")["negation"].mean())
    print("\n[info] overlap by label:")
    print(df.groupby("label")["overlap"].mean())
    print("\n[info] split sizes:")
    print(" train:", len(train_df), "val:", len(val_df), "test:", len(test_df))


if __name__ == "__main__":
    main()
