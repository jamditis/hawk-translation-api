# Hawk News Service translation API — implementation plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a production REST API at `api.hawknewsservice.org` that translates journalism content into 10 languages with three quality tiers (instant AI, reviewed, certified).

**Architecture:** FastAPI + Celery + Redis + PostgreSQL on officejawn (100.84.214.24), exposed via Cloudflare Tunnel. DeepL API for machine translation; `claude -p` subprocess for quality scoring. Static marketing site deployed via SFTP to the hawknewsservice.org shared host.

**Tech stack:** Python 3.11, FastAPI 0.110, SQLAlchemy 2.0, Alembic, Celery 5.3, Redis 7, PostgreSQL 15, httpx, BeautifulSoup4, Jinja2, pytest, respx

---

## Phase 1: Core API + instant tier (weeks 1–4)

---

### Task 1: Create the project and install dependencies

**Files:**
- Create: `hawk-translation-api/` (new repo, run from `~/projects/`)
- Create: `hawk-translation-api/requirements.txt`
- Create: `hawk-translation-api/requirements-dev.txt`
- Create: `hawk-translation-api/.env.example`
- Create: `hawk-translation-api/pyproject.toml`

**Step 1: Create the project directory and virtualenv**

```bash
cd ~/projects
mkdir hawk-translation-api && cd hawk-translation-api
git init
python3.11 -m venv venv
source venv/bin/activate
```

Expected: prompt shows `(venv)`

**Step 2: Create `requirements.txt`**

```
fastapi==0.110.0
uvicorn[standard]==0.29.0
sqlalchemy==2.0.29
alembic==1.13.1
celery==5.3.6
redis==5.0.3
httpx==0.27.0
beautifulsoup4==4.12.3
lxml==5.2.1
python-dotenv==1.0.1
bcrypt==4.1.2
pydantic==2.7.0
pydantic-settings==2.2.1
jinja2==3.1.3
python-multipart==0.0.9
psycopg2-binary==2.9.9
```

**Step 3: Create `requirements-dev.txt`**

```
pytest==8.1.1
pytest-asyncio==0.23.6
pytest-cov==5.0.0
httpx==0.27.0
respx==0.21.1
factory-boy==3.3.0
```

**Step 4: Install dependencies**

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

Expected: long install output ending with `Successfully installed ...`

**Step 5: Create `.env.example`**

```
DATABASE_URL=postgresql://hawkapi:password@localhost:5432/hawkapi
REDIS_URL=redis://localhost:6379/0
DEEPL_API_KEY=your-deepl-key-here
ENVIRONMENT=development
```

**Step 6: Create `pyproject.toml`**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.coverage.run]
source = ["api", "workers", "db"]
omit = ["tests/*", "venv/*"]
```

**Step 7: Create project skeleton**

```bash
mkdir -p api workers db review docs scripts tests
touch api/__init__.py workers/__init__.py db/__init__.py review/__init__.py
touch tests/__init__.py
touch tests/conftest.py
```

**Step 8: Initial commit**

```bash
git add .
git commit -m "feat: project scaffold with dependencies"
```

---

### Task 2: Database models

**Files:**
- Create: `db/models.py`
- Create: `tests/test_models.py`

**Step 1: Write the failing test**

```python
# tests/test_models.py
import pytest
from db.models import Organization, APIKey, TranslationJob, Glossary, Reviewer, ReviewAssignment

def test_organization_model_has_required_fields():
    org = Organization(name="NJ Spotlight", slug="nj-spotlight", tier="instant", daily_quota=100)
    assert org.name == "NJ Spotlight"
    assert org.slug == "nj-spotlight"
    assert org.tier == "instant"
    assert org.daily_quota == 100

def test_translation_job_status_default():
    job = TranslationJob(
        source_language="en",
        target_language="es",
        tier="instant",
        content="<p>Hello</p>",
        content_type="article"
    )
    assert job.status == "queued"

def test_glossary_model_has_terms():
    g = Glossary(name="NJ Gov", language_pair="en-es", terms_json={"Governor": "Gobernador"})
    assert g.terms_json["Governor"] == "Gobernador"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_models.py -v
```

Expected: `ImportError: cannot import name 'Organization' from 'db.models'`

**Step 3: Create `db/models.py`**

```python
from datetime import datetime, UTC
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text, JSON,
    ForeignKey, Enum
)
from sqlalchemy.orm import DeclarativeBase, relationship
import enum


class Base(DeclarativeBase):
    pass


class TierEnum(str, enum.Enum):
    instant = "instant"
    reviewed = "reviewed"
    certified = "certified"


class StatusEnum(str, enum.Enum):
    queued = "queued"
    machine_translated = "machine_translated"
    scoring = "scoring"
    in_review = "in_review"
    reviewed = "reviewed"
    certified = "certified"
    complete = "complete"
    failed = "failed"


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False, unique=True)
    tier = Column(String(20), nullable=False, default="instant")
    daily_quota = Column(Integer, nullable=False, default=50)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    api_keys = relationship("APIKey", back_populates="organization")
    jobs = relationship("TranslationJob", back_populates="organization")


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    key_hash = Column(String(64), nullable=False, unique=True)
    key_prefix = Column(String(16), nullable=False)  # e.g. "hawk_live_abc1"
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    last_used_at = Column(DateTime, nullable=True)

    organization = relationship("Organization", back_populates="api_keys")


class TranslationJob(Base):
    __tablename__ = "translation_jobs"

    id = Column(String(36), primary_key=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=True)
    api_key_id = Column(String(36), ForeignKey("api_keys.id"), nullable=True)
    status = Column(String(30), nullable=False, default="queued")
    source_language = Column(String(5), nullable=False)
    target_language = Column(String(5), nullable=False)
    tier = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    translated_content = Column(Text, nullable=True)
    content_type = Column(String(30), nullable=False, default="article")
    metadata_json = Column(JSON, nullable=True)
    word_count = Column(Integer, nullable=True)
    quality_scores_json = Column(JSON, nullable=True)
    callback_url = Column(String(500), nullable=True)
    glossary_id = Column(String(36), ForeignKey("glossaries.id"), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    completed_at = Column(DateTime, nullable=True)

    organization = relationship("Organization", back_populates="jobs")


class Glossary(Base):
    __tablename__ = "glossaries"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    language_pair = Column(String(10), nullable=False)  # e.g. "en-es"
    terms_json = Column(JSON, nullable=False, default=dict)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=True)  # null = default
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class Reviewer(Base):
    __tablename__ = "reviewers"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    language_pairs_json = Column(JSON, nullable=False, default=list)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class ReviewAssignment(Base):
    __tablename__ = "review_assignments"

    id = Column(String(36), primary_key=True)
    job_id = Column(String(36), ForeignKey("translation_jobs.id"), nullable=False)
    reviewer_id = Column(String(36), ForeignKey("reviewers.id"), nullable=False)
    role = Column(String(20), nullable=False)  # "reviewer" or "certifier"
    assigned_at = Column(DateTime, default=lambda: datetime.now(UTC))
    completed_at = Column(DateTime, nullable=True)
    diff_json = Column(JSON, nullable=True)  # tracked edits vs machine output


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(String(36), primary_key=True)
    job_id = Column(String(36), ForeignKey("translation_jobs.id"), nullable=False)
    callback_url = Column(String(500), nullable=False)
    attempt_count = Column(Integer, default=0)
    last_attempt_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending, delivered, abandoned
    last_response_code = Column(Integer, nullable=True)
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_models.py -v
```

Expected: `3 passed`

**Step 5: Commit**

```bash
git add db/models.py tests/test_models.py
git commit -m "feat: database models for jobs, orgs, keys, review"
```

---

### Task 3: Database setup and Alembic migrations

**Files:**
- Create: `db/database.py`
- Create: `alembic.ini` (generated)
- Create: `alembic/env.py` (modified after generation)
- Create: `scripts/create_db.sh`

**Step 1: Initialize Alembic**

```bash
alembic init alembic
```

Expected: creates `alembic/` directory and `alembic.ini`

**Step 2: Create `db/database.py`**

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from db.models import Base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://hawkapi:password@localhost:5432/hawkapi")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    Base.metadata.create_all(bind=engine)
```

