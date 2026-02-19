from unittest.mock import patch, MagicMock


SEGMENT = {
    "index": 0,
    "tag": "p",
    "text": "Hello world.",
    "translated": "Hola mundo.",
    "inner_html": "<p>Hello world.</p>",
}


def _make_mock_job(**overrides):
    mock_job = MagicMock()
    mock_job.id = "job-123"
    mock_job.status = "queued"
    mock_job.content = "<p>Hello world.</p>"
    mock_job.source_language = "en"
    mock_job.target_language = "es"
    mock_job.tier = "instant"
    mock_job.glossary_id = None
    mock_job.callback_url = None
    for k, v in overrides.items():
        setattr(mock_job, k, v)
    return mock_job


def test_translation_task_updates_job_status():
    """Pipeline updates status through queued -> translating -> machine_translated -> complete."""
    mock_db = MagicMock()
    mock_job = _make_mock_job()
    mock_db.get.return_value = mock_job

    with patch("workers.tasks.get_db_session", return_value=mock_db), \
         patch("workers.tasks.translate_segments", return_value=[SEGMENT]), \
         patch("workers.tasks.score_translation", return_value=None), \
         patch("workers.tasks.deliver_webhook"):
        from workers.tasks import run_translation_pipeline
        run_translation_pipeline("job-123")

    assert mock_db.commit.called


def test_pipeline_sets_translating_status():
    """Pipeline sets 'translating' before translation work, 'machine_translated' after."""
    mock_db = MagicMock()

    # Use a property on the mock's type to track status assignments in order
    statuses = []

    class TrackedJob:
        id = "job-123"
        content = "<p>Hello world.</p>"
        target_language = "es"
        tier = "instant"
        glossary_id = None
        callback_url = None
        word_count = 0
        translated_content = ""
        quality_scores_json = None
        error_message = None
        completed_at = None

        @property
        def status(self):
            return statuses[-1] if statuses else "queued"

        @status.setter
        def status(self, value):
            statuses.append(value)

    tracked_job = TrackedJob()
    mock_db.get.return_value = tracked_job

    with patch("workers.tasks.get_db_session", return_value=mock_db), \
         patch("workers.tasks.translate_segments", return_value=[SEGMENT]), \
         patch("workers.tasks.score_translation", return_value=None), \
         patch("workers.tasks.deliver_webhook"):
        from workers.tasks import run_translation_pipeline
        run_translation_pipeline("job-123")

    assert "translating" in statuses, f"'translating' never set; got: {statuses}"
    assert "machine_translated" in statuses, f"'machine_translated' never set; got: {statuses}"

    translating_idx = statuses.index("translating")
    machine_idx = statuses.index("machine_translated")
    assert translating_idx < machine_idx, (
        f"'translating' (idx {translating_idx}) must come before 'machine_translated' (idx {machine_idx}); got {statuses}"
    )


def test_pipeline_commits_at_least_three_times():
    """Pipeline commits for translating, machine_translated, and final status — at least 3 commits."""
    mock_db = MagicMock()
    mock_job = _make_mock_job()
    mock_db.get.return_value = mock_job

    with patch("workers.tasks.get_db_session", return_value=mock_db), \
         patch("workers.tasks.translate_segments", return_value=[SEGMENT]), \
         patch("workers.tasks.score_translation", return_value=None), \
         patch("workers.tasks.deliver_webhook"):
        from workers.tasks import run_translation_pipeline
        run_translation_pipeline("job-123")

    assert mock_db.commit.call_count >= 3, (
        f"Expected at least 3 commits (translating, machine_translated, final); got {mock_db.commit.call_count}"
    )


def test_pipeline_uses_exponential_backoff_first_retry():
    """On first failure (retries=0), retry countdown is 30s."""
    mock_db = MagicMock()
    mock_job = _make_mock_job()
    mock_db.get.return_value = mock_job

    exc = RuntimeError("DeepL API error")
    retry_kwargs = {}

    def fake_retry(**kwargs):
        retry_kwargs.update(kwargs)
        raise Exception("retry sentinel")

    with patch("workers.tasks.get_db_session", return_value=mock_db), \
         patch("workers.tasks.translate_segments", side_effect=exc), \
         patch("workers.tasks.deliver_webhook"):
        from workers.tasks import run_translation_pipeline
        run_translation_pipeline.push_request(retries=0)
        with patch.object(run_translation_pipeline, "retry", side_effect=fake_retry):
            try:
                run_translation_pipeline.run("job-123")
            except Exception:
                pass

    assert retry_kwargs.get("countdown") == 30, (
        f"Expected countdown=30 on first retry, got {retry_kwargs.get('countdown')}"
    )


def test_pipeline_uses_exponential_backoff_second_retry():
    """On second failure (retries=1), retry countdown is 120s."""
    mock_db = MagicMock()
    mock_job = _make_mock_job()
    mock_db.get.return_value = mock_job

    exc = RuntimeError("DeepL API error")
    retry_kwargs = {}

    def fake_retry(**kwargs):
        retry_kwargs.update(kwargs)
        raise Exception("retry sentinel")

    with patch("workers.tasks.get_db_session", return_value=mock_db), \
         patch("workers.tasks.translate_segments", side_effect=exc), \
         patch("workers.tasks.deliver_webhook"):
        from workers.tasks import run_translation_pipeline
        run_translation_pipeline.push_request(retries=1)
        with patch.object(run_translation_pipeline, "retry", side_effect=fake_retry):
            try:
                run_translation_pipeline.run("job-123")
            except Exception:
                pass

    assert retry_kwargs.get("countdown") == 120, (
        f"Expected countdown=120 on second retry, got {retry_kwargs.get('countdown')}"
    )


