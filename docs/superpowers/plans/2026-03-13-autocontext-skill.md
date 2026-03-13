# Autocontext skill implementation plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude Code plugin that accumulates project knowledge across sessions and developers through structured lessons, hooks, and a curator agent.

**Architecture:** A `.autocontext/` directory per project stores lessons as JSON. Five hooks handle the lifecycle: SessionStart (load + curate), UserPromptSubmit (detect corrections), SessionEnd (persist), PreToolUse (warn on mistakes), PostToolUse (track performance + test quality). Cross-developer sharing via git with a custom merge driver.

**Tech Stack:** Bash (command hooks), Markdown (prompt-based hooks, skills, agents), Python 3.11+ stdlib only (generate-playbook, merge driver), Claude Code plugin system. All config files use JSON (not YAML) to avoid pyyaml dependency.

**Spec:** `docs/superpowers/specs/2026-03-13-autocontext-skill-design.md`

---

## File structure

```
autocontext-plugin/
├── plugin.json                          # Plugin manifest
├── skills/
│   ├── setup.md                         # /autocontext-setup (first-run wizard)
│   ├── init.md                          # /autocontext-init (per-project setup)
│   ├── review.md                        # /autocontext-review (curate lessons)
│   └── status.md                        # /autocontext-status (show stats)
├── hooks/
│   ├── session-start.sh                 # Load lessons + curate pending (command hook)
│   ├── user-prompt-submit.sh            # Detect correction patterns (command hook)
│   ├── session-end.sh                   # Persist metadata + bump counts (command hook)
│   ├── pre-tool-use.md                  # Warn on known mistakes (prompt-based hook)
│   └── post-tool-use.sh                 # Performance + deterministic test checks (command hook)
├── agents/
│   └── curator.md                       # Curator agent for lesson validation
├── scripts/
│   ├── generate-playbook.py             # Regenerate playbook.md from lessons.json
│   ├── merge-driver.py                  # Git merge driver for lessons.json
│   └── seed-from-claude-md.py           # Extract lessons from existing CLAUDE.md
├── templates/
│   ├── config.yaml                      # Default project config
│   ├── config.local.yaml                # Default local config
│   ├── lessons.json                     # Empty initial lessons file
│   └── gitignore                        # .autocontext/.gitignore template
└── tests/
    ├── test_generate_playbook.py        # Playbook generation tests
    ├── test_merge_driver.py             # Merge driver tests
    ├── test_seed_from_claude_md.py       # CLAUDE.md extraction tests
    ├── test_session_start.sh            # SessionStart hook tests
    ├── test_user_prompt_submit.sh       # UserPromptSubmit hook tests
    ├── test_session_end.sh              # SessionEnd hook tests
    └── test_post_tool_use.sh            # PostToolUse hook tests
```

---

## Chunk 1: Plugin scaffold + knowledge model

### Task 1: Create plugin manifest

**Files:**
- Create: `autocontext-plugin/plugin.json`

- [ ] **Step 1: Write plugin.json**

```json
{
  "name": "autocontext",
  "version": "0.1.0",
  "description": "Accumulates project knowledge across sessions and developers through structured lessons and hooks",
  "author": "jamditis"
}
```

- [ ] **Step 2: Verify plugin structure is valid**

Run: `cat autocontext-plugin/plugin.json | python3 -c "import sys,json; json.load(sys.stdin); print('valid')"`
Expected: `valid`

- [ ] **Step 3: Commit**

```bash
git add autocontext-plugin/plugin.json
git commit -m "feat: initialize autocontext plugin scaffold"
```

### Task 2: Create template files

**Files:**
- Create: `autocontext-plugin/templates/config.json`
- Create: `autocontext-plugin/templates/config.local.json`
- Create: `autocontext-plugin/templates/lessons.json`
- Create: `autocontext-plugin/templates/gitignore`
- Create: `autocontext-plugin/templates/gitattributes`

- [ ] **Step 1: Write default config.json template**

All config uses JSON (not YAML) to avoid any non-stdlib dependency.

```json
{
  "project_name": "",
  "max_session_lessons": 15,
  "confidence_threshold": 0.3,
  "staleness_days": 60,
  "performance_baselines": true,
  "pretooluse_hook": true,
  "persistence_mode": "auto_curated",
  "baseline_commands": [
    "pytest", "npm test", "npm run test", "npm run build",
    "cargo test", "go test", "vitest", "jest", "make test"
  ],
  "baselines": {},
  "builtin_rules": {
    "tautological_test_check": true,
    "no_mock_everything": true,
    "no_happy_path_only": true,
    "no_assert_true": true,
    "test_independence": true
  }
}
```

`persistence_mode` values: `"auto_curated"` (default), `"ask_before_persist"`, `"auto_all"`.

- [ ] **Step 2: Write default config.local.json template**

```json
{
  "_comment": "Gitignored. Set your identity for lesson attribution.",
  "identity": ""
}
```

- [ ] **Step 3: Write empty lessons.json template**

```json
[]
```

- [ ] **Step 4: Write .gitignore template**

```
config.local.json
cache/
```

- [ ] **Step 5: Write .gitattributes template**

```
lessons.json merge=autocontext-union
```

- [ ] **Step 6: Verify templates are valid**

Run: `for f in autocontext-plugin/templates/config.json autocontext-plugin/templates/config.local.json autocontext-plugin/templates/lessons.json; do python3 -c "import json; json.load(open('$f')); print('$f ok')"; done`
Expected: All three files report `ok`.

- [ ] **Step 6: Commit**

```bash
git add autocontext-plugin/templates/
git commit -m "feat: add template files for project initialization"
```

### Task 3: Write generate-playbook.py