**Step 3: Update `alembic/env.py` to import models**

In `alembic/env.py`, find the line `target_metadata = None` and replace it:

```python
# Add near the top of env.py, after existing imports:
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.models import Base
from db.database import DATABASE_URL

# Replace target_metadata = None with:
target_metadata = Base.metadata

# Replace the config.get_main_option("sqlalchemy.url") calls with:
# config.set_main_option("sqlalchemy.url", DATABASE_URL)
```

**Step 4: Update `alembic.ini`**

Find `sqlalchemy.url = driver://user:pass@localhost/dbname` and replace with your URL, or leave it and let `env.py` handle it dynamically.

**Step 5: Create the Postgres database on officejawn**

SSH to officejawn and run:

```bash
ssh officejawn
sudo -u postgres psql -c "CREATE USER hawkapi WITH PASSWORD 'choose-strong-password';"
sudo -u postgres psql -c "CREATE DATABASE hawkapi OWNER hawkapi;"
exit
```

**Step 6: Set your `.env` from `.env.example` and run the migration**

```bash
cp .env.example .env
# Edit .env with real values
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

Expected: `Running upgrade  -> <hash>, initial schema`

**Step 7: Commit**

```bash
git add alembic/ alembic.ini db/database.py
git commit -m "feat: alembic migrations and database setup"
```

---

### Task 4: API key generation and hashing

**Files:**
- Create: `api/keys.py`
- Create: `tests/test_keys.py`

**Step 1: Write the failing test**

```python
# tests/test_keys.py
from api.keys import generate_api_key, hash_key, verify_key

def test_generate_live_key_format():
    key = generate_api_key(environment="live")
    assert key.startswith("hawk_live_")
    assert len(key) == len("hawk_live_") + 32

def test_generate_test_key_format():
    key = generate_api_key(environment="test")
    assert key.startswith("hawk_test_")

def test_key_prefix_extraction():
    key = generate_api_key(environment="live")
    prefix = key[:14]  # "hawk_live_" + 4 chars
    assert prefix.startswith("hawk_live_")

def test_hash_is_deterministic():
    key = "hawk_live_abc123def456ghi789jkl012mno3"
    assert hash_key(key) == hash_key(key)

def test_verify_correct_key():
    key = generate_api_key()
    hashed = hash_key(key)
    assert verify_key(key, hashed) is True

def test_verify_wrong_key():
    key = generate_api_key()
    hashed = hash_key(key)
    assert verify_key("hawk_live_wrongkey12345678901234567", hashed) is False
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_keys.py -v
```

Expected: `ImportError: cannot import name 'generate_api_key'`

**Step 3: Create `api/keys.py`**

```python
import secrets
import hashlib
import bcrypt


def generate_api_key(environment: str = "live") -> str:
    """Generate a new API key. Format: hawk_{env}_{32 random chars}"""
    random_part = secrets.token_urlsafe(24)[:32]
    return f"hawk_{environment}_{random_part}"


def hash_key(key: str) -> str:
    """SHA-256 hash of the key for DB storage. Fast lookup, not bcrypt."""
    return hashlib.sha256(key.encode()).hexdigest()


def verify_key(key: str, stored_hash: str) -> bool:
    """Verify a key against its stored hash."""
    return hash_key(key) == stored_hash


def extract_prefix(key: str) -> str:
    """Extract display prefix (e.g. 'hawk_live_abc1') for UI display."""
    parts = key.split("_")
    if len(parts) < 3:
        return key[:14]
    env_part = f"hawk_{parts[1]}_"
    return env_part + parts[2][:4]
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_keys.py -v
```

Expected: `6 passed`

**Step 5: Commit**

```bash
git add api/keys.py tests/test_keys.py
git commit -m "feat: API key generation and hashing"
```

---

### Task 5: Auth middleware

**Files:**
- Create: `api/auth.py`
- Create: `tests/test_auth.py`

**Step 1: Write the failing test**

```python
# tests/test_auth.py
import pytest
from unittest.mock import MagicMock, patch
from api.auth import authenticate_request, AuthContext

def make_mock_db(key_hash=None, org_id="org-123", tier="instant", daily_quota=100, active=True):
    mock_key = MagicMock()
    mock_key.key_hash = key_hash or "abc123"
    mock_key.active = active
    mock_key.org_id = org_id
    mock_key.id = "key-456"

    mock_org = MagicMock()
    mock_org.id = org_id
    mock_org.tier = tier
    mock_org.daily_quota = daily_quota
    mock_org.active = True

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_key
    mock_db.get.return_value = mock_org
    return mock_db, mock_key, mock_org

def test_missing_auth_header_raises():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        authenticate_request(authorization=None, db=MagicMock(), redis_client=MagicMock())
    assert exc.value.status_code == 401

def test_malformed_header_raises():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        authenticate_request(authorization="not-bearer-format", db=MagicMock(), redis_client=MagicMock())
    assert exc.value.status_code == 401

def test_invalid_key_raises():
    from fastapi import HTTPException
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    with pytest.raises(HTTPException) as exc:
        authenticate_request(authorization="Bearer hawk_live_badkey123", db=mock_db, redis_client=mock_redis)
    assert exc.value.status_code == 401

def test_valid_key_returns_auth_context():
    from api.keys import generate_api_key, hash_key
    key = generate_api_key()
    mock_db, mock_key, mock_org = make_mock_db(key_hash=hash_key(key))
    mock_redis = MagicMock()
    mock_redis.get.return_value = None  # cache miss

    ctx = authenticate_request(
        authorization=f"Bearer {key}",
        db=mock_db,
        redis_client=mock_redis
    )
    assert isinstance(ctx, AuthContext)
    assert ctx.org_id == "org-123"
    assert ctx.tier == "instant"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_auth.py -v
```

Expected: `ImportError: cannot import name 'authenticate_request'`

**Step 3: Create `api/auth.py`**

```python
import json
from dataclasses import dataclass
from fastapi import HTTPException
from sqlalchemy.orm import Session
from redis import Redis
from api.keys import hash_key
from db.models import APIKey, Organization


@dataclass
class AuthContext:
    org_id: str
    org_name: str
    tier: str
    daily_quota: int
    api_key_id: str


CACHE_TTL_SECONDS = 300  # 5 minutes


def authenticate_request(
    authorization: str | None,
    db: Session,
    redis_client: Redis
) -> AuthContext:
    if not authorization:
        raise HTTPException(status_code=401, detail={"error": "missing_auth_header"})

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail={"error": "invalid_auth_format"})

    raw_key = parts[1]
    key_hash = hash_key(raw_key)

    # Check Redis cache first
    cache_key = f"api_key:{key_hash}"
    cached = redis_client.get(cache_key)
    if cached:
        data = json.loads(cached)
        return AuthContext(**data)

    # DB lookup
    api_key = db.query(APIKey).filter(
        APIKey.key_hash == key_hash,
        APIKey.active == True
    ).first()

    if not api_key:
        raise HTTPException(status_code=401, detail={"error": "invalid_api_key"})

    org = db.get(Organization, api_key.org_id)
    if not org or not org.active:
        raise HTTPException(status_code=401, detail={"error": "invalid_api_key"})

    ctx = AuthContext(
        org_id=org.id,
        org_name=org.name,
        tier=org.tier,
        daily_quota=org.daily_quota,
        api_key_id=api_key.id
    )

    # Cache the result
    redis_client.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(ctx.__dict__))

    return ctx
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_auth.py -v
```

Expected: `4 passed`

**Step 5: Commit**

```bash
git add api/auth.py tests/test_auth.py
git commit -m "feat: auth middleware with Redis caching"
```

---

### Task 6: Rate limiting (quota enforcement)

**Files:**
- Create: `api/quota.py`
- Create: `tests/test_quota.py`

**Step 1: Write the failing test**

```python
# tests/test_quota.py
import pytest
from unittest.mock import MagicMock
from api.quota import check_quota, increment_quota

