from workers.glossary import apply_glossary


def test_applies_known_term():
    text = "The Governor announced the budget."
    terms = {"Governor": "Gobernador"}
    result = apply_glossary(text, terms)
    assert "Gobernador" in result


def test_case_insensitive_match():
    text = "The governor announced the budget."
    terms = {"Governor": "Gobernador"}
    result = apply_glossary(text, terms)
    assert "Gobernador" in result


def test_no_partial_match():
    text = "Governance matters."
    terms = {"Governor": "Gobernador"}
    result = apply_glossary(text, terms)
    assert "Gobernador" not in result
    assert "Governance" in result


def test_multiple_terms():
    text = "The Montclair Board of Education voted."
    terms = {"Board of Education": "Junta de Educación", "Montclair": "Montclair"}
    result = apply_glossary(text, terms)
    assert "Junta de Educación" in result


def test_empty_terms_returns_original():
    text = "Hello world."
    result = apply_glossary(text, {})
    assert result == text
