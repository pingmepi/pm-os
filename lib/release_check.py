"""Release check for a handoff folder, PM-OS-built or hand-built (backlog #72).

A handoff reaches a build team as a folder of files. This module reads that
folder the way the build team will and reports what they would trip over:

- stories with no epic or no priority, or a malformed priority value;
- ids cited in prose that nothing in the folder defines (any prefix, not just
  PM-OS's own families);
- relative links that do not resolve, or that leave the package;
- referenced files that do not exist;
- placeholder or pending markers;
- stale sources: a `generated_from` hash that no longer matches the source
  artifact (PM-OS packages), or a `source: <doc> vX` that is older than the
  version of `<doc>` in the folder (hand-built packages);
- for PM-OS packages, exported requirements no test case covers (backlog #53,
  option a).

It is pure and read-only: it never writes, never logs, never prompts. The
callers (`scripts/pm_release_check.py`, `pm_share.py --package`) decide what an
error means for them.

Id detection is generic because a package carries id families PM-OS has never
heard of (`R-01` rules, `BR-12` business rules, `S1-US-03` sprint stories). See
``ID_RULE`` below for the declaration and citation rule.
"""
from __future__ import annotations

import re
import tempfile
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote

import yaml

# ---------------------------------------------------------------------------
# Findings and report
# ---------------------------------------------------------------------------

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class ReleaseFinding:
    severity: str          # error | warning
    code: str
    path: str              # relative to the checked folder, POSIX separators
    line: int | None
    message: str
    fix: str

    def location(self) -> str:
        return f"{self.path}:{self.line}" if self.line else self.path

    def as_dict(self) -> dict:
        return {
            "severity": self.severity, "code": self.code, "path": self.path,
            "line": self.line, "message": self.message, "fix": self.fix,
        }


@dataclass
class ReleaseReport:
    folder: Path
    kind: str                       # "pm-os" | "hand-built"
    project_root: Path | None
    findings: list[ReleaseFinding] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def errors(self) -> list[ReleaseFinding]:
        return [f for f in self.findings if f.severity == ERROR]

    @property
    def warnings(self) -> list[ReleaseFinding]:
        return [f for f in self.findings if f.severity == WARNING]

    def error_codes(self) -> list[str]:
        return sorted({f.code for f in self.errors})

    def as_dict(self) -> dict:
        return {
            "folder": str(self.folder),
            "kind": self.kind,
            "project_root": str(self.project_root) if self.project_root else None,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "stats": self.stats,
            "findings": [f.as_dict() for f in self.findings],
        }


def format_report(report: ReleaseReport, *, label: str | None = None, max_findings: int | None = None) -> str:
    """Human-readable report: one block per finding with its location and fix."""
    s = report.stats
    lines = [
        f"Release check: {label or report.folder} ({report.kind} package"
        + (f", project {report.project_root.name}" if report.project_root else "") + ")",
        f"  {s.get('files', 0)} files · {s.get('stories', 0)} stories · "
        f"{s.get('ids_declared', 0)} ids defined · {s.get('links', 0)} relative links",
        "",
    ]
    shown = report.findings if max_findings is None else report.findings[:max_findings]
    for f in shown:
        lines.append(f"{f.severity.upper():7} {f.location()}  {f.code}")
        lines.append(f"        {f.message}")
        lines.append(f"        Fix: {f.fix}")
    if max_findings is not None and len(report.findings) > max_findings:
        lines.append(f"... {len(report.findings) - max_findings} more (re-run with --json for all)")
    if report.findings:
        lines.append("")
    lines.append(f"{len(report.errors)} error(s), {len(report.warnings)} warning(s).")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# File inventory
# ---------------------------------------------------------------------------

TEXT_SUFFIXES = {".md", ".markdown", ".yaml", ".yml", ".json", ".txt", ".csv"}
MARKDOWN_SUFFIXES = {".md", ".markdown"}
HANDOFF_MARKER = ".pm-os-handoff"
NOT_CAPTURED = "— not captured in source —"
_SKIP_DIRS = {".git", "__pycache__", "node_modules", "__MACOSX"}


@dataclass
class _Doc:
    path: Path
    rel: str
    text: str
    frontmatter: dict
    fm_end_line: int          # last line number of the frontmatter block (0 if none)

    @property
    def is_markdown(self) -> bool:
        return self.path.suffix.lower() in MARKDOWN_SUFFIXES

    def lines(self) -> list[str]:
        return self.text.splitlines()


def _split_frontmatter(text: str) -> tuple[dict, int]:
    if not text.startswith("---\n"):
        return {}, 0
    end = text.find("\n---\n", 4)
    if end == -1 and text.endswith("\n---"):
        end = len(text) - 4
    if end == -1:
        return {}, 0
    try:
        fm = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        fm = {"__invalid__": True}
    if not isinstance(fm, dict):
        fm = {}
    return fm, text[: end + 4].count("\n") + 1


def _inventory(folder: Path) -> tuple[list[Path], list[_Doc]]:
    files: list[Path] = []
    docs: list[_Doc] = []
    for path in sorted(folder.rglob("*")):
        if any(part in _SKIP_DIRS for part in path.relative_to(folder).parts):
            continue
        if not path.is_file():
            continue
        files.append(path)
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        fm, fm_end = _split_frontmatter(text) if path.suffix.lower() in MARKDOWN_SUFFIXES else ({}, 0)
        docs.append(_Doc(path, path.relative_to(folder).as_posix(), text, fm, fm_end))
    return files, docs


def _prose_lines(doc: _Doc) -> Iterable[tuple[int, str]]:
    """Markdown lines outside fenced code, with inline code spans removed.

    Code is where packages put sample data and schemas (`"sentence_id": "S-001"`),
    so ids, placeholders and paths inside code are examples, not claims.
    """
    in_fence = False
    for number, line in enumerate(doc.lines(), 1):
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        yield number, _INLINE_CODE_RE.sub(" ", line)


