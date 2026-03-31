#!/usr/bin/env python3
"""Fill empty uni_wien_url values in the NEX members CSV using DuckDuckGo search.

Uses a three-pass fallback chain per member:
  1. Department/faculty page on any *.univie.ac.at subdomain
  2. u:cris profile page (ucrisportal.univie.ac.at)
  3. Personal website (requires a second search query)

No API key required. Requires the `ddgs` package: pip install ddgs

Usage:
    python scripts/fill_nex_uni_wien_urls.py                      # dry-run: print candidates
    python scripts/fill_nex_uni_wien_urls.py --write              # write to CSV
    python scripts/fill_nex_uni_wien_urls.py --write --overwrite  # replace existing values too
"""

import argparse
import csv
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from ddgs import DDGS

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

NEX_MEMBERS_CSV = _PROJECT_ROOT / "knowledge_base" / "nex_knoweldge" / "nex_members_list.csv"
_SEARCH_DELAY_SECONDS = 0.5

# URL path segments that indicate a non-profile page — skip these
_SKIP_PATH_PATTERNS = [
    "/news/",
    "/eventsnews/",
    "/artikel/",
    "/fileadmin/",
    "/bilder/",
    "/podcast",
    "/futurethinking/",
    "/download/",
    "tx_news_pi1",
    "controller=news",
    "action=detail",
]

# URL path segments that indicate a person-listing section
_PROFILE_PATH_SIGNALS = [
    "/team/",
    "/staff/",
    "/people/",
    "/persons/",
    "/academic-staff/",
    "/pers/",
    "/mitarbeiter",
    "/professorinnen/",
    "/post-docs/",
    "/wissenschaftliche",
    "/about-us/",
    "/about/",
]

# Non-university domains to skip when searching for personal websites
_AGGREGATOR_DOMAINS = {
    "researchgate.net",
    "scholar.google.com",
    "academia.edu",
    "linkedin.com",
    "orcid.org",
    "semanticscholar.org",
    "pubmed.ncbi.nlm.nih.gov",
    "ncbi.nlm.nih.gov",
    "loop.frontiersin.org",
}

_UMLAUT_TABLE = str.maketrans({"ö": "o", "ü": "u", "ä": "a", "ß": "ss", "é": "e", "è": "e", "à": "a", "ï": "i"})


def _normalize_for_url(text: str) -> str:
    """Lowercase, transliterate umlauts, keep only alphanumeric and hyphens.

    Used to check whether a person's name appears in a URL path.
    """
    text = text.lower().translate(_UMLAUT_TABLE)
    return re.sub(r"[^a-z0-9\-]", "", text.replace(" ", "-"))


def _classify_and_score_url(url: str, first: str, last: str) -> int:
    """Score a URL for relevance as a researcher's profile page.

    Returns -1 to skip, otherwise a positive integer (higher = better).
    The caller uses the score to select the best URL from a list of candidates.

    Score tiers:
      80  dept page with surname in URL path  (best)
      50  dept page without name in URL
      40  ufind.univie.ac.at or homepage.univie.ac.at
      20  ucrisportal.univie.ac.at person page  (u:cris fallback)
       5  non-university URL  (personal website fallback)
      -1  skip (PDF, news article, wrong-person page, etc.)
    """
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        path = parsed.path.lower()
        full_url_lower = url.lower()
    except Exception:
        return -1

    # Skip PDFs and non-HTML files
    if path.endswith((".pdf", ".docx", ".doc", ".pptx", ".xlsx")):
        return -1

    # Skip news/event/CMS pages
    for pattern in _SKIP_PATH_PATTERNS:
        if pattern in full_url_lower:
            return -1

    # u:cris person page
    if host == "ucrisportal.univie.ac.at":
        return 20 if "/persons/" in path else -1

    # University people finder
    if host == "ufind.univie.ac.at":
        return 40

    # Personal university homepage
    if host == "homepage.univie.ac.at":
        return 40

    # Department / faculty subdomains
    if host.endswith(".univie.ac.at") or host == "univie.ac.at":
        # Skip bare root domain pages — too generic
        if path in ("", "/", "/en/", "/de/"):
            return -1

        has_profile_signal = any(sig in path for sig in _PROFILE_PATH_SIGNALS)

        # Check whether the researcher's surname appears in the URL path
        last_norm = _normalize_for_url(last.split()[0])  # use first token of last name
        surname_in_url = last_norm in _normalize_for_url(path)

        if surname_in_url and has_profile_signal:
            return 80
        if has_profile_signal:
            return 50
        if surname_in_url:
            return 45
        return -1  # generic univie page with no person identifier — skip

    # Non-university URL — potential personal website
    if any(agg in host for agg in _AGGREGATOR_DOMAINS):
        return -1
    return 5


