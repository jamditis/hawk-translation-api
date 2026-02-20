# Hawk News Service translation API — design

**Date:** 2026-02-19
**Status:** Approved
**Related:** `journalism/newsroom-api-opportunities.md`, `journalism/translation-api-plan.md`

---

## Context

The Center for Cooperative Media's Spanish Translation News Service (STNS) already delivers translations to NJ News Commons partners through professional human translators. This project formalizes that workflow into a production API — keeping human translators at the center of the process while adding machine translation and AI scoring as tools that make them faster and more effective.

The API will live at `api.hawknewsservice.org` and expose a human translator-centered pipeline as a REST service. Machine translation generates a first draft, AI quality scoring flags problem areas for human attention, and professional translators review, edit, and certify the final output. Three quality tiers let newsrooms choose the level of human translator involvement appropriate for each piece of content.

---

## Architecture

Human translators are the critical path for reviewed and certified tiers. Machine translation and AI scoring exist to support their work.

```
Newsroom (API key request)
        │
        ▼
api.hawknewsservice.org   ←── Cloudflare DNS
        │
        ▼
Cloudflare Tunnel ──────────── officejawn (100.84.214.24)
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
               FastAPI          PostgreSQL        Redis
               (uvicorn)        (jobs, keys,     (Celery
                    │            glossaries,      broker,
                    │            reviewers)       rate limits)
                    ▼
               Celery workers
                    │
          ┌─────────┼──────────┐
          ▼         ▼          ▼
        DeepL    `claude -p`  ╔═══════════════════╗
        API      subprocess   ║ HUMAN TRANSLATORS ║
        (draft)  (score &     ║ review, edit,     ║
                  flag for    ║ certify           ║
                  human       ║ (side-by-side UI) ║
                  attention)  ╚═══════════════════╝
                    │
                    ▼
             Webhook delivery
             + WordPress plugin push
```

**hawknewsservice.org shared host (37.27.121.163:4377, SFTP-only):**
Static website, API docs (Swagger UI static build), partner onboarding pages, signup form. No API logic runs here.

---

## Stack

| Component | Technology | Role |
|---|---|---|
| **Human translators** | Professional bilingual journalists | Review, edit, and certify translations for publication quality |
| API server | FastAPI + uvicorn | Request handling, auth, job creation |
| Task queue | Celery + Redis | Async machine draft pipeline |
| Database | PostgreSQL 15 | Jobs, API keys, orgs, glossaries, translator assignments, review state |
| Migrations | Alembic | Schema versioning |
| Machine draft | DeepL API | Generate initial translation draft (10 launch languages) |
| AI quality scoring | `claude -p` subprocess | Flag segments that need human translator attention |
| Translator review UI | FastAPI + Jinja2 | Browser-based side-by-side editor where human translators review and edit |
| Webhook delivery | Celery task | Fires callback URLs when human-approved translations are ready |

**Quality scoring supports human translators.** AI scoring via `claude -p` subprocess flags segments with low fluency or accuracy scores (< 3.0) so human translators can focus their effort where it matters most. Scoring is advisory — timeouts (30s) are non-blocking and produce null scores rather than failing jobs.

---

## Repo structure

```
hawk-translation-api/
├── api/           # FastAPI app, routes, auth middleware
├── workers/       # Celery tasks — machine draft pipeline (segmenter, glossary, translator, scorer)
├── review/        # Human translator workflow: assignment, side-by-side editor, certification
├── db/            # SQLAlchemy models + Alembic migrations (includes Reviewer, ReviewAssignment)
├── wp-plugin/     # WordPress PHP plugin
├── docs/          # OpenAPI spec, static Swagger build
└── scripts/       # Deploy, seed, key management
```

---

## Data flow

All tiers share the same machine draft pipeline. The tiers differ in how much human translator involvement follows the draft.

### Step 1: Job submission (all tiers)

```
POST /v1/translate
   → validate API key (Redis cache → DB fallback)
   → check quota (Redis counter, resets daily)
   → create job record (status: queued)
   → enqueue Celery task
   → return 202 + job_id immediately
```

### Step 2: Machine draft (all tiers)

```
Celery worker picks up job
   → segment HTML content (preserve tags, extract translatable text)
   → apply NJ journalism glossary (proper nouns, gov titles, place names)
   → generate machine draft via DeepL API per segment
   → reassemble with original HTML structure
   → update job (status: machine_translated)
```

### Step 3: AI quality scoring (all tiers)

```
AI scoring flags segments for human translator attention
   → spawn `claude -p` subprocess with scoring prompt
   → parse JSON output: {paragraph_scores, flags, overall}
   → segments scoring below 3.0 flagged as needs_review
   → store scores in DB
```

### Step 4: Human translator review (reviewed/certified tiers)

This is where the real translation quality happens. Machine drafts are a starting point — human translators make the editorial decisions.

