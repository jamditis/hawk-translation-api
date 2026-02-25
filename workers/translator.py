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

# Style rules for Spanish (es) — distilled from Yuli Delgado's STNS translation guide
# and validated/expanded via corpus analysis of 506 professionally translated articles.
# Source guide: resources/SPANISH-TRANSLATION-STYLE-GUIDE.md
# Corpus analysis: resources/corpus-analysis.md
SPANISH_STYLE_RULES = """
Follow these style rules from the STNS translation guide:

QUOTES
- Introduce with colon, capitalize first word: El informe señala: "Los resultados fueron claros".
- Add period after quotes ending in ! or ?: "¡Es urgente!".
- Use straight quotation marks (" "), not Spanish angle quotes (« »).

OXFORD COMMA
- Never use the Oxford comma before "y" or "o" in lists.

ACRONYMS (siglas)
- First use: Spanish expansion first, then (ACRONYM, por sus siglas en inglés) in parentheses.
  Example: Servicio de Inmigración y Control de Aduanas (ICE, por sus siglas en inglés)
- Order always: [Spanish name] ([ACRONYM], por sus siglas en inglés). Never reversed.
- In headings: full name only; expand in body text.
- Proper-noun acronyms with 4+ letters: capitalize first letter only (Unesco, not UNESCO).
- Subsequent uses: acronym alone. No plural "s" or apostrophe on acronyms.
- Well-known acronyms (FBI, SNAP, AIDS, COVID-19, LGBTQ+) do not need "por sus siglas en inglés".

DATES & TIMES
- Comma between weekday and date: el martes, 25 de diciembre de 2019
- Times: lowercase a.m./p.m. with periods: las 3:00 p.m., las 11:59 p.m.
- Dates: el 15 de marzo de 2025 (day + de + spelled-out month + de + year)
- Time zone: (hora del este)

NUMBERS
- Numerals for 10 and above; spell out 1-9.
- Always use numerals for: ages, dimensions, fractions, miles, money, percentages, times.
- Number ranges: use "a" or "y", not en-dash: paginas 94 a 98
- Avoid starting a sentence with a numeral.
- "1 billion" = "mil millones" (NOT "1 billón" — billón in Spanish != English billion).
- "1.3 billion" = "1,300 millones" (NOT "1.3 mil millones").
- "10+ billion" = "10 mil millones".
- Money uses US-style punctuation: $1,276.50 (NOT $1.276,50).
- Large dollar amounts: $X millones or $X mil millones. Do NOT add "dólares" after the $ sign.
  Correct: $20 millones. Incorrect: $20 millones de dólares or $20 dólares.
- Sub-dollar amounts: use the word "centavos", not the ¢ symbol.

UNITED STATES
- In body text: spell out "Estados Unidos". Never EEUU, EUA, or EE.UU. in body text.
- In headlines where space is tight: "EE. UU." (space after each period) is acceptable.

PREFIXES
- No hyphen: expresidente, sociocultural.
- Hyphen before proper nouns, acronyms, or numbers: anti-Brexit, pro-LGTBQ.
- Separate before multi-word units: ex vice presidente.

"Y/O"
- Never use "y/o". Use only "o".

MEASUREMENTS
- Keep original US measurements (feet, miles, pounds). Do NOT convert to metric.

STATE NAMES (use Spanish where different from English)
- Nueva Jersey, Nueva York, Nuevo México, Nuevo Hampshire, Pensilvania,
  Carolina del Norte, Carolina del Sur, Dakota del Norte, Dakota del Sur,
  Luisiana, Míchigan, Misisipi, Misuri, Oregón, Hawái, Virginia Occidental.
- California, Florida, Alaska, Texas, Montana, Kansas, Massachusetts: same in Spanish.
- In body text: always write "Nueva Jersey", never the abbreviation "NJ".

ATTRIBUTIVE VERBS (match verb to register, do not rotate mechanically)
- dijo: neutral baseline
- afirmó: emphatic personal statements
- declaró: formal or official statements (press releases, legal proceedings)
- señaló / señala: pointing to data, a document, or a written source
- explicó / explicaron: elaborations or context-giving remarks
- comentó: informal or conversational quotes
- informó: officials relaying factual information
- sostuvo / argumentaron: formal positions, legal arguments
- advirtió: warnings
- Also: expresó, mencionó, manifestó, añadió
- Do not repeat the same verb in adjacent paragraphs.

PROPER NAMES
- Never translate official names of publications, programs, brands, or organizations.
  Keep in English: NJ FamilyCare, Medicaid, Real ID, NJ.com, The New York Times.
- If clarification is needed: el programa NJ FamilyCare (seguro médico estatal).

ANGLICISMS
- English nouns used in US-context Spanish journalism: add required accent and gloss on first use.
  Example: escuela chárter (autónoma). Do not italicize. Do not apply to proper names.

BILL NUMBERS
- Keep legislative identifiers in English alphanumeric format: A1475, S-3947.

GEOGRAPHY
- "county" = "condado": condado de Somerset, condado de Bergen.
- "Garden State" as a proper epithet = "el Estado Jardín" (capitalized).

TITLE CAPITALIZATION
- Capitalize when used as a proper institutional reference: el Gobernador anunció.
- Lowercase when descriptive before a name: el gobernador Phil Murphy.

KEY TERMS
- "Humanitarian parole" = "permiso humanitario" (not "libertad condicional humanitaria")
- ICE = Servicio de Inmigración y Control de Aduanas (ICE, por sus siglas en inglés)
- ACA = Ley de Atención Médica Asequible (ACA, por sus siglas en inglés)
- ACLU = Unión Estadounidense por las Libertades Civiles
- affordable housing = vivienda asequible
- charter school = escuela chárter (autónoma)
- school district = distrito escolar / school board = junta escolar
- budget = presupuesto / bill (legislation) = proyecto de ley
- immigrants = inmigrantes / migrants = migrantes / deportations = deportaciones
- GOP = Partido Republicano (or "republicano" adjectivally)
- primary (election) = primarias / mayor = alcalde / county = condado
"""

SPANISH_TRANSLATION_PROMPT_TEMPLATE = """Translate these English journalism segments to Spanish for a US Hispanic audience.
{style_rules}
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
        _translate_batch(segments[i : i + BATCH_SIZE], target_language)

    return segments


def _translate_batch(batch: list[dict], target_language: str) -> None:
    """Translate a batch of segments in-place. Falls back to untranslated on failure."""
    language_name = LANGUAGE_NAMES[target_language]
    texts = [s["text"] for s in batch]

    if target_language == "es":
        prompt = SPANISH_TRANSLATION_PROMPT_TEMPLATE.format(
            style_rules=SPANISH_STYLE_RULES,
            segments_json=json.dumps(texts, ensure_ascii=False),
        )
    else:
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
