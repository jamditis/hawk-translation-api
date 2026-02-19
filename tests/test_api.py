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
    assert len(data["languages"]) == 10


def test_translate_requires_auth():
    response = client.post("/v1/translate", json={
        "content": "<p>Hello</p>",
        "source_language": "en",
        "target_language": "es",
        "tier": "instant",
    })
    assert response.status_code == 401


def test_translate_with_valid_key_returns_202_and_job_id():
    mock_ctx = MagicMock()
    mock_ctx.org_id = "org-123"
    mock_ctx.tier = "instant"
    mock_ctx.daily_quota = 100
    mock_ctx.api_key_id = "key-456"

    mock_db = MagicMock()
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)

    with patch("api.routes.translate.authenticate_request", return_value=mock_ctx), \
         patch("api.routes.translate.check_quota"), \
         patch("api.routes.translate.increment_quota"), \
         patch("api.routes.translate.run_translation_pipeline") as mock_task, \
         patch("api.routes.translate.get_db", return_value=iter([mock_db])):
        mock_task.delay = MagicMock()
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
    assert "job_id" in response.json()


def test_translate_rejects_unsupported_language():
    mock_ctx = MagicMock()
    mock_ctx.org_id = "org-123"
    mock_ctx.tier = "instant"
    mock_ctx.daily_quota = 100
    mock_ctx.api_key_id = "key-456"

    mock_db = MagicMock()

    with patch("api.routes.translate.authenticate_request", return_value=mock_ctx), \
         patch("api.routes.translate.check_quota"), \
         patch("api.routes.translate.get_db", return_value=iter([mock_db])):
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


def test_translate_rejects_oversized_content():
    mock_ctx = MagicMock()
    mock_ctx.org_id = "org-123"
    mock_ctx.tier = "instant"
    mock_ctx.daily_quota = 100
    mock_ctx.api_key_id = "key-456"

    mock_db = MagicMock()

    with patch("api.routes.translate.authenticate_request", return_value=mock_ctx), \
         patch("api.routes.translate.check_quota"), \
         patch("api.routes.translate.get_db", return_value=iter([mock_db])):
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


def test_get_job_status():
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

    mock_db = MagicMock()
    mock_db.get.return_value = mock_job

    with patch("api.routes.translate.authenticate_request", return_value=mock_ctx), \
         patch("api.routes.translate.get_db", return_value=iter([mock_db])):
        response = client.get(
            "/v1/translate/job-abc",
            headers={"Authorization": "Bearer hawk_live_test123"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "complete"
    assert data["translated_content"] == "<p>Hola mundo.</p>"


def test_get_job_not_found():
    mock_ctx = MagicMock()
    mock_ctx.org_id = "org-123"

    mock_db = MagicMock()
    mock_db.get.return_value = None

    with patch("api.routes.translate.authenticate_request", return_value=mock_ctx), \
         patch("api.routes.translate.get_db", return_value=iter([mock_db])):
        response = client.get(
            "/v1/translate/nonexistent",
            headers={"Authorization": "Bearer hawk_live_test123"},
        )
    assert response.status_code == 404
