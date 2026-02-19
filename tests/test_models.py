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

def test_organization_defaults_without_explicit_values():
    # Only required fields provided — defaults should kick in
    org = Organization(name="Test Outlet", slug="test-outlet")
    assert org.tier == "instant"
    assert org.daily_quota == 50
    assert org.active == True

def test_translation_job_defaults_without_explicit_values():
    job = TranslationJob(
        source_language="en",
        target_language="zh-Hant-TW",  # 10 chars — tests String(10) fix too
        tier="instant",
        content="<p>Hello</p>",
    )
    assert job.status == "queued"
    assert job.content_type == "article"

def test_webhook_delivery_default_status():
    from db.models import WebhookDelivery
    wd = WebhookDelivery(
        id="wd-1",
        job_id="job-1",
        callback_url="https://example.com/hook"
    )
    assert wd.status == "pending"
    assert wd.attempt_count == 0
