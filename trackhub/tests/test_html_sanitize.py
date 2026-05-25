from trackhub.utils.html_sanitize import (
    rich_text_is_empty,
    rich_text_to_plain_preview,
    sanitize_rich_text,
)


def test_sanitize_allows_basic_formatting():
    raw = "<p><strong>Olá</strong> <em>mundo</em></p><script>alert(1)</script>"
    out = sanitize_rich_text(raw)
    assert "<strong>Olá</strong>" in out
    assert "<em>mundo</em>" in out
    assert "script" not in out


def test_sanitize_strips_disallowed_tags():
    raw = '<a href="http://evil.com">link</a><u>ok</u>'
    out = sanitize_rich_text(raw)
    assert "href" not in out
    assert "<u>ok</u>" in out


def test_rich_text_is_empty():
    assert rich_text_is_empty("") is True
    assert rich_text_is_empty("<p><br></p>") is True
    assert rich_text_is_empty("<p>texto</p>") is False


def test_rich_text_to_plain_preview():
    assert rich_text_to_plain_preview("<p><b>Hi</b></p>", 10) == "Hi"
