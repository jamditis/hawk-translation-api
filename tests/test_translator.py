import pytest
import respx
import httpx
from unittest.mock import patch
from workers.translator import (
    translate_segments,
    DEEPL_API_URL,
    GOOGLE_TRANSLATE_URL,
    SUPPORTED_TARGET_LANGUAGES,
)


SUPPORTED_LANGUAGES = ["es", "pt", "ht", "zh", "ko", "ar", "fr", "pl", "hi", "ur"]


def test_supported_languages_list():
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


def test_unknown_language_raises_value_error():
    segments = [{"index": 0, "tag": "p", "text": "Hello.", "inner_html": "<p>Hello.</p>", "translated": None}]
    with pytest.raises(ValueError, match="Unsupported target language"):
        translate_segments(segments, target_language="de", api_key="fake-key")


def test_google_fallback_without_api_key_returns_untranslated():
    """Without GOOGLE_TRANSLATE_API_KEY, returns untranslated text flagged for review."""
    segments = [{"index": 0, "tag": "p", "text": "Hello world.", "inner_html": "<p>Hello world.</p>", "translated": None}]
    with patch.dict("os.environ", {"GOOGLE_TRANSLATE_API_KEY": ""}):
        result = translate_segments(segments, target_language="ht", api_key="fake-key")
    assert result[0]["translated"] == "Hello world."
    assert result[0]["needs_review"] is True


@respx.mock
def test_google_fallback_calls_google_translate_api():
    """With GOOGLE_TRANSLATE_API_KEY set, calls Google Cloud Translation API."""
    google_response = {
        "data": {
            "translations": [{"translatedText": "Bonjou mond."}]
        }
    }
    respx.post(GOOGLE_TRANSLATE_URL).mock(return_value=httpx.Response(200, json=google_response))

    segments = [{"index": 0, "tag": "p", "text": "Hello world.", "inner_html": "<p>Hello world.</p>", "translated": None}]
    with patch.dict("os.environ", {"GOOGLE_TRANSLATE_API_KEY": "fake-google-key"}):
        result = translate_segments(segments, target_language="ht", api_key="fake-key")
    assert result[0]["translated"] == "Bonjou mond."
    assert "needs_review" not in result[0]


@respx.mock
def test_google_fallback_handles_api_error_gracefully():
    """When Google Translate API returns an error, falls back to untranslated text."""
    respx.post(GOOGLE_TRANSLATE_URL).mock(return_value=httpx.Response(500, text="Internal Server Error"))

    segments = [{"index": 0, "tag": "p", "text": "Hello.", "inner_html": "<p>Hello.</p>", "translated": None}]
    with patch.dict("os.environ", {"GOOGLE_TRANSLATE_API_KEY": "fake-google-key"}):
        result = translate_segments(segments, target_language="hi", api_key="fake-key")
    assert result[0]["translated"] == "Hello."
    assert result[0]["needs_review"] is True


@respx.mock
def test_google_fallback_for_all_three_languages():
    """All three fallback languages (ht, hi, ur) use Google Translate."""
    for lang in ["ht", "hi", "ur"]:
        google_response = {
            "data": {
                "translations": [{"translatedText": f"translated-{lang}"}]
            }
        }
        respx.post(GOOGLE_TRANSLATE_URL).mock(return_value=httpx.Response(200, json=google_response))

        segments = [{"index": 0, "tag": "p", "text": "Hello.", "inner_html": "<p>Hello.</p>", "translated": None}]
        with patch.dict("os.environ", {"GOOGLE_TRANSLATE_API_KEY": "fake-google-key"}):
            result = translate_segments(segments, target_language=lang, api_key="fake-key")
        assert result[0]["translated"] == f"translated-{lang}"
        respx.reset()


@respx.mock
def test_partial_deepl_response_raises():
    mock_response = {
        "translations": [{"detected_source_language": "EN", "text": "Hola."}]
        # Only 1 translation returned for 2 segments
    }
    respx.post(DEEPL_API_URL).mock(return_value=httpx.Response(200, json=mock_response))
    segments = [
        {"index": 0, "tag": "p", "text": "Hello.", "inner_html": "<p>Hello.</p>", "translated": None},
        {"index": 1, "tag": "p", "text": "World.", "inner_html": "<p>World.</p>", "translated": None},
    ]
    with pytest.raises(Exception, match="translations"):
        translate_segments(segments, target_language="es", api_key="fake-key")
