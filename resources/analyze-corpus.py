#!/usr/bin/env python3
"""
Analyze the STNS parallel corpus to extract terminology, patterns, and style insights.

Reads corpus.jsonl (built by build-corpus.py) and runs three analysis phases:

  Phase 1 — Glossary extraction
    Sends EN/ES headline pairs to Claude in batches. Extracts consistent
    term translations. Saves to corpus-glossary.json.

  Phase 2 — Style pattern analysis
    Samples body text from articles. Claude identifies patterns in number
    formatting, acronym handling, state names, attribution verbs, etc.
    Saves raw observations to corpus-patterns.json.

  Phase 3 — Report generation
    Synthesizes findings into corpus-analysis.md — a structured set of
    additions and corrections for the style guide, plus a draft glossary.

Usage:
    python3 resources/analyze-corpus.py              # all phases
    python3 resources/analyze-corpus.py --phase 1    # glossary only
    python3 resources/analyze-corpus.py --phase 2    # patterns only
    python3 resources/analyze-corpus.py --phase 3    # report only
    python3 resources/analyze-corpus.py --sample 50  # limit body-text sample (phase 2)
"""
import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

# Allow running from resources/ or project root
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from workers.claude_runner import run_claude_p  # tmux-based, bypasses nested-session block

RESOURCES_DIR = Path(__file__).parent
CORPUS_PATH = RESOURCES_DIR / "corpus.jsonl"
GLOSSARY_PATH = RESOURCES_DIR / "corpus-glossary.json"
PATTERNS_PATH = RESOURCES_DIR / "corpus-patterns.json"
REPORT_PATH = RESOURCES_DIR / "corpus-analysis.md"

HEADLINE_BATCH_SIZE = 20   # headlines per Claude call in phase 1
BODY_SAMPLE_SIZE = 80      # articles to sample for phase 2
BODY_EXCERPT_CHARS = 1500  # chars of body text per article in phase 2

CLAUDE_TIMEOUT = 180       # seconds — phase 2 body-text batches
SYNTHESIS_TIMEOUT = 360   # seconds — phase 3 prose report is much larger


# ---------------------------------------------------------------------------
# Claude wrapper
# ---------------------------------------------------------------------------

def run_claude(prompt: str, label: str = "", timeout: int = CLAUDE_TIMEOUT) -> str | None:
    """Run claude -p via tmux (bypasses nested-session restriction)."""
    result = run_claude_p(prompt, session_prefix="analyze", timeout=timeout)
    if result is None:
        print(f"  [timeout/error] {label}", file=sys.stderr)
    return result


def extract_json(text: str) -> list | dict | None:
    """Extract the first JSON array or object from Claude's response."""
    import re
    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    stripped = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped)
    # Try raw parse first
    for candidate in (text.strip(), stripped):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    # Find first [...] or {...} block
    for pattern in (r'\[.*\]', r'\{.*\}'):
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


# ---------------------------------------------------------------------------
# Corpus loading
# ---------------------------------------------------------------------------