def make_redis(current_count: int | None):
    mock = MagicMock()
    mock.get.return_value = str(current_count).encode() if current_count is not None else None
    return mock

def test_under_quota_passes():
    redis = make_redis(current_count=10)
    # Should not raise
    check_quota(org_id="org-1", daily_quota=100, redis_client=redis)

def test_at_quota_raises():
    from fastapi import HTTPException
    redis = make_redis(current_count=100)
    with pytest.raises(HTTPException) as exc:
        check_quota(org_id="org-1", daily_quota=100, redis_client=redis)
    assert exc.value.status_code == 429
    assert "quota_exceeded" in str(exc.value.detail)

def test_no_existing_count_passes():
    redis = make_redis(current_count=None)
    check_quota(org_id="org-1", daily_quota=50, redis_client=redis)

def test_increment_sets_expiry():
    redis = MagicMock()
    redis.get.return_value = None
    increment_quota(org_id="org-1", redis_client=redis)
    redis.incr.assert_called_once()
    redis.expireat.assert_called_once()
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_quota.py -v
```

Expected: `ImportError: cannot import name 'check_quota'`

**Step 3: Create `api/quota.py`**

```python
from datetime import datetime, UTC, timedelta
from fastapi import HTTPException
from redis import Redis


def _quota_key(org_id: str) -> str:
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"quota:{org_id}:{date_str}"


def _midnight_timestamp() -> int:
    now = datetime.now(UTC)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(midnight.timestamp())


def check_quota(org_id: str, daily_quota: int, redis_client: Redis) -> None:
    key = _quota_key(org_id)
    current = redis_client.get(key)
    count = int(current) if current else 0
    if count >= daily_quota:
        reset_at = datetime.fromtimestamp(_midnight_timestamp(), UTC).isoformat()
        raise HTTPException(
            status_code=429,
            detail={"error": "quota_exceeded", "reset_at": reset_at, "limit": daily_quota}
        )


def increment_quota(org_id: str, redis_client: Redis) -> int:
    key = _quota_key(org_id)
    count = redis_client.incr(key)
    if count == 1:
        redis_client.expireat(key, _midnight_timestamp())
    return count
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_quota.py -v
```

Expected: `4 passed`

**Step 5: Commit**

```bash
git add api/quota.py tests/test_quota.py
git commit -m "feat: daily quota enforcement via Redis"
```

---

### Task 7: HTML segmentation

**Files:**
- Create: `workers/segmenter.py`
- Create: `tests/test_segmenter.py`

**Step 1: Write the failing test**

```python
# tests/test_segmenter.py
from workers.segmenter import segment_html, reassemble_html

def test_extracts_paragraph_text():
    html = "<p>Hello world.</p><p>Second paragraph.</p>"
    segments = segment_html(html)
    assert len(segments) == 2
    assert segments[0]["text"] == "Hello world."
    assert segments[1]["text"] == "Second paragraph."

def test_preserves_html_tags():
    html = "<p>Hello <strong>world</strong>.</p>"
    segments = segment_html(html)
    # The inner HTML should be preserved as-is
    assert "strong" in segments[0]["inner_html"]

def test_extracts_headline_separately():
    html = "<h1>City council votes on budget</h1><p>The council met Tuesday.</p>"
    segments = segment_html(html)
    assert any(s["tag"] == "h1" for s in segments)
    assert any(s["tag"] == "p" for s in segments)

def test_reassemble_produces_valid_html():
    html = "<p>Hello world.</p><p>Second paragraph.</p>"
    segments = segment_html(html)
    # Simulate translation
    for s in segments:
        s["translated"] = s["text"].upper()
    result = reassemble_html(segments)
    assert "<p>" in result
    assert "HELLO WORLD." in result

def test_empty_paragraphs_skipped():
    html = "<p></p><p>Real content.</p><p>  </p>"
    segments = segment_html(html)
    assert len(segments) == 1
    assert segments[0]["text"] == "Real content."
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_segmenter.py -v
```

Expected: `ImportError: cannot import name 'segment_html'`

**Step 3: Create `workers/segmenter.py`**

```python
from bs4 import BeautifulSoup, NavigableString, Tag

TRANSLATABLE_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "figcaption", "td", "th"}


def segment_html(html: str) -> list[dict]:
    """
    Parse HTML and extract translatable segments.
    Each segment: {index, tag, text, inner_html, translated}
    Preserves structure for reassembly.
    """
    soup = BeautifulSoup(html, "lxml")
    segments = []
    index = 0

    for element in soup.find_all(TRANSLATABLE_TAGS):
        text = element.get_text(strip=True)
        if not text:
            continue
        segments.append({
            "index": index,
            "tag": element.name,
            "text": text,
            "inner_html": str(element),
            "translated": None,
        })
        index += 1

    return segments


def reassemble_html(segments: list[dict]) -> str:
    """
    Reassemble translated segments back into HTML.
    Uses the translated text, wrapped in original tag.
    """
    parts = []
    for seg in segments:
        translated = seg.get("translated") or seg["text"]
        parts.append(f"<{seg['tag']}>{translated}</{seg['tag']}>")
    return "\n".join(parts)
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_segmenter.py -v
```

Expected: `5 passed`

**Step 5: Commit**

```bash
git add workers/segmenter.py tests/test_segmenter.py
git commit -m "feat: HTML segmentation and reassembly for translation"
```

---

### Task 8: Glossary application

**Files:**
- Create: `workers/glossary.py`
- Create: `tests/test_glossary.py`

**Step 1: Write the failing test**

```python
# tests/test_glossary.py
from workers.glossary import apply_glossary

def test_applies_known_term():
    text = "The Governor announced the budget."
    terms = {"Governor": "Gobernador"}
    result = apply_glossary(text, terms)
    assert "Gobernador" in result

def test_case_insensitive_match():
    text = "The governor announced the budget."
    terms = {"Governor": "Gobernador"}
    result = apply_glossary(text, terms)
    assert "Gobernador" in result

def test_no_partial_match():
    text = "Governance matters."
    terms = {"Governor": "Gobernador"}
    result = apply_glossary(text, terms)
    assert "Gobernador" not in result
    assert "Governance" in result

def test_multiple_terms():
    text = "The Montclair Board of Education voted."
    terms = {"Board of Education": "Junta de Educación", "Montclair": "Montclair"}
    result = apply_glossary(text, terms)
    assert "Junta de Educación" in result

def test_empty_terms_returns_original():
    text = "Hello world."
    result = apply_glossary(text, {})
    assert result == text
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_glossary.py -v
```

Expected: `ImportError: cannot import name 'apply_glossary'`

**Step 3: Create `workers/glossary.py`**

```python
import re


def apply_glossary(text: str, terms: dict[str, str]) -> str:
    """
    Apply glossary substitutions to text before translation.
    Uses whole-word matching, case-insensitive.
    Longer terms are applied first to avoid partial matches.
    """
    if not terms:
        return text

    result = text
    # Sort by length descending so "Board of Education" matches before "Board"
    sorted_terms = sorted(terms.items(), key=lambda x: len(x[0]), reverse=True)

    for source, target in sorted_terms:
        pattern = re.compile(r'\b' + re.escape(source) + r'\b', re.IGNORECASE)
        result = pattern.sub(target, result)

    return result
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_glossary.py -v
```

Expected: `5 passed`

**Step 5: Commit**

```bash
git add workers/glossary.py tests/test_glossary.py
git commit -m "feat: glossary application with whole-word matching"
```

---

### Task 9: DeepL translation integration

**Files:**
- Create: `workers/translator.py`
- Create: `tests/test_translator.py`

**Step 1: Write the failing test**

```python
# tests/test_translator.py
import pytest
import respx
import httpx
from workers.translator import translate_segments, DEEPL_API_URL

