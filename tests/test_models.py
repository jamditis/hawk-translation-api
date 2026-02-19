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
