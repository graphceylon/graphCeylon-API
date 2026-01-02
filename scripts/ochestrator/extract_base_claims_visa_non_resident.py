from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


WHITESPACE = re.compile(r"\s+")
BULLET_PREFIX = re.compile(r"^\s*[-•\u2022]+\s*")


def norm_text(s: str) -> str:
    s = s.replace("\u00a0", " ")  # nbsp
    s = WHITESPACE.sub(" ", s).strip()
    s = BULLET_PREFIX.sub("", s).strip()
    return s


def looks_like_noise(s: str) -> bool:
    if not s:
        return True
    low = s.lower()

    # UI-ish / boilerplate fragments
    bad_starts = (
        "click here",
        "download",
        "online",
        "here",
    )
    if any(low == b or low.startswith(b + " ") for b in bad_starts):
        return True

    # too short or just a heading-like fragment
    if len(s) < 12:
        return True

    # pure URL
    if low.startswith("http://") or low.startswith("https://"):
        return True

    return False


def sentence_split(text: str) -> List[str]:
    """
    Conservative split: split on punctuation boundaries, but keep numbered clauses too.
    """
    text = norm_text(text)
    if not text:
        return []
    # split on . ? ! plus handle "02." / "03." etc
    parts = re.split(r"(?<=[.!?])\s+|(?:(?<=\s)|^)(\d{1,2}\.)\s+", text)
    # The regex with capture may insert None / numbers; rebuild cleanly:
    rebuilt: List[str] = []
    buf = ""
    for p in parts:
        if p is None:
            continue
        p = p.strip()
        if not p:
            continue
        if re.fullmatch(r"\d{1,2}\.", p):
            # start a new numbered sentence
            if buf:
                rebuilt.append(buf.strip())
            buf = p
        else:
            if buf and re.fullmatch(r"\d{1,2}\.", buf):
                buf = f"{buf} {p}"
            else:
                if buf:
                    rebuilt.append(buf.strip())
                buf = p
    if buf:
        rebuilt.append(buf.strip())

    # Final cleanup
    out: List[str] = []
    for s in rebuilt:
        s = norm_text(s)
        if s and not looks_like_noise(s):
            # ensure period for uniformity
            if s[-1] not in ".!?":
                s += "."
            out.append(s)
    return out


def iter_text_fields(page: Dict[str, Any]) -> Iterable[Tuple[str, str]]:
    """
    Yield (kind, text) from page parts we care about.
    """
    # page main text
    if page.get("content_text"):
        yield ("content_text", str(page["content_text"]))

    # sections content
    for sec in page.get("sections") or []:
        # heading itself can be useful but often too short (we'll filter)
        if sec.get("heading"):
            yield ("section_heading", str(sec["heading"]))
        for item in sec.get("content") or []:
            t = item.get("text")
            if t:
                yield (f"section_{item.get('type','item')}", str(t))

    # requirements
    for req in page.get("requirements") or []:
        t = req.get("text")
        if t:
            yield ("requirement", str(t))

    # procedures steps
    for proc in page.get("procedures") or []:
        for step in proc.get("steps") or []:
            if step.get("description"):
                yield ("procedure_step", str(step["description"]))
            for det in step.get("details") or []:
                if det:
                    yield ("procedure_detail", str(det))

    # contact info
    ci = page.get("contact_info") or {}
    if ci.get("address"):
        yield ("contact_address", f"Address: {ci['address']}")
    if ci.get("working_hours"):
        yield ("contact_hours", f"Working hours: {ci['working_hours']}")


def derive_service_key(page: Dict[str, Any]) -> str:
    return str(page.get("service_key") or page.get("service_category") or "unknown").strip() or "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="Input JSON file path")
    ap.add_argument("--out", dest="out_path", required=True, help="Output CSV path")
    ap.add_argument("--domain", default="visa_non_resident", help="Domain name to write in CSV")
    args = ap.parse_args()

    in_path = Path(args.in_path)
    out_path = Path(args.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    obj = json.loads(in_path.read_text(encoding="utf-8"))

    # This JSON structure: top-level has "data": [ { metadata..., pages:[...] } ]
    bundles = obj.get("data") or []
    rows: List[Dict[str, str]] = []

    for bundle in bundles:
        pages = bundle.get("pages") or []
        bundle_meta = (bundle.get("metadata") or {})
        source_site = bundle_meta.get("source_website") or "https://www.immigration.gov.lk"

        for page in pages:
            page_id = str(page.get("page_id") or "")
            url = str(page.get("url") or "")
            title = norm_text(str(page.get("title") or "").strip())
            service_key = derive_service_key(page)

            for kind, text in iter_text_fields(page):
                for sent in sentence_split(text):
                    # lightweight pruning: avoid headings repeated verbatim
                    if looks_like_noise(sent):
                        continue
                    rows.append(
                        {
                            "domain": args.domain,
                            "service_key": service_key,
                            "page_id": page_id,
                            "title": title,
                            "source_url": url or source_site,
                            "claim": sent,
                            "source_field": kind,
                        }
                    )

    # de-dup exact claims per service/page
    seen = set()
    deduped = []
    for r in rows:
        key = (r["domain"], r["service_key"], r["page_id"], r["claim"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)

    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["domain", "service_key", "page_id", "title", "source_url", "source_field", "claim"],
        )
        w.writeheader()
        w.writerows(deduped)

    print(f"[ok] wrote base claims: {len(rows)} -> {len(deduped)} -> {out_path}")


if __name__ == "__main__":
    main()