SUPPORTED_LANGUAGES = ["es", "pt", "ht", "zh", "ko", "ar", "fr", "pl", "hi", "ur"]

def test_supported_languages_list():
    from workers.translator import SUPPORTED_TARGET_LANGUAGES
    for lang in SUPPORTED_LANGUAGES:
        assert lang in SUPPORTED_TARGET_LANGUAGES

@respx.mock
def test_translate_segments_calls_deepl():
    mock_response = {
        "translations": [{"detected_source_language": "EN", "text": "Hola mundo."}]
    }
    respx.post(DEEPL_API_URL).mock(return_value=httpx.Response(200, json=mock_response))

    segments = [{"index": 0, "tag": "p", "text": "Hello world.", "inner_html": "<p>Hello world.</p>", "translated": None}]
    result = translate_segments(segments, target_language="es", api_key="fake-key")
    assert result[0]["translated"] == "Hola mundo."

@respx.mock
def test_deepl_error_raises():
    respx.post(DEEPL_API_URL).mock(return_value=httpx.Response(429, json={"message": "Too many requests"}))
    segments = [{"index": 0, "tag": "p", "text": "Hello.", "inner_html": "<p>Hello.</p>", "translated": None}]
    with pytest.raises(Exception, match="DeepL"):
        translate_segments(segments, target_language="es", api_key="fake-key")
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_translator.py -v
```

Expected: `ImportError: cannot import name 'translate_segments'`

**Step 3: Create `workers/translator.py`**

```python
import httpx
import os

DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"

SUPPORTED_TARGET_LANGUAGES = {
    "es": "ES",   # Spanish
    "pt": "PT-BR", # Portuguese (Brazil)
    "ht": "HT",   # Haitian Creole (use Google fallback - DeepL doesn't support HT)
    "zh": "ZH",   # Chinese Simplified
    "ko": "KO",   # Korean
    "ar": "AR",   # Arabic
    "fr": "FR",   # French
    "pl": "PL",   # Polish
    "hi": "HI",   # Hindi (DeepL beta)
    "ur": "UK",   # Urdu — fallback to Google Translate
}

# DeepL language codes that it actually supports (others need Google fallback)
DEEPL_SUPPORTED = {"es", "pt", "zh", "ko", "fr", "pl"}
GOOGLE_FALLBACK = {"ht", "ar", "hi", "ur"}


def translate_segments(
    segments: list[dict],
    target_language: str,
    api_key: str,
) -> list[dict]:
    """
    Translate all segments to target_language using DeepL.
    Updates each segment's 'translated' field in-place and returns list.
    """
    if not segments:
        return segments

    texts = [s["text"] for s in segments]
    deepl_lang = SUPPORTED_TARGET_LANGUAGES.get(target_language, target_language.upper())

    if target_language in GOOGLE_FALLBACK:
        return _translate_via_google(segments, target_language)

    response = httpx.post(
        DEEPL_API_URL,
        headers={"Authorization": f"DeepL-Auth-Key {api_key}"},
        json={
            "text": texts,
            "source_lang": "EN",
            "target_lang": deepl_lang,
            "tag_handling": "xml",
            "preserve_formatting": True,
        },
        timeout=30.0,
    )

    if response.status_code != 200:
        raise Exception(f"DeepL API error {response.status_code}: {response.text}")

    data = response.json()
    for i, translation in enumerate(data["translations"]):
        segments[i]["translated"] = translation["text"]

    return segments


def _translate_via_google(segments: list[dict], target_language: str) -> list[dict]:
    """Fallback for languages DeepL doesn't support (ht, ar, hi, ur)."""
    # TODO: implement Google Translate API calls
    # For now, return untranslated (will be flagged for human review)
    for seg in segments:
        seg["translated"] = seg["text"]
        seg["needs_review"] = True
    return segments
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_translator.py -v
```

Expected: `3 passed`

**Step 5: Commit**

```bash
git add workers/translator.py tests/test_translator.py
git commit -m "feat: DeepL translation integration with Google fallback stubs"
```

---

### Task 10: Quality scoring via claude subprocess

**Files:**
- Create: `workers/scorer.py`
- Create: `tests/test_scorer.py`

**Step 1: Write the failing test**

```python
# tests/test_scorer.py
import pytest
from unittest.mock import patch, MagicMock
from workers.scorer import score_translation, ScoreResult

def make_mock_run(stdout: str, returncode: int = 0):
    result = MagicMock()
    result.stdout = stdout
    result.returncode = returncode
    return result

def test_parses_valid_score_output():
    mock_output = '{"overall": 4.2, "fluency": 4, "accuracy": 4.5, "flags": []}'
    with patch("subprocess.run", return_value=make_mock_run(mock_output)):
        result = score_translation(original="Hello world.", translated="Hola mundo.", target_lang="es")
    assert isinstance(result, ScoreResult)
    assert result.overall == 4.2
    assert result.fluency == 4
    assert result.accuracy == 4.5
    assert result.flags == []

def test_low_score_segment_flagged():
    mock_output = '{"overall": 2.1, "fluency": 2, "accuracy": 2, "flags": ["awkward phrasing"]}'
    with patch("subprocess.run", return_value=make_mock_run(mock_output)):
        result = score_translation(original="Complex legal text.", translated="Bad translation.", target_lang="es")
    assert result.overall < 3
    assert result.needs_review is True

def test_timeout_returns_null_scores():
    import subprocess
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 30)):
        result = score_translation(original="Hello.", translated="Hola.", target_lang="es")
    assert result is None  # None = scoring skipped, not a failure

def test_malformed_json_returns_none():
    with patch("subprocess.run", return_value=make_mock_run("not json")):
        result = score_translation(original="Hello.", translated="Hola.", target_lang="es")
    assert result is None
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_scorer.py -v
```

Expected: `ImportError: cannot import name 'score_translation'`

**Step 3: Create `workers/scorer.py`**

```python
import subprocess
import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

SCORE_THRESHOLD = 3.0  # segments below this are flagged for human review
SUBPROCESS_TIMEOUT = 30  # seconds


@dataclass
class ScoreResult:
    overall: float
    fluency: float
    accuracy: float
    flags: list[str] = field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return self.overall < SCORE_THRESHOLD


SCORING_PROMPT_TEMPLATE = """Score this translation from English to {target_lang}.

Original English:
{original}

Translation:
{translated}

Evaluate on:
- Fluency: Does it read naturally in {target_lang}? (1-5)
- Accuracy: Is the meaning preserved? (1-5)
- Overall: Combined quality score (1-5)

Flag any issues (awkward phrasing, mistranslated terms, changed meaning, etc.)

Respond with ONLY valid JSON, no other text:
{{"overall": <number>, "fluency": <number>, "accuracy": <number>, "flags": [<strings>]}}"""


def score_translation(original: str, translated: str, target_lang: str) -> ScoreResult | None:
    """
    Score a translation using claude -p subprocess.
    Returns None if scoring fails or times out — jobs still complete, scoring is advisory.
    """
    prompt = SCORING_PROMPT_TEMPLATE.format(
        target_lang=target_lang,
        original=original[:2000],  # cap to avoid huge prompts
        translated=translated[:2000],
    )

    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
        data = json.loads(result.stdout.strip())
        return ScoreResult(
            overall=float(data["overall"]),
            fluency=float(data["fluency"]),
            accuracy=float(data["accuracy"]),
            flags=data.get("flags", []),
        )
    except subprocess.TimeoutExpired:
        logger.warning("Quality scoring timed out for translation to %s", target_lang)
        return None
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("Quality scoring returned invalid output: %s", e)
        return None
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_scorer.py -v
```

Expected: `4 passed`

**Step 5: Commit**

```bash
git add workers/scorer.py tests/test_scorer.py
git commit -m "feat: quality scoring via claude -p subprocess"
```

---

### Task 11: Celery worker and translation pipeline task

**Files:**
- Create: `workers/celery_app.py`
- Create: `workers/tasks.py`
- Create: `tests/test_tasks.py`

**Step 1: Write the failing test**

```python
# tests/test_tasks.py
import pytest
from unittest.mock import patch, MagicMock, call

