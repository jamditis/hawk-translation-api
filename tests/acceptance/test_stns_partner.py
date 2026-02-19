"""
Acceptance tests for the STNS (Spanish Translation News Service) partner use case.
Run against a live API instance with real DeepL credentials.

Set HAWK_API_KEY and HAWK_API_BASE_URL before running.
"""
import os
import time
import pytest
import httpx

BASE_URL = os.getenv("HAWK_API_BASE_URL", "http://localhost:8090")
API_KEY = os.getenv("HAWK_API_KEY", "")

SAMPLE_ARTICLE = """<h1>Montclair Board of Education votes on budget</h1>
<p>The Montclair Board of Education voted Tuesday night to approve a $123 million budget for the upcoming school year.</p>
<p>Superintendent Jonathan Ponds said the new budget prioritizes reading programs and after-school activities.</p>
<p>The vote was 7-2, with two board members opposing the increase in spending.</p>"""

HEADERS = {"Authorization": f"Bearer {API_KEY}"}


@pytest.mark.skipif(not API_KEY, reason="HAWK_API_KEY not set — skipping live API test")
class TestInstantSpanishTranslation:
    """End-to-end test of the instant translation tier for Spanish."""

    def test_submit_translation_job(self):
        """POST /v1/translate returns 202 with a job_id."""
        response = httpx.post(
            f"{BASE_URL}/v1/translate",
            headers=HEADERS,
            json={
                "content": SAMPLE_ARTICLE,
                "source_language": "en",
                "target_language": "es",
                "tier": "instant",
            },
        )
        assert response.status_code == 202, f"Expected 202, got {response.status_code}: {response.text}"
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"
        assert data["target_language"] == "es"
        # Store job_id for subsequent tests
        TestInstantSpanishTranslation.job_id = data["job_id"]

    def test_job_completes_within_60_seconds(self):
        """GET /v1/translate/{job_id} eventually returns status: complete."""
        job_id = getattr(TestInstantSpanishTranslation, "job_id", None)
        if not job_id:
            pytest.skip("No job_id from previous test")

        for attempt in range(30):
            time.sleep(2)
            response = httpx.get(
                f"{BASE_URL}/v1/translate/{job_id}",
                headers=HEADERS,
            )
            assert response.status_code == 200
            data = response.json()
            if data["status"] in ("complete", "failed"):
                break

        assert data["status"] == "complete", f"Job did not complete: {data}"

    def test_html_structure_preserved(self):
        """Translated content preserves HTML tags."""
        job_id = getattr(TestInstantSpanishTranslation, "job_id", None)
        if not job_id:
            pytest.skip("No job_id from previous test")

        response = httpx.get(f"{BASE_URL}/v1/translate/{job_id}", headers=HEADERS)
        data = response.json()
        translated = data.get("translated_content", "")
        assert "<h1>" in translated, "h1 tag missing from translation"
        assert "<p>" in translated, "p tag missing from translation"

    def test_proper_noun_montclair_preserved(self):
        """'Montclair' is preserved as a proper noun in the translation."""
        job_id = getattr(TestInstantSpanishTranslation, "job_id", None)
        if not job_id:
            pytest.skip("No job_id from previous test")

        response = httpx.get(f"{BASE_URL}/v1/translate/{job_id}", headers=HEADERS)
        data = response.json()
        translated = data.get("translated_content", "")
        assert "Montclair" in translated, "Proper noun 'Montclair' was not preserved"

    def test_translation_is_in_spanish(self):
        """Translated content contains Spanish words."""
        job_id = getattr(TestInstantSpanishTranslation, "job_id", None)
        if not job_id:
            pytest.skip("No job_id from previous test")

        response = httpx.get(f"{BASE_URL}/v1/translate/{job_id}", headers=HEADERS)
        data = response.json()
        translated = data.get("translated_content", "")
        # Common Spanish words that should appear in a translation of this article
        spanish_indicators = ["de", "la", "el", "los", "del", "por", "en", "que"]
        found = [w for w in spanish_indicators if w in translated.lower()]
        assert len(found) >= 3, f"Translation doesn't appear to be Spanish. Found: {found}\nContent: {translated}"


@pytest.mark.skipif(not API_KEY, reason="HAWK_API_KEY not set — skipping live API test")
def test_health_check():
    """API health endpoint is reachable."""
    response = httpx.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.skipif(not API_KEY, reason="HAWK_API_KEY not set — skipping live API test")
def test_languages_endpoint():
    """Languages endpoint returns all 10 supported languages."""
    response = httpx.get(f"{BASE_URL}/v1/languages")
    assert response.status_code == 200
    data = response.json()
    assert len(data["languages"]) == 10
    codes = [lang["code"] for lang in data["languages"]]
    assert "es" in codes
    assert "ar" in codes
    assert "zh" in codes


@pytest.mark.skipif(not API_KEY, reason="HAWK_API_KEY not set — skipping live API test")
def test_translate_without_auth_returns_401():
    """Unauthenticated requests are rejected."""
    response = httpx.post(
        f"{BASE_URL}/v1/translate",
        json={"content": "<p>Test</p>", "source_language": "en", "target_language": "es", "tier": "instant"},
    )
    assert response.status_code == 401


@pytest.mark.skipif(not API_KEY, reason="HAWK_API_KEY not set — skipping live API test")
def test_unsupported_language_returns_422():
    """Unsupported target language is rejected at the API boundary."""
    response = httpx.post(
        f"{BASE_URL}/v1/translate",
        headers=HEADERS,
        json={"content": "<p>Test</p>", "source_language": "en", "target_language": "xx", "tier": "instant"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "unsupported_language"
