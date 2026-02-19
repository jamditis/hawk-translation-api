# Hawk News Service translation API

[![Tests](https://github.com/jamditis/hawk-translation-api/actions/workflows/tests.yml/badge.svg)](https://github.com/jamditis/hawk-translation-api/actions/workflows/tests.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![API docs](https://img.shields.io/badge/api-docs-orange)](https://api.hawknewsservice.org/docs)

REST API for translating journalism content into 10 languages. Built for the [Center for Cooperative Media](https://centerforcooperativemedia.org)'s Spanish Translation News Service (STNS) and NJ News Commons partner newsrooms.

Live at: `api.hawknewsservice.org`

---

## How it works

```
POST /v1/translate
    → validate API key (Redis cache → DB fallback)
    → check quota (Redis counter)
    → create job record (PostgreSQL)
    → enqueue Celery task
    → return 202 + job_id

Celery worker
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
| Translation | DeepL API (7 languages; `ht`, `hi`, `ur` are limited) |
| Quality scoring | `claude -p` subprocess — non-blocking, 30s timeout |

## Languages

| Language | Code | Status |
|---|---|---|
| Spanish | `es` | Supported |
| Portuguese | `pt` | Supported |
| Chinese (Simplified) | `zh` | Supported |
| Korean | `ko` | Supported |
| Arabic | `ar` | Supported |
| French | `fr` | Supported |
| Polish | `pl` | Supported |
| Haitian Creole | `ht` | Limited |
| Hindi | `hi` | Limited |
| Urdu | `ur` | Limited |

## Local dev

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env  # fill in real values
alembic upgrade head
uvicorn api.main:app --host 0.0.0.0 --port 8090 --reload
celery -A workers.celery_app worker --loglevel=info  # separate terminal
```

Requires: PostgreSQL and Redis running locally.

## Tests

```bash
# Unit tests (77 tests, no live services needed)
pytest -v

# Acceptance tests (requires live API + real DeepL key)
HAWK_API_KEY=hawk_test_xxx HAWK_API_BASE_URL=http://localhost:8090 pytest tests/acceptance/ -v -s
```

## API

### Submit a translation job

```http
POST /v1/translate
Authorization: Bearer hawk_live_<key>
Content-Type: application/json

{
  "content": "<p>Your article HTML here</p>",
  "source_language": "en",
  "target_language": "es",
  "tier": "instant",
  "callback_url": "https://yoursite.com/webhook"
}
```

Returns `202 Accepted` with a `job_id`.

### Check job status

```http
GET /v1/translate/{job_id}
Authorization: Bearer hawk_live_<key>
```

### List supported languages

```http
GET /v1/languages
```

## Deployment

```bash
# First time on officejawn
./scripts/deploy-officejawn.sh --install

# Subsequent deploys
./scripts/deploy-officejawn.sh
```

The deploy script rsyncs code, installs deps, runs `alembic upgrade head`, and restarts `hawk-api` and `hawk-worker` systemd services.

---

Built by [Joe Amditis](https://github.com/jamditis) for the Center for Cooperative Media, Montclair State University.
