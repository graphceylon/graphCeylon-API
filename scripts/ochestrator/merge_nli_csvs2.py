#!/usr/bin/env python3
import argparse
from pathlib import Path
import pandas as pd

REQ_COLS = ["premise", "hypothesis", "label"]

def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in REQ_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{path} is missing columns: {missing}. Found: {list(df.columns)}")
    # normalize whitespace
    for c in ["premise", "hypothesis", "label"]:
        df[c] = df[c].astype(str).str.strip()
    # drop empties
    df = df[(df["premise"] != "") & (df["hypothesis"] != "") & (df["label"] != "")]
    return df

def main():
    ap = argparse.ArgumentParser(description="Merge two NLI CSV files and remove duplicates.")
    ap.add_argument("--base", required=True, help="Base/master CSV")
    ap.add_argument("--add", required=True, help="CSV to add/merge in")
    ap.add_argument("--out", required=True, help="Output merged CSV path")
    ap.add_argument("--dedupe_on", default="premise,hypothesis,label",
                    help="Comma-separated columns to dedupe on (default: premise,hypothesis,label)")
    args = ap.parse_args()

    base_path = Path(args.base).expanduser()
    add_path  = Path(args.add).expanduser()
    out_path  = Path(args.out).expanduser()

    print("[info] Loading files...")
    base_df = load_csv(base_path)
    add_df  = load_csv(add_path)

    print(f"[info] Base rows : {len(base_df)}  ({base_path})")
    print(f"[info] Add rows  : {len(add_df)}  ({add_path})")

    merged = pd.concat([base_df, add_df], ignore_index=True)

    dedupe_cols = [c.strip() for c in args.dedupe_on.split(",") if c.strip()]
    before = len(merged)
    merged = merged.drop_duplicates(subset=dedupe_cols, keep="first")
    removed = before - len(merged)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out_path, index=False)

    print(f"[ok] Removed duplicates: {removed}")
    print(f"[ok] Final rows        : {len(merged)}")
    print("[ok] Label counts:")
    print(merged["label"].value_counts())

if __name__ == "__main__":
    main()
