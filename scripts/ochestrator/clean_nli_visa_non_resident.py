import argparse
import pandas as pd
import re

BAD_NEG = re.compile(r"\bnot\s+unable\b|\bnot\s+not\b|\bcannot\s+not\b", re.I)
BLOB = re.compile(r"(Sightseeing\s*/\s*Holidaying.*Visiting friend|Participate in business meeting.*Participate in symposium)", re.I)
HEADING = re.compile(r"^(Non\s*-\s*Resident\s*Visa\.?|Visit\s*Visa\s*Extension\.?)$", re.I)

def is_bad_row(p: str, h: str) -> bool:
    p = (p or "").strip()
    h = (h or "").strip()
    if not p or not h:
        return True
    if HEADING.match(p) or HEADING.match(h):
        return True
    if BAD_NEG.search(h):
        return True
    # strongly blob-like premises/hypotheses
    if len(p) > 260 or len(h) > 260:
        return True
    if BLOB.search(p) or BLOB.search(h):
        return True
    return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--max_not_true_contra_ratio", type=float, default=0.35)
    args = ap.parse_args()

    df = pd.read_csv(args.inp)
    df = df.dropna(subset=["premise", "hypothesis", "label"]).copy()

    before = len(df)
    df = df[~df.apply(lambda r: is_bad_row(str(r["premise"]), str(r["hypothesis"])), axis=1)]
    print(f"[ok] removed bad rows: {before - len(df)}")

    # dedupe exact rows
    before = len(df)
    df = df.drop_duplicates(subset=["premise", "hypothesis", "label"])
    print(f"[ok] removed duplicates: {before - len(df)}")

    # limit cheap contradiction template: "It is not true that:"
    contra = df[df["label"] == "contradiction"].copy()
    other = df[df["label"] != "contradiction"].copy()

    contra["is_template"] = contra["hypothesis"].astype(str).str.lower().str.startswith("it is not true that:")
    templ = contra[contra["is_template"]]
    hard = contra[~contra["is_template"]]

    # cap template contradictions ratio among contradictions
    max_templ = int(args.max_not_true_contra_ratio * len(contra))
    if len(templ) > max_templ:
        templ = templ.sample(n=max_templ, random_state=42)

    contra2 = pd.concat([templ, hard], ignore_index=True).drop(columns=["is_template"])

    out = pd.concat([other, contra2], ignore_index=True)
    out = out.sample(frac=1, random_state=42).reset_index(drop=True)

    out.to_csv(args.out, index=False)

    print("[ok] wrote:", args.out, "rows:", len(out))
    print(out["label"].value_counts())

if __name__ == "__main__":
    main()