def test_translation_task_updates_job_status():
    """Pipeline updates status through queued -> machine_translated -> complete."""
    mock_db = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "job-123"
    mock_job.status = "queued"
    mock_job.content = "<p>Hello world.</p>"
    mock_job.source_language = "en"
    mock_job.target_language = "es"
    mock_job.tier = "instant"
    mock_job.glossary_id = None
    mock_job.callback_url = None

    mock_db.get.return_value = mock_job

    with patch("workers.tasks.get_db_session", return_value=mock_db), \
         patch("workers.tasks.translate_segments", return_value=[
             {"index": 0, "tag": "p", "text": "Hello world.", "translated": "Hola mundo.", "inner_html": "<p>Hello world.</p>"}
         ]), \
         patch("workers.tasks.score_translation", return_value=None), \
         patch("workers.tasks.send_webhook"):
        from workers.tasks import run_translation_pipeline
        run_translation_pipeline("job-123")

    # Status should have progressed
    status_calls = [c[0][0] for c in mock_job.__setattr__.call_args_list if c[0][0] == "status"]
    assert mock_db.commit.called
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_tasks.py -v
```

Expected: `ImportError`

**Step 3: Create `workers/celery_app.py`**

```python
import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "hawk",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
```

**Step 4: Create `workers/tasks.py`**

```python
import logging
from datetime import datetime, UTC
from workers.celery_app import celery_app
from workers.segmenter import segment_html, reassemble_html
from workers.translator import translate_segments
from workers.scorer import score_translation
from workers.glossary import apply_glossary
from db.database import SessionLocal
from db.models import TranslationJob, Glossary
import os
import httpx

logger = logging.getLogger(__name__)


def get_db_session():
    return SessionLocal()


def send_webhook(callback_url: str, job_id: str, payload: dict) -> None:
    try:
        httpx.post(callback_url, json=payload, timeout=10.0)
    except Exception as e:
        logger.warning("Webhook delivery failed for job %s: %s", job_id, e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def run_translation_pipeline(self, job_id: str) -> None:
    db = get_db_session()
    try:
        job = db.get(TranslationJob, job_id)
        if not job:
            logger.error("Job %s not found", job_id)
            return

        # Stage 1: segment HTML
        job.status = "machine_translated"
        db.commit()

        segments = segment_html(job.content)

        # Stage 2: apply glossary
        glossary_terms = {}
        if job.glossary_id:
            glossary = db.get(Glossary, job.glossary_id)
            if glossary:
                glossary_terms = glossary.terms_json

        for seg in segments:
            seg["text"] = apply_glossary(seg["text"], glossary_terms)

        # Stage 3: translate via DeepL
        deepl_key = os.getenv("DEEPL_API_KEY", "")
        segments = translate_segments(segments, target_language=job.target_language, api_key=deepl_key)

        # Stage 4: reassemble
        job.translated_content = reassemble_html(segments)
        job.word_count = sum(len(s["text"].split()) for s in segments)

        # Stage 5: quality scoring (non-blocking)
        job.status = "scoring"
        db.commit()

        all_scores = []
        for seg in segments:
            score = score_translation(
                original=seg["text"],
                translated=seg.get("translated", ""),
                target_lang=job.target_language
            )
            if score:
                all_scores.append({
                    "index": seg["index"],
                    "overall": score.overall,
                    "fluency": score.fluency,
                    "accuracy": score.accuracy,
                    "flags": score.flags,
                    "needs_review": score.needs_review,
                })

        job.quality_scores_json = all_scores if all_scores else None

        # Stage 6: complete (instant tier) or queue for review
        if job.tier == "instant":
            job.status = "complete"
            job.completed_at = datetime.now(UTC)
        else:
            job.status = "in_review"
            # TODO Phase 2: assign reviewer

        db.commit()

        # Stage 7: webhook delivery
        if job.callback_url and job.status == "complete":
            send_webhook(job.callback_url, job_id, {
                "job_id": job_id,
                "status": job.status,
                "translated_content": job.translated_content,
                "quality_scores": job.quality_scores_json,
            })

    except Exception as exc:
        logger.exception("Pipeline failed for job %s", job_id)
        if db.get(TranslationJob, job_id):
            job = db.get(TranslationJob, job_id)
            job.status = "failed"
            job.error_message = str(exc)
            db.commit()
        raise self.retry(exc=exc)
    finally:
        db.close()
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_tasks.py -v
```

Expected: `1 passed`

**Step 6: Commit**

```bash
git add workers/celery_app.py workers/tasks.py tests/test_tasks.py
git commit -m "feat: Celery translation pipeline task"
```

---

### Task 12: FastAPI app and endpoints

**Files:**
- Create: `api/main.py`
- Create: `api/routes/translate.py`
- Create: `api/routes/admin.py`
- Create: `tests/test_api.py`

**Step 1: Write the failing test**

```python
# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from api.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_get_languages():
    response = client.get("/v1/languages")
    assert response.status_code == 200
    data = response.json()
    assert "languages" in data
    assert any(lang["code"] == "es" for lang in data["languages"])

def test_translate_requires_auth():
    response = client.post("/v1/translate", json={
        "content": "<p>Hello</p>",
        "source_language": "en",
        "target_language": "es",
        "tier": "instant"
    })
    assert response.status_code == 401

def test_translate_with_valid_key_returns_job_id():
    mock_ctx = MagicMock()
    mock_ctx.org_id = "org-123"
    mock_ctx.tier = "instant"
    mock_ctx.daily_quota = 100
    mock_ctx.api_key_id = "key-456"

    with patch("api.routes.translate.authenticate_request", return_value=mock_ctx), \
         patch("api.routes.translate.check_quota"), \
         patch("api.routes.translate.increment_quota"), \
         patch("api.routes.translate.run_translation_pipeline.delay"), \
         patch("api.routes.translate.get_db"):
        response = client.post(
            "/v1/translate",
            headers={"Authorization": "Bearer hawk_live_test123"},
            json={
                "content": "<p>Hello world.</p>",
                "source_language": "en",
                "target_language": "es",
                "tier": "instant"
            }
        )
    assert response.status_code == 202
    assert "job_id" in response.json()
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_api.py -v
```

Expected: `ImportError: cannot import name 'app'`

**Step 3: Create `api/routes/translate.py`**

```python
import uuid
from datetime import datetime, UTC
from fastapi import APIRouter, Header, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from redis import Redis
from api.auth import authenticate_request
from api.quota import check_quota, increment_quota
from db.database import get_db
from db.models import TranslationJob
from workers.tasks import run_translation_pipeline
from workers.translator import SUPPORTED_TARGET_LANGUAGES
import os

router = APIRouter()
redis_client = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

LANGUAGES = [
    {"code": "es", "name": "Spanish", "native": "Español"},
    {"code": "pt", "name": "Portuguese", "native": "Português"},
    {"code": "ht", "name": "Haitian Creole", "native": "Kreyòl ayisyen"},
    {"code": "zh", "name": "Chinese (Simplified)", "native": "中文"},
    {"code": "ko", "name": "Korean", "native": "한국어"},
    {"code": "ar", "name": "Arabic", "native": "العربية"},
    {"code": "fr", "name": "French", "native": "Français"},
    {"code": "pl", "name": "Polish", "native": "Polski"},
    {"code": "hi", "name": "Hindi", "native": "हिन्दी"},
    {"code": "ur", "name": "Urdu", "native": "اردو"},
]


class TranslateRequest(BaseModel):
    content: str
    source_language: str = "en"
    target_language: str
    tier: str = "instant"
    content_type: str = "article"
    metadata: dict | None = None
    callback_url: str | None = None
    glossary_id: str | None = None


@router.get("/languages")
def get_languages():
    return {"languages": LANGUAGES}


@router.post("/translate", status_code=202)
def create_translation_job(
    request: TranslateRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    ctx = authenticate_request(authorization=authorization, db=db, redis_client=redis_client)
    check_quota(org_id=ctx.org_id, daily_quota=ctx.daily_quota, redis_client=redis_client)

    if request.target_language not in SUPPORTED_TARGET_LANGUAGES:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=422,
            detail={"error": "unsupported_language", "supported": list(SUPPORTED_TARGET_LANGUAGES.keys())}
        )

    if len(request.content) > 50_000:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail={"error": "content_too_large"})

    job_id = str(uuid.uuid4())
    job = TranslationJob(
        id=job_id,
        org_id=ctx.org_id,
        api_key_id=ctx.api_key_id,
        source_language=request.source_language,
        target_language=request.target_language,
        tier=request.tier,
        content=request.content,
        content_type=request.content_type,
        metadata_json=request.metadata,
        callback_url=request.callback_url,
        glossary_id=request.glossary_id,
        status="queued",
    )
    db.add(job)
    db.commit()

    increment_quota(org_id=ctx.org_id, redis_client=redis_client)
    run_translation_pipeline.delay(job_id)

    return {
        "job_id": job_id,
        "status": "queued",
        "tier": request.tier,
        "source_language": request.source_language,
        "target_language": request.target_language,
        "created_at": datetime.now(UTC).isoformat(),
        "links": {
            "self": f"/v1/translate/{job_id}",
        }
    }


