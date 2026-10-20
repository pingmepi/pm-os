"""Unit tests for lib/secret_scan.py — the shared secret detector behind context import
and handoff export (GH #63 PMOS-001, backlog #40).

Every fake credential here is assembled at runtime by concatenation so this file never
itself looks like a committed secret to a scanner. See docs/guides/testing.md §5 (T1).
"""
import pytest

import secret_scan

pytestmark = pytest.mark.unit

# Body characters for fake keys: long, mixed, non-repeating enough to look real.
_BODY = "Q7xLp2Rk9VbN4mTz8WcY3hJd6FgS1aE5uI0oKqZ"


def _fakes():
    """kind -> a fake value of that shape (built at runtime, never a real credential)."""
    return {
        "google_api_key": "AI" + "za" + _BODY[:35],
        "aws_access_key_id": "AK" + "IA" + "QWERTYUIOP234567",
        "github_token": "gh" + "p_" + _BODY[:36],
        "slack_token": "xo" + "xb-" + "1234567890-" + _BODY[:20],
        "slack_webhook": "https://hooks.slack.com/services/" + "T0" + "ABC123/B0DEF456/" + _BODY[:24],
        "anthropic_key": "sk-" + "ant-" + "api03-" + _BODY[:30],
        "openai_key": "sk-" + "proj-" + _BODY[:32],
        "stripe_key": "sk" + "_live_" + _BODY[:24],
        "jwt": "ey" + "JhbGciOiJIUzI1NiJ9" + "." + "ey" + "JzdWIiOiIxMjM0NTYifQ" + "." + _BODY[:24],
    }


@pytest.mark.parametrize("kind", sorted(_fakes()))
def test_each_known_format_is_detected(kind):
    """Every high-precision pattern fires on a value of its documented shape, with the
    right kind and line number."""
    value = _fakes()[kind]
    findings = secret_scan.scan_text(f"Intro line.\nConfig uses {value} here.\n")
    assert [(f.kind, f.line) for f in findings] == [(kind, 2)]


def test_private_key_block_detected_and_fully_redacted():
    """A PEM private-key block is one finding, and redaction removes the whole block
    (header, base64 body, and footer), not just the header line."""
    begin = "-----BEGIN " + "RSA PRIVATE KEY-----"
    end = "-----END " + "RSA PRIVATE KEY-----"
    text = f"Notes\n{begin}\nMIIEow{_BODY}\n{_BODY}\n{end}\nAfter.\n"
    redacted, findings = secret_scan.redact_text(text)
    assert [(f.kind, f.line) for f in findings] == [("private_key_block", 2)]
    assert "MIIEow" not in redacted and "PRIVATE KEY" not in redacted
    assert "[REDACTED:private_key_block]" in redacted and "After." in redacted


def test_generic_assignment_detects_high_entropy_value():
    """`password = "<long mixed value>"` style assignments are caught, including an
    env-style `MY_API_KEY=` name; only the value is redacted, the name stays readable."""
    pw = "Zx9" + "Qw7Lm2Np8Rt4Vb"
    text = f'db_password = "{pw}"\nMY_API_KEY={_BODY[:24]}\n'
    redacted, findings = secret_scan.redact_text(text)
    assert [(f.kind, f.line) for f in findings] == [
        ("generic_assignment", 1), ("generic_assignment", 2)]
    assert pw not in redacted and _BODY[:24] not in redacted
    assert 'db_password = "[REDACTED:generic_assignment]"' in redacted
    assert "MY_API_KEY=[REDACTED:generic_assignment]" in redacted


@pytest.mark.parametrize("line", [
    'api_key = "<your-api-key-here>"',
    "API_KEY=${GOOGLE_API_KEY}",
    'password = "changeme-changeme"',
    "token: xxxxxxxxxxxxxxxxxxxxxxxx",
    'secret = os.environ["APP_SECRET_VALUE"]',
    "api_key = process.env.PAYMENTS_KEY_2024",
    "password: {{ vault_db_password_2024 }}",
    "token = REPLACE_WITH_REAL_TOKEN_123",
    "api_key = https://docs.example.org/keys/v2",
])
def test_placeholders_do_not_trigger(line):
    """Template slots, env lookups and documentation stand-ins are not secrets."""
    assert secret_scan.scan_text(line) == []