_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
_CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")


# ---------------------------------------------------------------------------
# Id rule (PM decision 2026-10-21; operator notes in docs/guides/sop.md)
# ---------------------------------------------------------------------------

ID_RULE = """\
An id is an upper-case prefix (one or more dash-joined segments, e.g. R, BR,
S1-US, OD-R2) followed by a dash and a number with optional dotted parts
(R-01, FR-1.1, US-001).

DEFINED: an id is defined by any of
  1. a Markdown heading that starts with it            (### US-001 — Sign in)
  2. a line or list item that starts with it in bold   (- **R-01** The live page…)
  3. a line or list item that starts with it then : — – ·   (FR-1.1: Start a run)
  4. the first cell of a table row                     (| **R-01 The live…** | …)
  5. a frontmatter / YAML key `id` or `<thing>_id`     (story_id: S1-US-01)
  6. a file name that starts with it                   (S1-US-01-start-a-run.md)

CITED: any id in Markdown prose. Fenced code, `inline code`, link targets and
URLs are skipped.

CHECKED: a cited id is checked only when its family is an id family in this
folder: the folder defines at least one id with that prefix, or prose cites at
least three distinct ids with it. One-off tokens (COVID-19, ISO-8601, SHA-256)
never form a family; well-known standard prefixes are ignored outright, and so
are 4+-digit numbers in a family the folder never defines (sample records like
RUN-0001).

RESULT for a checked id that nothing defines:
  - short form of exactly one defined id (US-13 for S1-US-13)  -> warning
  - short form of several defined ids (US-01: S1-US-01, S2-US-01) -> error
  - every citation is an example ("(S-001)", "e.g. E-12")      -> warning
  - defined in the PM-OS project's own artifacts but not
    shipped in this package                                    -> warning
  - otherwise                                                  -> error
"""

_ID = r"[A-Z][A-Z0-9]*(?:-[A-Z][A-Z0-9]*)*-\d+(?:\.\d+)*"
_ID_END = r"(?![A-Za-z0-9_-])"
ID_TOKEN_RE = re.compile(rf"(?<![A-Za-z0-9_./#-])({_ID}){_ID_END}")
_DECL_PATTERNS = (
    re.compile(rf"^\s*#{{1,6}}\s+(?:\*\*|__)?({_ID}){_ID_END}", re.M),
    re.compile(rf"^\s*(?:[-*+]\s+|\d+\.\s+)?(?:\*\*|__)({_ID}){_ID_END}", re.M),
    re.compile(rf"^\s*(?:[-*+]\s+|\d+\.\s+)?({_ID})\s*(?::|—|–|·)\s*\S", re.M),
    re.compile(rf"^\s*\|\s*(?:\*\*|__)?({_ID}){_ID_END}", re.M),
)
_KEY_ID_RE = re.compile(rf"^\s*-?\s*[\"']?(?:id|[a-z][a-z0-9_]*_id)[\"']?\s*:\s*[\"']?({_ID}){_ID_END}", re.M)
_FILENAME_ID_RE = re.compile(rf"^({_ID})(?:[-_.]|$)")
_CSV_FIRST_CELL_RE = re.compile(rf"^\s*\"?({_ID})\"?\s*[,;\t]", re.M)
_LINK_TARGET_RE = re.compile(r"\]\([^)]*\)")
_URL_RE = re.compile(r"\b(?:https?|ftp|mailto):[^\s)>\]]+", re.I)
_EXAMPLE_PAREN_RE = re.compile(r"\(\s*(?:e\.g\.|eg\b|for example|such as)[^)]*\)", re.I)
_EXAMPLE_LEAD_RE = re.compile(r"(?:e\.g\.|for example|such as)[^.;|]*$", re.I)

# Standards, encodings and other well-known "WORD-number" tokens that are never
# a package's own ids. Matched on the family prefix.
STANDARD_PREFIXES = frozenset({
    "AES", "ANSI", "BS", "CFR", "COVID", "CVE", "CWE", "DIN", "ECMA", "EN", "ES", "GMT",
    "GPT", "H", "HL", "HTTP", "ICD", "IEC", "IEEE", "IPV", "ISO", "MD", "MERS", "MPEG",
    "OWASP", "PCI", "PEP", "RFC", "RGB", "RSA", "SARS", "SHA", "SOC", "SSL", "TLS",
    "USB", "UTC", "UTF", "WCAG", "WPA",
})
SERIES_MIN = 3


def id_prefix(ident: str) -> str:
    return re.sub(r"-\d+(?:\.\d+)*$", "", ident)


def _id_number(ident: str) -> str:
    return re.search(r"-(\d+)(?:\.\d+)*$", ident).group(1)


def declared_ids(text: str, *, markdown: bool = True, csv: bool = False) -> set[str]:
    """Ids a document defines under ``ID_RULE`` (rules 1-5; a CSV's first column
    counts as rule 4)."""
    found: set[str] = set()
    patterns = _DECL_PATTERNS if markdown else ()
    for pattern in patterns:
        found.update(m.group(1) for m in pattern.finditer(text))
    if csv:
        found.update(m.group(1) for m in _CSV_FIRST_CELL_RE.finditer(text))
    found.update(m.group(1) for m in _KEY_ID_RE.finditer(text))
    return found


