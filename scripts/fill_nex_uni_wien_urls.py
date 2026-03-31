#!/usr/bin/env python3
"""Fill empty uni_wien_url values in the NEX members CSV using Bing Web Search.

Searches for each member's University of Vienna faculty page and writes the
best-matching univie.ac.at URL back to the CSV.

Usage:
    python scripts/fill_nex_uni_wien_urls.py                      # dry-run: print candidates
    python scripts/fill_nex_uni_wien_urls.py --write              # write to CSV
    python scripts/fill_nex_uni_wien_urls.py --write --overwrite  # replace existing values too

Setup:
    1. Create a "Bing Search v7" resource in the Azure portal.
    2. Copy the API key and add it to your .env file:
           BING_SEARCH_API_KEY=<your-key>
    3. Run this script from the project root.
"""

import argparse
import csv
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

NEX_MEMBERS_CSV = _PROJECT_ROOT / "knowledge_base" / "nex_knoweldge" / "nex_members_list.csv"
BING_SEARCH_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"


def _search_bing(query: str, api_key: str) -> list[str]:
    """Return a list of result URLs from Bing Web Search."""
    headers = {"Ocp-Apim-Subscription-Key": api_key}
    params = {"q": query, "count": 10, "mkt": "en-US"}
    response = requests.get(BING_SEARCH_ENDPOINT, headers=headers, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    return [item["url"] for item in data.get("webPages", {}).get("value", [])]


def _pick_univie_url(urls: list[str]) -> str | None:
    """Return the first URL whose domain ends in .univie.ac.at, or None."""
    for url in urls:
        try:
            host = urlparse(url).hostname or ""
            if host.endswith(".univie.ac.at") or host == "univie.ac.at":
                return url
        except Exception:
            continue
    return None


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
        description="Fill empty uni_wien_url values in the NEX members CSV using Bing Search."
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

    api_key = os.environ.get("BING_SEARCH_API_KEY", "")
    if not api_key:
        print("ERROR: BING_SEARCH_API_KEY is not set. Add it to your .env file.", file=sys.stderr)
        sys.exit(1)

    fieldnames, rows = _read_csv(NEX_MEMBERS_CSV)

    if "uni_wien_url" not in fieldnames:
        print(f"ERROR: 'uni_wien_url' column not found in {NEX_MEMBERS_CSV.name}", file=sys.stderr)
        sys.exit(1)

    Result = tuple[str, str, str | None]  # (full_name, query, found_url)
    results: list[Result] = []
    updated = 0

    for row in rows:
        first = row.get("first_name", "").strip()
        last = row.get("last_name", "").strip()
        full_name = f"{first} {last}".strip()
        existing_url = row.get("uni_wien_url", "").strip()

        if existing_url and not args.overwrite:
            continue

        query = f'"{first} {last}" site:univie.ac.at'
        print(f"  Searching: {query}")

        try:
            urls = _search_bing(query, api_key)
        except requests.HTTPError as e:
            print(f"    ERROR for {full_name}: {e}", file=sys.stderr)
            results.append((full_name, query, None))
            continue

        found_url = _pick_univie_url(urls)
        results.append((full_name, query, found_url))

        if found_url and args.write:
            row["uni_wien_url"] = found_url
            updated += 1

    # Print summary table
    print()
    name_width = max((len(name) for name, _, _ in results), default=10) + 2
    print(f"{'Member':<{name_width}}  Candidate URL")
    print("-" * (name_width + 80))
    for name, _, url in results:
        display = url if url else "(no univie.ac.at result found)"
        print(f"{name:<{name_width}}  {display}")

    found_count = sum(1 for _, _, url in results if url)
    print()
    print(f"Found: {found_count}/{len(results)} member(s) with a univie.ac.at URL.")

    if args.write:
        _write_csv(NEX_MEMBERS_CSV, fieldnames, rows)
        print(f"✓ Updated {updated} row(s) in {NEX_MEMBERS_CSV.name}")
    else:
        print("Dry-run — no changes written. Run with --write to save.")


if __name__ == "__main__":
    main()