def test_ordinary_prd_prose_does_not_trigger():
    """Normal PRD/brief prose that talks *about* keys, tokens and passwords — plus
    stable ids, URLs and tables — produces no findings."""
    prose = (
        "## Functional Requirements\n"
        "- **FR-001 (must):** The API key is rotated every 90 days by the platform team.\n"
        "- **FR-002 (should):** Password: must be at least 12 characters, with one digit.\n"
        "- **FR-003 (could):** Token refresh happens silently; see US-004 and TSK-012.\n"
        "Secret management is out of scope for MVP. Auth token lifetime: 15 minutes.\n"
        "Scoring wraps an sk-learn-compatible-pipeline-wrapper model.\n"
        "| Metric | Target |\n|---|---|\n| p95 latency | 300ms |\n"
        "Reference: https://example.com/docs/authentication-and-api-keys\n"
        "Skip AIza-like prefixes in prose such as 'AIza keys' — too short to be one.\n"
    )
    assert secret_scan.scan_text(prose) == []


def test_findings_and_formatting_never_contain_the_value():
    """KEY INVARIANT: neither a Finding (repr included) nor format_findings output
    carries the matched value — at most a 4-char masked preview, which the formatter
    omits entirely. Output is `path:line  kind` only."""
    value = _fakes()["google_api_key"]
    findings = secret_scan.scan_text(f"a\nb\nkey {value}\n")
    for f in findings:
        assert value not in repr(f)
        assert f.preview == value[:4] + "…"
    findings = [secret_scan.Finding(f.line, f.kind, f.preview, "notes.md") for f in findings]
    out = secret_scan.format_findings(findings)
    assert out == "  notes.md:3  google_api_key"
    assert value[4:] not in out and secret_scan.summarize(findings) == {
        "count": 1, "kinds": ["google_api_key"]}


def test_redact_text_leaves_clean_text_untouched():
    """Text with no secrets round-trips byte-for-byte (no gratuitous rewrites)."""
    text = "# Brief\r\nNo secrets here.\r\n"
    assert secret_scan.redact_text(text) == (text, [])


def test_scan_paths_walks_dirs_skips_git_and_binary(tmp_path):
    """scan_paths recurses into directories, reports root-relative path:line, and
    skips `.git/` and binary (NUL-bearing) files."""
    value = _fakes()["aws_access_key_id"]
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "notes.md").write_text(f"x\n{value}\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text(value, encoding="utf-8")
    (tmp_path / "blob.bin").write_bytes(b"\x00\x01" + value.encode())
    findings = secret_scan.scan_paths([tmp_path], root=tmp_path)
    assert [(f.path, f.line, f.kind) for f in findings] == [
        ("docs/notes.md", 2, "aws_access_key_id")]


def test_guard_export_blocks_then_allows(pmos, tmp_path, capsys):
    """guard_export raises SystemExit (blocked) on a hit unless allow=True, prints only
    path:line kind (never the value), and returns [] silently for clean input. Telemetry
    failure (no project here) only warns."""
    value = _fakes()["github_token"]
    clean = tmp_path / "01-brief.md"
    clean.write_text("Clean.\n", encoding="utf-8")
    assert secret_scan.guard_export(tmp_path, [clean], allow=False, export="t") == []

    dirty = tmp_path / "03-prd.md"
    dirty.write_text(f"## PRD\nToken {value}\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        secret_scan.guard_export(tmp_path, [clean, dirty], allow=False, export="t")
    assert "--allow-secrets" in str(exc.value)
    err = capsys.readouterr().err
    assert "03-prd.md:2  github_token" in err and value not in err

    found = secret_scan.guard_export(tmp_path, [dirty], allow=True, export="t")
    assert len(found) == 1
    assert value not in capsys.readouterr().err
