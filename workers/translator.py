import httpx

DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"

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

DEEPL_SUPPORTED = set(DEEPL_LANGUAGE_CODES.keys())
GOOGLE_FALLBACK = {"ht", "hi", "ur"}


def translate_segments(
    segments: list[dict],
    target_language: str,
    api_key: str,
) -> list[dict]:
    """
    Translate all segments to target_language.
    Uses DeepL for DEEPL_SUPPORTED languages; falls back to stub for GOOGLE_FALLBACK languages.
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
    """Stub for languages DeepL doesn't support. Returns untranslated, flagged for review."""
    for seg in segments:
        seg["translated"] = seg["text"]
        seg["needs_review"] = True
    return segments
