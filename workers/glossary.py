import re


def apply_glossary(text: str, terms: dict[str, str]) -> str:
    """
    Apply glossary substitutions to plain text before translation.

    Uses whole-word matching (regex word boundaries), case-insensitive.
    Applies longer terms first to avoid partial matches stomping multi-word phrases
    (e.g., "Board of Education" must be matched before "Board").
    """
    if not terms:
        return text

    result = text
    # Sort by source term length descending: "Board of Education" before "Board"
    sorted_terms = sorted(terms.items(), key=lambda x: len(x[0]), reverse=True)

    for source, target in sorted_terms:
        pattern = re.compile(r"\b" + re.escape(source) + r"\b", re.IGNORECASE)
        result = pattern.sub(target, result)

    return result
