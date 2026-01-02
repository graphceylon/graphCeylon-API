import argparse
import re
import pandas as pd

WS = re.compile(r"\s+")
HEADING_LIKE = re.compile(r"^(non\s*-\s*resident\s*visa\.?|visit\s*visa\s*extension\.?)$", re.I)

def norm(s: str) -> str:
    s = (s or "").replace("\u00a0", " ").strip()
    s = WS.sub(" ", s)
    return s

def is_heading(s: str) -> bool:
    return bool(HEADING_LIKE.match(s.strip()))

def rewrite_fragment(s: str) -> str:
    low = s.lower().strip()

    # rewrite fragments into propositions
    if low == "jpg image of data page of valid passport.":
        return "A JPG image of the data page of a valid passport is required."
    if low == "tourist visa return air ticket.":
        return "A return air ticket is required for a tourist visa."
    if low == "return air ticket.":
        return "A return air ticket is required."

    # handle "Required Documents: X"
    if low.startswith("required documents:"):
        rest = s.split(":", 1)[1].strip()
        if rest:
            return f"The following document is required: {rest}"
    return s

def split_list_blob(s: str):
    """
    Split claims that are clearly concatenated items.
    We only split on patterns that look like enumerations.
    """
    s = s.strip()

    # common concatenations from scrape
    if " Participate in " in s and "Not allowed" not in s:
        # e.g. "Participate in A Participate in B ..."
        parts = re.split(r"\s+(?=Participate in\s)", s)
        parts = [p.strip() for p in parts if p.strip()]
        return parts if len(parts) >= 2 else [s]

    # tourism allowed list often glued with no punctuation
    if " Sightseeing" in s and "Not allowed" not in s and " / " in s:
        # split by known activity starters
        starters = [
            "Sightseeing", "Visiting", "Medical treatment", "Participating"
        ]
        out = []
        buf = s
        # brute split by replacing starters with delimiter
        for st in starters:
            buf = buf.replace(st, f"||{st}")
        chunks = [c.strip(" ,;") for c in buf.split("||") if c.strip()]
        for c in chunks:
            # restore if lost prefix
            out.append(c if c[0].isupper() else c.capitalize())
        return out if len(out) >= 2 else [s]

    return [s]

def make_atomic(sent: str) -> str:
    sent = sent.strip().rstrip(";")
    # ensure it reads like a proposition
    if sent.endswith(".") is False:
        sent = sent + "."
    return sent

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    args = ap.parse_args()

    df = pd.read_csv(args.inp)

    # expected columns from your base claims csv
    if "claim" not in df.columns:
        raise SystemExit("CSV must contain a 'claim' column")

    rows = []
    for _, r in df.iterrows():
        claim = norm(str(r["claim"]))
        if not claim or is_heading(claim):
            continue

        claim = rewrite_fragment(claim)

        for piece in split_list_blob(claim):
            piece = norm(piece)
            if not piece or is_heading(piece):
                continue
            piece = rewrite_fragment(piece)
            piece = make_atomic(piece)

            out_row = dict(r)
            out_row["claim"] = piece
            rows.append(out_row)

    out = pd.DataFrame(rows)

    before = len(df)
    out = out.drop_duplicates(subset=["claim"])
    out.to_csv(args.out, index=False)

    print(f"[ok] atomized visa claims: {before} -> {len(out)} rows -> {args.out}")

if __name__ == "__main__":
    main()
