from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app
from db.database import get_db


def _make_mock_job(**overrides):
    job = MagicMock()
    job.id = "job-999"
    job.status = "in_review"
    job.tier = "reviewed"
    job.translated_content = "<p>Hola mundo.</p>"
    job.content = "<p>Hello world.</p>"
    job.source_language = "en"
    job.target_language = "es"
    job.created_at = None
    job.quality_scores_json = None
    job.callback_url = None
    for k, v in overrides.items():
        setattr(job, k, v)
    return job


def test_approve_sets_reviewed_status_for_reviewed_tier():
    """Approving a 'reviewed' tier job sets status to 'reviewed', not 'complete'."""
    mock_db = MagicMock()
    mock_job = _make_mock_job(tier="reviewed")
    mock_db.get.return_value = mock_job

    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app)

    with patch("review.routes.deliver_webhook"):
        response = client.post(
            "/review/job-999/approve",
            data={"edited_content": "<p>Hola mundo editado.</p>"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "reviewed"}
    assert mock_job.translated_content == "<p>Hola mundo editado.</p>"
    assert mock_job.status == "reviewed"
    mock_db.commit.assert_called_once()


def test_approve_sets_complete_status_for_instant_tier():
    """Approving a non-'reviewed' tier job (e.g. certified) sets status to 'complete'."""
    mock_db = MagicMock()
    mock_job = _make_mock_job(tier="certified")
    mock_db.get.return_value = mock_job

    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app)

    with patch("review.routes.deliver_webhook"):
        response = client.post(
            "/review/job-999/approve",
            data={"edited_content": "<p>Texto certificado.</p>"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "complete"}


def test_approve_returns_error_for_missing_job():
    """Approving a non-existent job returns an error dict."""
    mock_db = MagicMock()
    mock_db.get.return_value = None

    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app)

    response = client.post(
        "/review/no-such-job/approve",
        data={"edited_content": "anything"},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"error": "not found"}


def test_approve_fires_webhook_when_status_becomes_complete():
    """When a certified job is approved, deliver_webhook is called."""
    mock_db = MagicMock()
    mock_job = _make_mock_job(tier="certified", callback_url="https://example.com/hook")
    mock_db.get.return_value = mock_job

    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app)

    mock_deliver = MagicMock()
    with patch("review.routes.deliver_webhook", mock_deliver):
        client.post(
            "/review/job-999/approve",
            data={"edited_content": "<p>Done.</p>"},
        )

    app.dependency_overrides.clear()

    mock_deliver.delay.assert_called_once()
    payload = mock_deliver.delay.call_args[0][2]
    assert payload["status"] == "complete"
    assert payload["job_id"] == "job-999"
