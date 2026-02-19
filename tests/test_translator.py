import pytest
import respx
import httpx
from workers.translator import translate_segments, DEEPL_API_URL, SUPPORTED_TARGET_LANGUAGES


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