def load_corpus() -> list[dict]:
    if not CORPUS_PATH.exists():
        sys.exit(f"Corpus not found: {CORPUS_PATH}\nRun build-corpus.py first.")
    records = []
    with open(CORPUS_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


# ---------------------------------------------------------------------------
# Phase 1: Glossary extraction from headlines
# ---------------------------------------------------------------------------

GLOSSARY_PROMPT = """You are analyzing English-to-Spanish journalism translations from a New Jersey news service targeting US Hispanic readers.

Below are {n} English/Spanish headline pairs. For each pair, identify specific terminology decisions — English terms and their Spanish translations. Focus on:
- Government agency names (ICE, FBI, DEA, NJ Transit, etc.)
- Legal and policy terms (budget, parole, ordinance, etc.)
- NJ-specific place names, institutions, programs
- Medical or technical terms
- Any other domain-specific terms that appear to have a consistent Spanish translation choice

Return ONLY a JSON array. Each element: {{"term_en": "...", "term_es": "...", "category": "..."}}
Do not include whole-headline paraphrases — only specific term pairs.
If no clear term pairs exist in a pair, skip it.

Pairs:
{pairs}"""


def phase1_glossary(records: list[dict]) -> dict:
    print(f"\n=== Phase 1: Glossary extraction ({len(records)} headlines) ===")

    # Filter records with both EN and ES headlines
    pairs = [
        (r["headline_en"], r["headline_es"])
        for r in records
        if r.get("headline_en") and r.get("headline_es")
    ]
    print(f"  Usable pairs: {len(pairs)}")

    # Batch processing
    raw_terms: list[dict] = []
    batches = [pairs[i:i + HEADLINE_BATCH_SIZE] for i in range(0, len(pairs), HEADLINE_BATCH_SIZE)]

    for batch_num, batch in enumerate(batches, 1):
        pairs_text = "\n".join(
            f"EN: {en}\nES: {es}" for en, es in batch
        )
        prompt = GLOSSARY_PROMPT.format(n=len(batch), pairs=pairs_text)
        print(f"  Batch {batch_num}/{len(batches)} ({len(batch)} pairs)...", end=" ", flush=True)

        output = run_claude(prompt, label=f"glossary batch {batch_num}")
        if output is None:
            print("timeout/error — skipped")
            time.sleep(2)
            continue

        terms = extract_json(output)
        if not isinstance(terms, list):
            print(f"bad output ({output[:60]!r}) — skipped")
            continue

        valid = [t for t in terms if isinstance(t, dict) and "term_en" in t and "term_es" in t]
        raw_terms.extend(valid)
        print(f"got {len(valid)} terms")
        time.sleep(1)

    # Aggregate: count how many times each EN→ES pair appeared
    pair_counts: Counter = Counter()
    categories: dict[tuple, list[str]] = defaultdict(list)

    for t in raw_terms:
        key = (t["term_en"].strip().lower(), t["term_es"].strip())
        pair_counts[key] += 1
        if t.get("category"):
            categories[key].append(t["category"])

    # Build glossary sorted by frequency
    glossary = []
    for (en, es), count in pair_counts.most_common():
        cats = categories.get((en, es), [])
        cat = max(set(cats), key=cats.count) if cats else "general"
        glossary.append({
            "term_en": en,
            "term_es": es,
            "frequency": count,
            "category": cat,
        })

    print(f"  Total unique term pairs: {len(glossary)}")

    with open(GLOSSARY_PATH, "w") as f:
        json.dump(glossary, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {GLOSSARY_PATH}")
    return {"glossary": glossary, "raw_count": len(raw_terms)}


# ---------------------------------------------------------------------------
# Phase 2: Style pattern analysis from body text
# ---------------------------------------------------------------------------

PATTERN_PROMPT = """You are analyzing Spanish journalism translations from a New Jersey news service to document consistent style patterns.

Below are excerpts from {n} translated articles. For each of these style areas, identify patterns you observe — both consistent correct usage AND inconsistencies or edge cases:

1. NUMBERS & MONEY — How are large numbers (millions, billions) written? Dollar amounts? Percentages?
2. UNITED STATES — Is it "EE. UU.", "Estados Unidos", "EEUU", "EUA", "EE.UU." (no spaces), or mixed?
3. ACRONYMS — On first use, do they expand with "(por sus siglas en inglés)"? Are there consistent translations for specific agencies (ICE, FBI, etc.)?
4. STATE NAMES — Are Spanish-form names used (Nueva Jersey, Nueva York) or English forms (New Jersey, New York)?
5. ATTRIBUTION VERBS — What verbs beyond "dijo" appear (afirmó, señaló, etc.)? Are they used in variety?
6. MEASUREMENTS — Are feet/miles/pounds kept in US form, or converted to metric?
7. NEW PATTERNS — Any other consistent style choices not covered above?

Return ONLY a JSON array. Each element:
{{
  "area": "numbers|united_states|acronyms|state_names|attribution|measurements|other",
  "observation": "what you observed",
  "examples": ["example from text", "..."],
  "consistent": true|false,
  "recommendation": "suggested style rule addition or confirmation"
}}

Excerpts:
{excerpts}"""


def phase2_patterns(records: list[dict], sample_size: int) -> dict:
    print(f"\n=== Phase 2: Style pattern analysis (sample={sample_size}) ===")

    # Filter records with body text; sample evenly across topics
    with_body = [r for r in records if r.get("spanish_text") and len(r["spanish_text"]) > 200]

    # Try to sample across topics for diversity
    by_topic: dict[str, list] = defaultdict(list)
    for r in with_body:
        topic = (r.get("topics") or ["general"])[0]
        by_topic[topic].append(r)

    sampled = []
    topics = list(by_topic.keys())
    per_topic = max(1, sample_size // len(topics))
    for topic in topics:
        sampled.extend(by_topic[topic][:per_topic])
    sampled = sampled[:sample_size]

    print(f"  Sampled {len(sampled)} articles across {len(by_topic)} topics")

    # Build batches of ~10 excerpts each
    BATCH = 10
    all_observations: list[dict] = []
    batches = [sampled[i:i+BATCH] for i in range(0, len(sampled), BATCH)]

    for batch_num, batch in enumerate(batches, 1):
        excerpts = []
        for r in batch:
            body = r["spanish_text"][:BODY_EXCERPT_CHARS]
            headline = r.get("headline_es") or r.get("headline_en") or ""
            excerpts.append(f"--- {headline[:80]} ---\n{body}")
        excerpts_text = "\n\n".join(excerpts)

        prompt = PATTERN_PROMPT.format(n=len(batch), excerpts=excerpts_text)
        print(f"  Batch {batch_num}/{len(batches)} ({len(batch)} articles)...", end=" ", flush=True)

        output = run_claude(prompt, label=f"patterns batch {batch_num}")
        if output is None:
            print("timeout/error — skipped")
            time.sleep(2)
            continue

        observations = extract_json(output)
        if not isinstance(observations, list):
            print(f"bad output — skipped")
            continue

        valid = [o for o in observations if isinstance(o, dict) and "area" in o]
        all_observations.extend(valid)
        print(f"got {len(valid)} observations")
        time.sleep(1)

    # Group by area
    by_area: dict[str, list] = defaultdict(list)
    for obs in all_observations:
        by_area[obs["area"]].append(obs)

    print(f"  Total observations: {len(all_observations)}")
    print(f"  Areas covered: {list(by_area.keys())}")

    result = {"observations": all_observations, "by_area": dict(by_area)}
    with open(PATTERNS_PATH, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {PATTERNS_PATH}")
    return result


# ---------------------------------------------------------------------------
# Phase 3: Report generation
# ---------------------------------------------------------------------------

SYNTHESIS_PROMPT = """You are helping build an official Spanish translation style guide for NJ journalism newsrooms.

We have analyzed {n_glossary} terminology pairs and {n_obs} style observations from {n_articles} professionally translated articles.

EXISTING STYLE GUIDE RULES (Yuli Delgado, STNS):
{existing_rules}

CORPUS FINDINGS:

Terminology (top 40 most frequent term pairs):
{top_terms}

Style pattern observations:
{pattern_summary}

Based on this corpus evidence, write a structured report with these sections:

1. CONFIRMED RULES — Existing style guide rules confirmed by corpus evidence (cite examples)
2. RULE GAPS — Important patterns found in the corpus that are NOT in the existing guide
3. INCONSISTENCIES — Places where translators diverged from the guide or from each other
4. GLOSSARY ADDITIONS — New EN→ES term pairs worth adding to an official glossary (exclude what's already in the guide)
5. RECOMMENDED GUIDE ADDITIONS — Concrete new rule text, ready to add to the style guide

Write in plain prose (not JSON). Be specific and cite examples from the data."""


EXISTING_RULES_SUMMARY = """
- Quotes: introduce with colon, capitalize first word; add period after quotes ending in ! or ?
- Oxford comma: never use in Spanish
- Acronyms first use: full Spanish name + (por sus siglas en inglés)
- EE. UU. (with spaces after each period) — never USA, US, EEUU
- Numbers: numerals for 10+; spell out 1-9; 1 billion = mil millones (NOT billón)
- Money: US-style punctuation ($1,276.50)
- Measurements: keep US units, do not convert to metric
- State names: Nueva Jersey, Nueva York, Nuevo México, Pensilvania, etc.
- Attributive verbs: expresó, mencionó, comentó, afirmó, declaró, manifestó, señaló, explicó, añadió, sostuvo
- "Humanitarian parole" = permiso humanitario
- Prefixes: no hyphen (expresidente); hyphen before proper nouns/acronyms (anti-Brexit)
- No y/o — use only "o"
"""


def phase3_report(glossary_result: dict | None, patterns_result: dict | None) -> None:
    print(f"\n=== Phase 3: Report generation ===")

    # Load from disk if not provided
    if glossary_result is None:
        if not GLOSSARY_PATH.exists():
            print("  No glossary found — run phase 1 first")
            return
        with open(GLOSSARY_PATH) as f:
            glossary_result = {"glossary": json.load(f)}

    if patterns_result is None:
        if not PATTERNS_PATH.exists():
            print("  No patterns found — run phase 2 first")
            return
        with open(PATTERNS_PATH) as f:
            patterns_result = json.load(f)

    glossary = glossary_result.get("glossary", [])
    observations = patterns_result.get("observations", [])

    # Top 40 terms formatted
    top_terms_lines = []
    for t in glossary[:40]:
        top_terms_lines.append(
            f'  "{t["term_en"]}" → "{t["term_es"]}" [{t["category"]}, freq={t["frequency"]}]'
        )
    top_terms = "\n".join(top_terms_lines) if top_terms_lines else "(none yet)"

    # Pattern summary: group by area, deduplicate
    by_area: dict[str, list] = defaultdict(list)
    for obs in observations:
        by_area[obs.get("area", "other")].append(obs)

    pattern_lines = []
    for area, obs_list in by_area.items():
        pattern_lines.append(f"\n  {area.upper()}:")
        for obs in obs_list[:4]:  # cap per area to keep prompt manageable
            rec = obs.get("recommendation", "")
            examples = obs.get("examples", [])[:2]
            pattern_lines.append(f"    - {obs.get('observation', '')}")
            if examples:
                pattern_lines.append(f"      Examples: {'; '.join(str(e) for e in examples)}")
            if rec:
                pattern_lines.append(f"      Recommendation: {rec}")
    pattern_summary = "\n".join(pattern_lines) or "(none yet)"

    n_articles = len(load_corpus())
    prompt = SYNTHESIS_PROMPT.format(
        n_glossary=len(glossary),
        n_obs=len(observations),
        n_articles=n_articles,
        existing_rules=EXISTING_RULES_SUMMARY,
        top_terms=top_terms,
        pattern_summary=pattern_summary,
    )

    print(f"  Running synthesis ({len(glossary)} terms, {len(observations)} observations)...", flush=True)
    output = run_claude(prompt, label="synthesis", timeout=SYNTHESIS_TIMEOUT)

    if output is None:
        print("  Synthesis timed out")
        return

    # Build the full report
    header = f"""# Corpus analysis report — STNS Spanish translation style guide

*Generated from {n_articles} professionally translated articles (2022–present)*
*{len(glossary)} terminology pairs extracted · {len(observations)} style observations*

---

"""
    report = header + output + "\n\n---\n\n"

    # Append full glossary table
    report += "## Full glossary ({} terms)\n\n".format(len(glossary))
    report += "| English | Spanish | Category | Frequency |\n"
    report += "|---------|---------|----------|-----------|\n"
    for t in glossary:
        report += f"| {t['term_en']} | {t['term_es']} | {t['category']} | {t['frequency']} |\n"

    with open(REPORT_PATH, "w") as f:
        f.write(report)
    print(f"  Saved: {REPORT_PATH}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def wait_for_corpus(min_records: int = 500, poll_interval: int = 30) -> None:
    """Block until corpus.jsonl has at least min_records lines."""
    import subprocess as _sp
    while True:
        count = 0
        if CORPUS_PATH.exists():
            with open(CORPUS_PATH) as f:
                count = sum(1 for _ in f)
        # Also check if build process is still running
        running = _sp.run(
            ["pgrep", "-f", "build-corpus.py"], capture_output=True
        ).returncode == 0
        print(f"  Corpus: {count} records (build {'running' if running else 'done'})")
        if count >= min_records or not running:
            break
        print(f"  Waiting {poll_interval}s...")
        time.sleep(poll_interval)


def main():
    parser = argparse.ArgumentParser(description="Analyze STNS translation corpus")
    parser.add_argument("--phase", type=int, choices=[1, 2, 3], default=0,
                        help="Run a specific phase only (default: all)")
    parser.add_argument("--sample", type=int, default=BODY_SAMPLE_SIZE,
                        help=f"Body-text sample size for phase 2 (default: {BODY_SAMPLE_SIZE})")
    parser.add_argument("--wait", action="store_true",
                        help="Wait for build-corpus.py to finish before analyzing")
    args = parser.parse_args()

    if args.wait:
        print("Waiting for corpus build to complete...")
        wait_for_corpus()

    records = load_corpus()
    print(f"Loaded {len(records)} corpus records")

    glossary_result = None
    patterns_result = None

    run_all = args.phase == 0
    if run_all or args.phase == 1:
        glossary_result = phase1_glossary(records)

    if run_all or args.phase == 2:
        patterns_result = phase2_patterns(records, args.sample)

    if run_all or args.phase == 3:
        phase3_report(glossary_result, patterns_result)

    print("\nDone.")
    if REPORT_PATH.exists():
        print(f"Main output: {REPORT_PATH}")


if __name__ == "__main__":
    main()
