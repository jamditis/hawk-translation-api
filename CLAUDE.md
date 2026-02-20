# Hawk News Service translation API — development context

## What this is

A production REST API for translating journalism content into 10 languages. Built for the Center for Cooperative Media's Spanish Translation News Service (STNS) and NJ News Commons partner newsrooms.

Live at: `api.hawknewsservice.org` (via Cloudflare Tunnel → officejawn)

---

## Architecture

```
POST /v1/translate
    → validate API key (Redis cache → DB fallback)
    → check quota (Redis counter)
    → create job record (PostgreSQL)
    → enqueue Celery task
    → return 202 + job_id

Celery worker (officejawn)
    → segment HTML (BeautifulSoup4)
    → apply NJ journalism glossary
    → translate via DeepL API
    → reassemble HTML
    → score quality via `claude -p` subprocess
    → mark complete, fire webhook
```

## Stack

| Component | Technology |
|---|---|
| API server | FastAPI + uvicorn (port 8090) |
| Task queue | Celery 5.3 + Redis |
| Database | PostgreSQL 15 + SQLAlchemy 2.0 + Alembic |
| Translation | DeepL API (7 languages); Google Cloud Translation API (`ht`, `hi`, `ur`) |
| Quality scoring | `claude -p` subprocess — non-blocking, 30s timeout, retries on timeout |
| Deployment | officejawn (100.84.214.24) via `scripts/deploy-officejawn.sh` |

---

## Local dev setup

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env  # fill in real values
alembic upgrade head
uvicorn api.main:app --host 0.0.0.0 --port 8090 --reload
celery -A workers.celery_app worker --loglevel=info  # separate terminal
```

Requires: PostgreSQL running locally (or on officejawn), Redis running locally.

## Tests

```bash
# Standard unit tests (81+ tests, no live services needed)
pytest -v

# Acceptance tests (requires live API + real DeepL key)
HAWK_API_KEY=hawk_test_xxx HAWK_API_BASE_URL=http://localhost:8090 pytest tests/acceptance/ -v -s
```

---

## Key design decisions

**No direct LLM API calls.** Quality scoring uses `claude -p` subprocess, not the Anthropic SDK. This keeps costs on existing subscriptions. Timeouts (30s) produce null scores — jobs still complete.

**API key format:** `hawk_live_<32 chars>` or `hawk_test_<32 chars>`. Stored as SHA-256 hash. Auth uses `hmac.compare_digest` for constant-time comparison.

**Quota enforcement:** Atomic check-and-increment via Redis Lua script (`check_and_increment_quota`). Eliminates the TOCTOU race that existed with separate check/increment calls. The old `check_quota` and `increment_quota` functions are still available for admin tooling.

**Webhook delivery** is a separate Celery task (`deliver_webhook`) with its own retry schedule (5x over 24h). This decouples delivery retries from pipeline retries.

**`ht`, `hi`, `ur` use Google Cloud Translation API.** Requires `GOOGLE_TRANSLATE_API_KEY` env var. If the key is missing or the API fails, falls back gracefully to untranslated text flagged with `needs_review: true`. These three languages are marked `"status": "limited"` in `GET /v1/languages` until the translations are validated for quality.

---

## Repo structure

```
api/          FastAPI app, routes, auth, quota
workers/      Celery tasks, segmenter, glossary, translator, scorer
db/           SQLAlchemy models, Alembic migrations
tests/        Unit tests (pytest)
tests/acceptance/  Live API tests (skipped in standard run)
scripts/      Systemd service files, deploy script
```

---

## Deployment

First time on officejawn:
```bash
./scripts/deploy-officejawn.sh --install
```

Subsequent deploys:
```bash
./scripts/deploy-officejawn.sh
```

The deploy script rsyncs code, installs deps, runs `alembic upgrade head` with verification that migrations applied cleanly, and restarts `hawk-api` and `hawk-worker` systemd services. The deploy fails if migrations don't reach head or if services fail to start.

---

## CI

GitHub Actions at `.github/workflows/tests.yml`. Matrix build across Python 3.11 and 3.12, runs on push/PR to main.

Unit tests use mocked Redis and DB — no live services needed in CI. The workflow sets `DATABASE_URL=sqlite:///./test.db` as a safety net, but tests should never actually hit the DB (they use `MagicMock` via `app.dependency_overrides`). If a CI run fails with a connection error, a test is leaking a real DB call and needs to be fixed, not the workflow.

CI also runs integration tests (`tests/test_quota_integration.py`) against a real Redis service container to verify atomic quota enforcement and TTL behavior.

---

## Bug-fixing workflow

When a bug is reported:
1. Write a failing test that reproduces it
2. Fix the root cause
3. Verify the test passes — a passing test proves the fix

Do not patch symptoms. Find the root cause.
