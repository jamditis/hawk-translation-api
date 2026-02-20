# Hawk News Service translation API

[![Tests](https://github.com/jamditis/hawk-translation-api/actions/workflows/tests.yml/badge.svg)](https://github.com/jamditis/hawk-translation-api/actions/workflows/tests.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![API docs](https://img.shields.io/badge/api-docs-orange)](https://api.hawknewsservice.org/docs)

A human translator-centered REST API for translating journalism content into 10 languages. Machine translation and AI quality scoring produce a first draft; professional human translators review, edit, and certify the final output. Built for the [Center for Cooperative Media](https://centerforcooperativemedia.org)'s Spanish Translation News Service (STNS) and NJ News Commons partner newsrooms.

Live at: `api.hawknewsservice.org`

---

## How it works

Every translation passes through a pipeline designed to support human translators, not replace them. Machine translation generates a first draft, AI scoring highlights problem areas, and human translators make the final call on quality.

```
POST /v1/translate
    → validate API key
    → check quota
    → create job record
    → enqueue pipeline task
    → return 202 + job_id

Pipeline (machine draft)
    → segment HTML (BeautifulSoup4)
    → apply NJ journalism glossary (proper nouns, gov titles, place names)
    → generate machine draft via DeepL API
    → reassemble HTML
    → AI quality scoring flags segments for human attention

Human translator review
    → reviewer assigned by language pair + availability
    → side-by-side editor: machine draft vs. source
    → AI scores highlight segments that need the most attention
    → translator edits, approves, or rewrites segments
    → certified tier: second translator verifies

Delivery
    → webhook fires when human-approved translation is ready
    → result available at GET /v1/translate/{job_id}
```

### Translation tiers

| Tier | What happens |
|---|---|
| **Instant** | Machine draft + AI scoring. Fast turnaround, no human review. Suitable for time-sensitive content where speed matters most. |
| **Reviewed** | Machine draft + AI scoring + **one human translator** reviews and edits. The standard for publication-quality journalism translation. |
| **Certified** | Machine draft + AI scoring + **human translator reviews** + **second translator certifies**. Full audit trail of edits. For content requiring the highest accuracy. |

## Stack

| Component | Technology |
|---|---|
| **Human translators** | Professional bilingual journalists and translators matched by language pair |
| API server | FastAPI + uvicorn (port 8090) |
| Task queue | Celery 5.3 + Redis |
| Database | PostgreSQL 15 + SQLAlchemy 2.0 + Alembic |
| Machine draft | DeepL API (7 languages); Google Cloud Translation (`ht`, `hi`, `ur` — limited) |
| AI quality scoring | `claude -p` subprocess — flags segments for human translator attention |

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
  "tier": "reviewed",
  "callback_url": "https://yoursite.com/webhook"
}
```

The `tier` field controls how much human translator involvement your job gets:
- `"instant"` — machine draft + AI scoring only (no human review)
- `"reviewed"` — machine draft reviewed and edited by a human translator
- `"certified"` — reviewed by one translator, certified by a second

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

## Philosophy

Machine translation is a tool, not a replacement for human expertise. The Hawk News Service exists because NJ's diverse communities deserve journalism translated by people who understand the language, the culture, and the local context. Every piece of technology in this pipeline — DeepL, AI scoring, the glossary system — exists to make human translators faster and more effective, not to cut them out of the process.

---

Built by [Joe Amditis](https://github.com/jamditis) for the Center for Cooperative Media, Montclair State University.
