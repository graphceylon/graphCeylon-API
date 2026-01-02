# make_splits_v3.py
# Input : /Users/dev/Desktop/graphCeylon-API/data/orchestrator/processed/nli_v2/augmented_full_v3.csv
# Output: /Users/dev/Desktop/graphCeylon-API/data/orchestrator/processed/nli_v3/splits/{train,val,test}.csv
# Stratified by label. Keeps your existing test_hard.csv untouched.

from __future__ import annotations

from pathlib import Path
import pandas as pd
from sklearn.model_selection import train_test_split

IN_PATH = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/processed/nli_v2/augmented_full_v3.csv")
OUT_DIR = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/processed/nli_v3/splits")

# ratios (change if you want)
TEST_SIZE = 0.15   # 15% test
VAL_SIZE  = 0.10   # 10% val (of total). We'll compute this from remaining.

RANDOM_SEED = 42

REQUIRED_COLS = ["premise", "hypothesis", "label"]


def _print_dist(df: pd.DataFrame, name: str) -> None:
    print(f"\n{name}: {df.shape}")
    if "label" in df.columns:
        print("Label dist:", df["label"].value_counts().to_dict())
    if "pair_type" in df.columns:
        top = df["pair_type"].value_counts().head(12).to_dict()
        print("Pair_type top12:", top)


def main():
    if not IN_PATH.exists():
        raise FileNotFoundError(f"Input not found: {IN_PATH}")

    df = pd.read_csv(IN_PATH)

    # sanity: required columns
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in CSV: {missing}")

    # drop exact duplicates (safe)
    before = len(df)
    df = df.drop_duplicates(subset=["premise", "hypothesis", "label"]).reset_index(drop=True)
    print(f"Loaded: {IN_PATH} rows={before}")
    print(f"Removed duplicates: {before - len(df)}")

    # remove rows with missing labels
    df = df[df["label"].notna()].reset_index(drop=True)

    # 1) split out TEST (stratified)
    train_val_df, test_df = train_test_split(
        df,
        test_size=TEST_SIZE,
        random_state=RANDOM_SEED,
        stratify=df["label"],
    )

    # 2) split TRAIN vs VAL from remaining
    # We want VAL_SIZE of total; so val fraction of remaining = VAL_SIZE / (1 - TEST_SIZE)
    val_fraction_of_remaining = VAL_SIZE / (1.0 - TEST_SIZE)

    train_df, val_df = train_test_split(
        train_val_df,
        test_size=val_fraction_of_remaining,
        random_state=RANDOM_SEED,
        stratify=train_val_df["label"],
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(OUT_DIR / "train.csv", index=False)
    val_df.to_csv(OUT_DIR / "val.csv", index=False)
    test_df.to_csv(OUT_DIR / "test.csv", index=False)

    # print distributions
    _print_dist(df, "FULL (deduped)")
    _print_dist(train_df, "TRAIN")
    _print_dist(val_df, "VAL")
    _print_dist(test_df, "TEST")

    print(f"\nSaved splits to: {OUT_DIR}")
    print("DONE ✅")


if __name__ == "__main__":
    main()
