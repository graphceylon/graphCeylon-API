import re
import pandas as pd
from config import SRC_FULL, OUT_ROOT, OUT_FULL_V2

OUT_ROOT.mkdir(parents=True, exist_ok=True)

REQ_COLS = ["premise", "hypothesis", "label"]
OPTIONAL_COLS = ["negation", "overlap", "domain", "pair_type"]

def ensure_cols(df: pd.DataFrame) -> pd.DataFrame:
    for c in REQ_COLS:
        if c not in df.columns:
            raise ValueError(f"Missing required column: {c}")
    for c in OPTIONAL_COLS:
        if c not in df.columns:
            df[c] = None
    return df

# --- Step A: Rewrite templated negation into implicit contradictions ---
NEG_PATTERNS = [
    r"^\s*It is not true that\s+",
    r"^\s*It's not true that\s+",
    r"^\s*It is false that\s+",
]

def strip_neg_template(text: str) -> str:
    t = str(text).strip()
    for pat in NEG_PATTERNS:
        t = re.sub(pat, "", t, flags=re.IGNORECASE)
    return t.strip()

def implicit_negation_rewrite(h: str) -> str:
    """
    Very simple heuristic rewrite:
    - removes template prefix
    - converts common 'not X' style into factual negative phrasing
    Keep it conservative: better to just remove template than hallucinate new facts.
    """
    t = strip_neg_template(h)

    # If it still contains obvious negation phrase, keep it but remove template.
    # You can add more domain-specific rewrites later.
    return t

def rewrite_negation_rows(df: pd.DataFrame) -> pd.DataFrame:
    if "pair_type" not in df.columns:
        return df

    neg_mask = df["pair_type"].astype(str).eq("negation_contradiction")
    if neg_mask.sum() == 0:
        return df

    neg_df = df.loc[neg_mask].copy()
    neg_df["hypothesis"] = neg_df["hypothesis"].apply(implicit_negation_rewrite)
    neg_df["pair_type"] = "implicit_negation"
    neg_df["negation"] = False

    df_keep = df.loc[~neg_mask].copy()
    return pd.concat([df_keep, neg_df], ignore_index=True)

# --- Step B: Remove pair_type leakage by adding cross-label examples ---
def make_entailment_variant(row: pd.Series) -> dict:
    # safest entailment: hypothesis == premise (perfect entailment)
    return {
        "premise": row["premise"],
        "hypothesis": row["premise"],
        "label": "entailment",
        "negation": False,
        "overlap": 1.0,
        "domain": row.get("domain", "unknown"),
        "pair_type": f"{row.get('pair_type','unknown')}_entail_variant",
    }

def make_contradiction_variant(row: pd.Series) -> dict:
    # conservative contradiction template (generic). Later you can replace with richer contradictions.
    return {
        "premise": row["premise"],
        "hypothesis": "This statement is false based on the given description.",
        "label": "contradiction",
        "negation": False,
        "overlap": 0.0,
        "domain": row.get("domain", "unknown"),
        "pair_type": f"{row.get('pair_type','unknown')}_contra_variant",
    }

def add_variants_for_single_label_pairtypes(df: pd.DataFrame) -> pd.DataFrame:
    if "pair_type" not in df.columns:
        return df

    targets = ["easy_neutral", "hard_neutral"]  # your known leakage buckets
    new_rows = []
    for pt in targets:
        sub = df[df["pair_type"].astype(str) == pt]
        if len(sub) == 0:
            continue

        # add 1 entail + 1 contra per row (you can downsample later if it becomes too big)
        for _, r in sub.iterrows():
            new_rows.append(make_entailment_variant(r))
            new_rows.append(make_contradiction_variant(r))

    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
    return df

# --- Step C: Deduplicate ---
def dedupe(df: pd.DataFrame) -> pd.DataFrame:
    # primary key for NLI examples
    before = len(df)
    df = df.drop_duplicates(subset=["premise", "hypothesis", "label"])
    print("Removed duplicates:", before - len(df))
    return df

def main():
    df = pd.read_csv(SRC_FULL)
    df = ensure_cols(df)

    print("Loaded:", SRC_FULL, "rows=", len(df))

    df = rewrite_negation_rows(df)
    df = add_variants_for_single_label_pairtypes(df)
    df = dedupe(df)

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_FULL_V2, index=False)
    print("Saved full v2:", OUT_FULL_V2, "rows=", len(df))
    print("Label dist:", df["label"].value_counts().to_dict())
    if "pair_type" in df.columns:
        print("Pair_type dist (top10):", df["pair_type"].value_counts().head(10).to_dict())

if __name__ == "__main__":
    main()
