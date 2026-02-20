import pytest
import subprocess
from unittest.mock import patch, MagicMock, call
from workers.scorer import score_translation, ScoreResult, MAX_RETRIES


def make_mock_run(stdout: str, returncode: int = 0):
    result = MagicMock()
    result.stdout = stdout
    result.returncode = returncode
    return result


def test_parses_valid_score_output():
    mock_output = '{"overall": 4.2, "fluency": 4, "accuracy": 4.5, "flags": []}'
    with patch("subprocess.run", return_value=make_mock_run(mock_output)):
        result = score_translation(original="Hello world.", translated="Hola mundo.", target_lang="es")
    assert isinstance(result, ScoreResult)
    assert result.overall == 4.2
    assert result.fluency == 4
    assert result.accuracy == 4.5
    assert result.flags == []


def test_low_score_segment_flagged():
    mock_output = '{"overall": 2.1, "fluency": 2, "accuracy": 2, "flags": ["awkward phrasing"]}'
    with patch("subprocess.run", return_value=make_mock_run(mock_output)):
        result = score_translation(original="Complex legal text.", translated="Bad translation.", target_lang="es")
    assert result.overall < 3
    assert result.needs_review is True


def test_timeout_retries_then_returns_none():
    """Timeouts are retried MAX_RETRIES times before returning None."""
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 30)) as mock_run:
        result = score_translation(original="Hello.", translated="Hola.", target_lang="es")
    assert result is None
    assert mock_run.call_count == MAX_RETRIES + 1


def test_timeout_succeeds_on_retry():
    """If the first attempt times out but the second succeeds, return the score."""
    mock_output = '{"overall": 4.0, "fluency": 4, "accuracy": 4, "flags": []}'
    with patch("subprocess.run", side_effect=[
        subprocess.TimeoutExpired("claude", 30),
        make_mock_run(mock_output),
    ]) as mock_run:
        result = score_translation(original="Hello.", translated="Hola.", target_lang="es")
    assert result is not None
    assert result.overall == 4.0
    assert mock_run.call_count == 2


def test_malformed_json_does_not_retry():
    """Parse errors bail immediately without retrying."""
    with patch("subprocess.run", return_value=make_mock_run("not json")) as mock_run:
        result = score_translation(original="Hello.", translated="Hola.", target_lang="es")
    assert result is None
    assert mock_run.call_count == 1


def test_null_overall_score_returns_none():
    """Model returning null for a numeric field should return None, not raise TypeError."""
    mock_output = '{"overall": null, "fluency": 4, "accuracy": 4, "flags": []}'
    with patch("subprocess.run", return_value=make_mock_run(mock_output)):
        result = score_translation(original="Hello.", translated="Hola.", target_lang="es")
    assert result is None


def test_null_flags_returns_empty_list():
    """flags: null in JSON should produce an empty list, not None."""
    mock_output = '{"overall": 4.0, "fluency": 4, "accuracy": 4, "flags": null}'
    with patch("subprocess.run", return_value=make_mock_run(mock_output)):
        result = score_translation(original="Hello.", translated="Hola.", target_lang="es")
    assert result is not None
    assert result.flags == []


def test_curly_braces_in_content_do_not_raise():
    """Content containing { or } should not break the prompt .format() call."""
    mock_output = '{"overall": 4.0, "fluency": 4, "accuracy": 4, "flags": []}'
    with patch("subprocess.run", return_value=make_mock_run(mock_output)):
        result = score_translation(
            original='The {"key": "value"} JSON was published.',
            translated='El {"key": "value"} JSON fue publicado.',
            target_lang="es",
        )
    assert result is not None
    assert result.overall == 4.0
