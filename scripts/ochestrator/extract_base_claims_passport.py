#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import html
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple


SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")

# Keep only sentences that look like factual rules / requirements / service info
FACTY_RE = re.compile(
    r"\b(required|must|should|will|no longer|cannot|can obtain|eligible|valid|available|only|fee|fees|days|hours|submit|apply|obtain|issued|collect|fingerprints|photograph|documents)\b",
    re.IGNORECASE,
)


def strip_html(text: str) -> str:
    text = html.unescape(text or "")
    text = TAG_RE.sub(" ", text)
    text = WS_RE.sub(" ", text).strip()
    return text


def normalize(text: str) -> str:
    text = strip_html(text)
    # normalize weird spaces
    text = text.replace("–", "-").replace("—", "-")
    return text.strip()


def sentence_candidates(text: str) -> Iterable[str]:
    text = normalize(text)
    if not text:
        return []
    parts = SENT_SPLIT.split(text)
    for s in parts:
        s = s.strip()
        if not s:
            continue
        # make sure it ends with punctuation for clean claims
        if s[-1] not in ".!?":
            s += "."
        yield s


def add_claim(claims: Set[str], s: str) -> None:
    s = normalize(s)
    if not s:
        return
    # ensure period
    if s[-1] not in ".!?":
        s += "."
    # avoid ultra-short junk
    if len(s) < 20:
        return
    claims.add(s)


def extract_from_sections(service_title: str, sections: List[Dict[str, Any]], claims: Set[str]) -> None:
    for sec in sections or []:
        sec_title = (sec.get("title") or "").strip()
        # requirements often appear as list[str] or list[dict]
        reqs = sec.get("requirements") or []
        if isinstance(reqs, list):
            for r in reqs:
                if isinstance(r, str):
                    add_claim(claims, f"{service_title} requires {r}")
                elif isinstance(r, dict):
                    desc = r.get("description") or r.get("text") or ""
                    if desc:
                        add_claim(claims, f"{service_title} requires {desc}")

        steps = sec.get("steps") or []
        if isinstance(steps, list):
            for st in steps:
                if isinstance(st, str):
                    add_claim(claims, f"For {service_title}: {st}")
                elif isinstance(st, dict):
                    n = st.get("step_number")
                    desc = st.get("description") or ""
                    if desc:
                        prefix = f"For {service_title}, step {n}: " if n is not None else f"For {service_title}: "
                        add_claim(claims, prefix + desc)

        # sometimes sections contain free text fields
        for k in ["content_text", "description", "details", "note"]:
            v = sec.get(k)
            if isinstance(v, str):
                for sent in sentence_candidates(v):
                    if FACTY_RE.search(sent):
                        add_claim(claims, sent)


def extract_from_page(page: Dict[str, Any], claims: Set[str]) -> None:
    title = (page.get("title") or page.get("service_category") or page.get("service_key") or "Passport Service").strip()

    # structured “sections”
    sections = page.get("sections") or page.get("content") or []
    if isinstance(sections, list):
        extract_from_sections(title, sections, claims)

    # contact info
    contact = page.get("contact_info") or {}
    if isinstance(contact, dict):
        addr = contact.get("address")
        if addr:
            add_claim(claims, f"{title} address is {addr}")
        hours = contact.get("working_hours")
        if hours and hours != "?":
            add_claim(claims, f"{title} working hours are {hours}")

    # raw text/html blocks
    for k in ["content_text", "content_html"]:
        v = page.get(k)
        if isinstance(v, str) and v.strip():
            for sent in sentence_candidates(v):
                if FACTY_RE.search(sent):
                    add_claim(claims, sent)


def find_pages(root: Any) -> List[Dict[str, Any]]:
    """
    Tries to locate a list of pages anywhere inside the JSON.
    Your file clearly contains page-like objects (page_id, url, title, etc.). :contentReference[oaicite:2]{index=2}
    """
    pages: List[Dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            # page signature
            if ("page_id" in node or "url" in node) and ("title" in node or "content_text" in node or "content_html" in node):
                pages.append(node)  # type: ignore[arg-type]
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for it in node:
                walk(it)

    walk(root)

    # Deduplicate by (page_id,url,title)
    seen: Set[Tuple[Any, Any, Any]] = set()
    uniq: List[Dict[str, Any]] = []
    for p in pages:
        key = (p.get("page_id"), p.get("url"), p.get("title"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to passport_services_data.json")
    ap.add_argument("--output", required=True, help="Path to write base_claims_passport.txt")
    args = ap.parse_args()

    in_path = Path(args.input).expanduser().resolve()
    out_path = Path(args.output).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    root = json.loads(in_path.read_text(encoding="utf-8"))

    pages = find_pages(root)
    claims: Set[str] = set()

    for p in pages:
        extract_from_page(p, claims)

    # final clean + stable sort
    cleaned = sorted({normalize(c) for c in claims if c and len(c) >= 20})

    out_path.write_text("\n".join(cleaned) + "\n", encoding="utf-8")

    print(f"Pages found: {len(pages)}")
    print(f"Saved {len(cleaned)} raw claims -> {out_path}")


if __name__ == "__main__":
    main()
