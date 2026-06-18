"""Unit tests for html_render — the security-critical escaping + section parsing.

Full companion rendering (stage 04/05 on approval) is exercised in integration.
"""
import pytest

import html_render

pytestmark = pytest.mark.unit


def test_markdownish_escapes_untrusted_html():
    out = html_render._markdownish("Hello <script>alert('xss')</script> world")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_inline_escapes_and_formats():
    out = html_render._inline("danger <img src=x onerror=1> and **bold** and `code`")
    assert "<img" not in out
    assert "&lt;img" in out
    assert "<strong>bold</strong>" in out
    assert "<code>code</code>" in out


def test_parse_sections_splits_on_h2():
    md = "# Title\n\n## Problem\nproblem text\n\n## Users\nuser text\n"
    sections = html_render._parse_sections(md)
    titles = [s["title"] for s in sections]
    assert "Problem" in titles
    assert "Users" in titles
    # body text is escaped/rendered into html
    problem = next(s for s in sections if s["title"] == "Problem")
    assert "problem text" in problem["html"]


def test_parse_sections_no_headings_defaults_overview():
    sections = html_render._parse_sections("just a paragraph, no headings\n")
    assert len(sections) == 1
    assert sections[0]["title"] == "Overview"
