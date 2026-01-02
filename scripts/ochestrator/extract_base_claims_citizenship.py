#!/usr/bin/env python3
"""
Extract atomic base claims from citizenship_services_data.json into a CSV.

Input:  citizenship JSON scraped from immigration.gov.lk (GraphCeylon)
Output: CSV with columns: domain, service_key, page_id, title, source_url, claim

Usage:
  python extract_base_claims_citizenship.py \
    --in /mnt/data/citizenship_services_data.json \
    --out /Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/base_claims_citizenship.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


# -----------------------------
# Text helpers
# -----------------------------
_WS_RE = re.compile(r"\s+")
_BULLET_PREFIX_RE = re.compile(r"^\s*[-•\u2022]\s+")
_NUM_PREFIX_RE = re.compile(r"^\s*(?:\(?\d+[.)]|\(?[a-zA-Z][.)])\s+")

def norm_ws(s: str) -> str:
    return _WS_RE.sub(" ", (s or "").replace("\u00a0", " ")).strip()

def strip_list_prefix(s: str) -> str:
    s = _BULLET_PREFIX_RE.sub("", s)
    s = _NUM_PREFIX_RE.sub("", s)
    return s.strip()

def is_probably_junk(line: str) -> bool:
    """
    Filter out obvious UI / navigation / empty fragments.
    Keep conservative: cleaning script will do stronger pruning later if needed.
    """
    if not line:
        return True
    if len(line) < 12:
        return True
    low = line.lower()

    junk_phrases = [
        "click here", "see note", "see special provisions", "for more information",
        "download", "pdf", "print", "home", "back", "next", "copyright",
    ]
    if any(p in low for p in junk_phrases):
        # still might contain facts, but usually navigation
        return True

    # avoid headings-only lines
    if low in {"note:", "note", "documents required", "how to collect certificate ?"}:
        return True

    return False

def split_into_sentences(text: str) -> List[str]:
    """
    Sentence splitter: safe for policy pages.
    Not perfect, but good enough for base claims generation.
    """
    text = norm_ws(text)
    if not text:
        return []

    # Break on punctuation boundaries.
    # Keep abbreviations conservatively (Act No. 18 of 1948) by not splitting on "No."
    # We'll temporarily protect "No." tokens.
    protected = text.replace("No.", "No<prd>")
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(])", protected)
    out = []
    for p in parts:
        p = p.replace("No<prd>", "No.")
        p = norm_ws(p)
        if p:
            out.append(p)
    return out

def yield_claims_from_text_block(text: str) -> Iterable[str]:
    """
    Convert paragraphs / mixed lists into short factual lines.
    """
    text = norm_ws(text)
    if not text:
        return

    # First split by obvious list separators / line breaks if present
    rough = re.split(r"(?:\n+|•|\u2022)", text)
    for chunk in rough:
        chunk = norm_ws(chunk)
        if not chunk:
            continue

        # If chunk is long, sentence-split it
        if len(chunk) > 240:
            for sent in split_into_sentences(chunk):
                sent = strip_list_prefix(sent)
                sent = norm_ws(sent)
                if sent and not is_probably_junk(sent):
                    yield sent
        else:
            chunk = strip_list_prefix(chunk)
            chunk = norm_ws(chunk)
            if chunk and not is_probably_junk(chunk):
                yield chunk


# -----------------------------
# JSON traversal helpers
# -----------------------------
def safe_get(d: Dict[str, Any], *keys: str, default=None):
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

def iter_pages(doc: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    data = doc.get("data", [])
    for item in data:
        for page in item.get("pages", []) or []:
            if isinstance(page, dict):
                yield page

def extract_page_facts(page: Dict[str, Any]) -> Iterable[str]:
    # Primary: content_text
    content_text = page.get("content_text", "")
    yield from yield_claims_from_text_block(content_text)

    # Sections content
    for sec in page.get("sections", []) or []:
        for c in sec.get("content", []) or []:
            txt = norm_ws(c.get("text", ""))
            yield from yield_claims_from_text_block(txt)

    # Requirements
    for req in page.get("requirements", []) or []:
        txt = norm_ws(req.get("text", ""))
        yield from yield_claims_from_text_block(txt)

    # Procedures (steps)
    for proc in page.get("procedures", []) or []:
        for step in proc.get("steps", []) or []:
            txt = norm_ws(step.get("description", ""))
            yield from yield_claims_from_text_block(txt)
            for detail in step.get("details", []) or []:
                yield from yield_claims_from_text_block(norm_ws(str(detail)))

    # Fees table entries (if present)
    for fee in page.get("fees", []) or []:
        # Some scrapers store fee text; some store structured fields.
        txt = norm_ws(fee.get("text", ""))
        if txt:
            yield from yield_claims_from_text_block(txt)

    # Contact info
    ci = page.get("contact_info", {}) or {}
    addr = norm_ws(ci.get("address", ""))
    wh = norm_ws(ci.get("working_hours", ""))
    email = norm_ws(ci.get("email", ""))
    phone = norm_ws(ci.get("phone", ""))

    if addr:
        yield f"Applications are handled at {addr}"
    if wh:
        yield f"Working hours are {wh}"
    if email:
        yield f"Contact email is {email}"
    if phone:
        yield f"Contact phone is {phone}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input citizenship JSON path")
    ap.add_argument("--out", dest="out", required=True, help="Output CSV path")
    ap.add_argument("--domain", default="citizenship", help="Domain name to store")
    args = ap.parse_args()

    inp = Path(args.inp)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    doc = json.loads(inp.read_text(encoding="utf-8"))

    rows: List[Tuple[str, str, str, str, str, str]] = []
    seen: set[str] = set()

    for page in iter_pages(doc):
        page_id = str(page.get("page_id", ""))
        title = norm_ws(page.get("title", "")) or norm_ws(page.get("service_category", ""))
        url = norm_ws(page.get("url", ""))
        service_key = norm_ws(page.get("service_key", "")) or "citizenship_unknown"

        for claim in extract_page_facts(page):
            claim = norm_ws(claim)
            if not claim or is_probably_junk(claim):
                continue

            # Dedup within extractor stage
            key = f"{service_key}||{claim}"
            if key in seen:
                continue
            seen.add(key)

            rows.append((args.domain, service_key, page_id, title, url, claim))

    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["domain", "service_key", "page_id", "title", "source_url", "claim"])
        w.writerows(rows)

    print(f"[ok] wrote base claims: {len(rows)} -> {out}")


if __name__ == "__main__":
    main()
