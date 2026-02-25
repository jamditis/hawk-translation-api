import json
from unittest.mock import patch

import pytest

from workers.translator import (
    SUPPORTED_TARGET_LANGUAGES,
    translate_segments,
    SPANISH_STYLE_RULES,
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


def test_supported_languages_list():
    for lang in SUPPORTED_LANGUAGES:
        assert lang in SUPPORTED_TARGET_LANGUAGES


def test_translate_segments_calls_claude():
    segments = [make_segment("Hello world.")]
    with patch("workers.translator.run_claude_p", return_value=json.dumps(["Hola mundo."])) as mock_run:
        result = translate_segments(segments, target_language="es")
    assert result[0]["translated"] == "Hola mundo."
    mock_run.assert_called_once()
    # Verify the prompt contains the language name and the source text
    prompt_arg = mock_run.call_args[0][0]
    assert "Spanish" in prompt_arg
    assert "Hello world." in prompt_arg


def test_all_supported_languages_translate():
    for lang in SUPPORTED_LANGUAGES:
        segments = [make_segment()]
        with patch("workers.translator.run_claude_p", return_value=json.dumps(["translated"])):
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
    with patch("workers.translator.run_claude_p", return_value=json.dumps(["Hola.", "Mundo."])):
        result = translate_segments(segments, target_language="es")
    assert result[0]["translated"] == "Hola."
    assert result[1]["translated"] == "Mundo."


def test_timeout_falls_back_to_untranslated():
    segments = [make_segment()]
    with patch("workers.translator.run_claude_p", return_value=None):
        result = translate_segments(segments, target_language="es")
    assert result[0]["translated"] == "Hello world."
    assert result[0]["needs_review"] is True


def test_invalid_json_falls_back_to_untranslated():
    segments = [make_segment()]
    with patch("workers.translator.run_claude_p", return_value="not valid json"):
        result = translate_segments(segments, target_language="es")
    assert result[0]["translated"] == "Hello world."
    assert result[0]["needs_review"] is True


def test_wrong_count_falls_back_to_untranslated():
    segments = [make_segment("A."), make_segment("B.", 1)]
    with patch("workers.translator.run_claude_p", return_value=json.dumps(["Only one translation"])):
        result = translate_segments(segments, target_language="es")
    for seg in result:
        assert seg["needs_review"] is True


def test_timeout_retries_then_falls_back():
    segments = [make_segment()]
    with patch("workers.translator.run_claude_p", return_value=None) as mock_run:
        result = translate_segments(segments, target_language="fr")
    assert mock_run.call_count == 3  # MAX_RETRIES + 1
    assert result[0]["needs_review"] is True


def test_parse_error_does_not_retry():
    """Bad JSON should bail immediately without retrying — it won't self-resolve."""
    segments = [make_segment()]
    with patch("workers.translator.run_claude_p", return_value="not json") as mock_run:
        result = translate_segments(segments, target_language="ko")
    assert mock_run.call_count == 1  # no retries on parse error
    assert result[0]["needs_review"] is True


def test_spanish_prompt_includes_style_rules():
    """Spanish translations inject Yuli's STNS style guide into the prompt."""
    segments = [make_segment("The mayor spoke today.")]
    with patch("workers.translator.run_claude_p", return_value=json.dumps(["El alcalde habló hoy."])) as mock_run:
        translate_segments(segments, target_language="es")
    prompt_arg = mock_run.call_args[0][0]
    assert "EE. UU." in prompt_arg
    assert "mil millones" in prompt_arg
    assert "permiso humanitario" in prompt_arg
    assert "expresó" in prompt_arg


def test_non_spanish_prompt_excludes_style_rules():
    """Non-Spanish languages use the generic prompt without Spanish-specific rules."""
    segments = [make_segment("The mayor spoke today.")]
    with patch("workers.translator.run_claude_p", return_value=json.dumps(["Le maire a parlé aujourd'hui."])) as mock_run:
        translate_segments(segments, target_language="fr")
    prompt_arg = mock_run.call_args[0][0]
    assert "EE. UU." not in prompt_arg
    assert "mil millones" not in prompt_arg
    assert "French" in prompt_arg


def test_spanish_style_rules_constant_has_required_sections():
    """The SPANISH_STYLE_RULES constant covers all key sections from Yuli's guide."""
    assert "QUOTES" in SPANISH_STYLE_RULES
    assert "ACRONYMS" in SPANISH_STYLE_RULES
    assert "NUMBERS" in SPANISH_STYLE_RULES
    assert "UNITED STATES" in SPANISH_STYLE_RULES
    assert "MEASUREMENTS" in SPANISH_STYLE_RULES
    assert "STATE NAMES" in SPANISH_STYLE_RULES
    assert "EE. UU." in SPANISH_STYLE_RULES
    assert "billón" in SPANISH_STYLE_RULES
