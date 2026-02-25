#!/usr/bin/env python3
"""
Build a parallel corpus from the STNS Airtable base.

Pulls all records from the ✅ Submissions table, reads each Google Doc
(Spanish translation), and saves the result to corpus.jsonl.

Corpus record format (one JSON per line):
{
    "airtable_id": str,
    "headline_en": str,        # from Airtable Headline field or Doc header
    "headline_es": str | null, # from Doc (if present as first content line)
    "original_url": str,
    "google_doc_id": str,
    "spanish_text": str,       # full Spanish body from the Doc
    "excerpt_en": str | null,  # Airtable Excerpt field (may be rich text)
    "topics": list[str],
    "status": list[str],
    "added": str,
}

Usage:
    python3 resources/build-corpus.py
    python3 resources/build-corpus.py --limit 20   # test run
    python3 resources/build-corpus.py --resume     # skip already-saved docs
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# --- Airtable ---
AIRTABLE_BASE_ID = "appSlnfrkpWHKL6wV"
AIRTABLE_TABLE_ID = "tbl1DivGEALMspzR8"
AIRTABLE_FIELDS = [
    "Headline", "Original URL", "Translated version",
    "Excerpt", "Story topic(s)", "Status", "Disregard", "Date added",
]

# --- Paths ---
RESOURCES_DIR = Path(__file__).parent
CORPUS_PATH = RESOURCES_DIR / "corpus.jsonl"
DRIVE_TOKEN_PATH = Path.home() / ".claude/google/drive-token.json"
PASS_GET = Path.home() / ".claude/pass-get"


def get_airtable_pat() -> str:
    result = subprocess.run(
        [str(PASS_GET), "claude/tokens/airtable-pat"],
        capture_output=True, text=True, timeout=10,
    )
    token = result.stdout.strip()
    if not token:
        sys.exit("No Airtable PAT found in pass store at claude/tokens/airtable-pat")
    return token


def get_drive_service():
    import json as _json
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    with open(DRIVE_TOKEN_PATH) as f:
        token_data = _json.load(f)
    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data["refresh_token"],
        token_uri=token_data["token_uri"],
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=token_data["scopes"],
    )
    return build("drive", "v3", credentials=creds)


def fetch_all_airtable_records(pat: str) -> list[dict]:
    """Paginate through all records in the Submissions table."""
    import urllib.request
    import urllib.parse

    records = []
    offset = None
    params = {f"fields[]": AIRTABLE_FIELDS}
    base_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}"

    while True:
        query = []
        for field in AIRTABLE_FIELDS:
            query.append(f"fields[]={urllib.parse.quote(field)}")
        if offset:
            query.append(f"offset={offset}")
        url = base_url + "?" + "&".join(query)

        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {pat}"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())

        records.extend(data["records"])
        print(f"  Fetched {len(records)} records...", end="\r")
        offset = data.get("offset")
        if not offset:
            break
        time.sleep(0.2)  # stay under rate limit

    print(f"  Fetched {len(records)} records total.")
    return records


def extract_doc_id(url: str) -> str | None:
    """Extract Google Doc file ID from a Docs URL."""
    match = re.search(r"/document/d/([a-zA-Z0-9_-]+)", url)
    return match.group(1) if match else None


def parse_doc_text(raw: str) -> dict:
    """
    Parse the raw exported Doc text.

    Expected format:
        \ufeffOriginal hed: [English headline]
        Link: [URL]
        [several blank lines]
        [Spanish headline]
        [Spanish byline]
        [Spanish body...]

    Returns dict with keys: headline_en, doc_link, headline_es, spanish_text
    """
    # Labels that appear before or alongside the Spanish headline — skip these
    SKIP_PREFIXES = (
        "translated hed",
        "shorter hed",
        "alternate hed",
        "alt hed",
        "hed:",
    )

    def is_label_line(s: str) -> bool:
        low = s.lower()
        return any(low.startswith(p) for p in SKIP_PREFIXES)

    # Strip BOM and split into lines
    text = raw.lstrip("\ufeff")
    lines = text.splitlines()

    headline_en = None
    doc_link = None
    header_end = 0

    # Parse the header block (first ~10 lines): handle both "Link:" and "link:"
    for i, line in enumerate(lines[:10]):
        stripped = line.strip()
        low = stripped.lower()
        if low.startswith("original hed:"):
            headline_en = stripped[len("original hed:"):].strip()
            header_end = i + 1
        elif low.startswith("link:"):
            doc_link = stripped[stripped.index(":") + 1:].strip()
            header_end = i + 1

    # Find Spanish headline: first non-blank, non-label line after header
    headline_es = None
    body_start = header_end
    for i, line in enumerate(lines[header_end:], start=header_end):
        stripped = line.strip()
        if stripped and not is_label_line(stripped):
            headline_es = stripped
            body_start = i + 1
            break

    spanish_text = "\n".join(lines[body_start:]).strip()
    return {
        "headline_en": headline_en,
        "doc_link": doc_link,
        "headline_es": headline_es,
        "spanish_text": spanish_text,
    }


def fetch_doc_text(service, doc_id: str) -> str | None:
    """Export a Google Doc as plain text via Drive API."""
    try:
        request = service.files().export_media(fileId=doc_id, mimeType="text/plain")
        content = request.execute()
        return content.decode("utf-8", errors="replace")
    except Exception as e:
        return None


def load_already_saved(corpus_path: Path) -> set[str]:
    """Return set of airtable IDs already in corpus.jsonl."""
    if not corpus_path.exists():
        return set()
    saved = set()
    with open(corpus_path) as f:
        for line in f:
            try:
                rec = json.loads(line)
                saved.add(rec["airtable_id"])
            except Exception:
                pass
    return saved


def main():
    parser = argparse.ArgumentParser(description="Build STNS translation corpus")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N records (0 = all)")
    parser.add_argument("--resume", action="store_true", help="Skip records already in corpus.jsonl")
    args = parser.parse_args()

    print("Connecting to Airtable...")
    pat = get_airtable_pat()

    print("Connecting to Google Drive...")
    try:
        drive = get_drive_service()
    except Exception as e:
        sys.exit(f"Failed to connect to Google Drive: {e}")

    print("Fetching Airtable records...")
    records = fetch_all_airtable_records(pat)

    already_saved = set()
    if args.resume:
        already_saved = load_already_saved(CORPUS_PATH)
        print(f"Resuming: {len(already_saved)} records already in corpus")

    # Filter to usable records
    usable = []
    for r in records:
        f = r.get("fields", {})
        if f.get("Disregard"):
            continue
        trans_url = f.get("Translated version", "")
        orig_url = f.get("Original URL", "")
        if not trans_url or not orig_url:
            continue
        doc_id = extract_doc_id(trans_url)
        if not doc_id:
            continue
        if args.resume and r["id"] in already_saved:
            continue
        usable.append((r, doc_id, orig_url, trans_url))

    total = len(usable)
    if args.limit:
        usable = usable[: args.limit]
        print(f"Processing {len(usable)} of {total} usable records (--limit {args.limit})")
    else:
        print(f"Processing {total} usable records")

    saved = 0
    failed = 0
    drive_errors = 0

    mode = "a" if args.resume else "w"
    with open(CORPUS_PATH, mode) as out:
        for i, (record, doc_id, orig_url, trans_url) in enumerate(usable, 1):
            f = record.get("fields", {})
            headline_airtable = f.get("Headline", "")
            excerpt = f.get("Excerpt", "")
            topics = f.get("Story topic(s)", [])
            status = f.get("Status", [])
            added = f.get("Date added", "")

            raw_text = fetch_doc_text(drive, doc_id)
            if raw_text is None:
                drive_errors += 1
                failed += 1
                print(f"[{i}/{len(usable)}] SKIP (drive error) {headline_airtable[:50]}")
                time.sleep(0.5)
                continue

            parsed = parse_doc_text(raw_text)
            headline_en = parsed["headline_en"] or headline_airtable

            corpus_record = {
                "airtable_id": record["id"],
                "headline_en": headline_en,
                "headline_es": parsed["headline_es"],
                "original_url": orig_url,
                "google_doc_id": doc_id,
                "spanish_text": parsed["spanish_text"],
                "excerpt_en": excerpt or None,
                "topics": topics,
                "status": status,
                "added": added,
            }

            out.write(json.dumps(corpus_record, ensure_ascii=False) + "\n")
            out.flush()
            saved += 1

            if i % 10 == 0 or i == len(usable):
                print(f"[{i}/{len(usable)}] saved={saved} failed={failed} | {headline_en[:55]}")

            # Stay well under Drive API quota (300 req/min)
            time.sleep(0.25)

    print(f"\nDone. Saved: {saved}, Failed: {failed} (drive errors: {drive_errors})")
    print(f"Corpus: {CORPUS_PATH}")
    if CORPUS_PATH.exists():
        size_kb = CORPUS_PATH.stat().st_size // 1024
        print(f"Size: {size_kb} KB")


if __name__ == "__main__":
    main()
