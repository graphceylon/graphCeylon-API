#!/usr/bin/env python3
"""
Intent cleaning script for GraphCeylon orchestrator.

Input:
  /Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/generated_intents.csv

Outputs (same folder by default):
  - generated_intents.cleaned.csv
  - generated_intents.dropped.csv
  - generated_intents.summary.json
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd


# ---------------------------
# Config
# ---------------------------
IN_PATH = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/generated_intents.csv")

# If you want outputs elsewhere, change OUT_DIR.
OUT_DIR = IN_PATH.parent

OUT_CLEAN = OUT_DIR / "generated_intents.cleaned.csv"
OUT_DROPPED = OUT_DIR / "generated_intents.dropped.csv"
OUT_SUMMARY = OUT_DIR / "generated_intents.summary.json"


# ---------------------------
# Helpers
# ---------------------------
_WS_RE = re.compile(r"\s+")
_BAD_QUOTES_RE = re.compile(r"[“”‘’]")
_ALLOWED_INTENT_RE = re.compile(r"^[a-z0-9_]{2,64}$")  # e.g., plan_trip, visa_policy, hotel_search

def norm_text(s: str) -> str:
    s = str(s) if s is not None else ""
    s = _BAD_QUOTES_RE.sub("'", s)
    s = s.replace("\u200b", "")  # zero-width space
    s = s.replace("\xa0", " ")   # nbsp
    s = _WS_RE.sub(" ", s).strip()
    return s

def norm_intent(s: str) -> str:
    s = norm_text(s).lower()
    # common normalizations
    s = s.replace("-", "_").replace(" ", "_")
    s = re.sub(r"_+", "_", s).strip("_")
    return s

def detect_columns(df: pd.DataFrame) -> Tuple[str, str]:
    """
    Try to infer (text_col, intent_col) without asking you questions.
    """
    cols = [c.strip() for c in df.columns]
    low = {c.lower(): c for c in cols}

    # likely text columns
    text_candidates = ["text", "utterance", "query", "user_text", "input", "raw_text", "prompt"]
    intent_candidates = ["intent", "label", "pred_intent", "predicted_intent", "class", "category"]

    text_col = None
    intent_col = None

    for k in text_candidates:
        if k in low:
            text_col = low[k]
            break

    for k in intent_candidates:
        if k in low:
            intent_col = low[k]
            break

    if text_col is None:
        # fallback: first column that looks like text (object dtype) and not intent-ish
        for c in cols:
            if df[c].dtype == "object" and "intent" not in c.lower() and "label" not in c.lower():
                text_col = c
                break

    if intent_col is None:
        # fallback: first column containing 'intent' or 'label'
        for c in cols:
            if "intent" in c.lower() or "label" in c.lower():
                intent_col = c
                break

    if text_col is None or intent_col is None:
        raise ValueError(
            f"Couldn't infer columns. Found columns={cols}. "
            "Make sure your CSV has a text column and an intent/label column."
        )

    return text_col, intent_col


@dataclass
class CleanResult:
    clean_df: pd.DataFrame
    dropped_df: pd.DataFrame
    summary: Dict


def clean_intents(df: pd.DataFrame) -> CleanResult:
    text_col, intent_col = detect_columns(df)

    work = df.copy()

    # Normalize text + intent
    work[text_col] = work[text_col].map(norm_text)
    work[intent_col] = work[intent_col].map(norm_intent)

    # Drop empty rows
    reasons: List[str] = []
    keep_mask = []
    for _, row in work[[text_col, intent_col]].iterrows():
        t = row[text_col]
        it = row[intent_col]

        if not t:
            keep_mask.append(False)
            reasons.append("empty_text")
            continue
        if not it:
            keep_mask.append(False)
            reasons.append("empty_intent")
            continue
        if not _ALLOWED_INTENT_RE.match(it):
            keep_mask.append(False)
            reasons.append("bad_intent_format")
            continue

        keep_mask.append(True)
        reasons.append("")

    work["_drop_reason"] = reasons
    keep_mask = pd.Series(keep_mask, index=work.index)

    clean = work.loc[keep_mask].drop(columns=["_drop_reason"])
    dropped = work.loc[~keep_mask].copy()

    # Deduplicate exact (text, intent) pairs
    before_dupes = len(clean)
    clean = clean.drop_duplicates(subset=[text_col, intent_col], keep="first")
    removed_dupes = before_dupes - len(clean)

    # Summary
    summary = {
        "input_rows": int(len(df)),
        "kept_rows": int(len(clean)),
        "dropped_rows": int(len(dropped)),
        "dedup_removed": int(removed_dupes),
        "text_col": text_col,
        "intent_col": intent_col,
        "top_intents": clean[intent_col].value_counts().head(25).to_dict(),
        "drop_reasons": dropped["_drop_reason"].value_counts().to_dict() if len(dropped) else {},
    }

    return CleanResult(clean_df=clean, dropped_df=dropped, summary=summary)


def main() -> None:
    if not IN_PATH.exists():
        raise FileNotFoundError(f"Input CSV not found: {IN_PATH}")

    df = pd.read_csv(IN_PATH)
    result = clean_intents(df)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    result.clean_df.to_csv(OUT_CLEAN, index=False)
    result.dropped_df.to_csv(OUT_DROPPED, index=False)

    with open(OUT_SUMMARY, "w", encoding="utf-8") as f:
        json.dump(result.summary, f, indent=2, ensure_ascii=False)

    print("✅ Done")
    print(f"Input:    {IN_PATH}")
    print(f"Cleaned:  {OUT_CLEAN}  (rows={len(result.clean_df)})")
    print(f"Dropped:  {OUT_DROPPED}  (rows={len(result.dropped_df)})")
    print(f"Summary:  {OUT_SUMMARY}")
    print("\nTop intents:")
    for k, v in list(result.summary["top_intents"].items())[:10]:
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
