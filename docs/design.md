# Hawk News Service translation API — design

**Date:** 2026-02-19
**Status:** Approved
**Related:** `journalism/newsroom-api-opportunities.md`, `journalism/translation-api-plan.md`

---

## Context

The Center for Cooperative Media's Spanish Translation News Service (STNS) already delivers translations to NJ News Commons partners manually. This project formalizes that into a production API, making translation programmatically accessible to the 330+ newsroom partners and beyond.

The API will live at `api.hawknewsservice.org` and expose the translation pipeline as a REST service with three quality tiers, human review workflow, and direct CMS integration.

---

## Architecture

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
                    │            users, orgs)     rate limits)
                    ▼
               Celery workers
                    │
          ┌─────────┼──────────┐
          ▼         ▼          ▼
        DeepL    `claude -p`  Human review
        API      subprocess   web UI
        (translate) (score)   (reviewed/certified)
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
| API server | FastAPI + uvicorn | Request handling, auth, job creation |
| Task queue | Celery + Redis | Async translation pipeline |
| Database | PostgreSQL 15 | Jobs, API keys, orgs, glossaries, review state |
| Migrations | Alembic | Schema versioning |
| Translation | DeepL API | Machine translation (10 launch languages) |
| Quality scoring | `claude -p` subprocess | Paragraph-level fluency/accuracy scoring |
| Review UI | FastAPI + Jinja2 | Browser-based side-by-side editor for human reviewers |
| Webhook delivery | Celery task | Fires callback URLs when jobs complete |

**Quality scoring constraint:** LLM calls use `claude -p` via subprocess (not direct API). Scoring is advisory — timeouts (30s) are non-blocking and produce null scores rather than failing jobs.

---

## Repo structure

```
hawk-translation-api/
├── api/           # FastAPI app, routes, auth middleware
├── workers/       # Celery tasks (translation, scoring, delivery)
├── review/        # Human review web UI (Jinja2 templates)
├── db/            # SQLAlchemy models + Alembic migrations
├── wp-plugin/     # WordPress PHP plugin
├── docs/          # OpenAPI spec, static Swagger build
└── scripts/       # Deploy, seed, key management
```

---

## Data flow

### Instant tier (happy path)

```
1. POST /v1/translate
   → validate API key (Redis cache → DB fallback)
   → check quota (Redis counter, resets daily)
   → create job record (status: queued)
   → enqueue Celery task
   → return 202 + job_id immediately

2. Celery worker picks up job
   → segment HTML content (preserve tags, extract translatable text)
   → apply NJ journalism glossary (proper nouns, gov titles, place names)
   → call DeepL API per segment
   → reassemble with original HTML structure
   → update job (status: machine_translated)

3. Quality scoring
   → spawn `claude -p` subprocess with scoring prompt
   → parse JSON output: {paragraph_scores, flags, overall}
   → store scores in DB
   → instant tier: status → complete

4. Delivery
   → fire webhook to callback_url (if provided)
   → result available at GET /v1/translate/{job_id}
```

### Reviewed/certified tier (diverges at step 3)

```
3b. Flagged segments (score < 3) highlighted in review queue
    → reviewer assigned (language pair + availability)
    → reviewer edits in side-by-side UI, diffs tracked
    → certified: second reviewer approves
    → status: reviewed | certified → webhook fires
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
- Human review state machine (queued → in_review → reviewed → certified)
- Rate limiting (Redis counters)

**Partner acceptance test (2-3 STNS newsrooms):**
- Submit real Spanish-language stories
- Verify HTML structure preserved in output
- Verify glossary terms applied correctly (NJ place names, government titles)
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

**Phase 1 (weeks 1–4):** Instant tier live
- Core FastAPI app, DB schema, Alembic migrations
- API key auth + quota enforcement (Redis)
- DeepL integration + HTML segmentation
- `claude -p` quality scoring
- Webhook delivery
- GET /v1/translate/{job_id}, GET /v1/languages
- STNS partner acceptance test

**Phase 2 (weeks 5–10):** Human review + CMS integration
- Celery + Redis worker infrastructure
- Human review queue + reviewer web UI
- Reviewed and certified tier pipeline
- WordPress plugin (PHP)
- Static docs site deployed to hawknewsservice.org

---

## Reference

Full endpoint spec, DB schema, pricing model, and reviewer compensation model: `journalism/translation-api-plan.md`