**Files:**
- Create: `autocontext-plugin/scripts/generate-playbook.py`
- Create: `autocontext-plugin/tests/test_generate_playbook.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for generate-playbook.py"""
import json
import tempfile
import os
import subprocess
import sys

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "generate-playbook.py")


def _run(lessons_data, expect_success=True):
    """Run generate-playbook.py with given lessons data, return playbook text."""
    with tempfile.TemporaryDirectory() as d:
        lessons_path = os.path.join(d, "lessons.json")
        playbook_path = os.path.join(d, "playbook.md")
        with open(lessons_path, "w") as f:
            json.dump(lessons_data, f)
        result = subprocess.run(
            [sys.executable, SCRIPT, lessons_path, playbook_path],
            capture_output=True, text=True,
        )
        if expect_success:
            assert result.returncode == 0, f"Failed: {result.stderr}"
            with open(playbook_path) as f:
                return f.read()
        return result


def test_empty_lessons():
    playbook = _run([])
    assert "0 active lessons" in playbook


def test_groups_by_category():
    lessons = [
        {"id": "a", "category": "efficiency", "text": "Use trailing slash", "confidence": 0.9,
         "validated_count": 3, "tags": ["api"], "deleted": False},
        {"id": "b", "category": "codebase", "text": "Schema uses UUID", "confidence": 0.8,
         "validated_count": 1, "tags": ["db"], "deleted": False},
    ]
    playbook = _run(lessons)
    assert "## Efficiency" in playbook
    assert "## Codebase" in playbook
    assert "Use trailing slash" in playbook
    assert "Schema uses UUID" in playbook


def test_excludes_deleted():
    lessons = [
        {"id": "a", "category": "efficiency", "text": "Active lesson", "confidence": 0.9,
         "validated_count": 1, "tags": [], "deleted": False},
        {"id": "b", "category": "efficiency", "text": "Deleted lesson", "confidence": 0.5,
         "validated_count": 0, "tags": [], "deleted": True},
    ]
    playbook = _run(lessons)
    assert "Active lesson" in playbook
    assert "Deleted lesson" not in playbook
    assert "1 active lessons" in playbook


def test_sorts_by_confidence():
    lessons = [
        {"id": "a", "category": "efficiency", "text": "Low conf", "confidence": 0.3,
         "validated_count": 1, "tags": [], "deleted": False},
        {"id": "b", "category": "efficiency", "text": "High conf", "confidence": 0.9,
         "validated_count": 5, "tags": [], "deleted": False},
    ]
    playbook = _run(lessons)
    high_pos = playbook.index("High conf")
    low_pos = playbook.index("Low conf")
    assert high_pos < low_pos


def test_shows_confidence_and_tags():
    lessons = [
        {"id": "a", "category": "optimization", "text": "Cache is slow", "confidence": 0.75,
         "validated_count": 2, "tags": ["perf", "cache"], "deleted": False},
    ]
    playbook = _run(lessons)
    assert "[0.75]" in playbook or "[0.8]" in playbook  # Allow rounding
    assert "perf" in playbook
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd autocontext-plugin && python3 -m pytest tests/test_generate_playbook.py -v`
Expected: FAIL (script doesn't exist yet)

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
"""Generate playbook.md from lessons.json.

Usage: generate-playbook.py <lessons.json path> <playbook.md path>

No dependencies beyond Python stdlib.
"""
import json
import sys
from datetime import datetime, timezone


def generate(lessons_path: str, playbook_path: str) -> None:
    with open(lessons_path) as f:
        lessons = json.load(f)

    active = [l for l in lessons if not l.get("deleted", False)]
    active.sort(key=lambda l: l.get("confidence", 0), reverse=True)

    categories = {}
    for lesson in active:
        cat = lesson.get("category", "uncategorized")
        categories.setdefault(cat, []).append(lesson)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        f"# Project playbook (auto-generated)",
        f"Last updated: {now} | {len(active)} active lessons",
        "",
    ]

    for cat_name in ["efficiency", "codebase", "optimization", "uncategorized"]:
        cat_lessons = categories.get(cat_name, [])
        if not cat_lessons:
            continue
        lines.append(f"## {cat_name.capitalize()} ({len(cat_lessons)} lessons)")
        for lesson in cat_lessons:
            conf = lesson.get("confidence", 0)
            tags = ", ".join(lesson.get("tags", []))
            tag_str = f" ({tags})" if tags else ""
            lines.append(f"- **[{conf}]** {lesson['text']}{tag_str}")
        lines.append("")

    with open(playbook_path, "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <lessons.json> <playbook.md>", file=sys.stderr)
        sys.exit(1)
    generate(sys.argv[1], sys.argv[2])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd autocontext-plugin && python3 -m pytest tests/test_generate_playbook.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add autocontext-plugin/scripts/generate-playbook.py autocontext-plugin/tests/test_generate_playbook.py
git commit -m "feat: add playbook generation script with tests"
```

### Task 4: Write merge-driver.py

**Files:**
- Create: `autocontext-plugin/scripts/merge-driver.py`
- Create: `autocontext-plugin/tests/test_merge_driver.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for merge-driver.py — lessons.json three-way merge."""
import json
import tempfile
import os
import subprocess
import sys

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "merge-driver.py")


def _merge(ancestor, ours, theirs):
    """Run merge driver, return merged lessons list."""
    with tempfile.TemporaryDirectory() as d:
        paths = {}
        for name, data in [("ancestor", ancestor), ("ours", ours), ("theirs", theirs)]:
            p = os.path.join(d, f"{name}.json")
            with open(p, "w") as f:
                json.dump(data, f)
            paths[name] = p
        result = subprocess.run(
            [sys.executable, SCRIPT, paths["ancestor"], paths["ours"], paths["theirs"]],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Merge failed: {result.stderr}"
        return json.loads(result.stdout)


def test_union_new_lessons():
    ancestor = []
    ours = [{"id": "a", "text": "lesson A", "validated_count": 1, "confidence": 0.5,
             "deleted": False, "tags": ["x"]}]
    theirs = [{"id": "b", "text": "lesson B", "validated_count": 1, "confidence": 0.5,
               "deleted": False, "tags": ["y"]}]
    merged = _merge(ancestor, ours, theirs)
    ids = {l["id"] for l in merged}
    assert ids == {"a", "b"}


def test_additive_validated_count():
    ancestor = [{"id": "a", "text": "lesson", "validated_count": 5, "confidence": 0.7,
                 "deleted": False, "tags": [], "last_validated": "2026-03-01T00:00:00Z"}]
    ours = [{"id": "a", "text": "lesson", "validated_count": 7, "confidence": 0.8,
             "deleted": False, "tags": [], "last_validated": "2026-03-10T00:00:00Z"}]
    theirs = [{"id": "a", "text": "lesson", "validated_count": 8, "confidence": 0.75,
               "deleted": False, "tags": [], "last_validated": "2026-03-12T00:00:00Z"}]
    merged = _merge(ancestor, ours, theirs)
    lesson = merged[0]
    # ours added 2, theirs added 3, total from ancestor = 5 + 2 + 3 = 10
    assert lesson["validated_count"] == 10
    assert lesson["confidence"] == 0.8  # higher wins
    assert lesson["last_validated"] == "2026-03-12T00:00:00Z"  # most recent


def test_deleted_wins():
    ancestor = [{"id": "a", "text": "lesson", "validated_count": 1, "confidence": 0.5,
                 "deleted": False, "tags": []}]
    ours = [{"id": "a", "text": "lesson", "validated_count": 1, "confidence": 0.5,
             "deleted": True, "tags": []}]
    theirs = [{"id": "a", "text": "lesson", "validated_count": 2, "confidence": 0.6,
               "deleted": False, "tags": []}]
    merged = _merge(ancestor, ours, theirs)
    assert merged[0]["deleted"] is True


def test_tags_union():
    ancestor = [{"id": "a", "text": "lesson", "validated_count": 1, "confidence": 0.5,
                 "deleted": False, "tags": ["common"]}]
    ours = [{"id": "a", "text": "lesson", "validated_count": 1, "confidence": 0.5,
             "deleted": False, "tags": ["common", "ours-tag"]}]
    theirs = [{"id": "a", "text": "lesson", "validated_count": 1, "confidence": 0.5,
               "deleted": False, "tags": ["common", "theirs-tag"]}]
    merged = _merge(ancestor, ours, theirs)
    assert set(merged[0]["tags"]) == {"common", "ours-tag", "theirs-tag"}


def test_text_conflict_flags_review():
    ancestor = [{"id": "a", "text": "original text", "validated_count": 1, "confidence": 0.5,
                 "deleted": False, "tags": []}]
    ours = [{"id": "a", "text": "our edit", "validated_count": 1, "confidence": 0.5,
             "deleted": False, "tags": []}]
    theirs = [{"id": "a", "text": "their edit", "validated_count": 1, "confidence": 0.5,
               "deleted": False, "tags": []}]
    merged = _merge(ancestor, ours, theirs)
    assert merged[0].get("needs_review") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd autocontext-plugin && python3 -m pytest tests/test_merge_driver.py -v`
Expected: FAIL (script doesn't exist yet)

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
"""Three-way merge driver for lessons.json.