```
Instant tier: status → complete (machine draft only, no human review)

Reviewed tier:
   → human translator assigned by language pair + availability
   → translator opens side-by-side editor: machine draft vs. source
   → AI scores highlight segments that need the most attention
   → translator edits, approves, or rewrites each segment
   → all edits tracked in diff_json for quality feedback loop
   → status: reviewed → webhook fires

Certified tier:
   → same as reviewed, PLUS:
   → second human translator reviews the first translator's work
   → certifier approves or requests further edits
   → status: certified → webhook fires
```

### Step 5: Delivery (all tiers)

```
   → fire webhook to callback_url (if provided)
   → result available at GET /v1/translate/{job_id}
```

### Auth flow

```
API key format: hawk_live_<32 random chars>
                hawk_test_<32 random chars>

Request → extract from Authorization: Bearer header
       → hash key → look up in Redis (5min TTL)
       → on miss: look up in DB → cache result
       → attach org + tier + quota to request context
```

---

## Error handling

### API layer

| Scenario | Response |
|---|---|
| Invalid/expired API key | 401, `error: invalid_api_key` |
| Quota exceeded | 429, `error: quota_exceeded`, `reset_at: <timestamp>` |
| Unsupported language pair | 422, `error: unsupported_language`, `supported: [...]` |
| Content over 50k chars | 422, `error: content_too_large` |
| DeepL API down | 503, job retried up to 3x with exponential backoff, then `status: failed` |

### Worker layer

- DeepL failures: Celery retry with backoff (30s, 2m, 10m). After 3 failures: job `failed`, error webhook fired.
- `claude -p` subprocess timeout (30s): skip scoring, set scores to `null`, log warning. Job still completes.
- Partial translation (some segments fail): deliver succeeded segments, flag failures in response metadata.

### Webhook delivery

- Retry up to 5x over 24 hours on non-2xx callback response.
- After 5 failures: delivery marked `abandoned`, job result still accessible via GET.

---

## Testing

**Unit tests (pytest):**
- API key validation logic
- HTML segmentation (preserves tags, handles nested elements)
- Glossary application
- Quality score parsing from `claude -p` subprocess output
- Webhook retry logic

**Integration tests:**
- Full instant-tier pipeline with mocked DeepL response
- Human translator review state machine (queued → in_review → reviewed → certified)
- Translator assignment by language pair
- Rate limiting (Redis counters)

**Partner acceptance test (2-3 STNS newsrooms):**
- Submit real Spanish-language stories
- Verify HTML structure preserved in output
- Verify glossary terms applied correctly (NJ place names, government titles)
- Human translators review machine draft quality for each language pair
- Measure latency baseline for instant tier

---

## Language support (launch)

Based on NJ demographic data, per the full technical plan:

| Language | Code | Community |
|---|---|---|
| Spanish | es | Largest NJ language community |
| Portuguese | pt | Brazilian + Portuguese communities |
| Haitian Creole | ht | Large community in Newark, Trenton |
| Chinese (Simplified) | zh | Northern NJ Chinese communities |
| Korean | ko | Bergen County |
| Arabic | ar | Paterson, Edison |
| French | fr | West African diaspora |
| Polish | pl | Historic NJ Polish communities |
| Hindi | hi | Edison, Middlesex County |
| Urdu | ur | Pakistani community, shared with Hindi |

---

## Deployment target

- **API:** officejawn (100.84.214.24), exposed via Cloudflare Tunnel → `api.hawknewsservice.org`
- **Website/docs:** hawknewsservice.org shared host (37.27.121.163), deployed via SFTP
- **Systemd services on officejawn:** `hawk-api` (uvicorn), `hawk-worker` (Celery), `hawk-beat` (Celery beat for scheduled tasks)

---

## Phased delivery

**Phase 1 (weeks 1–4):** Machine draft pipeline + instant tier
- Core FastAPI app, DB schema, Alembic migrations
- API key auth + quota enforcement (Redis)
- DeepL integration + HTML segmentation (generates machine draft for human translators)
- AI quality scoring (flags segments for human translator attention)
- Webhook delivery
- GET /v1/translate/{job_id}, GET /v1/languages
- STNS partner acceptance test

**Phase 2 (weeks 5–10):** Human translator workflow (core of the product)
- Human translator assignment engine (match by language pair + availability)
- Translator review queue + side-by-side editing UI
- Reviewed and certified tier pipeline with full edit tracking
- Quality feedback loop: translator edits improve future AI scoring
- WordPress plugin (PHP)
- Static docs site deployed to hawknewsservice.org

Phase 2 is not an add-on — it delivers the human translator workflow that is the product's core value proposition. Phase 1 builds the machine draft infrastructure that supports it.

---

## Reference

Full endpoint spec, DB schema, pricing model, and human translator compensation model: `journalism/translation-api-plan.md`