def _pick_best_from_scores(scored: list[tuple[int, str]]) -> tuple[str | None, str | None]:
    """From a scored list, return (best_dept_or_ufind_url, best_ucris_url).

    `best_dept_or_ufind_url` is the highest-scored URL with score ≥ 40.
    `best_ucris_url` is the highest-scored URL with score == 20.
    """
    dept_url: str | None = None
    ucris_url: str | None = None
    best_dept_score = -1

    for score, url in scored:
        if score >= 40 and score > best_dept_score:
            best_dept_score = score
            dept_url = url
        if score == 20 and ucris_url is None:
            ucris_url = url

    return dept_url, ucris_url


def _find_best_url(ddgs: DDGS, first: str, last: str) -> str | None:
    """Three-pass URL search for a researcher's University of Vienna web presence.

    Pass 1: department/faculty page on *.univie.ac.at
    Pass 2: u:cris profile page (ucrisportal.univie.ac.at)
    Pass 3: personal website (second search query, only if passes 1 & 2 fail)
    """
    # Search 1: university pages
    query1 = f'"{first} {last}" univie.ac.at'
    raw1 = ddgs.text(query1, max_results=10) or []
    urls1 = [r["href"] for r in raw1]

    scored1 = [(score, url) for url in urls1 if (score := _classify_and_score_url(url, first, last)) >= 0]
    dept_url, ucris_url = _pick_best_from_scores(scored1)

    if dept_url:
        return dept_url  # Pass 1 ✓
    if ucris_url:
        return ucris_url  # Pass 2 ✓

    # Search 2: personal website (only reaches here if no university page found)
    time.sleep(_SEARCH_DELAY_SECONDS)
    query2 = f'"{first} {last}" professor Vienna'
    raw2 = ddgs.text(query2, max_results=5) or []
    for r in raw2:
        url = r.get("href", "")
        score = _classify_and_score_url(url, first, last)
        if score == 5:  # personal website score
            return url  # Pass 3 ✓

    return None  # Pass 4: leave blank


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    return fieldnames, rows


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fill empty uni_wien_url values in the NEX members CSV using DuckDuckGo."
    )
    parser.add_argument("--write", action="store_true", help="Write found URLs back to the CSV.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Also replace existing non-empty uni_wien_url values (implies --write).",
    )
    args = parser.parse_args()

    if args.overwrite:
        args.write = True

    fieldnames, rows = _read_csv(NEX_MEMBERS_CSV)

    if "uni_wien_url" not in fieldnames:
        print(f"ERROR: 'uni_wien_url' column not found in {NEX_MEMBERS_CSV.name}", file=sys.stderr)
        sys.exit(1)

    Result = tuple[str, str | None]  # (full_name, found_url)
    results: list[Result] = []
    updated = 0

    with DDGS() as ddgs:
        for row in rows:
            first = row.get("first_name", "").strip()
            last = row.get("last_name", "").strip()
            full_name = f"{first} {last}".strip()
            existing_url = row.get("uni_wien_url", "").strip()

            if existing_url and not args.overwrite:
                continue

            print(f"  Searching: {full_name}")

            try:
                found_url = _find_best_url(ddgs, first, last)
            except Exception as e:
                print(f"    ERROR for {full_name}: {e}", file=sys.stderr)
                results.append((full_name, None))
                time.sleep(_SEARCH_DELAY_SECONDS)
                continue

            results.append((full_name, found_url))

            if found_url and args.write:
                row["uni_wien_url"] = found_url
                updated += 1

            time.sleep(_SEARCH_DELAY_SECONDS)

    # Print summary table
    if results:
        print()
        name_width = max((len(name) for name, _ in results), default=10) + 2
        print(f"{'Member':<{name_width}}  Candidate URL")
        print("-" * (name_width + 80))
        for name, url in results:
            display = url if url else "(not found)"
            print(f"{name:<{name_width}}  {display}")

        found_count = sum(1 for _, url in results if url)
        print()
        print(f"Found: {found_count}/{len(results)} member(s).")
    else:
        print("All members already have a uni_wien_url. Use --overwrite to re-search.")

    if args.write:
        _write_csv(NEX_MEMBERS_CSV, fieldnames, rows)
        print(f"✓ Updated {updated} row(s) in {NEX_MEMBERS_CSV.name}")
    else:
        print("Dry-run — no changes written. Run with --write to save.")


if __name__ == "__main__":
    main()
