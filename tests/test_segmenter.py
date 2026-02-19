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


def test_nested_translatable_tags_emits_leaf_only():
    """blockquote containing li — only li segments should be emitted, not the blockquote."""
    html = "<blockquote><ul><li>Item one</li><li>Item two</li></ul></blockquote>"
    segments = segment_html(html)
    tags = [s["tag"] for s in segments]
    assert "blockquote" not in tags
    assert tags.count("li") == 2


def test_preserves_tag_attributes_in_reassembly():
    """class and id on a <p> should survive segmentation and reassembly."""
    html = '<p class="lede" id="first">Lead text.</p>'
    segments = segment_html(html)
    segments[0]["translated"] = "Texto principal."
    result = reassemble_html(segments)
    assert 'class="lede"' in result
    assert 'id="first"' in result


def test_inline_markup_word_boundaries_preserved():
    """Inline elements like <strong> should not eat surrounding spaces in text."""
    html = "<p>Hello <strong>world</strong> today.</p>"
    segments = segment_html(html)
    assert "world" in segments[0]["text"]
    # Words should be space-separated, not concatenated
    assert "Helloworld" not in segments[0]["text"]
