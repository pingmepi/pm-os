"""Unit tests for lib/html_render.py — the security-critical escaping + section parsing
behind the stage 04/05 HTML companions. Untrusted artifact Markdown must never become live
HTML. Full companion rendering on approval is exercised in integration. See docs/guides/testing.md §5 (T1)."""
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


def test_color_swatches_wraps_hex_and_rgb_literals():
    """Color literals (#RGB / #RRGGBB / rgb() / rgba()) each gain a preview swatch span
    styled with that color as its background, so a design spec renders colors rather than
    bare hashcodes (GH #62). The literal text itself is preserved next to the swatch."""
    src = html_render._markdownish(
        "- Primary #FF5733\n- Short #0af\n- Surface rgb(255,255,255)\n- Muted rgba(0,0,0,0.5)"
    )
    out = html_render._color_swatches(src)
    assert out.count('class="color-swatch"') == 4
    assert "background:#FF5733" in out
    assert "background:rgb(255,255,255)" in out
    assert "#FF5733" in out  # original literal is kept, not replaced


def test_color_swatches_ignores_non_color_hash_tokens():
    """A `#SCR-001` anchor-style token is not a valid color literal and must not get a
    swatch — guards against swatching screen ids or other `#`-prefixed text."""
    out = html_render._color_swatches(html_render._markdownish("See #SCR-001 and #NOTHEX"))
    assert "color-swatch" not in out


def test_prototype_screens_carry_scr_anchor_when_declared():
    """The lo-fi fallback renderer extracts the SCR-### id from each 'Screens to Include'
    item so the mockup is deep-linkable at `#SCR-###`, matching the anchor requirement the
    pm-prototype-html skill and validator enforce (backlog #29). Screens named without an
    id (a design spec predating screen ids) carry an empty screen_id, not a bogus one."""
    screens = [
        "SCR-001 - Agency list - purpose; content; controls",
        "Plain screen with no id",
    ]
    result = html_render._prototype_screens(screens, interactions=[], components=[])
    assert result[0]["screen_id"] == "SCR-001"
    assert result[1]["screen_id"] == ""
