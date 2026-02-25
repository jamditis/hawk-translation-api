# Hawk News Service translation API — development context

## What this is

A human translator-centered REST API for translating journalism content into 10 languages. Machine translation and AI quality scoring generate a first draft; **professional human translators** review, edit, and certify the final output. Built for the Center for Cooperative Media's Spanish Translation News Service (STNS) and NJ News Commons partner newsrooms.

The technology in this pipeline exists to make human translators faster and more effective — not to replace them. Every design decision should be evaluated through that lens.

Live at: `api.hawknewsservice.org` (via Cloudflare Tunnel → houseofjawn)

---

## Architecture

```
POST /v1/translate
    → validate API key (Redis cache → DB fallback)
    → check quota (Redis counter)
    → create job record (PostgreSQL)
    → enqueue Celery task
    → return 202 + job_id

Machine draft (Celery worker, houseofjawn)
    → segment HTML (BeautifulSoup4)
    → apply NJ journalism glossary
    → generate machine draft via claude -p subprocess
    → reassemble HTML
    → AI quality scoring flags segments for human attention

Human translator review (reviewed/certified tiers)
    → assign translator by language pair + availability
    → side-by-side editor: machine draft vs. source
    → translator edits, approves, or rewrites segments
    → certified tier: second translator verifies
    → all edits tracked for quality feedback loop

Delivery
    → fire webhook when translation is ready
    → result available at GET /v1/translate/{job_id}
```

## Stack

| Component | Technology |
|---|---|
| **Human translators** | Professional bilingual journalists and translators, matched by language pair |
| API server | FastAPI + uvicorn (port 8091) |
| Task queue | Celery 5.3 + Redis |
| Database | PostgreSQL 15 + SQLAlchemy 2.0 + Alembic |
| Machine draft | `claude -p` subprocess — all 10 languages via Claude subscription |
| AI quality scoring | `claude -p` subprocess — flags segments for human translator attention (non-blocking, 30s timeout) |
| Deployment | houseofjawn (100.122.208.15) via `scripts/deploy-houseofjawn.sh` |

---

## Local dev setup

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env  # fill in real values
alembic upgrade head
uvicorn api.main:app --host 0.0.0.0 --port 8091 --reload
celery -A workers.celery_app worker --loglevel=info  # separate terminal
```

Requires: PostgreSQL running locally, Redis running locally.

## Tests

```bash
# Standard unit tests (81+ tests, no live services needed)
pytest -v

# Acceptance tests (requires live API + Claude CLI logged in)
HAWK_API_KEY=hawk_test_xxx HAWK_API_BASE_URL=http://localhost:8091 pytest tests/acceptance/ -v -s
```

---

## Key design decisions

**Human translators are the core of the pipeline.** Machine translation produces a draft; AI scoring highlights problem areas; human translators make the final editorial decisions. The "instant" tier (machine-only) exists for time-sensitive content, but the reviewed and certified tiers — where human translators edit and approve — are the standard for publication-quality journalism.

**Three tiers control human involvement.** `instant` = machine draft + AI scoring only. `reviewed` = machine draft reviewed and edited by one human translator. `certified` = reviewed by one translator, certified by a second, with full edit tracking. The tier system ensures every newsroom can choose the right balance of speed and human oversight.

**AI scoring serves human translators.** Quality scoring via `claude -p` subprocess flags segments that likely need human attention (score < 3.0), so translators can focus their effort where it matters most. Scoring is advisory — timeouts (30s) produce null scores and jobs still complete. Uses subprocess, not direct API calls, to keep costs on existing subscriptions.

**API key format:** `hawk_live_<32 chars>` or `hawk_test_<32 chars>`. Stored as SHA-256 hash. Auth uses `hmac.compare_digest` for constant-time comparison.

**Quota enforcement:** Atomic check-and-increment via Redis Lua script (`check_and_increment_quota`). Eliminates the TOCTOU race that existed with separate check/increment calls. The old `check_quota` and `increment_quota` functions are still available for admin tooling.

**Webhook delivery** is a separate Celery task (`deliver_webhook`) with its own retry schedule (5x over 24h). This decouples delivery retries from pipeline retries.

**`ht`, `hi`, `ur` are marked `"status": "limited"` in `GET /v1/languages`** until human translators have validated the machine output quality. All 10 languages run through the same `claude -p` subprocess pipeline — "limited" reflects translator validation status, not engine capability.

---

## Repo structure

```
api/          FastAPI app, routes, auth, quota
workers/      Celery tasks — machine draft pipeline (segmenter, glossary, translator, scorer)
review/       Human translator review workflow (assignment, web UI, certification)
db/           SQLAlchemy models, Alembic migrations
tests/        Unit tests (pytest)
tests/acceptance/  Live API tests (skipped in standard run)
scripts/      Systemd service files, deploy script
```

---

## Deployment

Run directly on houseofjawn (no SSH needed — the API runs here):

First time:
```bash
./scripts/deploy-houseofjawn.sh --install
```

Subsequent deploys:
```bash
./scripts/deploy-houseofjawn.sh
```

The deploy script installs deps, runs `alembic upgrade head` with verification that migrations applied cleanly, and restarts `hawk-api` and `hawk-worker` systemd services. The deploy fails if migrations don't reach head or if services fail to start.

**Cloudflare tunnel:** Route for `api.hawknewsservice.org` → `http://127.0.0.1:8091` is in `~/.cloudflared/config.yml`. DNS CNAME for `api.hawknewsservice.org` needs to be added by the domain owner (Marty) pointing to the tunnel's CNAME target.