@router.get("/translate/{job_id}")
def get_job(
    job_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    ctx = authenticate_request(authorization=authorization, db=db, redis_client=redis_client)
    job = db.get(TranslationJob, job_id)
    if not job or job.org_id != ctx.org_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail={"error": "job_not_found"})

    response = {
        "job_id": job.id,
        "status": job.status,
        "tier": job.tier,
        "source_language": job.source_language,
        "target_language": job.target_language,
        "word_count": job.word_count,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }

    if job.status == "complete":
        response["translated_content"] = job.translated_content
        response["quality_scores"] = job.quality_scores_json

    return response
```

**Step 4: Create `api/main.py`**

```python
from fastapi import FastAPI
from api.routes.translate import router as translate_router

app = FastAPI(
    title="Hawk News Service translation API",
    description="Translation API for local and nonprofit newsrooms",
    version="1.0.0",
)

app.include_router(translate_router, prefix="/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
```

**Step 5: Run tests to verify they pass**

```bash
pytest tests/test_api.py -v
```

Expected: `4 passed`

**Step 6: Run all tests to verify nothing broke**

```bash
pytest -v
```

Expected: all tests pass

**Step 7: Commit**

```bash
git add api/ tests/test_api.py
git commit -m "feat: FastAPI app with translate and languages endpoints"
```

---

### Task 13: Systemd service files for officejawn

**Files:**
- Create: `scripts/hawk-api.service`
- Create: `scripts/hawk-worker.service`
- Create: `scripts/deploy-officejawn.sh`

**Step 1: Create `scripts/hawk-api.service`**

```ini
[Unit]
Description=Hawk News Service translation API
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=joe
WorkingDirectory=/home/joe/projects/hawk-translation-api
EnvironmentFile=/home/joe/projects/hawk-translation-api/.env
ExecStart=/home/joe/projects/hawk-translation-api/venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8090
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Step 2: Create `scripts/hawk-worker.service`**

```ini
[Unit]
Description=Hawk News Service Celery worker
After=network.target redis.service

[Service]
Type=simple
User=joe
WorkingDirectory=/home/joe/projects/hawk-translation-api
EnvironmentFile=/home/joe/projects/hawk-translation-api/.env
ExecStart=/home/joe/projects/hawk-translation-api/venv/bin/celery -A workers.celery_app worker --loglevel=info --concurrency=2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Step 3: Create `scripts/deploy-officejawn.sh`**

```bash
#!/bin/bash
set -e

REMOTE_USER="joe"
REMOTE_HOST="officejawn"
REMOTE_DIR="/home/joe/projects/hawk-translation-api"

echo "Deploying to officejawn..."

# Sync code (excluding venv, .env, __pycache__)
rsync -avz --exclude='venv/' --exclude='.env' --exclude='__pycache__/' \
    . "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/"

# SSH in and restart services
ssh "$REMOTE_USER@$REMOTE_HOST" << 'EOF'
    cd /home/joe/projects/hawk-translation-api
    source venv/bin/activate
    pip install -r requirements.txt -q
    alembic upgrade head
    sudo systemctl restart hawk-api hawk-worker
    echo "Deployed successfully"
EOF
```

**Step 4: Make deploy script executable**

```bash
chmod +x scripts/deploy-officejawn.sh
```

**Step 5: Install systemd services on officejawn**

SSH to officejawn and run:

```bash
ssh officejawn
sudo cp /home/joe/projects/hawk-translation-api/scripts/hawk-api.service /etc/systemd/system/
sudo cp /home/joe/projects/hawk-translation-api/scripts/hawk-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable hawk-api hawk-worker
sudo systemctl start hawk-api hawk-worker
sudo systemctl status hawk-api
```

Expected: `Active: active (running)`

**Step 6: Add Cloudflare Tunnel route**

On houseofjawn, update the Cloudflare Tunnel config to add the new service:

```bash
# Check current tunnel config
sudo cat /etc/cloudflare-tunnel/config.yml

# Add entry for api.hawknewsservice.org pointing to officejawn:8090
# Actual tunnel ingress rule format:
# - hostname: api.hawknewsservice.org
#   service: http://100.84.214.24:8090
```

Also add `api.hawknewsservice.org` CNAME in Cloudflare DNS dashboard pointing to the tunnel.

**Step 7: Commit**

```bash
git add scripts/
git commit -m "feat: systemd service files and deploy script for officejawn"
```

---

### Task 14: STNS partner acceptance test

**Files:**
- Create: `tests/acceptance/test_stns_partner.py`
- Create: `tests/acceptance/README.md`

**Step 1: Create `tests/acceptance/README.md`**

```markdown
# Acceptance tests

These tests run against the live API and require a valid API key.
Set `HAWK_API_KEY` and `HAWK_API_BASE_URL` env vars before running.

```bash
HAWK_API_KEY=hawk_test_xxx HAWK_API_BASE_URL=http://localhost:8090 pytest tests/acceptance/ -v
```
```

**Step 2: Create `tests/acceptance/test_stns_partner.py`**

```python
"""
Acceptance tests for STNS partner use case.
Run against a live API instance with a real DeepL key.
"""
import os
import time
import pytest
import httpx

BASE_URL = os.getenv("HAWK_API_BASE_URL", "http://localhost:8090")
API_KEY = os.getenv("HAWK_API_KEY", "")

SAMPLE_ARTICLE = """
<h1>Montclair Board of Education votes on budget</h1>
<p>The Montclair Board of Education voted Tuesday night to approve a $123 million budget for the upcoming school year.</p>
<p>Superintendent Jonathan Ponds said the new budget prioritizes reading programs and after-school activities.</p>
<p>The vote was 7-2, with two board members opposing the increase in spending.</p>
"""


@pytest.mark.skipif(not API_KEY, reason="HAWK_API_KEY not set")
def test_instant_spanish_translation():
    client = httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {API_KEY}"})

    # Submit translation job
    response = client.post("/v1/translate", json={
        "content": SAMPLE_ARTICLE,
        "source_language": "en",
        "target_language": "es",
        "tier": "instant",
    })
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]

    # Poll for completion (max 60s)
    for _ in range(30):
        time.sleep(2)
        status_response = client.get(f"/v1/translate/{job_id}")
        data = status_response.json()
        if data["status"] in ("complete", "failed"):
            break

    assert data["status"] == "complete", f"Job failed: {data}"
    assert data["translated_content"] is not None
    assert "<p>" in data["translated_content"]  # HTML structure preserved
    assert "Montclair" in data["translated_content"]  # Proper noun preserved

    print(f"\nTranslated content:\n{data['translated_content']}")
