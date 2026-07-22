"""Unit coverage for the Markdown → Jira wiki markup converter (`lib/jira_markup.py`),
which renders ticket descriptions for the offline CSV export. See docs/guides/testing.md §5 (T1)."""
import pytest

from jira_markup import to_jira_markup

pytestmark = pytest.mark.unit


def test_headings_emphasis_and_links():
    """Headings become `hN.`, `**bold**` becomes Jira's `*bold*`, `~~x~~` becomes `-x-`,
    and a Markdown link becomes `[text|url]`."""
    assert to_jira_markup("## Overview") == "h2. Overview"
    assert to_jira_markup("###### Deep") == "h6. Deep"
    assert to_jira_markup("A **bold** word") == "A *bold* word"
    assert to_jira_markup("A ~~struck~~ word") == "A -struck- word"
    assert to_jira_markup("See [the PRD](https://x.test/prd)") == "See [the PRD|https://x.test/prd]"
    assert to_jira_markup("_italic_ stays _italic_") == "_italic_ stays _italic_"


def test_lists_preserve_nesting_depth():
    """Bullets become `*` and ordered items `#`, with one marker per two-space indent
    level — the shape the PM-OS artifact templates emit."""
    markdown = "- top\n  - nested\n    - deeper\n1. first\n   1. sub\n"
    assert to_jira_markup(markdown).splitlines() == [
        "* top", "** nested", "*** deeper", "# first", "## sub",
    ]


def test_code_is_protected_from_every_other_rule():
    """Inline code becomes `{{…}}` and a fenced block becomes `{code:lang}`; neither has
    its contents rewritten, so Markdown syntax inside a code sample survives intact."""
    out = to_jira_markup("Set `status: **done**` now.")
    assert out == "Set {{status: **done**}} now."

    fenced = to_jira_markup('```python\nx = "**not bold**"\n# not a heading\n```')
    assert fenced.splitlines() == ["{code:python}", 'x = "**not bold**"', "# not a heading", "{code}"]
    assert to_jira_markup("```\nplain\n```").splitlines()[0] == "{code}"


def test_unterminated_fence_is_closed():
    """A description truncated mid-code-block still renders in Jira rather than
    swallowing the rest of the ticket."""
    assert to_jira_markup("```\nx = 1").splitlines() == ["{code}", "x = 1", "{code}"]


def test_tables_mark_the_header_row_and_drop_the_separator():
    """A Markdown table becomes `||header||` + `|cell|`; the `|---|` separator row is
    dropped because Jira has no equivalent."""
    markdown = "| Role | Primary |\n|---|---|\n| Extraction | model-a |\n"
    assert to_jira_markup(markdown).splitlines() == [
        "||Role||Primary||", "|Extraction|model-a|",
    ]


def test_quotes_rules_and_unknown_syntax_pass_through():
    """Blockquotes become `bq.`, thematic breaks `----`, and anything the subset does not
    recognize is emitted unchanged — the safe failure mode for a ticket body."""
    assert to_jira_markup("> note") == "bq. note"
    assert to_jira_markup("---") == "----"
    assert to_jira_markup("Plain sentence, 1 < 2 & fine.") == "Plain sentence, 1 < 2 & fine."
    assert to_jira_markup("") == ""
