import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from api.main import app
from db.database import get_db

client = TestClient(app)


@pytest.fixture(autouse=False)
def mock_db():
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.clear()


@pytest.fixture(autouse=False)
def mock_auth_ctx():
    ctx = MagicMock()
    ctx.org_id = "org-123"
    ctx.tier = "instant"
    ctx.daily_quota = 100
    ctx.api_key_id = "key-456"
    return ctx


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_languages():
    response = client.get("/v1/languages")
    assert response.status_code == 200
    data = response.json()
    assert "languages" in data
    assert len(data["languages"]) == 10
    assert any(lang["code"] == "es" for lang in data["languages"])
    # Verify all languages have a status field
    assert all("status" in lang for lang in data["languages"])
    # Verify limited languages are flagged
    ht = next(lang for lang in data["languages"] if lang["code"] == "ht")
    assert ht["status"] == "limited"


def test_translate_requires_auth(mock_db):
    response = client.post("/v1/translate", json={
        "content": "<p>Hello</p>",
        "source_language": "en",
        "target_language": "es",
        "tier": "instant",
    })
    assert response.status_code == 401


def test_translate_with_valid_key_returns_202_and_job_id(mock_db, mock_auth_ctx):
    with patch("api.routes.translate.authenticate_request", return_value=mock_auth_ctx), \
         patch("api.routes.translate.check_quota"), \
         patch("api.routes.translate.increment_quota"), \
         patch("api.routes.translate.run_translation_pipeline") as mock_task:
        response = client.post(
            "/v1/translate",
            headers={"Authorization": "Bearer hawk_live_test123"},
            json={
                "content": "<p>Hello world.</p>",
                "source_language": "en",
                "target_language": "es",
                "tier": "instant",
            },
        )
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert data["tier"] == "instant"
    assert data["source_language"] == "en"
    assert data["target_language"] == "es"
    assert "links" in data
    assert "self" in data["links"]
    assert "created_at" in data


def test_translate_rejects_unsupported_language(mock_db, mock_auth_ctx):
    with patch("api.routes.translate.authenticate_request", return_value=mock_auth_ctx), \
         patch("api.routes.translate.check_quota"):
        response = client.post(
            "/v1/translate",
            headers={"Authorization": "Bearer hawk_live_test123"},
            json={
                "content": "<p>Hello</p>",
                "source_language": "en",
                "target_language": "xx",  # not a real language code
                "tier": "instant",
            },
        )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "unsupported_language"


def test_translate_rejects_oversized_content(mock_db, mock_auth_ctx):
    with patch("api.routes.translate.authenticate_request", return_value=mock_auth_ctx), \
         patch("api.routes.translate.check_quota"):
        response = client.post(
            "/v1/translate",
            headers={"Authorization": "Bearer hawk_live_test123"},
            json={
                "content": "x" * 50_001,
                "source_language": "en",
                "target_language": "es",
                "tier": "instant",
            },
        )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "content_too_large"


def test_get_job_status(mock_db):
    mock_ctx = MagicMock()
    mock_ctx.org_id = "org-123"

    mock_job = MagicMock()
    mock_job.id = "job-abc"
    mock_job.org_id = "org-123"
    mock_job.status = "complete"
    mock_job.tier = "instant"
    mock_job.source_language = "en"
    mock_job.target_language = "es"
    mock_job.word_count = 10
    mock_job.translated_content = "<p>Hola mundo.</p>"
    mock_job.quality_scores_json = None
    mock_job.created_at = None
    mock_job.completed_at = None

    mock_db.get.return_value = mock_job

    with patch("api.routes.translate.authenticate_request", return_value=mock_ctx):
        response = client.get(
            "/v1/translate/job-abc",
            headers={"Authorization": "Bearer hawk_live_test123"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "complete"
    assert data["translated_content"] == "<p>Hola mundo.</p>"


def test_get_job_not_found(mock_db):
    mock_ctx = MagicMock()
    mock_ctx.org_id = "org-123"

    mock_db.get.return_value = None

    with patch("api.routes.translate.authenticate_request", return_value=mock_ctx):
        response = client.get(
            "/v1/translate/nonexistent",
            headers={"Authorization": "Bearer hawk_live_test123"},
        )
    assert response.status_code == 404


def test_translate_returns_429_when_quota_exceeded(mock_db, mock_auth_ctx):
    from fastapi import HTTPException
    with patch("api.routes.translate.authenticate_request", return_value=mock_auth_ctx), \
         patch("api.routes.translate.check_quota", side_effect=HTTPException(
             status_code=429,
             detail={"error": "quota_exceeded", "reset_at": "2026-02-20T00:00:00Z", "limit": 50}
         )):
        response = client.post(
            "/v1/translate",
            headers={"Authorization": "Bearer hawk_live_test123"},
            json={"content": "<p>Hello</p>", "source_language": "en", "target_language": "es", "tier": "instant"},
        )
    assert response.status_code == 429
    assert response.json()["detail"]["error"] == "quota_exceeded"


def test_get_job_returns_404_for_different_org(mock_db):
    mock_ctx = MagicMock()
    mock_ctx.org_id = "org-abc"  # different from job's org

    mock_job = MagicMock()
    mock_job.org_id = "org-xyz"  # different org owns this job
    mock_db.get.return_value = mock_job

    with patch("api.routes.translate.authenticate_request", return_value=mock_ctx):
        response = client.get(
            "/v1/translate/job-abc",
            headers={"Authorization": "Bearer hawk_live_test123"},
        )
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "job_not_found"


def test_translate_rejects_invalid_tier(mock_db, mock_auth_ctx):
    with patch("api.routes.translate.authenticate_request", return_value=mock_auth_ctx), \
         patch("api.routes.translate.check_quota"):
        response = client.post(
            "/v1/translate",
            headers={"Authorization": "Bearer hawk_live_test123"},
            json={
                "content": "<p>Hello</p>",
                "source_language": "en",
                "target_language": "es",
                "tier": "not_a_real_tier",
            },
        )
    assert response.status_code == 422


def test_translate_rejects_non_http_callback_url(mock_db, mock_auth_ctx):
    with patch("api.routes.translate.authenticate_request", return_value=mock_auth_ctx), \
         patch("api.routes.translate.check_quota"):
        response = client.post(
            "/v1/translate",
            headers={"Authorization": "Bearer hawk_live_test123"},
            json={
                "content": "<p>Hello</p>",
                "source_language": "en",
                "target_language": "es",
                "tier": "instant",
                "callback_url": "file:///etc/passwd",
            },
        )
    assert response.status_code == 422


def test_translate_returns_503_when_celery_unavailable(mock_db, mock_auth_ctx):
    mock_db.refresh = MagicMock()  # make refresh a no-op
    with patch("api.routes.translate.authenticate_request", return_value=mock_auth_ctx), \
         patch("api.routes.translate.check_quota"), \
         patch("api.routes.translate.increment_quota"), \
         patch("api.routes.translate.run_translation_pipeline") as mock_task:
        mock_task.delay.side_effect = Exception("Celery broker unavailable")
        response = client.post(
            "/v1/translate",
            headers={"Authorization": "Bearer hawk_live_test123"},
            json={
                "content": "<p>Hello</p>",
                "source_language": "en",
                "target_language": "es",
                "tier": "instant",
            },
        )
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "service_unavailable"
