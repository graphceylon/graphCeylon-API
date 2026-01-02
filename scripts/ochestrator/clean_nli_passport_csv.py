import re
import pandas as pd
from pathlib import Path

IN_PATH  = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/nli_passport_balanced.csv")
OUT_PATH = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/nli_passport_balanced_clean.csv")

MAX_CHARS = 350  # cap long lines (passport text can get huge)

def normalize_text(s: str) -> str:
    s = str(s).strip()

    # Fix common typos
    s = re.sub(r"\bwill\s+will\b", "will", s, flags=re.I)

    # Basic whitespace cleanup
    s = re.sub(r"\s+", " ", s).strip()

    # Fix common subject-verb agreement errors introduced by templates
    # (not perfect NLP, but it fixes the worst offenders)
    s = re.sub(r"\bWe is\b", "We are", s)
    s = re.sub(r"\bwe is\b", "we are", s)
    s = re.sub(r"\bApplicants is\b", "Applicants are", s)
    s = re.sub(r"\ball applicants is\b", "all applicants are", s, flags=re.I)
    s = re.sub(r"\bAll applicants is\b", "All applicants are", s)

    # Fix "documents is expected" -> "documents are expected"
    s = re.sub(r"\bdocuments is expected\b", "documents are expected", s, flags=re.I)
    s = re.sub(r"\bdocuments is not required\b", "documents are not required", s, flags=re.I)

    # Fix "copies of parents is expected" -> "copies of parents are expected"
    s = re.sub(r"\bcopies of parents is expected\b", "copies of parents are expected", s, flags=re.I)
    s = re.sub(r"\bcopies of parents is not required\b", "copies of parents are not required", s, flags=re.I)

    return s

def main():
    df = pd.read_csv(IN_PATH)

    # Ensure columns exist
    needed = {"premise", "hypothesis", "label"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}. Found: {df.columns.tolist()}")

    # Normalize
    df["premise"] = df["premise"].map(normalize_text)
    df["hypothesis"] = df["hypothesis"].map(normalize_text)

    # Drop empty
    df = df[(df["premise"].str.len() > 0) & (df["hypothesis"].str.len() > 0)]

    # Drop overly long rows (keeps your training clean)
    df = df[(df["premise"].str.len() <= MAX_CHARS) & (df["hypothesis"].str.len() <= MAX_CHARS)]

    # Drop exact duplicates
    before = len(df)
    df = df.drop_duplicates(subset=["premise", "hypothesis", "label"])
    removed = before - len(df)

    df.to_csv(OUT_PATH, index=False)
    print("IN :", IN_PATH)
    print("OUT:", OUT_PATH)
    print("Removed duplicates:", removed)
    print("Rows:", len(df))
    print(df["label"].value_counts())

if __name__ == "__main__":
    main()
