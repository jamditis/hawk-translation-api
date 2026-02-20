import logging
import os

import httpx

logger = logging.getLogger(__name__)

DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"
GOOGLE_TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"

# All 10 language codes the API layer accepts
SUPPORTED_TARGET_LANGUAGES = {"es", "pt", "ht", "zh", "ko", "ar", "fr", "pl", "hi", "ur"}

# Mapping from our codes to DeepL's target language codes (only for DEEPL_SUPPORTED languages)
DEEPL_LANGUAGE_CODES = {
    "es": "ES",
    "pt": "PT-BR",
    "zh": "ZH",
    "ko": "KO",
    "ar": "AR",
    "fr": "FR",
    "pl": "PL",
}

# Mapping from our codes to Google Translate language codes
GOOGLE_LANGUAGE_CODES = {
    "ht": "ht",
    "hi": "hi",
    "ur": "ur",
}

DEEPL_SUPPORTED = set(DEEPL_LANGUAGE_CODES.keys())
GOOGLE_FALLBACK = set(GOOGLE_LANGUAGE_CODES.keys())


def translate_segments(
    segments: list[dict],
    target_language: str,
    api_key: str,
) -> list[dict]:
    """
    Translate all segments to target_language.
    Uses DeepL for DEEPL_SUPPORTED languages; falls back to Google Translate for GOOGLE_FALLBACK.
    Updates each segment's 'translated' field in-place and returns the list.
    """
    if not segments:
        return segments

    if target_language not in SUPPORTED_TARGET_LANGUAGES:
        raise ValueError(
            f"Unsupported target language: {target_language!r}. "
            f"Supported: {sorted(SUPPORTED_TARGET_LANGUAGES)}"
        )

    if target_language in GOOGLE_FALLBACK:
        return _translate_via_google(segments, target_language)

    texts = [s["text"] for s in segments]
    deepl_lang = DEEPL_LANGUAGE_CODES[target_language]

    response = httpx.post(
        DEEPL_API_URL,
        headers={"Authorization": f"DeepL-Auth-Key {api_key}"},
        json={
            "text": texts,
            "source_lang": "EN",
            "target_lang": deepl_lang,
            "preserve_formatting": True,
        },
        timeout=30.0,
    )

    if response.status_code != 200:
        raise Exception(f"DeepL API error {response.status_code}: {response.text}")

    data = response.json()
    if len(data["translations"]) != len(texts):
        raise Exception(
            f"DeepL returned {len(data['translations'])} translations for {len(texts)} segments"
        )
    for i, translation in enumerate(data["translations"]):
        segments[i]["translated"] = translation["text"]

    return segments


def _translate_via_google(segments: list[dict], target_language: str) -> list[dict]:
    """Translate segments using Google Cloud Translation API.

    Falls back to returning untranslated text (flagged for review) if the API
    key is missing or the request fails, so jobs never hard-fail due to Google.
    """
    google_key = os.getenv("GOOGLE_TRANSLATE_API_KEY", "")
    if not google_key:
        logger.warning(
            "GOOGLE_TRANSLATE_API_KEY not set — returning untranslated text for %s",
            target_language,
        )
        for seg in segments:
            seg["translated"] = seg["text"]
            seg["needs_review"] = True
        return segments

    google_lang = GOOGLE_LANGUAGE_CODES[target_language]
    texts = [s["text"] for s in segments]

    # Google Translate API accepts batches of up to ~128 segments.
    # Batch in chunks of 100 to stay well within limits.
    BATCH_SIZE = 100
    all_translations = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        try:
            response = httpx.post(
                GOOGLE_TRANSLATE_URL,
                params={"key": google_key},
                json={
                    "q": batch,
                    "source": "en",
                    "target": google_lang,
                    "format": "text",
                },
                timeout=30.0,
            )
            if response.status_code != 200:
                raise Exception(
                    f"Google Translate API error {response.status_code}: {response.text}"
                )
            data = response.json()
            translations = data["data"]["translations"]
            all_translations.extend(t["translatedText"] for t in translations)
        except Exception:
            logger.exception(
                "Google Translate failed for batch %d–%d, target=%s",
                i, i + len(batch), target_language,
            )
            # Fall back to untranslated for the whole request on any failure
            for seg in segments:
                seg["translated"] = seg["text"]
                seg["needs_review"] = True
            return segments

    for i, translated_text in enumerate(all_translations):
        segments[i]["translated"] = translated_text

    return segments
