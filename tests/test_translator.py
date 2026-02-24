import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from workers.translator import (
    SUPPORTED_TARGET_LANGUAGES,
    translate_segments,
)

SUPPORTED_LANGUAGES = ["es", "pt", "ht", "zh", "ko", "ar", "fr", "pl", "hi", "ur"]


def make_segment(text="Hello world.", index=0):
    return {
        "index": index,
        "tag": "p",
        "text": text,
        "inner_html": f"<p>{text}</p>",
        "translated": None,
    }


def mock_claude_response(translations: list[str]) -> MagicMock:
    mock = MagicMock()
    mock.stdout = json.dumps(translations)
    return mock


def test_supported_languages_list():
    for lang in SUPPORTED_LANGUAGES:
        assert lang in SUPPORTED_TARGET_LANGUAGES


def test_translate_segments_calls_claude():
    segments = [make_segment("Hello world.")]
    with patch("workers.translator.subprocess.run", return_value=mock_claude_response(["Hola mundo."])) as mock_run:
        result = translate_segments(segments, target_language="es")
    assert result[0]["translated"] == "Hola mundo."
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "claude"
    assert cmd[1] == "-p"
    assert "Spanish" in cmd[2]


def test_all_supported_languages_translate():
    for lang in SUPPORTED_LANGUAGES:
        segments = [make_segment()]
        with patch("workers.translator.subprocess.run", return_value=mock_claude_response(["translated"])):
            result = translate_segments(segments, target_language=lang)
        assert result[0]["translated"] == "translated"


def test_unknown_language_raises_value_error():
    segments = [make_segment()]
    with pytest.raises(ValueError, match="Unsupported target language"):
        translate_segments(segments, target_language="de")


def test_empty_segments_returns_empty():
    result = translate_segments([], target_language="es")
    assert result == []


def test_multiple_segments_translated_in_order():
    segments = [make_segment("Hello.", 0), make_segment("World.", 1)]
    with patch("workers.translator.subprocess.run", return_value=mock_claude_response(["Hola.", "Mundo."])):
        result = translate_segments(segments, target_language="es")
    assert result[0]["translated"] == "Hola."
    assert result[1]["translated"] == "Mundo."


def test_timeout_falls_back_to_untranslated():
    segments = [make_segment()]
    with patch("workers.translator.subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 60)):
        result = translate_segments(segments, target_language="es")
    assert result[0]["translated"] == "Hello world."
    assert result[0]["needs_review"] is True


def test_invalid_json_falls_back_to_untranslated():
    mock = MagicMock()
    mock.stdout = "not valid json"
    segments = [make_segment()]
    with patch("workers.translator.subprocess.run", return_value=mock):
        result = translate_segments(segments, target_language="es")
    assert result[0]["translated"] == "Hello world."
    assert result[0]["needs_review"] is True


def test_wrong_count_falls_back_to_untranslated():
    segments = [make_segment("A."), make_segment("B.", 1)]
    with patch("workers.translator.subprocess.run", return_value=mock_claude_response(["Only one translation"])):
        result = translate_segments(segments, target_language="es")
    for seg in result:
        assert seg["needs_review"] is True


def test_timeout_retries_then_falls_back():
    segments = [make_segment()]
    with patch("workers.translator.subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 60)) as mock_run:
        result = translate_segments(segments, target_language="fr")
    assert mock_run.call_count == 3  # MAX_RETRIES + 1
    assert result[0]["needs_review"] is True


def test_parse_error_does_not_retry():
    """Bad JSON should bail immediately without retrying — it won't self-resolve."""
    mock = MagicMock()
    mock.stdout = "not json"
    segments = [make_segment()]
    with patch("workers.translator.subprocess.run", return_value=mock) as mock_run:
        result = translate_segments(segments, target_language="ko")
    assert mock_run.call_count == 1  # no retries on parse error
    assert result[0]["needs_review"] is True