Usage: merge-driver.py <ancestor> <ours> <theirs>
Outputs merged JSON to stdout. Exit 0 on success.

Per-field resolution rules:
- validated_count: additive from ancestor
- confidence: higher value wins
- last_validated: most recent wins
- deleted: true wins (if either side deleted)
- tags: union of both sides
- text/context/category: if different, flag needs_review
- supersedes: non-null wins; if both non-null, flag needs_review
"""
import json
import sys


def merge_lesson(ancestor, ours, theirs):
    """Merge a single lesson modified on both sides."""
    result = dict(ours)  # Start from ours

    # Additive validated_count
    anc_count = (ancestor or {}).get("validated_count", 0)
    ours_delta = ours.get("validated_count", 0) - anc_count
    theirs_delta = theirs.get("validated_count", 0) - anc_count
    result["validated_count"] = anc_count + max(0, ours_delta) + max(0, theirs_delta)

    # Higher confidence
    result["confidence"] = max(ours.get("confidence", 0), theirs.get("confidence", 0))

    # Most recent last_validated
    ours_lv = ours.get("last_validated", "")
    theirs_lv = theirs.get("last_validated", "")
    result["last_validated"] = max(ours_lv, theirs_lv)

    # Deleted wins
    if ours.get("deleted") or theirs.get("deleted"):
        result["deleted"] = True

    # Tags union
    ours_tags = set(ours.get("tags", []))
    theirs_tags = set(theirs.get("tags", []))
    result["tags"] = sorted(ours_tags | theirs_tags)

    # Text/context/category conflicts
    for field in ("text", "context", "category"):
        if ours.get(field) != theirs.get(field):
            anc_val = (ancestor or {}).get(field)
            if ours.get(field) != anc_val and theirs.get(field) != anc_val:
                # Both sides changed — conflict
                result["needs_review"] = True
                break

    # Supersedes conflicts
    ours_sup = ours.get("supersedes")
    theirs_sup = theirs.get("supersedes")
    if ours_sup and theirs_sup and ours_sup != theirs_sup:
        result["needs_review"] = True
    elif theirs_sup and not ours_sup:
        result["supersedes"] = theirs_sup

    return result


def merge(ancestor_path, ours_path, theirs_path):
    with open(ancestor_path) as f:
        ancestor = {l["id"]: l for l in json.load(f)}
    with open(ours_path) as f:
        ours = {l["id"]: l for l in json.load(f)}
    with open(theirs_path) as f:
        theirs = {l["id"]: l for l in json.load(f)}

    all_ids = set(ancestor) | set(ours) | set(theirs)
    merged = []

    for lid in sorted(all_ids):
        in_anc = lid in ancestor
        in_ours = lid in ours
        in_theirs = lid in theirs

        if in_ours and in_theirs:
            if ours[lid] == theirs[lid]:
                merged.append(ours[lid])
            else:
                merged.append(merge_lesson(
                    ancestor.get(lid), ours[lid], theirs[lid]
                ))
        elif in_ours:
            merged.append(ours[lid])
        elif in_theirs:
            merged.append(theirs[lid])
        # If only in ancestor, both sides deleted it — omit

    return merged


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <ancestor> <ours> <theirs>", file=sys.stderr)
        sys.exit(1)
    result = merge(sys.argv[1], sys.argv[2], sys.argv[3])
    print(json.dumps(result, indent=2))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd autocontext-plugin && python3 -m pytest tests/test_merge_driver.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add autocontext-plugin/scripts/merge-driver.py autocontext-plugin/tests/test_merge_driver.py
git commit -m "feat: add three-way merge driver for lessons.json"
```

---

## Chunk 2: Command hooks (SessionStart, UserPromptSubmit, SessionEnd)

### Task 5: Write SessionStart hook

**Files:**
- Create: `autocontext-plugin/hooks/session-start.sh`

The SessionStart hook does two things: (1) curate pending lessons from the previous session via `claude -p`, and (2) load and cache lessons for the current session.

Reference: Claude Code hooks receive JSON on stdin with `session_id`, `cwd`, and other fields. The hook outputs JSON to stdout with a `result` field. For SessionStart, the output format is `{"hookResponse": {"message": "text to inject"}}`.

- [ ] **Step 1: Write the hook script**

```bash
#!/usr/bin/env bash
# SessionStart hook: load lessons + curate pending candidates from previous session.
# Receives JSON on stdin. Outputs hookResponse JSON to stdout.
set -euo pipefail

# Read hook input
INPUT=$(cat)
CWD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd','.'))")

AUTOCONTEXT_DIR="$CWD/.autocontext"
LESSONS_FILE="$AUTOCONTEXT_DIR/lessons.json"
CACHE_DIR="$AUTOCONTEXT_DIR/cache"
PENDING_FILE="$CACHE_DIR/pending-lessons.json"
SESSION_CACHE="$CACHE_DIR/session-lessons.json"
CONFIG_FILE="$AUTOCONTEXT_DIR/config.yaml"
LOCAL_CONFIG="$AUTOCONTEXT_DIR/config.local.yaml"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$(dirname "$0")")}"

# Exit silently if no .autocontext directory
if [ ! -d "$AUTOCONTEXT_DIR" ]; then
    echo '{}'
    exit 0
fi

mkdir -p "$CACHE_DIR"

# Phase 1: Curate pending lessons from previous session
if [ -f "$PENDING_FILE" ] && [ -s "$PENDING_FILE" ]; then
    PENDING_COUNT=$(python3 -c "import json; print(len(json.load(open('$PENDING_FILE'))))" 2>/dev/null || echo "0")
    if [ "$PENDING_COUNT" -gt 0 ]; then
        # Read curator prompt from agent definition
        CURATOR_PROMPT="You are a knowledge curator. Given lesson candidates from a previous session, decide which are worth persisting.

A good lesson:
- Is specific to this project (not general programming knowledge)
- Is actionable (tells a future session what to do or avoid)
- Would save time if known at session start
- NEVER includes secrets, API keys, tokens, passwords, or PII

Reject if:
- General knowledge any developer would know
- Too vague to act on
- About a one-time task that won't recur

Input: the pending candidates JSON.
Output JSON: {\"lessons\": [{\"category\": \"efficiency|codebase|optimization\", \"text\": \"...\", \"context\": \"...\", \"tags\": [\"...\"]}]}
If none are worth keeping: {\"lessons\": []}"

        PENDING_CONTENT=$(cat "$PENDING_FILE")
        CURATED=$(echo "$PENDING_CONTENT" | timeout --foreground 45 claude -p "$CURATOR_PROMPT" 2>/dev/null || echo '{"lessons":[]}')

        # Merge curated lessons into lessons.json
        python3 -c "
import json, uuid, sys
from datetime import datetime, timezone

curated_raw = '''$CURATED'''
try:
    curated = json.loads(curated_raw)
except:
    sys.exit(0)

lessons_path = '$LESSONS_FILE'
try:
    with open(lessons_path) as f:
        lessons = json.load(f)
except:
    lessons = []

existing_texts = {l['text'] for l in lessons if not l.get('deleted')}
now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

for cl in curated.get('lessons', []):
    if cl.get('text') and cl['text'] not in existing_texts:
        lessons.append({
            'id': 'lesson_' + uuid.uuid4().hex[:8],
            'schema_version': 1,
            'category': cl.get('category', 'efficiency'),
            'text': cl['text'],
            'context': cl.get('context', ''),
            'confidence': 0.5,
            'validated_count': 0,
            'last_validated': now,
            'created': now,
            'created_by': '',  # filled below
            'supersedes': None,
            'deleted': False,
            'tags': cl.get('tags', []),
        })

with open(lessons_path, 'w') as f:
    json.dump(lessons, f, indent=2)
" 2>/dev/null || true

        # Regenerate playbook
        python3 "$PLUGIN_ROOT/scripts/generate-playbook.py" "$LESSONS_FILE" "$AUTOCONTEXT_DIR/playbook.md" 2>/dev/null || true

        # Clean up pending file
        rm -f "$PENDING_FILE"
    fi
fi

# Phase 2: Load and cache lessons for this session
if [ ! -f "$LESSONS_FILE" ]; then
    echo '{}'
    exit 0
fi

# Filter and rank lessons, write cache, output context message
MESSAGE=$(python3 -c "
import json, subprocess, os

lessons_path = '$LESSONS_FILE'
config_path = '$CONFIG_FILE'
cache_path = '$SESSION_CACHE'
cwd = '$CWD'

try:
    with open(lessons_path) as f:
        lessons = json.load(f)
except:
    print('[autocontext] Warning: lessons.json is malformed. Skipping lesson injection.')
    exit(0)

# Read config
max_lessons = 15
threshold = 0.3
try:
    import yaml
    with open(config_path) as f:
        config = yaml.safe_load(f) or {}
    max_lessons = config.get('max_session_lessons', 15)
    threshold = config.get('confidence_threshold', 0.3)
    project_name = config.get('project_name', '')
except:
    project_name = ''

# Filter
import socket
hostname = socket.gethostname()
active = []
for l in lessons:
    if l.get('deleted'):
        continue
    if l.get('confidence', 0) < threshold:
        continue
    # Filter machine-specific tags
    machine_tags = [t for t in l.get('tags', []) if t.startswith('machine:')]
    if machine_tags and not any(t == f'machine:{hostname}' for t in machine_tags):
        continue
    active.append(l)

# Rank by relevance
try:
    result = subprocess.run(
        ['git', 'diff', '--name-only', 'HEAD~5..HEAD'],
        capture_output=True, text=True, cwd=cwd, timeout=5
    )
    recent_files = set(result.stdout.strip().split('\n')) if result.returncode == 0 else set()
except:
    recent_files = set()

def relevance(l):
    tags = set(l.get('tags', []))
    file_match = 1 if tags & recent_files else 0
    return (file_match, l.get('confidence', 0), l.get('last_validated', ''))

active.sort(key=relevance, reverse=True)
selected = active[:max_lessons]

# Write cache for PreToolUse hook
with open(cache_path, 'w') as f:
    json.dump(selected, f, indent=2)

# Check merge driver
try:
    result = subprocess.run(
        ['git', 'config', 'merge.autocontext-union.driver'],
        capture_output=True, text=True, cwd=cwd, timeout=5
    )
    merge_ok = result.returncode == 0
except:
    merge_ok = True  # Don't warn if git isn't available

# Format output
if not selected:
    if not merge_ok:
        print('[autocontext] Warning: merge driver not configured. Run /autocontext-init.')
    exit(0)

cats = {}
for l in selected:
    cats.setdefault(l.get('category', '?'), []).append(l)

cat_summary = ', '.join(f'{len(v)} {k}' for k, v in sorted(cats.items()))
name = f' for {project_name}' if project_name else ''
lines = [f'[autocontext] Loaded {len(selected)} lessons{name} ({cat_summary})']
lines.append('Top lessons for current work area:')
for l in selected[:5]:
    lines.append(f'- [{l.get(\"confidence\", 0)}] {l[\"text\"]}')

if not merge_ok:
    lines.append('')
    lines.append('[autocontext] Warning: merge driver not configured. Run /autocontext-init.')

print('\n'.join(lines))
" 2>/dev/null)

if [ -n "$MESSAGE" ]; then
    python3 -c "
import json, sys
msg = '''$MESSAGE'''
print(json.dumps({'hookResponse': {'message': msg}}))
"
else
    echo '{}'
fi
```

- [ ] **Step 2: Make executable**

Run: `chmod +x autocontext-plugin/hooks/session-start.sh`

- [ ] **Step 3: Commit**

```bash
git add autocontext-plugin/hooks/session-start.sh
git commit -m "feat: add SessionStart hook (load lessons + curate pending)"
```

### Task 6: Write UserPromptSubmit hook

**Files:**
- Create: `autocontext-plugin/hooks/user-prompt-submit.sh`

- [ ] **Step 1: Write the hook script**

```bash
#!/usr/bin/env bash
# UserPromptSubmit hook: detect correction patterns in user messages.
# Lightweight pattern matching — no LLM call.
set -euo pipefail

INPUT=$(cat)
CWD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd','.'))")
AUTOCONTEXT_DIR="$CWD/.autocontext"
CACHE_DIR="$AUTOCONTEXT_DIR/cache"
PENDING_FILE="$CACHE_DIR/pending-lessons.json"

# Exit silently if no .autocontext directory
if [ ! -d "$AUTOCONTEXT_DIR" ]; then
    echo '{}'
    exit 0
fi

mkdir -p "$CACHE_DIR"

# Extract user message and check for correction patterns
python3 -c "
import json, sys, re
from datetime import datetime, timezone

input_data = json.loads('''$(echo "$INPUT" | python3 -c "import sys; print(sys.stdin.read().replace(\"'''\", \"'''\"))")''')
user_message = input_data.get('user_message', input_data.get('content', ''))
if not isinstance(user_message, str):
    sys.exit(0)

# Correction patterns (case-insensitive)
patterns = [
    r'no[,.]?\s+(use|it.s|that.s|the correct|it should|it needs)',
    r'that.s wrong',
    r'don.t do that',
    r'actually[,]?\s+(it|you|the)',
    r'remember (that|this)',
    r'keep in mind',
    r'the correct way',
    r'you forgot',
    r'stop doing',
    r'instead[,]?\s+(use|do|try)',
]

matched = any(re.search(p, user_message, re.IGNORECASE) for p in patterns)
if not matched:
    sys.exit(0)

# Append candidate to pending file
now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
candidate = {
    'user_message': user_message[:2000],
    'timestamp': now,
}

pending_path = '$PENDING_FILE'
try:
    with open(pending_path) as f:
        pending = json.load(f)
except:
    pending = []

pending.append(candidate)

with open(pending_path, 'w') as f:
    json.dump(pending, f, indent=2)
" 2>/dev/null || true

echo '{}'
```

- [ ] **Step 2: Make executable**

Run: `chmod +x autocontext-plugin/hooks/user-prompt-submit.sh`

- [ ] **Step 3: Commit**

```bash
git add autocontext-plugin/hooks/user-prompt-submit.sh
git commit -m "feat: add UserPromptSubmit hook (correction pattern detection)"
```

### Task 7: Write SessionEnd hook

**Files:**
- Create: `autocontext-plugin/hooks/session-end.sh`

- [ ] **Step 1: Write the hook script**

```bash
#!/usr/bin/env bash
# SessionEnd hook: bump validated_count on used lessons, finalize pending.
# Pure file I/O — no LLM calls. Must complete within 1.5s.
set -euo pipefail

INPUT=$(cat)
CWD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd','.'))")
AUTOCONTEXT_DIR="$CWD/.autocontext"
LESSONS_FILE="$AUTOCONTEXT_DIR/lessons.json"
SESSION_CACHE="$AUTOCONTEXT_DIR/cache/session-lessons.json"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$(dirname "$0")")}"

if [ ! -d "$AUTOCONTEXT_DIR" ] || [ ! -f "$LESSONS_FILE" ]; then
    echo '{}'
    exit 0
fi

# Bump validated_count on lessons that were loaded this session
python3 -c "
import json
from datetime import datetime, timezone

lessons_path = '$LESSONS_FILE'
cache_path = '$SESSION_CACHE'

try:
    with open(lessons_path) as f:
        lessons = json.load(f)
    with open(cache_path) as f:
        cached = json.load(f)
except:
    exit(0)

cached_ids = {l['id'] for l in cached}
now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

for lesson in lessons:
    if lesson['id'] in cached_ids and not lesson.get('deleted'):
        lesson['validated_count'] = lesson.get('validated_count', 0) + 1
        lesson['last_validated'] = now
        conf = lesson.get('confidence', 0.5) + 0.1
        lesson['confidence'] = min(conf, 1.0)

with open(lessons_path, 'w') as f:
    json.dump(lessons, f, indent=2)
" 2>/dev/null || true

# Regenerate playbook (fast — just JSON to markdown)
python3 "$PLUGIN_ROOT/scripts/generate-playbook.py" "$LESSONS_FILE" "$AUTOCONTEXT_DIR/playbook.md" 2>/dev/null || true

echo '{}'
```

- [ ] **Step 2: Make executable**

Run: `chmod +x autocontext-plugin/hooks/session-end.sh`

- [ ] **Step 3: Commit**

```bash
git add autocontext-plugin/hooks/session-end.sh
git commit -m "feat: add SessionEnd hook (bump validated_count, regenerate playbook)"
```

---

## Chunk 3: PreToolUse + PostToolUse hooks

### Task 8: Write PreToolUse prompt-based hook

**Files:**
- Create: `autocontext-plugin/hooks/pre-tool-use.md`

This is a prompt-based hook (markdown file, not shell script). It runs through the LLM and can reason about whether lessons apply.

- [ ] **Step 1: Write the prompt hook**

```markdown
---
name: autocontext-pre-tool-use
description: Inject relevant project lessons before Edit/Write/Bash tool calls
hooks:
  - event: PreToolUse
    type: prompt
    matcher: "Edit|Write|Bash"
---

Check if any lessons from .autocontext/cache/session-lessons.json are relevant to this tool call. If the file being edited or the command being run matches a lesson's tags or context, inject a brief warning.

For test files (files in `tests/` or `__tests__/` directories, or files ending in `_test.py`, `.test.ts`, `.test.js`, `.spec.ts`, `.spec.js`, or named `test_*.py`), also check:
- Are assertions based on desired behavior (from the task/spec), not current implementation output?
- Is there at least one error/edge case, not just the happy path?
- Would this test fail if the feature broke?
- Are mocked return values being used as the expected assertions?

Only inject warnings when genuinely relevant. Do not warn on every tool call. Cap at 3 warnings.
```

- [ ] **Step 2: Commit**

```bash
git add autocontext-plugin/hooks/pre-tool-use.md
git commit -m "feat: add PreToolUse prompt-based hook (lesson injection + test quality)"
```

### Task 9: Write PostToolUse command hook

**Files:**
- Create: `autocontext-plugin/hooks/post-tool-use.sh`

- [ ] **Step 1: Write the hook script**

```bash
#!/usr/bin/env bash
# PostToolUse hook: performance baselines + deterministic test quality checks.
set -euo pipefail

INPUT=$(cat)
CWD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd','.'))")
AUTOCONTEXT_DIR="$CWD/.autocontext"

if [ ! -d "$AUTOCONTEXT_DIR" ]; then
    echo '{}'
    exit 0
fi

python3 -c "
import json, sys, re, os

input_data = json.loads(sys.stdin.read())
tool_name = input_data.get('tool_name', '')
tool_input = input_data.get('tool_input', {})
tool_output = input_data.get('tool_result', '')

autocontext_dir = '$AUTOCONTEXT_DIR'
config_path = os.path.join(autocontext_dir, 'config.yaml')
warnings = []

# Load config
try:
    import yaml
    with open(config_path) as f:
        config = yaml.safe_load(f) or {}
except:
    config = {}

rules = config.get('builtin_rules', {})

# --- Deterministic test checks (on Edit/Write of test files) ---
if tool_name in ('Edit', 'Write'):
    file_path = tool_input.get('file_path', '')

    # Check if this is a test file
    is_test = any([
        '/tests/' in file_path,
        '/__tests__/' in file_path,
        file_path.endswith('_test.py'),
        file_path.endswith('.test.ts'),
        file_path.endswith('.test.js'),
        file_path.endswith('.spec.ts'),
        file_path.endswith('.spec.js'),
        os.path.basename(file_path).startswith('test_'),
    ])

    if is_test and os.path.isfile(file_path):
        with open(file_path) as f:
            content = f.read()

        # no_assert_true check
        if rules.get('no_assert_true', True):
            bare_asserts = re.findall(
                r'assert\s+True|assert\s+\w+\s+is\s+not\s+None|'
                r'assert\s+len\(\w+\)\s*>\s*0|self\.assertTrue\(True\)',
                content
            )
            if bare_asserts:
                warnings.append(
                    f'[autocontext] Test quality: found {len(bare_asserts)} bare assertion(s) '
                    f'(assert True, is not None, len>0). Use specific value assertions.'
                )

        # no_happy_path_only check
        if rules.get('no_happy_path_only', True):
            test_methods = re.findall(r'def (test_\w+)', content)
            if test_methods:
                happy = [m for m in test_methods if any(
                    m.startswith(p) for p in ('test_success', 'test_valid', 'test_happy', 'test_can_', 'test_should_')
                )]
                error = [m for m in test_methods if any(
                    kw in m for kw in ('error', 'fail', 'invalid', 'edge', 'missing', 'empty', 'bad', 'reject')
                )]
                if len(happy) == len(test_methods) and not error and len(test_methods) > 1:
                    warnings.append(
                        '[autocontext] Test quality: all test methods appear to be happy-path only. '
                        'Consider adding error/edge case tests.'
                    )

# --- Performance baselines (on Bash commands matching test/build patterns) ---
if tool_name == 'Bash' and config.get('performance_baselines', False):
    command = tool_input.get('command', '')
    baseline_cmds = config.get('baseline_commands', [])

    matched_cmd = None
    for bc in baseline_cmds:
        if bc in command:
            matched_cmd = bc
            break

    if matched_cmd and isinstance(tool_output, str):
        # Try to extract timing from common test runner output
        time_match = re.search(r'(\d+\.?\d*)\s*s(?:econds?)?', tool_output)
        if time_match:
            elapsed = float(time_match.group(1))
            baselines = config.get('baselines', {})
            prev = baselines.get(matched_cmd)
            if prev and elapsed > prev * 1.1:
                warnings.append(
                    f'[autocontext] Performance regression: {matched_cmd} took {elapsed:.1f}s '
                    f'(baseline: {prev:.1f}s, +{((elapsed/prev)-1)*100:.0f}%)'
                )
            # Update baseline
            baselines[matched_cmd] = elapsed
            config['baselines'] = baselines
            try:
                import yaml
                with open(config_path, 'w') as f:
                    yaml.dump(config, f, default_flow_style=False)
            except:
                pass

if warnings:
    msg = '\n'.join(warnings)
    print(json.dumps({'hookResponse': {'message': msg}}))
else:
    print('{}')
" <<< "$INPUT" 2>/dev/null || echo '{}'
```

- [ ] **Step 2: Make executable**

Run: `chmod +x autocontext-plugin/hooks/post-tool-use.sh`

- [ ] **Step 3: Commit**

```bash
git add autocontext-plugin/hooks/post-tool-use.sh
git commit -m "feat: add PostToolUse hook (performance baselines + test quality checks)"
```

---

## Chunk 4: Slash commands

### Task 10: Write /autocontext-setup skill

**Files:**
- Create: `autocontext-plugin/skills/setup.md`

- [ ] **Step 1: Write the skill**

```markdown
---
name: autocontext-setup
description: First-run configuration for the autocontext plugin
---

Run the autocontext first-run setup wizard. Use AskUserQuestion for each step.

Step 1: Ask "What should we call you in lesson attribution?" with a text input option. Store the answer.

Step 2: Ask "Which built-in test quality rules do you want enabled?" as a multi-select:
- Tautological test check (tests that describe code instead of testing behavior)
- No mock everything (tests where mocks are the assertions)
- No happy path only (require error/edge cases)
- No bare assertions (flag assert True / assert is not None)
- Test independence (flag tests that pass without their feature)

Step 3: Ask "How aggressively should lessons be loaded at session start?" with options:
- Conservative (5 lessons, confidence >= 0.7)
- Balanced (15 lessons, confidence >= 0.3) (recommended)
- Aggressive (25 lessons, confidence >= 0.1)

Step 4: Ask "How should new lessons be persisted at session end?" with options:
- Auto-persist with curator validation (recommended)
- Always ask before persisting
- Auto-persist everything (no curator)

After all questions are answered, write the config to ~/.claude/autocontext.yaml with the selected values. Confirm to the user that setup is complete and they can now run /autocontext-init in any project.
```

- [ ] **Step 2: Commit**

```bash
git add autocontext-plugin/skills/setup.md
git commit -m "feat: add /autocontext-setup skill (first-run wizard)"
```

### Task 11: Write /autocontext-init skill

**Files:**
- Create: `autocontext-plugin/skills/init.md`

- [ ] **Step 1: Write the skill**

```markdown
---
name: autocontext-init
description: Initialize .autocontext/ in the current project for knowledge persistence
---

Initialize the autocontext knowledge directory in the current project. Use AskUserQuestion for setup decisions.

First, check if .autocontext/ already exists. If it does, inform the user and ask if they want to reinitialize (this will NOT delete existing lessons).

Step 1: If a CLAUDE.md file exists in the project root, ask:
"This project has a CLAUDE.md. Seed initial lessons from it?"
- Yes, extract and let me review each one
- Yes, extract automatically
- No, start fresh

Step 2: Ask "Will other developers use Claude Code on this repo?"
- Yes, set up cross-developer sharing
- No, just me

Step 3: Ask "Track test/build performance baselines?"
- Yes
- No

Then create the .autocontext/ directory structure:
1. Create .autocontext/ directory
2. Copy config.yaml template from ${CLAUDE_PLUGIN_ROOT}/templates/config.yaml
3. Set project_name in config.yaml to the git repo name or directory name
4. Create config.local.yaml with the user's identity (from ~/.claude/autocontext.yaml or ask)
5. Copy empty lessons.json from template
6. Copy .gitignore from template (ignores config.local.yaml and cache/)
7. If sharing enabled: create .gitattributes with merge driver entry and install the driver in local git config:
   ```bash
   git config merge.autocontext-union.name "Autocontext lessons.json union merge"
   git config merge.autocontext-union.driver "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/merge-driver.py %O %A %B"
   ```
8. If CLAUDE.md seeding was requested: run ${CLAUDE_PLUGIN_ROOT}/scripts/seed-from-claude-md.py
9. Generate initial playbook.md

Confirm completion with a summary of what was created.
```

- [ ] **Step 2: Commit**

```bash
git add autocontext-plugin/skills/init.md
git commit -m "feat: add /autocontext-init skill (per-project setup)"
```

### Task 12: Write /autocontext-review and /autocontext-status skills

**Files:**
- Create: `autocontext-plugin/skills/review.md`
- Create: `autocontext-plugin/skills/status.md`

- [ ] **Step 1: Write the review skill**

```markdown
---
name: autocontext-review
description: Interactively review and curate accumulated project lessons
---

Review accumulated lessons in .autocontext/lessons.json. Use AskUserQuestion to walk through lessons.

First, read .autocontext/lessons.json. Separate into active lessons and tombstoned (deleted) lessons.

For active lessons, sort by confidence (lowest first — these need the most attention).

Present lessons in batches of 3-4 using AskUserQuestion. For each lesson show:
- Text, category, confidence score, validated count, created by, age
- Options: Approve (bump confidence +0.2), Edit (modify text/tags), Delete (tombstone), Supersede (replace with new), Skip

After reviewing active lessons, if there are tombstoned lessons, ask:
"There are N tombstoned lessons. Permanently remove them?"
- Yes, remove all tombstones
- Let me review them individually
- No, keep them

After all reviews, regenerate playbook.md using ${CLAUDE_PLUGIN_ROOT}/scripts/generate-playbook.py.

Report summary: N lessons reviewed, M approved, K deleted, J edited.
```

- [ ] **Step 2: Write the status skill**

```markdown
---
name: autocontext-status
description: Show knowledge stats for the current project
---

Read .autocontext/lessons.json and .autocontext/config.yaml. Display stats:

1. Total lessons by category (active vs tombstoned)
2. Average confidence across active lessons
3. Top 5 most-validated lessons (highest validated_count)
4. Top 5 stalest lessons (lowest confidence or oldest last_validated)
5. Lessons by developer (created_by breakdown)
6. Lessons added in the last 7 days
7. Merge driver status: check if git config merge.autocontext-union.driver is set

If .autocontext/ doesn't exist, suggest running /autocontext-init.

Format as a clean table/list. No AskUserQuestion needed — this is read-only.
```

- [ ] **Step 3: Commit**

```bash
git add autocontext-plugin/skills/review.md autocontext-plugin/skills/status.md
git commit -m "feat: add /autocontext-review and /autocontext-status skills"
```

---

## Chunk 5: Curator agent + CLAUDE.md seeder

### Task 13: Write curator agent

**Files:**
- Create: `autocontext-plugin/agents/curator.md`

- [ ] **Step 1: Write the agent definition**

```markdown
---
name: autocontext-curator
description: Validates and structures lesson candidates before persisting to lessons.json
tools:
  - Read
  - Write
  - Bash
---

You are a knowledge curator for a software project. Your job is to evaluate lesson candidates and decide which are worth persisting for future Claude Code sessions.

You will receive lesson candidates (raw user corrections and context). For each one, decide:

**Persist if:**
- Specific to this project (not general programming knowledge)
- Actionable (tells a future session what to do or avoid)
- Would save time if known at session start
- The correction was validated during the session (the fix worked)

**Reject if:**
- General knowledge any developer would know
- Too vague to act on ("be careful with X" without specifics)
- About a one-time task that won't recur
- Contains secrets, API keys, tokens, passwords, or PII

For each accepted lesson, output structured JSON:
```json
{
  "category": "efficiency|codebase|optimization",
  "text": "concise, actionable description",
  "context": "where in the codebase this applies",
  "tags": ["file-paths", "module-names", "concepts"]
}
```

Read the existing lessons from .autocontext/lessons.json to check for duplicates before adding new ones.
```

- [ ] **Step 2: Commit**

```bash
git add autocontext-plugin/agents/curator.md
git commit -m "feat: add curator agent definition"
```

### Task 14: Write seed-from-claude-md.py

**Files:**
- Create: `autocontext-plugin/scripts/seed-from-claude-md.py`
- Create: `autocontext-plugin/tests/test_seed_from_claude_md.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for seed-from-claude-md.py"""
import json
import tempfile
import os
import subprocess
import sys

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "seed-from-claude-md.py")


