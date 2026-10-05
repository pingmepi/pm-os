"""Pattern-based secret detection + redaction (GH #63 PMOS-001, backlog #40).

Context import must not persist a live credential into `.history/` (which the
project's local git repo commits), and a handoff export must not ship one to a
tracker or another team. This module is the single, pure-stdlib detector both
paths share:

  scan_text(text)      -> [Finding]        what looks like a secret, and where
  redact_text(text)    -> (text, [Finding]) same, with each value replaced by
                                            `[REDACTED:<kind>]`
  scan_file / scan_paths                    file/directory helpers (skip binary,
                                            skip `.git/`)
  format_findings(findings)                 `path:line  kind` lines for output
  guard_export(...)                         block-or-allow gate for an export

KEY INVARIANT: a Finding never carries the matched value. It holds the line,
the kind, and a masked preview (first 4 chars + `…`) — and `format_findings`
does not even print the preview. Nothing this module returns or prints can
re-leak the secret it found.

Precision over recall: known key formats are matched by their documented
prefixes/shapes. The one heuristic rule (`generic_assignment`,
`password = "…"` style) requires a long, mixed, high-entropy value and skips
obvious placeholders, so ordinary PRD prose ("the API key is rotated
quarterly") never trips it.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

# Ordered most-specific first: when two rules overlap the same span, the earlier
# one wins (e.g. `sk-ant-…` is an Anthropic key, never re-reported as OpenAI).
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # A PEM private key: the whole block when an END line follows, else the
    # BEGIN header alone (never "the rest of the document").
    ("private_key_block", re.compile(
        r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----"
        r"(?:[\s\S]*?-----END (?:[A-Z0-9]+ )*PRIVATE KEY-----)?")),
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("aws_access_key_id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github_token", re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{22,255})")),
    ("slack_token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}")),
    ("slack_webhook", re.compile(
        r"https://hooks\.slack\.com/services/T[A-Za-z0-9_]+/B[A-Za-z0-9_]+/[A-Za-z0-9_]+")),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}")),
    # The lookaheads demand a digit and an uppercase letter inside the token, so a
    # hyphenated identifier like `sk-learn-compatible-pipeline` is not a key.
    ("openai_key", re.compile(
        r"\bsk-(?!ant-)(?=[A-Za-z0-9_\-]*[0-9])(?=[A-Za-z0-9_\-]*[A-Z])"
        r"(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{20,}")),
    ("stripe_key", re.compile(r"\b(?:sk|rk)_(?:live|test)_[0-9A-Za-z]{16,}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")),
]

# `<name> = "<value>"` / `<name>: <value>` where the name says "credential". Only
# the value (group "value") is reported/redacted, so the line stays readable. The
# lookbehind (not `\b`) lets `MY_API_KEY=` match: `_` is a word character.
_GENERIC_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:password|passwd|pwd|secret|client[_-]?secret|api[_-]?key|apikey|"
    r"access[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|token|private[_-]?key)"
    r"[\"']?\s*[:=]\s*[\"']?(?P<value>[^\s\"'`,;)\]}]{16,})"
)

# Values that are obviously not real credentials — template slots, env lookups,
# documentation stand-ins. Checked case-insensitively against the value.
_PLACEHOLDER_MARKERS = (
    "xxx", "***", "...", "your", "example", "sample", "changeme", "change_me",
    "placeholder", "dummy", "redacted", "insert", "replace", "todo", "fixme",
    "os.environ", "process.env", "getenv", "env(", "env[", "secrets.", "vault:",
)
_PLACEHOLDER_PREFIXES = ("<", "${", "{{", "%(", "$(", "[", "{")

_MIN_GENERIC_ENTROPY = 3.0  # bits/char; real keys sit ~4+, English words ~2.5-3


@dataclass(frozen=True)
class Finding:
    """One likely secret. Deliberately has no field for the matched value."""

    line: int | None          # 1-based; None when the source has no meaningful lines (binary)
    kind: str
    preview: str              # masked: first 4 chars + "…" — never the full value
    path: str | None = None   # set by scan_file / guard_export


def _entropy(value: str) -> float:
    counts: dict[str, int] = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(value)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _looks_like_secret_value(value: str) -> bool:
    low = value.lower()
    if value.startswith(_PLACEHOLDER_PREFIXES) or any(m in low for m in _PLACEHOLDER_MARKERS):
        return False
    if not (re.search(r"[A-Za-z]", value) and re.search(r"\d", value)):
        return False  # a real credential mixes letters and digits; prose/identifiers rarely do
    if re.fullmatch(r"https?://\S+", value):
        return False  # a URL is a reference, not a credential
    return _entropy(value) >= _MIN_GENERIC_ENTROPY


def _mask(value: str) -> str:
    return value[:4] + "…"


def _matches(text: str) -> list[tuple[int, int, str]]:
    """Non-overlapping (start, end, kind) spans, sorted by start."""
    spans: list[tuple[int, int, str]] = []

    def _free(start: int, end: int) -> bool:
        return all(end <= s or start >= e for s, e, _k in spans)

    for kind, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            if _free(m.start(), m.end()):
                spans.append((m.start(), m.end(), kind))
    for m in _GENERIC_RE.finditer(text):
        start, end = m.span("value")
        if _free(start, end) and _looks_like_secret_value(m.group("value")):
            spans.append((start, end, "generic_assignment"))
    return sorted(spans)


def _finding(text: str, start: int, end: int, kind: str, path: str | None = None) -> Finding:
    return Finding(line=text.count("\n", 0, start) + 1, kind=kind,
                   preview=_mask(text[start:end]), path=path)


def scan_text(text: str) -> list[Finding]:
    """Every likely secret in ``text``, in document order."""
    return [_finding(text, s, e, k) for s, e, k in _matches(text)]


def redact_text(text: str) -> tuple[str, list[Finding]]:
    """``text`` with each secret replaced by ``[REDACTED:<kind>]``, plus the findings.

    Line numbers in the findings refer to the ORIGINAL text. A redacted private-key
    block collapses to one line, so later line numbers in the redacted copy can shift.
    """
    spans = _matches(text)
    findings = [_finding(text, s, e, k) for s, e, k in spans]
    out, cursor = [], 0
    for start, end, kind in spans:
        out.append(text[cursor:start])
        out.append(f"[REDACTED:{kind}]")
        cursor = end
    out.append(text[cursor:])
    return "".join(out), findings


# --- files ---------------------------------------------------------------------

SKIP_DIRS = {".git", "__pycache__", "node_modules"}


def is_binary(data: bytes) -> bool:
    """Cheap binary sniff: a NUL byte in the first 8 KiB."""
    return b"\x00" in data[:8192]


def scan_file(path: Path, display: str | None = None) -> list[Finding]:
    """Findings for one text file (binary files return []). ``display`` is the path
    string reported in each finding (defaults to ``str(path)``)."""
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError:
        return []
    if is_binary(data):
        return []
    label = display if display is not None else str(path)
    text = data.decode("utf-8", errors="replace")
    return [Finding(f.line, f.kind, f.preview, label) for f in scan_text(text)]


def scan_paths(paths, root: Path | None = None) -> list[Finding]:
    """Findings across files and directories (recursive; skips `.git/` etc. and binary
    files). With ``root``, reported paths are relative to it where possible."""
    findings: list[Finding] = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files = sorted(f for f in p.rglob("*")
                           if f.is_file() and not (set(f.relative_to(p).parts) & SKIP_DIRS))
        elif p.is_file():
            files = [p]
        else:
            continue
        for f in files:
            findings.extend(scan_file(f, _display(f, root)))
    return findings


def _display(path: Path, root: Path | None) -> str:
    if root is not None:
        try:
            return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
        except ValueError:
            pass
    return str(path)


def format_findings(findings, indent: str = "  ") -> str:
    """One `path:line  kind` line per finding — NO value, NO preview."""
    lines = []
    for f in findings:
        where = f.path or "<text>"
        if f.line is not None:
            where = f"{where}:{f.line}"
        lines.append(f"{indent}{where}  {f.kind}")
    return "\n".join(lines)


def summarize(findings) -> dict:
    """Telemetry-safe summary: count + sorted distinct kinds (never values)."""
    return {"count": len(findings), "kinds": sorted({f.kind for f in findings})}


# --- export gate -----------------------------------------------------------------

def guard_export(root: Path, paths, *, allow: bool, export: str, stream=None) -> list[Finding]:
    """Scan the files an export is about to include; block unless ``allow``.

    Blocked: prints the findings (path:line kind only) + the fix to ``stream``
    (stderr by default), logs `secrets_blocked`, and raises SystemExit(1) BEFORE the
    caller writes anything. Allowed (``--allow-secrets``): prints a warning, logs
    `secrets_allowed`, and returns. No findings: silent, returns []. Telemetry
    carries only the export name, count, kinds, and file names.
    """
    import sys

    stream = stream or sys.stderr
    findings = scan_paths(paths, root)
    if not findings:
        return findings
    payload = {"surface": export, **summarize(findings),
               "files": sorted({f.path for f in findings if f.path})}
    print(f"Secret scan: {len(findings)} likely secret(s) in the content this export "
          f"would include (values not shown):", file=stream)
    print(format_findings(findings), file=stream)
    event = "secrets_allowed" if allow else "secrets_blocked"
    try:
        from telemetry import log
        log(event, root, None, payload)
    except Exception as e:  # telemetry must never break the workflow
        print(f"Warning: telemetry logging failed: {e}", file=stream)
    if allow:
        print("--allow-secrets given: exporting anyway (logged). Rotate the exposed "
              "credential(s) at their source.", file=stream)
        return findings
    raise SystemExit(
        "Export blocked — nothing was written. Remove the value(s) from the named "
        "artifact(s), rotate the credential at its source (anything already committed "
        "or shared is exposed), re-approve the stage, then re-run. To export anyway, "
        "re-run with --allow-secrets (logged)."
    )
