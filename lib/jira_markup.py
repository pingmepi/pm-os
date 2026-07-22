"""Markdown → Jira wiki markup, for the offline CSV export.

Jira's CSV importer stores a ticket's Description verbatim and renders it as
**wiki markup**, not Markdown — so a description pasted straight from a PM-OS
artifact arrives with literal ``##`` and ``**`` in it. This module converts the
narrow slice of Markdown the PM-OS artifacts actually emit.

It is a deliberate, documented subset (same posture as ``html_render._markdownish``)
rather than a general Markdown parser — anything it does not recognize passes
through unchanged, which is the safe failure mode for a ticket description:

===========================  ==================================
Markdown                     Jira
===========================  ==================================
``## Heading``               ``h2. Heading``
``**bold**``                 ``*bold*``
``_italic_``                 ``_italic_`` (unchanged)
``~~struck~~``               ``-struck-``
``` `code` ```               ``{{code}}``
fenced block                 ``{code:lang}`` … ``{code}``
``- item`` / ``1. item``     ``* item`` / ``# item`` (nesting preserved)
``[text](url)``              ``[text|url]``
``> quote``                  ``bq. quote``
``---``                      ``----``
table + ``|---|`` separator  ``||header||`` + ``|cell|``
===========================  ==================================

Inline code and fenced blocks are protected: no other rule rewrites their
contents, so a description containing ``**`` inside a code sample survives.
"""
from __future__ import annotations

import re

_FENCE_RE = re.compile(r"^\s*```+\s*(?P<lang>[A-Za-z0-9_+-]*)\s*$")
_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.*)$")
_BULLET_RE = re.compile(r"^(?P<indent>\s*)[-*+]\s+(?P<text>.*)$")
_ORDERED_RE = re.compile(r"^(?P<indent>\s*)\d+[.)]\s+(?P<text>.*)$")
_QUOTE_RE = re.compile(r"^\s*>\s?(?P<text>.*)$")
_RULE_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|(?:\s*:?-{2,}:?\s*\|)+\s*$")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_BOLD_RE = re.compile(r"\*\*(?!\s)(.+?)(?<!\s)\*\*", re.DOTALL)
_STRIKE_RE = re.compile(r"~~(?!\s)(.+?)(?<!\s)~~", re.DOTALL)
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")

# Two indent columns per nesting level — the shape Markdown emitters (and the
# PM-OS artifact templates) use. Capped so a deeply/oddly indented line cannot
# emit an absurd bullet run.
_INDENT_WIDTH = 2
_MAX_LIST_DEPTH = 6

_CODE_TOKEN = "\x00jiracode{}\x00"


def _list_depth(indent: str) -> int:
    """1-based list nesting level for a line's leading whitespace."""
    columns = len(indent.expandtabs(_INDENT_WIDTH))
    return min(1 + columns // _INDENT_WIDTH, _MAX_LIST_DEPTH)


def _inline(text: str) -> str:
    """Apply the inline rules, with inline code stashed so nothing rewrites it."""
    stash: list[str] = []

    def _park(match: "re.Match[str]") -> str:
        stash.append(match.group(1))
        return _CODE_TOKEN.format(len(stash) - 1)

    text = _INLINE_CODE_RE.sub(_park, text)
    text = _BOLD_RE.sub(r"*\1*", text)
    text = _STRIKE_RE.sub(r"-\1-", text)
    text = _LINK_RE.sub(r"[\1|\2]", text)
    for index, code in enumerate(stash):
        text = text.replace(_CODE_TOKEN.format(index), "{{" + code + "}}")
    return text


def to_jira_markup(markdown: str) -> str:
    """Convert ``markdown`` to Jira wiki markup. Empty input returns ''."""
    if not markdown:
        return ""

    lines = markdown.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    in_fence = False

    for index, line in enumerate(lines):
        fence = _FENCE_RE.match(line)
        if fence:
            if in_fence:
                out.append("{code}")
                in_fence = False
            else:
                lang = fence.group("lang")
                out.append("{code:" + lang + "}" if lang else "{code}")
                in_fence = True
            continue
        if in_fence:
            out.append(line)  # verbatim: no inline rules inside a code block
            continue

        if _TABLE_SEPARATOR_RE.match(line):
            continue  # Jira has no separator row; the header is marked with ||
        if _TABLE_ROW_RE.match(line):
            cells = [_inline(cell.strip()) for cell in line.strip().strip("|").split("|")]
            is_header = _TABLE_SEPARATOR_RE.match(lines[index + 1]) if index + 1 < len(lines) else None
            delimiter = "||" if is_header else "|"
            out.append(delimiter + delimiter.join(cells) + delimiter)
            continue

        if _RULE_RE.match(line):
            out.append("----")
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            out.append(f"h{len(heading.group('hashes'))}. {_inline(heading.group('text').strip())}")
            continue

        ordered = _ORDERED_RE.match(line)
        if ordered:
            out.append("#" * _list_depth(ordered.group("indent")) + " " + _inline(ordered.group("text")))
            continue

        bullet = _BULLET_RE.match(line)
        if bullet:
            out.append("*" * _list_depth(bullet.group("indent")) + " " + _inline(bullet.group("text")))
            continue

        quote = _QUOTE_RE.match(line)
        if quote:
            out.append(f"bq. {_inline(quote.group('text'))}")
            continue

        out.append(_inline(line))

    if in_fence:  # unterminated fence in the source — close it so Jira renders
        out.append("{code}")
    return "\n".join(out)