def _citations(doc: _Doc) -> Iterable[tuple[int, str, bool]]:
    """(line, id, is_example) for every id cited in a Markdown doc's prose.

    An example is an id standing alone in parentheses (`(S-001)`), inside an
    "(e.g. …)" aside, or after "e.g." / "for example" / "such as" in the same
    clause."""
    for number, line in _prose_lines(doc):
        cleaned = _URL_RE.sub(" ", _LINK_TARGET_RE.sub("]()", line))
        matches = list(ID_TOKEN_RE.finditer(cleaned))
        if not matches:
            continue
        asides = [(m.start(), m.end()) for m in _EXAMPLE_PAREN_RE.finditer(cleaned)]
        for match in matches:
            start, end = match.span(1)
            alone = cleaned[:start].rstrip().endswith("(") and cleaned[end:].lstrip().startswith(")")
            example = alone or any(a <= start < b for a, b in asides) or bool(
                _EXAMPLE_LEAD_RE.search(cleaned[:start]))
            yield number, match.group(1), example


# ---------------------------------------------------------------------------
# Package classification and the owning project
# ---------------------------------------------------------------------------

def _is_pmos_package(folder: Path, docs: list[_Doc]) -> bool:
    if (folder / HANDOFF_MARKER).exists() or any(folder.rglob(HANDOFF_MARKER)):
        return True
    return any("generated_from" in d.frontmatter and "canonical_source" in d.frontmatter for d in docs)


def find_project_root(folder: Path) -> Path | None:
    for candidate in (folder, *folder.parents):
        if (candidate / ".meta.yaml").is_file():
            return candidate
    return None


