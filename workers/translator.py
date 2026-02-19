import httpx

DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"

SUPPORTED_TARGET_LANGUAGES = {
    "es": "ES",       # Spanish
    "pt": "PT-BR",    # Portuguese (Brazil)
    "ht": "HT",       # Haitian Creole (Google fallback — DeepL doesn't support HT)
    "zh": "ZH",       # Chinese Simplified
    "ko": "KO",       # Korean
    "ar": "AR",       # Arabic
    "fr": "FR",       # French
    "pl": "PL",       # Polish
    "hi": "HI",       # Hindi
    "ur": "UR",       # Urdu (Google fallback)
}

# Languages DeepL natively supports vs. those needing a Google fallback
DEEPL_SUPPORTED = {"es", "pt", "zh", "ko", "fr", "pl"}
GOOGLE_FALLBACK = {"ht", "ar", "hi", "ur"}


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

    if target_language in GOOGLE_FALLBACK:
        return _translate_via_google(segments, target_language)

    texts = [s["text"] for s in segments]
    deepl_lang = SUPPORTED_TARGET_LANGUAGES[target_language]

    response = httpx.post(
        DEEPL_API_URL,
        headers={"Authorization": f"DeepL-Auth-Key {api_key}"},
        json={
            "text": texts,
            "source_lang": "EN",
            "target_lang": deepl_lang,
            "tag_handling": "xml",
            "preserve_formatting": True,
        },
        timeout=30.0,
    )

    if response.status_code != 200:
        raise Exception(f"DeepL API error {response.status_code}: {response.text}")

    data = response.json()
    for i, translation in enumerate(data["translations"]):
        segments[i]["translated"] = translation["text"]

    return segments


def _translate_via_google(segments: list[dict], target_language: str) -> list[dict]:
    """Stub for languages DeepL doesn't support. Returns untranslated, flagged for review."""
    for seg in segments:
        seg["translated"] = seg["text"]
        seg["needs_review"] = True
    return segments
