# AutoContext-inspired knowledge persistence skill

Running log of decisions, gotchas, and steps. Written to be reusable as a template.

## Goals

- Build a Claude Code skill + hooks system inspired by AutoContext's knowledge persistence patterns
- Solve: cross-session memory loss, cross-developer divergence, repeated mistakes, workflow drift
- Test on hawk-translation-api first (concrete, scorable domain)
- Generalize to slopworks, houseofjawn daily work, and any other project
- Package as a shareable skill for skills.amditis.tech

## Decision: approach C (custom skill)

Evaluated three approaches on 2026-03-13:

| Approach | What | Rejected because |
|----------|------|-----------------|
| A: AutoContext direct | Use AutoContext as-is for hawk translation scoring | Narrow scope, requires Anthropic API key (conflicts with no-direct-API-calls rule) |
| B: AutoContext knowledge layer | Use LessonStore/MCP as infrastructure | Underuses the tool, adds operational overhead for 20% of the value |
| **C: Custom skill** | Build our own skill + hooks inspired by AutoContext's patterns | **Selected** — solves the actual problem, works for all projects, no external deps |

## What we're taking from AutoContext

Patterns worth adopting:
- **Structured lessons with metadata** — not just text, but generation/score/staleness tracking (`ApplicabilityMeta`)
- **Curator gating** — not everything gets persisted, a validation step filters garbage
- **Knowledge directory per project** — `knowledge/<project>/lessons.json`, `playbook.md`, `hints.md`
- **Staleness tracking** — lessons that haven't been validated recently get deprioritized
- **Lesson supersession** — new lessons can explicitly replace outdated ones

Patterns we're skipping:
- Parametric scenario optimization (game-playing loop)
- Tournament/Elo scoring
- LLM provider abstraction (we use `claude -p` subprocess)
- MCP server (overkill — hooks are lighter)
- Code generation from specs

## Pain points to solve (all of these, roughly equally)

1. **Cross-session memory loss** — new sessions start cold, forget schema/constants/conventions
2. **Cross-developer divergence** — Joe's Claude and Kevin's Claude learn different things
3. **Repeated mistakes** — same errors on API patterns, trailing slashes, status sync, etc.
4. **CRM/Board workflow drift** — categorization errors, missed action items, duplicates
5. **Handoff protocol breakdown** — coordination processes forgotten between sessions

## Target projects

| Project | Primary pain | Knowledge type |
|---------|-------------|----------------|
| hawk-translation-api | Scoring prompt quality, glossary gaps | Translation patterns, terminology |
| slopworks | Schema drift, cross-developer sync | Game data structures, conventions, handoff protocols |
| houseofjawn (bot + dashboard + scheduler) | CRM workflow drift, API patterns | Board/CRM patterns, API gotchas, email processing rules |

## Process log

### 2026-03-13: Research and decision
- Explored AutoContext repo (scenario format, knowledge layer, MCP server, provider config)
- Explored hawk-translation-api (7-stage pipeline, DeepL+Google translation, claude -p scoring, glossary system, review workflow)
- Key finding: hawk uses DeepL/Google for translation, claude -p only for quality scoring
- Key finding: human review schema exists (ReviewAssignment.diff_json) but no feedback pipeline yet
- Key finding: AutoContext's knowledge layer (LessonStore, playbooks, hints) is the useful part, not the game loop
- Decided on approach C: custom skill + hooks
- Joe wants this packaged for skills.amditis.tech with relevant hooks

## Gotchas and lessons

- AutoContext requires Anthropic API key for direct API calls — conflicts with the no-direct-API-calls rule
- hawk-translation-api README vs CLAUDE.md disagreed on translation backend (README said claude -p, CLAUDE.md correctly says DeepL/Google)
- Don't waste firecrawl tokens on repos you have gh access to