---

## CI

GitHub Actions at `.github/workflows/tests.yml`. Matrix build across Python 3.11 and 3.12, runs on push/PR to main.

Unit tests use mocked Redis and DB — no live services needed in CI. The workflow sets `DATABASE_URL=sqlite:///./test.db` as a safety net, but tests should never actually hit the DB (they use `MagicMock` via `app.dependency_overrides`). If a CI run fails with a connection error, a test is leaking a real DB call and needs to be fixed, not the workflow.

CI also runs integration tests (`tests/test_quota_integration.py`) against a real Redis service container to verify atomic quota enforcement and TTL behavior.

---

## Current status (as of 2026-02-25)

### Running on houseofjawn
| Service | Status | Port |
|---------|--------|------|
| `hawk-api` | active | 8091 |
| `hawk-worker` | active | — |
| `redis-hawk` | active | 6380 |
| PostgreSQL `hawkapi` db | active | 5432 |

### Done
- Phase 1 + 2 complete: full pipeline, human review workflow, three tiers, quota enforcement, webhook delivery
- Translation engine: replaced DeepL/Google Translate with `claude -p` via tmux (`workers/claude_runner.py`)
- `claude_runner.py` wired into scorer and translator — both use `run_claude_p()` instead of raw subprocess
- Cloudflare tunnel config correct: `api.hawknewsservice.org` → `http://127.0.0.1:8091` (in `/etc/cloudflared/config.yml`)
- `hawk-worker` service redeployed with correct PATH (`/home/jamditis/.local/bin` included)
- WordPress plugin scaffolded at `wp-plugin/hawk-translation/`
- 97 tests passing
- Corpus analysis complete: 506 translated articles → `resources/corpus-analysis.md` (pattern gaps, inconsistencies, glossary additions)
- `SPANISH_STYLE_RULES` in `workers/translator.py` expanded with 13+ corpus-derived rules (EE. UU. usage, ICE canonical, attribution verbs, anglicisms, bill numbers, etc.)
- `docs/style-guide.html` built: searchable 266-term glossary + style rule cards, served from GitHub Pages
- All docs pages mobile-responsive: hamburger nav, responsive grid breakpoints, overflow protection
- Docs deployed to GitHub Pages: `https://jamditis.github.io/hawk-translation-api/` (switching back to hawknewsservice.org once Marty fixes Cloudflare SSL)
- `nginx.conf` no-cache rule added to prevent 10-year CDN TTL on HTML files (preserved for when hawknewsservice.org hosting resumes)

### DNS / routing status (2026-02-24)

Marty added `jamditis@gmail.com` as an approved user on his Cloudflare account.

DNS for `api.hawknewsservice.org` is now correct:
- CNAME `api → 901f6cfd-3fd0-4135-9321-3488fcaf41b6.cfargotunnel.com` (proxied, orange cloud on)

**Still returning 1033.** Most likely cause: cross-account tunnel routing — tunnel is in `jamditis@gmail.com` CF account but zone is in Marty's account. Waiting to hear back from Marty to resolve.

Fallback plan if cross-account CNAME doesn't work: `hawknewsservice.org/api/...` (WordPress page slug + reverse proxy). Main site is WordPress at `172.236.116.153`.

Tunnel ID: `901f6cfd-3fd0-4135-9321-3488fcaf41b6`
CNAME target: `901f6cfd-3fd0-4135-9321-3488fcaf41b6.cfargotunnel.com`
hawk-api local health: `curl http://127.0.0.1:8091/health` → `{"status":"ok"}`

### Not started yet
- Resolve API routing (waiting on Marty — see above)
- Create API keys for newsroom partners (admin tooling / key provisioning flow)
- Reviewer management UI (assign translators to language pairs, manage availability)
- Production `.env` hardening (real secrets, not dev defaults)

---

## Bug-fixing workflow

When a bug is reported:
1. Write a failing test that reproduces it
2. Fix the root cause
3. Verify the test passes — a passing test proves the fix

Do not patch symptoms. Find the root cause.
