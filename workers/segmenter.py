from bs4 import BeautifulSoup

TRANSLATABLE_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "figcaption", "td", "th"}


def segment_html(html: str) -> list[dict]:
    """
    Parse HTML and extract translatable segments.

    Each segment dict: {index, tag, text, inner_html, translated}
    - text: plain text content (for translation input)
    - inner_html: full tag with attributes (for reference)
    - translated: None until translation is applied
    """
    soup = BeautifulSoup(html, "lxml")
    segments = []
    index = 0

    for element in soup.find_all(TRANSLATABLE_TAGS):
        text = element.get_text(strip=True)
        if not text:
            continue
        segments.append({
            "index": index,
            "tag": element.name,
            "text": text,
            "inner_html": str(element),
            "translated": None,
        })
        index += 1

    return segments


def reassemble_html(segments: list[dict]) -> str:
    """
    Reassemble translated segments into HTML.
    Uses the translated text (or original if untranslated), wrapped in the original tag.
    """
    parts = []
    for seg in segments:
        translated = seg.get("translated") or seg["text"]
        parts.append(f"<{seg['tag']}>{translated}</{seg['tag']}>")
    return "\n".join(parts)
