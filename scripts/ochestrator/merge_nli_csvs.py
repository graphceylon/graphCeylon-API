import pandas as pd
from pathlib import Path

BASE = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/nli_final.csv")
ADD  = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/nli_passport_balanced_clean.csv")

OUT  = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/nli_final_plus_passport.csv")

def main():
    base = pd.read_csv(BASE)
    add  = pd.read_csv(ADD)

    # Safety: keep only the 3 columns and same order
    base = base[["premise", "hypothesis", "label"]]
    add  = add[["premise", "hypothesis", "label"]]

    merged = pd.concat([base, add], ignore_index=True)

    # Dedupe after merge
    before = len(merged)
    merged = merged.drop_duplicates(subset=["premise", "hypothesis", "label"])
    removed = before - len(merged)

    # Shuffle for training
    merged = merged.sample(frac=1, random_state=42).reset_index(drop=True)

    merged.to_csv(OUT, index=False)

    print("BASE rows:", len(base))
    print("ADD rows :", len(add))
    print("Removed duplicates after merge:", removed)
    print("FINAL rows:", len(merged))
    print(merged["label"].value_counts())

if __name__ == "__main__":
    main()
