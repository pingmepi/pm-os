"""Unit tests for lib/html_render.py — the security-critical escaping + section parsing
behind the stage 04/05 HTML companions. Untrusted artifact Markdown must never become live
HTML. Full companion rendering on approval is exercised in integration. See docs/TESTING.md §5 (T1)."""
import pytest

import html_render

pytestmark = pytest.mark.unit


def test_markdownish_escapes_untrusted_html():
    """A <script> tag in artifact content is HTML-escaped, not emitted raw — the XSS guard
    for the rendered companion."""
    out = html_render._markdownish("Hello <script>alert('xss')</script> world")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_inline_escapes_and_formats():
    """Inline rendering escapes dangerous HTML (e.g. <img onerror>) while still converting
    the safe **bold** and `code` subset."""
    out = html_render._inline("danger <img src=x onerror=1> and **bold** and `code`")
    assert "<img" not in out
    assert "&lt;img" in out
    assert "<strong>bold</strong>" in out
    assert "<code>code</code>" in out


def test_parse_sections_splits_on_h2():
    """Markdown is split into sections on `##` headings, and body text is rendered into the
    section's html."""
    md = "# Title\n\n## Problem\nproblem text\n\n## Users\nuser text\n"
    sections = html_render._parse_sections(md)
    titles = [s["title"] for s in sections]
    assert "Problem" in titles
    assert "Users" in titles
    problem = next(s for s in sections if s["title"] == "Problem")
    assert "problem text" in problem["html"]


def test_parse_sections_no_headings_defaults_overview():
    """A body with no `##` headings collapses to a single 'Overview' section rather than
    producing nothing."""
    sections = html_render._parse_sections("just a paragraph, no headings\n")
    assert len(sections) == 1
    assert sections[0]["title"] == "Overview"
