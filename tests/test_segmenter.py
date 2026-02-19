from workers.segmenter import segment_html, reassemble_html


def test_extracts_paragraph_text():
    html = "<p>Hello world.</p><p>Second paragraph.</p>"
    segments = segment_html(html)
    assert len(segments) == 2
    assert segments[0]["text"] == "Hello world."
    assert segments[1]["text"] == "Second paragraph."


def test_preserves_html_tags():
    html = "<p>Hello <strong>world</strong>.</p>"
    segments = segment_html(html)
    assert "strong" in segments[0]["inner_html"]


def test_extracts_headline_separately():
    html = "<h1>City council votes on budget</h1><p>The council met Tuesday.</p>"
    segments = segment_html(html)
    assert any(s["tag"] == "h1" for s in segments)
    assert any(s["tag"] == "p" for s in segments)


def test_reassemble_produces_valid_html():
    html = "<p>Hello world.</p><p>Second paragraph.</p>"
    segments = segment_html(html)
    for s in segments:
        s["translated"] = s["text"].upper()
    result = reassemble_html(segments)
    assert "<p>" in result
    assert "HELLO WORLD." in result


def test_empty_paragraphs_skipped():
    html = "<p></p><p>Real content.</p><p>  </p>"
    segments = segment_html(html)
    assert len(segments) == 1
    assert segments[0]["text"] == "Real content."