def test_pipeline_uses_exponential_backoff_third_retry():
    """On third failure (retries=2), retry countdown is 600s."""
    mock_db = MagicMock()
    mock_job = _make_mock_job()
    mock_db.get.return_value = mock_job

    exc = RuntimeError("DeepL API error")
    retry_kwargs = {}

    def fake_retry(**kwargs):
        retry_kwargs.update(kwargs)
        raise Exception("retry sentinel")

    with patch("workers.tasks.get_db_session", return_value=mock_db), \
         patch("workers.tasks.translate_segments", side_effect=exc), \
         patch("workers.tasks.deliver_webhook"):
        from workers.tasks import run_translation_pipeline
        run_translation_pipeline.push_request(retries=2)
        with patch.object(run_translation_pipeline, "retry", side_effect=fake_retry):
            try:
                run_translation_pipeline.run("job-123")
            except Exception:
                pass

    assert retry_kwargs.get("countdown") == 600, (
        f"Expected countdown=600 on third retry, got {retry_kwargs.get('countdown')}"
    )


def test_error_webhook_fired_on_final_failure():
    """When all retries are exhausted, deliver_webhook is called with status='failed'."""
    mock_db = MagicMock()
    mock_job = _make_mock_job(callback_url="https://example.com/webhook")
    mock_db.get.return_value = mock_job

    exc = RuntimeError("Unrecoverable error")
    mock_deliver = MagicMock()

    def fake_retry(**kwargs):
        raise Exception("retry sentinel")

    with patch("workers.tasks.get_db_session", return_value=mock_db), \
         patch("workers.tasks.translate_segments", side_effect=exc), \
         patch("workers.tasks.deliver_webhook", mock_deliver):
        from workers.tasks import run_translation_pipeline
        run_translation_pipeline.push_request(retries=3)  # retries == max_retries == 3
        with patch.object(run_translation_pipeline, "retry", side_effect=fake_retry):
            try:
                run_translation_pipeline.run("job-123")
            except Exception:
                pass

    mock_deliver.delay.assert_called_once()
    payload = mock_deliver.delay.call_args[0][2]
    assert payload["status"] == "failed", f"Expected status='failed', got: {payload}"
    assert "error" in payload


def test_error_webhook_not_fired_on_intermediate_failure():
    """On a non-final retry, deliver_webhook is not called with status='failed'."""
    mock_db = MagicMock()
    mock_job = _make_mock_job(callback_url="https://example.com/webhook")
    mock_db.get.return_value = mock_job

    exc = RuntimeError("Transient error")
    mock_deliver = MagicMock()

    def fake_retry(**kwargs):
        raise Exception("retry sentinel")

    with patch("workers.tasks.get_db_session", return_value=mock_db), \
         patch("workers.tasks.translate_segments", side_effect=exc), \
         patch("workers.tasks.deliver_webhook", mock_deliver):
        from workers.tasks import run_translation_pipeline
        run_translation_pipeline.push_request(retries=0)  # not the final attempt
        with patch.object(run_translation_pipeline, "retry", side_effect=fake_retry):
            try:
                run_translation_pipeline.run("job-123")
            except Exception:
                pass

    mock_deliver.delay.assert_not_called()


def test_deliver_webhook_retries_on_non_2xx():
    """deliver_webhook retries when the server returns a non-2xx status."""
    with patch("workers.tasks.httpx.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        from workers.tasks import deliver_webhook

        retry_kwargs = {}

        def fake_retry(**kwargs):
            retry_kwargs.update(kwargs)
            raise Exception("retry sentinel")

        deliver_webhook.push_request(retries=0)
        with patch.object(deliver_webhook, "retry", side_effect=fake_retry):
            try:
                deliver_webhook.run("https://example.com/hook", "job-123", {"status": "complete"})
            except Exception:
                pass

    assert retry_kwargs.get("countdown") == 300, (
        f"Expected countdown=300 for first webhook retry, got {retry_kwargs.get('countdown')}"
    )


def test_deliver_webhook_abandons_after_max_retries():
    """deliver_webhook logs 'abandoned' and returns without raising after max retries."""
    with patch("workers.tasks.httpx.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_post.return_value = mock_response

        from workers.tasks import deliver_webhook

        deliver_webhook.push_request(retries=5)  # retries == max_retries == 5

        # Should return None cleanly without raising
        result = deliver_webhook.run("https://example.com/hook", "job-123", {"status": "complete"})
        assert result is None


def test_deliver_webhook_skips_invalid_url_scheme():
    """deliver_webhook returns immediately for non-http(s) URLs without making a request."""
    with patch("workers.tasks.httpx.post") as mock_post:
        from workers.tasks import deliver_webhook

        deliver_webhook.push_request(retries=0)
        result = deliver_webhook.run("ftp://example.com/hook", "job-123", {"status": "complete"})
        assert result is None
        mock_post.assert_not_called()


def test_deliver_webhook_succeeds_on_2xx():
    """deliver_webhook does not retry when the server returns a 2xx status."""
    with patch("workers.tasks.httpx.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        from workers.tasks import deliver_webhook

        retry_called = []

        def fake_retry(**kwargs):
            retry_called.append(kwargs)
            raise Exception("retry sentinel")

        deliver_webhook.push_request(retries=0)
        with patch.object(deliver_webhook, "retry", side_effect=fake_retry):
            result = deliver_webhook.run("https://example.com/hook", "job-123", {"status": "complete"})

        assert result is None
        assert not retry_called, f"retry should not be called on 2xx, got: {retry_called}"