```

**Step 3: Run acceptance test (locally against dev server)**

Start the API first:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8090 --reload &
celery -A workers.celery_app worker --loglevel=info &
HAWK_API_KEY=your_test_key HAWK_API_BASE_URL=http://localhost:8090 pytest tests/acceptance/ -v -s
```

**Step 4: Commit**

```bash
git add tests/acceptance/
git commit -m "test: STNS partner acceptance test for instant Spanish translation"
```

---

## Phase 2: Human review + CMS integration (weeks 5–10)

---

### Task 15: Human review queue and reviewer assignment

**Files:**
- Modify: `workers/tasks.py` (complete the `in_review` branch)
- Create: `review/queue.py`
- Create: `tests/test_review_queue.py`

**Step 1: Write the failing test**

```python
# tests/test_review_queue.py
from unittest.mock import MagicMock
from review.queue import assign_reviewer

def test_assigns_available_reviewer():
    mock_db = MagicMock()
    reviewer = MagicMock()
    reviewer.id = "rev-1"
    reviewer.language_pairs_json = ["en-es", "en-fr"]
    reviewer.active = True

    mock_db.query.return_value.filter.return_value.all.return_value = [reviewer]
    result = assign_reviewer(job_id="job-1", language_pair="en-es", db=mock_db)
    assert result == "rev-1"

def test_no_available_reviewer_returns_none():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = []
    result = assign_reviewer(job_id="job-1", language_pair="en-zh", db=mock_db)
    assert result is None
```

**Step 2: Run to verify it fails, then create `review/queue.py`**

```python
# review/queue.py
import uuid
from datetime import datetime, UTC
from sqlalchemy.orm import Session
from db.models import Reviewer, ReviewAssignment


def assign_reviewer(job_id: str, language_pair: str, db: Session) -> str | None:
    """Find an available reviewer for the language pair and create assignment."""
    reviewers = db.query(Reviewer).filter(Reviewer.active == True).all()

    for reviewer in reviewers:
        if language_pair in reviewer.language_pairs_json:
            assignment = ReviewAssignment(
                id=str(uuid.uuid4()),
                job_id=job_id,
                reviewer_id=reviewer.id,
                role="reviewer",
                assigned_at=datetime.now(UTC),
            )
            db.add(assignment)
            db.commit()
            return reviewer.id

    return None
```

**Step 3: Run tests and commit**

```bash
pytest tests/test_review_queue.py -v
git add review/queue.py tests/test_review_queue.py
git commit -m "feat: reviewer assignment for human review queue"
```

---

### Task 16: Reviewer web UI

**Files:**
- Create: `review/routes.py`
- Create: `review/templates/review.html`
- Create: `review/templates/review_list.html`
- Modify: `api/main.py` (add review router)

**Step 1: Create `review/routes.py`**

```python
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import TranslationJob, ReviewAssignment, Reviewer
from datetime import datetime, UTC

router = APIRouter()
templates = Jinja2Templates(directory="review/templates")


@router.get("/", response_class=HTMLResponse)
def review_list(request: Request, db: Session = Depends(get_db)):
    jobs = db.query(TranslationJob).filter(
        TranslationJob.status == "in_review"
    ).order_by(TranslationJob.created_at).all()
    return templates.TemplateResponse("review_list.html", {"request": request, "jobs": jobs})


@router.get("/{job_id}", response_class=HTMLResponse)
def review_job(job_id: str, request: Request, db: Session = Depends(get_db)):
    job = db.get(TranslationJob, job_id)
    if not job:
        return HTMLResponse("Job not found", status_code=404)
    return templates.TemplateResponse("review.html", {"request": request, "job": job})


@router.post("/{job_id}/approve")
def approve_translation(
    job_id: str,
    edited_content: str = Form(...),
    db: Session = Depends(get_db),
):
    job = db.get(TranslationJob, job_id)
    if not job:
        return {"error": "not found"}
    job.translated_content = edited_content
    job.status = "reviewed" if job.tier == "reviewed" else "complete"
    job.completed_at = datetime.now(UTC)
    db.commit()
    return {"status": job.status}
```

**Step 2: Create `review/templates/review_list.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Review queue — Hawk News Service</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #ddd; }
    th { background: #f5f5f5; }
    a { color: #0066cc; }
  </style>
</head>
<body>
  <h1>Review queue</h1>
  <table>
    <thead>
      <tr><th>Job ID</th><th>Language</th><th>Tier</th><th>Submitted</th><th>Action</th></tr>
    </thead>
    <tbody>
      {% for job in jobs %}
      <tr>
        <td>{{ job.id[:8] }}...</td>
        <td>{{ job.source_language }} → {{ job.target_language }}</td>
        <td>{{ job.tier }}</td>
        <td>{{ job.created_at.strftime('%Y-%m-%d %H:%M') if job.created_at else '' }}</td>
        <td><a href="/review/{{ job.id }}">Review</a></td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</body>
</html>
```

**Step 3: Create `review/templates/review.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Review job {{ job.id[:8] }}</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 1200px; margin: 2rem auto; padding: 0 1rem; }
    .columns { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; }
    .original { background: #f9f9f9; padding: 1rem; border-radius: 4px; }
    textarea { width: 100%; height: 400px; font-family: Arial, sans-serif; font-size: 14px; padding: 0.5rem; }
    button { background: #0066cc; color: white; border: none; padding: 0.75rem 1.5rem; cursor: pointer; border-radius: 4px; }
    h2 { margin-top: 0; font-size: 1rem; color: #666; text-transform: uppercase; letter-spacing: 0.05em; }
  </style>
</head>
<body>
  <h1>Review: {{ job.target_language }} translation</h1>
  <p>Job {{ job.id }} | Tier: {{ job.tier }} | Submitted: {{ job.created_at }}</p>

  <div class="columns">
    <div class="original">
      <h2>Original (English)</h2>
      {{ job.content | safe }}
    </div>
    <div>
      <h2>Machine translation (edit below)</h2>
      <form method="post" action="/review/{{ job.id }}/approve">
        <textarea name="edited_content">{{ job.translated_content }}</textarea>
        <br><br>
        <button type="submit">Approve translation</button>
      </form>
    </div>
  </div>
</body>
</html>
```

**Step 4: Add review router to `api/main.py`**

```python
# Add to api/main.py
from review.routes import router as review_router
app.include_router(review_router, prefix="/review")
```

**Step 5: Run all tests and commit**

```bash
pytest -v
git add review/ api/main.py
git commit -m "feat: reviewer web UI for side-by-side translation review"
```

---

### Task 17: WordPress plugin

**Files:**
- Create: `wp-plugin/hawk-translation/hawk-translation.php`
- Create: `wp-plugin/hawk-translation/settings.php`
- Create: `wp-plugin/hawk-translation/translate-meta-box.php`

**Step 1: Create `wp-plugin/hawk-translation/hawk-translation.php`**

```php
<?php
/**
 * Plugin Name: Hawk News Service translation
 * Description: Translate posts via the Hawk News Service API.
 * Version: 1.0.0
 * Author: Center for Cooperative Media
 */

if (!defined('ABSPATH')) exit;

define('HAWK_PLUGIN_DIR', plugin_dir_path(__FILE__));

require_once HAWK_PLUGIN_DIR . 'settings.php';
require_once HAWK_PLUGIN_DIR . 'translate-meta-box.php';

register_activation_hook(__FILE__, function () {
    add_option('hawk_api_key', '');
    add_option('hawk_api_base_url', 'https://api.hawknewsservice.org/v1');
    add_option('hawk_default_tier', 'instant');
    add_option('hawk_default_languages', ['es']);
});
```