def _seed(claude_md_content):
    """Run seeder, return extracted lessons."""
    with tempfile.TemporaryDirectory() as d:
        claude_md = os.path.join(d, "CLAUDE.md")
        lessons_path = os.path.join(d, "lessons.json")
        with open(claude_md, "w") as f:
            f.write(claude_md_content)
        with open(lessons_path, "w") as f:
            json.dump([], f)
        result = subprocess.run(
            [sys.executable, SCRIPT, claude_md, lessons_path],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Failed: {result.stderr}"
        with open(lessons_path) as f:
            return json.load(f)


def test_extracts_from_bullet_points():
    md = """# CLAUDE.md
## Key gotchas
- POST /api/ideas/ needs trailing slash
- Always use timeout --foreground in tmux
"""
    lessons = _seed(md)
    assert len(lessons) >= 2
    texts = [l["text"] for l in lessons]
    assert any("trailing slash" in t for t in texts)


def test_skips_general_knowledge():
    md = """# CLAUDE.md
## Notes
- Use git for version control
- Python is a programming language
- The API requires a trailing slash on POST /api/ideas/
"""
    lessons = _seed(md)
    texts = [l["text"] for l in lessons]
    # Should include the API-specific one but not general knowledge
    assert any("trailing slash" in t for t in texts)


def test_assigns_categories():
    md = """# CLAUDE.md
## Architecture
- Belt items use distance-offset struct for O(1) updates
## Bug fixes
- scorer.py escapes curly braces to prevent format() breakage
"""
    lessons = _seed(md)
    categories = {l["category"] for l in lessons}
    assert len(categories) >= 1  # Should have at least one category


def test_empty_claude_md():
    lessons = _seed("# CLAUDE.md\n\nNo specific notes.\n")
    assert isinstance(lessons, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd autocontext-plugin && python3 -m pytest tests/test_seed_from_claude_md.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
"""Extract lessons from an existing CLAUDE.md file.

Usage: seed-from-claude-md.py <CLAUDE.md path> <lessons.json path>

Uses claude -p to extract actionable project-specific lessons.
Falls back to simple bullet-point extraction if claude -p is unavailable.
"""
import json
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone


def extract_bullets(content: str) -> list[str]:
    """Extract bullet points that look like project-specific gotchas."""
    bullets = []
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("- ") or line.startswith("* "):
            text = line[2:].strip()
            # Skip very short or very generic lines
            if len(text) < 15:
                continue
            # Skip lines that are just general knowledge
            generic = [
                "use git", "python is", "install", "run the",
                "see the", "check the", "read the", "refer to",
            ]
            if any(text.lower().startswith(g) for g in generic):
                continue
            bullets.append(text)
    return bullets


def categorize(text: str) -> str:
    """Simple keyword-based categorization."""
    lower = text.lower()
    if any(kw in lower for kw in ["slow", "performance", "cache", "latency", "timeout", "memory"]):
        return "optimization"
    if any(kw in lower for kw in ["schema", "struct", "model", "database", "column", "table", "architecture"]):
        return "codebase"
    return "efficiency"


def seed(claude_md_path: str, lessons_path: str) -> None:
    with open(claude_md_path) as f:
        content = f.read()

    with open(lessons_path) as f:
        existing = json.load(f)

    existing_texts = {l["text"] for l in existing}

    # Try claude -p for smart extraction, fall back to bullet parsing
    try:
        prompt = (
            "Extract actionable, project-specific lessons from this CLAUDE.md. "
            "Only include items that would save time if known at session start. "
            "Skip general programming knowledge. "
            "NEVER include secrets, API keys, or passwords. "
            "Output JSON: {\"lessons\": [{\"text\": \"...\", \"category\": \"efficiency|codebase|optimization\", \"tags\": []}]}\n\n"
            + content[:15000]
        )
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout.strip())
            bullets_with_cats = [
                (l["text"], l.get("category", "efficiency"), l.get("tags", []))
                for l in data.get("lessons", [])
            ]
        else:
            raise RuntimeError("claude -p failed")
    except Exception:
        # Fallback: simple bullet extraction
        raw_bullets = extract_bullets(content)
        bullets_with_cats = [(b, categorize(b), []) for b in raw_bullets]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for text, category, tags in bullets_with_cats:
        if text in existing_texts:
            continue
        existing.append({
            "id": "lesson_" + uuid.uuid4().hex[:8],
            "schema_version": 1,
            "category": category,
            "text": text,
            "context": "Seeded from CLAUDE.md",
            "confidence": 0.6,  # Slightly higher than auto-extracted — human-written
            "validated_count": 0,
            "last_validated": now,
            "created": now,
            "created_by": "seed",
            "supersedes": None,
            "deleted": False,
            "tags": tags,
        })

    with open(lessons_path, "w") as f:
        json.dump(existing, f, indent=2)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <CLAUDE.md> <lessons.json>", file=sys.stderr)
        sys.exit(1)
    seed(sys.argv[1], sys.argv[2])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd autocontext-plugin && python3 -m pytest tests/test_seed_from_claude_md.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add autocontext-plugin/scripts/seed-from-claude-md.py autocontext-plugin/tests/test_seed_from_claude_md.py
git commit -m "feat: add CLAUDE.md lesson seeder with tests"
```

---

## Chunk 6: Integration test + final packaging

### Task 15: Update plugin.json with all components

**Files:**
- Modify: `autocontext-plugin/plugin.json`

- [ ] **Step 1: Update plugin.json with hooks, skills, and agents**

Refer to Claude Code plugin documentation for the exact manifest format. The plugin.json needs to reference all hooks with their event types, matchers, and timeouts. Verify the format by checking existing plugins in `~/.claude/plugins/` for examples.

- [ ] **Step 2: Commit**

```bash
git add autocontext-plugin/plugin.json
git commit -m "feat: complete plugin.json with all hooks, skills, and agents"
```

### Task 16: Test on hawk-translation-api

- [ ] **Step 1: Install the plugin locally**

```bash
# Link the plugin for testing
ln -s ~/projects/hawk-translation-api/autocontext-plugin ~/.claude/plugins/autocontext
```

- [ ] **Step 2: Run /autocontext-init on hawk-translation-api**

Start a Claude Code session in `~/projects/hawk-translation-api/` and run `/autocontext-init`. Choose to seed from CLAUDE.md.

- [ ] **Step 3: Verify lessons were seeded**

```bash
cat ~/projects/hawk-translation-api/.autocontext/lessons.json | python3 -m json.tool | head -30
cat ~/projects/hawk-translation-api/.autocontext/playbook.md
```

Expected: Lessons extracted from hawk's CLAUDE.md, playbook.md generated.

- [ ] **Step 4: Test SessionStart in a new session**

Start a new Claude Code session. Verify `[autocontext]` message appears with loaded lessons.

- [ ] **Step 5: Test correction detection**

In the session, type something like "no, the API uses DeepL not claude -p for translation" and verify it appears in `.autocontext/cache/pending-lessons.json`.

- [ ] **Step 6: Test SessionEnd persistence**

End the session. Verify `validated_count` was bumped on loaded lessons in `lessons.json`.

- [ ] **Step 7: Test next-session curation**

Start another session. Verify pending lessons were curated and added to `lessons.json`.

- [ ] **Step 8: Commit the .autocontext/ directory**

```bash
cd ~/projects/hawk-translation-api
git add .autocontext/
git commit -m "feat: initialize autocontext knowledge for hawk-translation-api"
```

### Task 17: Final documentation

- [ ] **Step 1: Write README for the plugin**

Create `autocontext-plugin/README.md` with:
- What it does (one paragraph)
- Install instructions
- Quick start (/autocontext-setup then /autocontext-init)
- Available commands
- How cross-developer sharing works
- Configuration reference

- [ ] **Step 2: Commit**

```bash
git add autocontext-plugin/README.md
git commit -m "docs: add plugin README"
```

---

## Review fixes (apply during implementation)

The plan was reviewed and the following fixes must be applied during implementation. These are listed here rather than inline to preserve the review trail.

### Fix 1: All config files use JSON, not YAML

Every `import yaml` / `yaml.safe_load` / `yaml.dump` in the hook scripts must be replaced with `import json` / `json.load` / `json.dump`. Config files are `.json` not `.yaml`. This affects:
- `session-start.sh`: replace `config.yaml` references with `config.json`, remove `import yaml`
- `post-tool-use.sh`: same — replace all YAML reads/writes with JSON
- `init.md` skill: reference `config.json` and `config.local.json` templates
- `setup.md` skill: write `~/.claude/autocontext.json` (not `.yaml`)
- `status.md` skill: read `config.json`

### Fix 2: Add confidence decay to SessionStart

In the SessionStart hook's Phase 2 (load lessons), add decay calculation before filtering:

```python
from datetime import datetime, timezone

now = datetime.now(timezone.utc)
staleness_days = config.get('staleness_days', 60)

for l in lessons:
    if l.get('deleted'):
        continue
    last_val = l.get('last_validated', l.get('created', ''))
    if not last_val:
        continue
    try:
        last_dt = datetime.fromisoformat(last_val.replace('Z', '+00:00'))
        days_stale = (now - last_dt).days
        if days_stale > staleness_days:
            decay_periods = (days_stale - staleness_days) // 30
            l['confidence'] = max(0.0, l.get('confidence', 0.5) - (0.1 * decay_periods))
    except:
        pass
```

This goes before the `confidence >= threshold` filter.

### Fix 3: Add preceding_context to UserPromptSubmit candidates

In the UserPromptSubmit hook, the candidate should include more context:

```python
candidate = {
    'user_message': user_message[:2000],
    'preceding_context': input_data.get('assistant_message', '')[:1000],
    'files_touched': input_data.get('files_touched', []),
    'timestamp': now,
}
```

Check the actual Claude Code hook input schema for the correct field names for assistant context and file paths.

### Fix 4: Create archive directory in templates

Add `autocontext-plugin/templates/archive/` directory with an empty `superseded.json` file (`[]`). The `/autocontext-init` skill should create this directory.

### Fix 5: Check persistence_mode in SessionStart curation

In SessionStart Phase 1, before auto-persisting curated lessons:

```python
config_path = os.path.join(autocontext_dir, 'config.json')
try:
    with open(config_path) as f:
        config = json.load(f)
except:
    config = {}

if config.get('persistence_mode') == 'ask_before_persist':
    # Write to cache/curated-pending.json instead of lessons.json
    # User runs /autocontext-review to approve
    ...
```

### Fix 6: Don't bump contradicted lessons in SessionEnd

In SessionEnd, cross-reference loaded lessons against UserPromptSubmit correction candidates:

```python
# Load pending corrections from this session
pending_path = os.path.join(cache_dir, 'pending-lessons.json')
try:
    with open(pending_path) as f:
        pending = json.load(f)
    correction_texts = ' '.join(p.get('user_message', '') for p in pending).lower()
except:
    correction_texts = ''

for lesson in lessons:
    if lesson['id'] in cached_ids and not lesson.get('deleted'):
        # Skip bumping if a correction this session mentioned something related
        if any(tag.lower() in correction_texts for tag in lesson.get('tags', [])):
            continue
        lesson['validated_count'] += 1
        ...
```

### Fix 7: Fix UserPromptSubmit JSON embedding

Replace the fragile triple-quote embedding with heredoc stdin:

```bash
python3 << 'PYEOF' "$PENDING_FILE"
import json, sys, re
from datetime import datetime, timezone

input_data = json.loads(sys.stdin.read())
# ... rest of script
PYEOF
```

Or pipe `$INPUT` via stdin: `echo "$INPUT" | python3 -c "..."`

### Fix 8: Fix test_shows_confidence_and_tags

Remove the dead `or "[0.8]"` branch:

```python
def test_shows_confidence_and_tags():
    # ...
    assert "[0.75]" in playbook
    assert "perf" in playbook
```
