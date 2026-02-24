import json
import logging

from workers.claude_runner import run_claude_p

logger = logging.getLogger(__name__)

SUBPROCESS_TIMEOUT = 60  # longer than scoring — translating full articles
MAX_RETRIES = 2
BATCH_SIZE = 50  # segments per claude -p call

SUPPORTED_TARGET_LANGUAGES = {"es", "pt", "ht", "zh", "ko", "ar", "fr", "pl", "hi", "ur"}

LANGUAGE_NAMES = {
    "es": "Spanish",
    "pt": "Portuguese (Brazilian)",
    "zh": "Chinese (Simplified)",
    "ko": "Korean",
    "ar": "Arabic",
    "fr": "French",
    "pl": "Polish",
    "ht": "Haitian Creole",
    "hi": "Hindi",
    "ur": "Urdu",
}

TRANSLATION_PROMPT_TEMPLATE = """Translate these English journalism segments to {language_name}.

Return a JSON array of translated strings in the same order. No other text.

{segments_json}"""


def translate_segments(
    segments: list[dict],
    target_language: str,
) -> list[dict]:
    """
    Translate all segments to target_language using claude -p subprocess.

    Sends segments in batches to Claude, which handles all 10 supported languages
    with no external API keys. If a batch fails (timeout or bad JSON), returns
    untranslated text flagged with needs_review=True so jobs still complete and
    human translators can address them in review.
    """
    if not segments:
        return segments

    if target_language not in SUPPORTED_TARGET_LANGUAGES:
        raise ValueError(
            f"Unsupported target language: {target_language!r}. "
            f"Supported: {sorted(SUPPORTED_TARGET_LANGUAGES)}"
        )

    language_name = LANGUAGE_NAMES[target_language]

    for i in range(0, len(segments), BATCH_SIZE):
        _translate_batch(segments[i : i + BATCH_SIZE], language_name)

    return segments


def _translate_batch(batch: list[dict], language_name: str) -> None:
    """Translate a batch of segments in-place. Falls back to untranslated on failure."""
    texts = [s["text"] for s in batch]
    prompt = TRANSLATION_PROMPT_TEMPLATE.format(
        language_name=language_name,
        segments_json=json.dumps(texts, ensure_ascii=False),
    )

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        output = run_claude_p(prompt, session_prefix="translator", timeout=SUBPROCESS_TIMEOUT)
        if output is None:
            last_error = "timeout"
            logger.warning(
                "Translation timed out (attempt %d/%d, batch=%d segments)",
                attempt + 1, MAX_RETRIES + 1, len(batch),
            )
            continue
        try:
            translations = json.loads(output.strip())
            if not isinstance(translations, list) or len(translations) != len(batch):
                raise ValueError(
                    f"Expected {len(batch)} translations, got "
                    f"{'non-list' if not isinstance(translations, list) else len(translations)}"
                )
            for i, translated_text in enumerate(translations):
                batch[i]["translated"] = str(translated_text)
            return
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.warning("Translation returned invalid output: %s", e)
            last_error = str(e)
            break  # parse errors won't self-resolve — skip remaining retries

    logger.warning(
        "Translation failed for batch of %d segments (last: %s) — returning untranslated",
        len(batch), last_error,
    )
    for seg in batch:
        seg["translated"] = seg["text"]
        seg["needs_review"] = True
