import re

from bs4 import BeautifulSoup

TRANSLATABLE_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "figcaption", "td", "th"}


def _has_translatable_descendant(element) -> bool:
    """Return True if element contains any nested translatable tag."""
    for tag in TRANSLATABLE_TAGS:
        if element.find(tag):
            return True
    return False


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
        if _has_translatable_descendant(element):
            continue  # translatable children will be picked up in their own iterations
        text = element.get_text(separator=" ", strip=True)
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
    Preserves original tag attributes (class, id, lang, etc.) from inner_html.
    """
    parts = []
    for seg in segments:
        translated = seg["translated"] if seg.get("translated") is not None else seg["text"]
        # Extract the opening tag with its original attributes from inner_html
        open_tag_match = re.match(r"<[^>]+>", seg["inner_html"])
        open_tag = open_tag_match.group(0) if open_tag_match else f"<{seg['tag']}>"
        close_tag = f"</{seg['tag']}>"
        parts.append(f"{open_tag}{translated}{close_tag}")
    return "\n".join(parts)