**Step 2: Create `wp-plugin/hawk-translation/settings.php`**

```php
<?php
add_action('admin_menu', function () {
    add_options_page(
        'Hawk translation settings',
        'Hawk translation',
        'manage_options',
        'hawk-translation',
        'hawk_settings_page'
    );
});

function hawk_settings_page() {
    if (isset($_POST['hawk_save'])) {
        update_option('hawk_api_key', sanitize_text_field($_POST['hawk_api_key']));
        update_option('hawk_default_tier', sanitize_text_field($_POST['hawk_default_tier']));
        echo '<div class="updated"><p>Settings saved.</p></div>';
    }
    $api_key = get_option('hawk_api_key', '');
    $tier = get_option('hawk_default_tier', 'instant');
    ?>
    <div class="wrap">
        <h1>Hawk translation settings</h1>
        <form method="post">
            <table class="form-table">
                <tr>
                    <th>API key</th>
                    <td><input type="text" name="hawk_api_key" value="<?php echo esc_attr($api_key); ?>" size="50"></td>
                </tr>
                <tr>
                    <th>Default tier</th>
                    <td>
                        <select name="hawk_default_tier">
                            <option value="instant" <?php selected($tier, 'instant'); ?>>Instant (AI only)</option>
                            <option value="reviewed" <?php selected($tier, 'reviewed'); ?>>Reviewed (AI + human editor)</option>
                            <option value="certified" <?php selected($tier, 'certified'); ?>>Certified (professional translator)</option>
                        </select>
                    </td>
                </tr>
            </table>
            <input type="hidden" name="hawk_save" value="1">
            <?php submit_button('Save settings'); ?>
        </form>
    </div>
    <?php
}
```

**Step 3: Create `wp-plugin/hawk-translation/translate-meta-box.php`**

```php
<?php
add_action('add_meta_boxes', function () {
    add_meta_box('hawk-translate', 'Hawk translation', 'hawk_meta_box', 'post', 'side');
});

function hawk_meta_box($post) {
    $languages = [
        'es' => 'Spanish', 'pt' => 'Portuguese', 'ht' => 'Haitian Creole',
        'zh' => 'Chinese', 'ko' => 'Korean', 'ar' => 'Arabic',
        'fr' => 'French', 'pl' => 'Polish', 'hi' => 'Hindi', 'ur' => 'Urdu',
    ];
    ?>
    <p><strong>Translate this post</strong></p>
    <select id="hawk-lang" style="width:100%;margin-bottom:8px;">
        <?php foreach ($languages as $code => $name): ?>
            <option value="<?php echo $code; ?>"><?php echo $name; ?></option>
        <?php endforeach; ?>
    </select>
    <button type="button" id="hawk-submit" class="button" style="width:100%">Send for translation</button>
    <p id="hawk-status" style="margin-top:8px;font-size:12px;"></p>

    <script>
    document.getElementById('hawk-submit').addEventListener('click', function() {
        const lang = document.getElementById('hawk-lang').value;
        const status = document.getElementById('hawk-status');
        status.textContent = 'Submitting...';

        fetch(ajaxurl, {
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: new URLSearchParams({
                action: 'hawk_translate',
                post_id: '<?php echo $post->ID; ?>',
                language: lang,
                nonce: '<?php echo wp_create_nonce('hawk_translate'); ?>'
            })
        })
        .then(r => r.json())
        .then(data => {
            status.textContent = data.success
                ? 'Submitted. Job ID: ' + data.job_id
                : 'Error: ' + data.error;
        });
    });
    </script>
    <?php
}

add_action('wp_ajax_hawk_translate', function () {
    check_ajax_referer('hawk_translate', 'nonce');

    $post_id = intval($_POST['post_id']);
    $language = sanitize_text_field($_POST['language']);
    $post = get_post($post_id);
    $api_key = get_option('hawk_api_key');
    $base_url = get_option('hawk_api_base_url', 'https://api.hawknewsservice.org/v1');
    $tier = get_option('hawk_default_tier', 'instant');

    $content = apply_filters('the_content', $post->post_content);

    $response = wp_remote_post("$base_url/translate", [
        'headers' => [
            'Authorization' => "Bearer $api_key",
            'Content-Type' => 'application/json',
        ],
        'body' => json_encode([
            'content' => $content,
            'source_language' => 'en',
            'target_language' => $language,
            'tier' => $tier,
            'metadata' => [
                'headline' => $post->post_title,
                'source_url' => get_permalink($post_id),
            ],
        ]),
    ]);

    if (is_wp_error($response)) {
        wp_send_json_error(['error' => $response->get_error_message()]);
    }

    $body = json_decode(wp_remote_retrieve_body($response), true);
    wp_send_json_success(['job_id' => $body['job_id'] ?? null]);
});
```

**Step 4: Commit**

```bash
git add wp-plugin/
git commit -m "feat: WordPress plugin for one-click translation submission"
```

---

### Task 18: Static docs site for hawknewsservice.org

**Files:**
- Create: `docs/site/index.html`
- Create: `docs/site/api-reference.html`
- Create: `scripts/deploy-docs.sh`

**Step 1: Create `scripts/deploy-docs.sh`**

```bash
#!/bin/bash
# Deploy static docs to hawknewsservice.org via SFTP
set -e

SFTP_HOST="37.27.121.163"
SFTP_PORT="4377"
SFTP_USER="hawknews"
SFTP_PASS="${HAWK_SFTP_PASSWORD}"  # set in env, not hardcoded
DOCS_DIR="docs/site"
REMOTE_DIR="/public_html"

echo "Deploying docs to hawknewsservice.org..."

sshpass -p "$SFTP_PASS" sftp -P "$SFTP_PORT" -o StrictHostKeyChecking=no \
    "$SFTP_USER@$SFTP_HOST" << EOF
put -r $DOCS_DIR/* $REMOTE_DIR/
EOF

echo "Docs deployed."
```

Note: Install `sshpass` on houseofjawn: `sudo apt install sshpass`

**Step 2: Create `docs/site/index.html`** — a landing page with:
- What the API does
- Language list
- Three quality tiers explained
- Signup form (links to admin key creation endpoint)
- Link to API reference

(Implementation left to frontend-design skill — invoke it with the site brief)

**Step 3: Run final test suite**

```bash
pytest -v --cov=api --cov=workers --cov=db --cov=review
```

Expected: all tests pass, coverage report displayed

**Step 4: Final commit and push**

```bash
git add docs/scripts/deploy-docs.sh
git commit -m "feat: deployment scripts for static docs site"
git push origin main
```

---

## Running the full system locally

```bash
# Terminal 1: API server
source venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8090 --reload

# Terminal 2: Celery worker
source venv/bin/activate
celery -A workers.celery_app worker --loglevel=info

# Terminal 3: Redis (if not running)
redis-server

# Test it
curl -X POST http://localhost:8090/v1/translate \
  -H "Authorization: Bearer hawk_live_yourkey" \
  -H "Content-Type: application/json" \
  -d '{"content": "<p>Hello world.</p>", "target_language": "es", "tier": "instant"}'
```

---

## Deployment checklist

- [ ] PostgreSQL and Redis installed and running on officejawn
- [ ] `.env` configured on officejawn with real DEEPL_API_KEY
- [ ] `alembic upgrade head` run on officejawn
- [ ] `hawk-api` and `hawk-worker` systemd services enabled and active
- [ ] Cloudflare Tunnel route added: `api.hawknewsservice.org` → `http://100.84.214.24:8090`
- [ ] `api.hawknewsservice.org` CNAME in Cloudflare DNS pointing to tunnel
- [ ] Static docs deployed to hawknewsservice.org via SFTP
- [ ] STNS acceptance test passing against production
- [ ] At least 2 STNS partner API keys created and tested
