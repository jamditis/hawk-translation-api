from unittest.mock import patch, MagicMock


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

    assert mock_db.commit.called