def _project_artifacts(project_root: Path) -> dict[str, dict]:
    """Stage artifacts of the owning project: name -> {hash, status, ids}."""
    out: dict[str, dict] = {}
    try:
        meta = yaml.safe_load((project_root / ".meta.yaml").read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        meta = {}
    try:  # an approved stage edited since approval counts as `edited`, not approved
        from hashing import mark_edited_in_memory
        mark_edited_in_memory(project_root, meta)
    except Exception:
        pass
    statuses = {str(s.get("id")): s.get("status") for s in meta.get("stages") or [] if isinstance(s, dict)}
    for path in sorted(project_root.glob("0[0-9]*.md")):
        try:
            text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        except (OSError, UnicodeDecodeError):
            continue
        fm, _ = _split_frontmatter(text)
        stage = path.name[:2]
        out[path.name] = {
            "hash": str(fm.get("content_hash") or fm.get("generated_hash") or ""),
            "status": statuses.get(stage) or fm.get("status"),
            "ids": declared_ids(text),
        }
    return out


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

_LABEL_RE_CACHE: dict[str, re.Pattern[str]] = {}


def _labeled(text: str, label: str) -> tuple[str | None, int | None]:
    pattern = _LABEL_RE_CACHE.setdefault(label, re.compile(
        rf"^\s*(?:[-*+]\s+|\d+\.\s+)?(?:\*\*)?{label}(?:\*\*)?\s*:(?:\*\*)?[ \t]*(?P<value>.*)$",
        re.I | re.M))
    match = pattern.search(text)
    if not match:
        return None, None
    return match.group("value").strip(), text[: match.start()].count("\n") + 1


def _fm_line(doc: _Doc, key: str) -> int:
    for number, line in enumerate(doc.lines()[: doc.fm_end_line], 1):
        if re.match(rf"^{re.escape(key)}\s*:", line):
            return number
    return 1


def _is_story(doc: _Doc) -> bool:
    if not doc.is_markdown:
        return False
    if doc.frontmatter.get("story_id"):
        return True
    parts = Path(doc.rel).parts
    return len(parts) >= 2 and parts[-2].lower() == "stories" and bool(_FILENAME_ID_RE.match(doc.path.name))


def _blank(value) -> bool:
    return value is None or str(value).strip() in ("", NOT_CAPTURED, "—", "-", "n/a", "N/A", "TBD")


_MALFORMED_VALUE_RE = re.compile(r"^\s*(?:\*|_|`)|\*\*|__")


def _check_stories(docs: list[_Doc]) -> tuple[list[ReleaseFinding], int]:
    findings: list[ReleaseFinding] = []
    stories = [d for d in docs if _is_story(d)]
    for doc in stories:
        story = doc.frontmatter.get("story_id") or _FILENAME_ID_RE.match(doc.path.name).group(1)
        if doc.frontmatter.get("__invalid__"):
            findings.append(ReleaseFinding(
                ERROR, "STORY_FRONTMATTER_INVALID", doc.rel, 1,
                f"{story}: the frontmatter is not valid YAML, so no reader can parse its fields.",
                "Fix the YAML between the opening and closing `---` (quote values that contain `: `)."))
        body = doc.text
        epic = doc.frontmatter.get("epic") or doc.frontmatter.get("epic_id")
        epic_line = _fm_line(doc, "epic") if epic else None
        if _blank(epic):
            epic, epic_line = _labeled(body, "Epic")
        if _blank(epic):
            findings.append(ReleaseFinding(
                ERROR, "STORY_EPIC_MISSING", doc.rel, 1,
                f"{story} names no epic.",
                f"Add `epic: <epic id>` to the frontmatter of {doc.path.name} (PM-OS packages: "
                "give the story an `Epic: EPIC-###` line in 03-prd.md and rebuild)."))
        priority = doc.frontmatter.get("priority")
        priority_line = _fm_line(doc, "priority") if priority is not None else None
        if _blank(priority):
            priority, priority_line = _labeled(body, "Priority")
        if _blank(priority):
            findings.append(ReleaseFinding(
                ERROR, "STORY_PRIORITY_MISSING", doc.rel, 1,
                f"{story} has no priority.",
                f"Add `priority: <Must|Should|Could|Won't …>` to the frontmatter of {doc.path.name} "
                "(PM-OS packages: give the story a `Priority:` line in 03-prd.md and rebuild)."))
        elif _MALFORMED_VALUE_RE.search(str(priority)):
            clean = re.sub(r"\*\*|__", "", str(priority)).strip(" *_`")
            findings.append(ReleaseFinding(
                ERROR, "STORY_PRIORITY_MALFORMED", doc.rel, priority_line,
                f"{story}: priority is {str(priority)!r}, which carries Markdown markup.",
                f"Set it to {clean!r}. PM-OS packages: rebuild with `/pm-handoff --package` "
                "(fixed in backlog #70)."))
    return findings, len(stories)


_MD_LINK_RE = re.compile(r"(?<!!)\[(?:[^\]\n]*)\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
_IMG_LINK_RE = re.compile(r"!\[(?:[^\]\n]*)\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
_REF_DEF_RE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)")
_HTML_LINK_RE = re.compile(r"""<(?:a|img)\b[^>]*\b(?:href|src)\s*=\s*["']([^"']+)["']""", re.I)


def _github_slug(heading: str) -> str:
    text = re.sub(r"<[^>]+>", "", heading).strip().lower()
    text = re.sub(r"[`*_~\[\]()]", "", text)
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def _anchors(doc: _Doc) -> set[str]:
    anchors: set[str] = set()
    counts: dict[str, int] = defaultdict(int)
    for _, line in _prose_lines(doc):
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match:
            slug = _github_slug(match.group(1))
            anchors.add(slug if counts[slug] == 0 else f"{slug}-{counts[slug]}")
            counts[slug] += 1
    anchors.update(re.findall(r"""\b(?:id|name)\s*=\s*["']([^"']+)["']""", doc.text))
    return anchors


def _check_links(folder: Path, docs: list[_Doc]) -> tuple[list[ReleaseFinding], int]:
    findings: list[ReleaseFinding] = []
    by_path = {d.path.resolve(): d for d in docs}
    anchor_cache: dict[Path, set[str]] = {}
    root = folder.resolve()
    count = 0
    for doc in docs:
        if not doc.is_markdown:
            continue
        in_fence = False
        for number, line in enumerate(doc.lines(), 1):
            if re.match(r"^\s*(```|~~~)", line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            line = _INLINE_CODE_RE.sub(" ", line)
            targets = [m.group(1) for rx in (_MD_LINK_RE, _IMG_LINK_RE, _HTML_LINK_RE) for m in rx.finditer(line)]
            ref = _REF_DEF_RE.match(line)
            if ref:
                targets.append(ref.group(1))
            for raw in targets:
                if re.match(r"^[a-z][a-z0-9+.-]*:", raw, re.I) or raw.startswith("//"):
                    continue  # URL, mailto:, data:
                count += 1
                target, _, fragment = raw.partition("#")
                target = unquote(target.split("?", 1)[0])
                if not target:
                    resolved = doc.path.resolve()
                elif target.startswith("/"):
                    findings.append(ReleaseFinding(
                        ERROR, "LINK_ABSOLUTE", doc.rel, number,
                        f"Link `{raw}` is an absolute path, which only resolves on the author's machine.",
                        "Make it relative to this file."))
                    continue
                else:
                    resolved = (doc.path.parent / target).resolve()
                inside = resolved == root or root in resolved.parents
                if not resolved.exists():
                    findings.append(ReleaseFinding(
                        ERROR, "LINK_BROKEN", doc.rel, number,
                        f"Link `{raw}` points to a file that does not exist"
                        + ("" if inside else " (and is outside this package)") + ".",
                        "Fix the path, add the missing file to the package, or remove the link."))
                    continue
                if not inside:
                    findings.append(ReleaseFinding(
                        ERROR, "LINK_OUTSIDE_PACKAGE", doc.rel, number,
                        f"Link `{raw}` leaves this package; whoever receives the package will not have the target.",
                        "Copy the target into the package and link it relatively, or cite it by name without a link."))
                    continue
                if fragment and resolved.is_file() and resolved in by_path:
                    target_doc = by_path[resolved]
                    if target_doc.is_markdown:
                        anchors = anchor_cache.setdefault(resolved, _anchors(target_doc))
                        if unquote(fragment).lower() not in {a.lower() for a in anchors}:
                            findings.append(ReleaseFinding(
                                WARNING, "LINK_ANCHOR_MISSING", doc.rel, number,
                                f"Link `{raw}` names a heading `#{fragment}` that {target_doc.rel} does not have.",
                                "Point the link at an existing heading, or drop the `#…` part."))
    return findings, count


_PATH_TOKEN_RE = re.compile(
    r"(?<![\w/.-])((?:\.{1,2}/)?(?:[\w.-]+/)*[\w.-]+\."
    r"(?:md|markdown|ya?ml|json|txt|csv|html?|png|jpe?g|svg|gif|pdf|docx?|xlsx?|pptx?|zip|py|ts|js|sql))(?![\w/-])",
    re.I,
)


def _check_referenced_files(folder: Path, docs: list[_Doc], files: list[Path],
                            owed: dict[str, str] | None = None) -> list[ReleaseFinding]:
    """Files named in code spans (and YAML values) that the package lacks.

    Only paths whose first directory exists in the package are checked (so
    `config/brands/x.yaml` is checked when `config/` ships, while `src/app.py`,
    a file the developer will create, is not). A bare file name is not checked:
    in practice it is usually a repository file the build team creates.
    """
    root = folder.resolve()

    def _inside(path: Path) -> bool:
        return path == root or root in path.parents

    findings: list[ReleaseFinding] = []
    seen: set[tuple[str, str]] = set()
    for doc in docs:
        if doc.path.name == "readiness.yaml":
            continue  # the record of owed files; its paths are checked as owed, not as references
        if doc.is_markdown:
            candidates = []
            for number, line in enumerate(doc.lines(), 1):
                for span in _CODE_SPAN_RE.findall(line):
                    candidates += [(number, m.group(1)) for m in _PATH_TOKEN_RE.finditer(span)]
        elif doc.path.suffix.lower() in {".yaml", ".yml"}:
            candidates = [(n, m.group(1)) for n, line in enumerate(doc.lines(), 1)
                          if not line.lstrip().startswith("#")
                          for m in _PATH_TOKEN_RE.finditer(line.split("#", 1)[0])]
        else:
            continue
        for number, ref in candidates:
            if re.match(r"^[a-z][a-z0-9+.-]*:", ref, re.I) or (doc.rel, ref) in seen:
                continue
            seen.add((doc.rel, ref))
            parts = Path(ref).parts
            if len(parts) == 1:
                continue  # a bare name is too often a repo file the build team creates
            here = (doc.path.parent / ref).resolve()
            from_root = (root / ref).resolve()
            if here.exists() or from_root.exists():
                continue
            # Checked only when the folder it names ships in the package; an
            # explicit ./ or ../ path is checked whenever it stays inside it.
            explicit = parts[0] in (".", "..")
            relevant = any(
                c.parent.is_dir() and _inside(c.parent) and (explicit or c.parent != root)
                for c in ((here,) if explicit else (here, from_root))
            )
            if not relevant:
                continue
            owed_by = next((item for path, item in (owed or {}).items()
                            if ref.replace("\\", "/").removeprefix("./").endswith(path)), None)
            if owed_by:
                findings.append(ReleaseFinding(
                    WARNING, "FILE_PENDING", doc.rel, number,
                    f"`{ref}` is not in the package yet; the readiness record lists it as owed ({owed_by}).",
                    f"Deliver it and mark {owed_by} received, before the milestone that needs it."))
                continue
            findings.append(ReleaseFinding(
                ERROR, "FILE_REFERENCE_MISSING", doc.rel, number,
                f"`{ref}` is referenced, but the package has no such file.",
                "Add the file at that path, fix the path, or list it as pending in the readiness record."))
    return findings


# Unfilled-template markers: an error. The capitalised tokens are matched
# case-sensitively so ordinary prose ("a to-do list", "xxx-large") is left alone.
_PLACEHOLDER_ERROR_RE = re.compile(
    r"\b(?:TODO|TBD|FIXME|XXX)\b"
    r"|(?i:lorem ipsum|\[(?:insert|placeholder)[^\]]*\]|<(?:insert|placeholder)[^>]*>)"
    r"|\{\{[^}]+\}\}"
)
# Disclosed gaps: a warning. They may be deliberate, but the build team should
# see every one before it starts.
_PLACEHOLDER_WARN_RE = re.compile(
    r"\b(?:placeholder|still to come|coming soon|to be confirmed|to be decided|pending)\b|\bTBC\b",
    re.I,
)


def _check_placeholders(docs: list[_Doc]) -> list[ReleaseFinding]:
    findings: list[ReleaseFinding] = []
    for doc in docs:
        if not doc.is_markdown:
            continue
        not_captured: list[int] = []
        pending: dict[str, list[tuple[int, str]]] = defaultdict(list)
        for number, line in _prose_lines(doc):
            if number <= doc.fm_end_line:
                continue
            if NOT_CAPTURED in line:
                not_captured.append(number)
                continue
            hard = _PLACEHOLDER_ERROR_RE.search(line)
            if hard:
                findings.append(ReleaseFinding(
                    ERROR, "PLACEHOLDER", doc.rel, number,
                    f"Unfilled placeholder `{hard.group(0)}`: {line.strip()[:120]}",
                    "Replace it with the real content, or move the open item to the readiness record "
                    "and say so here."))
                continue
            soft = _PLACEHOLDER_WARN_RE.search(line)
            if soft:
                pending[soft.group(0).lower()].append((number, line.strip()))
        # One finding per marker per file: a status table with forty "pending"
        # rows is one thing for the PM to review, not forty.
        for marker, hits in pending.items():
            more = f" (and {len(hits) - 1} more line(s) in this file)" if len(hits) > 1 else ""
            findings.append(ReleaseFinding(
                WARNING, "PENDING_MARKER", doc.rel, hits[0][0],
                f"Marked `{marker}`: {hits[0][1][:120]}{more}",
                "Confirm the build team can start without it, or deliver it before the release."))
        if not_captured:
            findings.append(ReleaseFinding(
                WARNING, "NOT_CAPTURED", doc.rel, not_captured[0],
                f"{len(not_captured)} section(s) say \"{NOT_CAPTURED}\" (the source artifact has no content for them).",
                "Fill the gap in the canonical stage artifact and rebuild, or confirm it is intentional."))
    return findings


_SOURCE_PAIR_RE = re.compile(r"(?P<doc>[A-Za-z0-9][\w.-]*?)\s+v(?P<ver>\d+(?:\.\d+)*)\b")
_VERSION_RE = re.compile(r"\bv(\d+(?:\.\d+)+)\b")


def _doc_version(doc: _Doc) -> str | None:
    version = doc.frontmatter.get("version")
    if version not in (None, ""):
        return str(version).lstrip("vV")
    seen = 0
    for line in doc.lines()[doc.fm_end_line:]:
        if not line.strip():
            continue
        match = _VERSION_RE.search(line)
        if match:
            return match.group(1)
        seen += 1
        if seen >= 5:
            break
    return None


def _version_key(version: str) -> tuple[int, ...]:
    """Numeric parts of a version for ordering; `draft` or `1.0-rc` must not crash."""
    return tuple(int(part) for part in re.findall(r"\d+", str(version))) or (0,)


def _check_hand_built_sources(docs: list[_Doc]) -> list[ReleaseFinding]:
    findings: list[ReleaseFinding] = []
    # Only documents some file names as its `source:` are versioned sources;
    # comparing every README.md's first-line version would be noise.
    cited_names = {
        match.group("doc").lower()
        for doc in docs if doc.is_markdown and isinstance(doc.frontmatter.get("source"), str)
        for match in _SOURCE_PAIR_RE.finditer(doc.frontmatter["source"])
    }
    versions: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for doc in docs:
        if doc.is_markdown and doc.path.stem.lower() in cited_names:
            version = _doc_version(doc)
            if version:
                versions[doc.path.stem.lower()][version].append(doc.rel)
    for name, by_version in sorted(versions.items()):
        if len(by_version) > 1:
            listing = "; ".join(f"v{v}: {', '.join(paths)}" for v, paths in sorted(by_version.items(), key=lambda kv: _version_key(kv[0])))
            first = sorted(p for paths in by_version.values() for p in paths)[0]
            findings.append(ReleaseFinding(
                ERROR, "SOURCE_VERSION_CONFLICT", first, 1,
                f"The package carries {name} at more than one version ({listing}).",
                "Ship one version: replace the older copies with the current one."))
    for doc in docs:
        source = doc.frontmatter.get("source")
        if not doc.is_markdown or not isinstance(source, str):
            continue
        for match in _SOURCE_PAIR_RE.finditer(source):
            name, cited = match.group("doc").lower(), match.group("ver")
            current = versions.get(name)
            if not current:
                findings.append(ReleaseFinding(
                    WARNING, "SOURCE_NOT_IN_PACKAGE", doc.rel, _fm_line(doc, "source"),
                    f"Built from {match.group('doc')} v{cited}, which is not in the package (or states no version).",
                    f"Ship {match.group('doc')} with the package, with its version on the first line or in `version:`."))
                continue
            latest = max(current, key=_version_key)
            if _version_key(cited) < _version_key(latest):
                findings.append(ReleaseFinding(
                    ERROR, "SOURCE_STALE", doc.rel, _fm_line(doc, "source"),
                    f"Built from {match.group('doc')} v{cited}; the package carries v{latest}.",
                    f"Re-check this file against {match.group('doc')} v{latest}, update it, and set `source:` "
                    f"to {match.group('doc')} v{latest}."))
    return findings


_GENERATED_FROM_RE = re.compile(r"^(?P<name>[\w.-]+\.md)@(?P<hash>[0-9a-f]{6,64})$")


def _check_pmos_sources(docs: list[_Doc], artifacts: dict[str, dict]) -> list[ReleaseFinding]:
    findings: list[ReleaseFinding] = []
    stale: dict[str, list[_Doc]] = defaultdict(list)
    unapproved: dict[str, list[_Doc]] = defaultdict(list)
    for doc in docs:
        for entry in doc.frontmatter.get("generated_from") or []:
            match = _GENERATED_FROM_RE.match(str(entry))
            if not match:
                continue
            art = artifacts.get(match.group("name"))
            if art is None:
                continue
            if art["hash"] and not art["hash"].startswith(match.group("hash")):
                stale[match.group("name")].append(doc)
            elif art["status"] not in ("approved", None):
                unapproved[match.group("name")].append(doc)
    for name, affected in sorted(stale.items()):
        findings.append(ReleaseFinding(
            ERROR, "SOURCE_STALE", affected[0].rel, _fm_line(affected[0], "generated_from"),
            f"{len(affected)} file(s) were generated from an older {name}; it has changed since.",
            "Rebuild the package with `/pm-handoff --package`."))
    for name, affected in sorted(unapproved.items()):
        status = artifacts[name]["status"]
        findings.append(ReleaseFinding(
            ERROR, "SOURCE_NOT_APPROVED", affected[0].rel, _fm_line(affected[0], "generated_from"),
            f"{len(affected)} file(s) come from {name}, which is now `{status}`, not approved.",
            f"Re-approve stage {name[:2]} (`/pm-approve {name[:2]}`), then rebuild the package."))
    return findings


def _check_ids(folder: Path, docs: list[_Doc], files: list[Path], project_ids: dict[str, str],
               ignore: set[str]) -> tuple[list[ReleaseFinding], int]:
    defined: dict[str, str] = {}
    for path in files:
        match = _FILENAME_ID_RE.match(path.name)
        if match:
            defined.setdefault(match.group(1), path.relative_to(folder).as_posix())
    for doc in docs:
        csv = doc.path.suffix.lower() == ".csv"
        for ident in declared_ids(doc.text, markdown=doc.is_markdown, csv=csv):
            defined.setdefault(ident, doc.rel)
    cited: dict[str, list[tuple[str, int, bool]]] = defaultdict(list)
    for doc in docs:
        if doc.is_markdown:
            for number, ident, example in _citations(doc):
                cited[ident].append((doc.rel, number, example))
    defined_prefixes = {id_prefix(i) for i in defined}
    series: dict[str, set[str]] = defaultdict(set)
    for ident in cited:
        series[id_prefix(ident)].add(ident)

    findings: list[ReleaseFinding] = []
    for ident in sorted(cited, key=lambda i: (id_prefix(i), _id_number(i).zfill(8), i)):
        if ident in defined:
            continue
        prefix = id_prefix(ident)
        if prefix in STANDARD_PREFIXES or prefix in ignore or ident in ignore:
            continue
        is_family = prefix in defined_prefixes or len(series[prefix]) >= SERIES_MIN
        if not is_family:
            continue
        if prefix not in defined_prefixes and len(_id_number(ident)) >= 4:
            continue
        where = cited[ident]
        rel, line, _ = where[0]
        spread = f" Cited {len(where)} times in {len({w[0] for w in where})} file(s)." if len(where) > 1 else ""
        longer = sorted(d for d in defined if d.endswith("-" + ident))
        if len(longer) == 1:
            findings.append(ReleaseFinding(
                WARNING, "ID_SHORT_FORM", rel, line,
                f"`{ident}` is not defined; it reads as a short form of `{longer[0]}`.{spread}",
                f"Write `{longer[0]}` so a reader (or an agent) cannot mistake it."))
            continue
        if len(longer) > 1:
            findings.append(ReleaseFinding(
                ERROR, "ID_AMBIGUOUS", rel, line,
                f"`{ident}` is not defined and could mean any of {', '.join(f'`{d}`' for d in longer)}.{spread}",
                "Write the full id each time."))
            continue
        if all(w[2] for w in where):
            findings.append(ReleaseFinding(
                WARNING, "ID_EXAMPLE_UNDEFINED", rel, line,
                f"`{ident}` appears only as an example and is not defined.{spread}",
                f"Put example values in code (`{ident}`) so they don't read as references."))
            continue
        if ident in project_ids:
            findings.append(ReleaseFinding(
                WARNING, "ID_NOT_IN_PACKAGE", rel, line,
                f"`{ident}` is defined in {project_ids[ident]}, but the package does not include that definition.{spread}",
                "Rebuild the package with `/pm-handoff --package` (current packages ship the full PRD/TRD "
                "under reference/)."))
            continue
        findings.append(ReleaseFinding(
            ERROR, "ID_UNDEFINED", rel, line,
            f"`{ident}` is cited but nothing in the package defines it.{spread}",
            f"Add its definition to the package (a heading, a bold `**{ident}**` line, or a table row "
            f"starting with it), or stop citing it."))
    return findings, len(defined)


def _check_coverage(docs: list[_Doc], project_root: Path, artifacts: dict[str, dict]) -> list[ReleaseFinding]:
    """Backlog #53 option (a): an exported story/requirement with no test case.

    Only once the QA plan is approved: a design package is legitimately built
    from a stage-04 brief before stage 06 exists, and blocking it then would
    stop the pipeline in its normal order. Before that, one warning says
    coverage was not checked.
    """
    exported = [d for d in docs if d.frontmatter.get("story_id") or d.frontmatter.get("requirement_id")]
    if not exported:
        return []
    qa = artifacts.get("06-qa-plan.md")
    if not qa or qa.get("status") != "approved":
        state = qa.get("status") if qa else "missing"
        return [ReleaseFinding(
            WARNING, "COVERAGE_NOT_CHECKED", exported[0].rel, 1,
            f"Test coverage was not checked: the QA plan (stage 06) is {state}, not approved.",
            "Approve the QA plan before the build handoff; the release check then requires a "
            "covering TC-### for every exported story and requirement.")]
    try:
        import traceability
        from delivery_map import build_prd_delivery_map
        index = traceability.build_index(project_root)
        prd_text = (project_root / "03-prd.md").read_text(encoding="utf-8").replace(chr(13) + chr(10), chr(10))
        _, prd_end = _split_frontmatter(prd_text)
        delivery = build_prd_delivery_map(chr(10).join(prd_text.splitlines()[prd_end:]))
    except Exception:
        return []
    requirements = index.get("requirements") or {}
    test_cases = index.get("test_cases") or {}

    def covering(ident: str) -> set[str]:
        # The same resolution the package uses for a story's "Covering test
        # cases": the story's own id plus every requirement it owns, in either
        # direction (a TC that covers FR-001 covers the story that owns FR-001).
        found: set[str] = set()
        for ref in delivery.story_requirements.get(ident, [ident]):
            entry = requirements.get(ref)
            if entry:
                found.update(entry.get("test_cases") or [])
            else:
                found.update(tc for tc, rec in test_cases.items() if ref in (rec.get("requirements") or []))
        return found

    findings: list[ReleaseFinding] = []
    for doc in docs:
        ident = doc.frontmatter.get("story_id") or doc.frontmatter.get("requirement_id")
        if not ident or (ident not in requirements and ident not in delivery.story_requirements):
            continue
        if not covering(ident):
            findings.append(ReleaseFinding(
                ERROR, "REQUIREMENT_UNTESTED", doc.rel, 1,
                f"{ident} is exported, but no test case in 06-qa-plan.md covers it.",
                f"Add a `TC-###` that cites {ident} to the QA plan, re-approve stage 06, and rebuild."))
    return findings


_READINESS_CODES = {
    "eval_sets": ("READINESS_EVAL_SET_NOT_READY", "is not starter-ready",
                  "Get the starter set reviewed and mark it `starter_ready`, or move `due` with the PM's agreement."),
    "test_inputs": ("READINESS_INPUT_MISSING", "has not been received",
                    "Get the file from its supplier and mark it `received` (or `not_needed`)."),
    "open_decisions": ("READINESS_DECISION_OVERDUE", "is still open and blocking",
                       "Decide it and record the outcome in `decision`, or agree a later `decide_by`."),
}


def _check_readiness(folder: Path, project_root: Path | None) -> tuple[dict | None, list[ReleaseFinding], dict[str, str]]:
    """Backlog #74: block a release on owed items that are overdue.

    Reads `readiness.yaml` from the folder (a package carries its copy; a
    hand-built folder may have one) or else from the owning project. Returns
    the data, findings, and the files still owed (path -> TI id), which turn a
    missing referenced file from an error into a warning.
    """
    import readiness

    path = folder / readiness.READINESS_FILE
    label = readiness.READINESS_FILE
    if not path.is_file() and project_root is not None:
        path = Path(project_root) / readiness.READINESS_FILE
        label = f"{readiness.READINESS_FILE} (project)"
    data, problem = readiness.load(path)
    if problem:
        return None, [ReleaseFinding(ERROR, "READINESS_INVALID", label, None, problem.message, problem.fix)], {}
    if data is None:
        return None, [], {}
    findings = [
        ReleaseFinding(ERROR, "READINESS_INVALID", label, None, f"{issue.item or 'file'}: {issue.message}", issue.fix)
        for issue in readiness.validate(data) if issue.severity == "error"
    ]
    for item in readiness.overdue(data):
        code, state, fix = _READINESS_CODES[item["section"]]
        findings.append(ReleaseFinding(
            ERROR, code, label, None,
            f"{item['id']} ({item['summary']}) {state}; it was due by {item['due']}.", fix))
    owed = {
        str(row["file"]).replace("\\", "/").removeprefix("./"): str(row.get("id"))
        for row in data.get("test_inputs") or []
        if isinstance(row, dict) and row.get("file") and row.get("status") not in readiness.INPUT_DONE
    }
    return data, findings, owed


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = {ERROR: 0, WARNING: 1}


def check_release(path: Path | str, *, project_root: Path | None = None,
                  ignore_ids: Iterable[str] = ()) -> ReleaseReport:
    """Run every release check on a handoff folder (or a `.zip` of one)."""
    path = Path(path)
    if path.is_file() and path.suffix.lower() == ".zip":
        with tempfile.TemporaryDirectory(prefix="pm-os-release-check-") as tmp:
            extract_zip(path, Path(tmp))
            report = check_release(Path(tmp), project_root=project_root, ignore_ids=ignore_ids)
            report.folder = path  # findings are already relative to the archive root
            return report
    if not path.is_dir():
        raise FileNotFoundError(f"{path} is not a folder or a .zip file")
    folder = path.resolve()
    files, docs = _inventory(folder)
    kind = "pm-os" if _is_pmos_package(folder, docs) else "hand-built"
    if project_root is None and kind == "pm-os":
        project_root = find_project_root(folder)
    artifacts = _project_artifacts(project_root) if project_root and kind == "pm-os" else {}
    project_ids = {ident: name for name, art in artifacts.items() for ident in art["ids"]}

    story_findings, story_count = _check_stories(docs)
    link_findings, link_count = _check_links(folder, docs)
    id_findings, id_count = _check_ids(folder, docs, files, project_ids, {i.upper() for i in ignore_ids})
    findings = story_findings + link_findings + id_findings
    readiness_data, readiness_findings, owed = _check_readiness(folder, project_root if kind == "pm-os" else None)
    findings += readiness_findings
    findings += _check_referenced_files(folder, docs, files, owed)
    findings += _check_placeholders(docs)
    if kind == "pm-os":
        findings += _check_pmos_sources(docs, artifacts)
        if project_root:
            findings += _check_coverage(docs, project_root, artifacts)
    else:
        findings += _check_hand_built_sources(docs)
    findings.sort(key=lambda f: (_SEVERITY_ORDER.get(f.severity, 9), f.code, f.path, f.line or 0))
    report = ReleaseReport(folder, kind, project_root if kind == "pm-os" else None, findings)
    report.stats = {"files": len(files), "stories": story_count, "ids_declared": id_count, "links": link_count}
    return report


def extract_zip(archive: Path, dest: Path) -> None:
    """Extract a package zip, refusing members that would land outside ``dest``."""
    dest = dest.resolve()
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            target = (dest / member.filename).resolve()
            if target != dest and dest not in target.parents:
                raise ValueError(f"{archive.name}: member {member.filename!r} escapes the archive")
        zf.extractall(dest)


# ---------------------------------------------------------------------------
# Export gate
# ---------------------------------------------------------------------------

def summarize_codes(findings: Iterable[ReleaseFinding]) -> str:
    counts: dict[str, int] = defaultdict(int)
    for f in findings:
        counts[f.code] += 1
    return ", ".join(f"{code} ({n})" for code, n in sorted(counts.items()))


def guard_release(root: Path, reports: list[tuple[str, ReleaseReport]], *, allow: bool,
                  surface: str, stream=None, max_findings: int = 40) -> None:
    """Block an export on release-check errors unless ``allow`` (backlog #72).

    ``reports`` pairs a display label (`handoff/dev/`) with its report. Errors
    print in full (up to ``max_findings`` per folder) and warnings as a count per
    code. Blocked: logs `release_check_blocked` and raises SystemExit(1) before
    the caller publishes anything. Allowed (`--allow-release-errors`): logs
    `release_check_overridden` naming the overridden codes and returns.
    """
    import sys

    stream = stream or sys.stderr
    errors = [f for _, r in reports for f in r.errors]
    warnings = [f for _, r in reports for f in r.warnings]
    for label, report in reports:
        if report.errors:
            blocking = ReleaseReport(report.folder, report.kind, report.project_root, report.errors, report.stats)
            print(format_report(blocking, label=label, max_findings=max_findings), file=stream)
            print("", file=stream)
        if report.warnings:
            print(f"Release check warnings in {label}: {summarize_codes(report.warnings)} "
                  f"(see them with `/pm-check --release {label}`).", file=stream)
    if not errors:
        if not warnings:
            print("Release check: no findings.", file=stream)
        return
    codes = sorted({f.code for f in errors})
    payload = {
        "surface": surface,
        "folders": [label for label, _ in reports],
        "errors": len(errors),
        "warnings": len(warnings),
        "codes": codes,
    }
    event = "release_check_overridden" if allow else "release_check_blocked"
    try:
        from telemetry import log
        log(event, root, None, payload)
    except Exception as e:  # telemetry must never break the workflow
        print(f"Warning: telemetry logging failed: {e}", file=stream)
    if allow:
        print(f"--allow-release-errors given: exporting despite {len(errors)} release-check "
              f"error(s) ({', '.join(codes)}). Logged as release_check_overridden.", file=stream)
        return
    raise SystemExit(
        f"Export blocked by the release check — nothing was written. {len(errors)} error(s): "
        f"{', '.join(codes)}. Fix each one at the location shown (usually in the canonical "
        "stage artifact, then re-approve), and re-run. To export anyway, re-run with "
        "--allow-release-errors (logged)."
    )
