"""GH #63 PMOS-001 (backlog #40) — secrets never persist through context import or leave
through a handoff export.

`pm_context_import.py register` redacts likely secrets from text snapshots under
`.history/` (which the project's git repo commits) and refuses a non-redactable source
(docx/pdf/...) holding one unless `--allow-secrets`. `pm_share.py` (raw + `--package`)
and `pm_handoff.py` (`plan` + `export`) refuse to write anything while an exported
artifact holds one, unless `--allow-secrets`. In every path the output names file:line
and kind only — the value never appears on stdout/stderr or in telemetry.

Fake keys are assembled at runtime so this file never looks like a committed secret.
See docs/guides/testing.md §5 (Secret scanning)."""
import json
import zipfile

import pytest
import yaml

from helpers import run_script, make_draft, read_events

pytestmark = pytest.mark.integration

FAKE_GOOGLE_KEY = "AI" + "za" + "Sy" + "Q7xLp2Rk9VbN4mTz8WcY3hJd6FgS1aE5u"  # AIza + 35 chars

_PRD_BODY = """## Product Epics
### EPIC-001 — Approved content access
**Outcome:** Reps can use only approved content.
**Scope:** Approved-content visibility.
**Success signal:** Reps see approved assets.
## User Stories with Acceptance Criteria
### US-001 — Rep sees only approved content
Epic: EPIC-001
Priority: Must
Implements FR-001.
## Functional Requirements
- **FR-001 (must):** Surface only MLR-approved assets.
  - Epic: EPIC-001
"""


def _ctx_proj(pmos, new_project, slug):
    proj = new_project(slug, "Existing context to import")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    return proj


def _sources(proj):
    return yaml.safe_load((proj / ".sources.yaml").read_text(encoding="utf-8")) or []


def _telemetry_text(proj):
    return (proj / "telemetry.jsonl").read_text(encoding="utf-8")


def _approved_prd(pmos, new_project, slug, *, leak: bool):
    proj = new_project(slug, "A problem")
    body = _PRD_BODY + (f"\nIntegration note: maps key {FAKE_GOOGLE_KEY} for geocoding.\n" if leak else "")
    make_draft(proj, "03", body=body)
    res = run_script(pmos, "pm_approve.py", "03", cwd=proj)
    assert res.returncode == 0, res.stderr
    return proj


def test_register_redacts_secret_in_text_snapshot(pmos, new_project):
    """ACCEPTANCE: registering a text source containing a Google API key persists a
    REDACTED snapshot, records `secrets_redacted`/`secret_kinds` in .sources.yaml, warns
    with filename:line + kind, logs `secrets_redacted` — and the key appears in none of
    the snapshot, stdout/stderr, .sources.yaml, or telemetry."""
    proj = _ctx_proj(pmos, new_project, "sec-text")
    (proj / "notes.md").write_text(
        f"# Integration notes\nUse the maps API.\nkey: {FAKE_GOOGLE_KEY}\nEnd.\n", encoding="utf-8")
    res = run_script(pmos, "pm_context_import.py", "register", "notes.md", cwd=proj)
    assert res.returncode == 0, res.stderr
    out = res.stdout + res.stderr
    assert FAKE_GOOGLE_KEY not in out
    assert "notes.md:3  google_api_key" in out
    assert "rotate" in out.lower()

    entry = _sources(proj)[-1]
    assert entry["secrets_redacted"] == 1 and entry["secret_kinds"] == ["google_api_key"]
    snapshot = (proj / entry["snapshot"]).read_text(encoding="utf-8")
    assert FAKE_GOOGLE_KEY not in snapshot
    assert "key: [REDACTED:google_api_key]" in snapshot and "Use the maps API." in snapshot

    events = [e for e in read_events(proj) if e["event_type"] == "secrets_redacted"]
    assert events and events[-1]["payload"]["count"] == 1
    assert events[-1]["payload"]["kinds"] == ["google_api_key"]
    assert FAKE_GOOGLE_KEY not in _telemetry_text(proj)
    assert FAKE_GOOGLE_KEY not in (proj / ".sources.yaml").read_text(encoding="utf-8")


def test_register_clean_source_is_byte_identical(pmos, new_project):
    """A source with no secrets is preserved byte-for-byte and gets no secret fields —
    the scan never rewrites clean material."""
    proj = _ctx_proj(pmos, new_project, "sec-clean")
    raw = b"# Research\r\nThe API key is rotated quarterly.\r\n"
    (proj / "research.md").write_bytes(raw)
    res = run_script(pmos, "pm_context_import.py", "register", "research.md", cwd=proj)
    assert res.returncode == 0, res.stderr
    entry = _sources(proj)[-1]
    assert "secrets_redacted" not in entry and "secret_kinds" not in entry
    assert (proj / entry["snapshot"]).read_bytes() == raw


def _docx_with(path, text):
    """A minimal OOXML-shaped zip whose document part carries ``text`` split across runs."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        half = len(text) // 2
        zf.writestr("word/document.xml",
                    f"<w:document><w:body><w:p><w:r><w:t>{text[:half]}</w:t></w:r>"
                    f"<w:r><w:t>{text[half:]}</w:t></w:r></w:p></w:body></w:document>")


def test_register_blocks_unredactable_source_with_secret(pmos, new_project):
    """A .docx holding a key can't be redacted in place, so register refuses it (non-zero,
    nothing snapshotted or registered, `secrets_blocked` logged) and names the file + kind
    only. A folder import skips just that file and still registers the clean ones."""
    proj = _ctx_proj(pmos, new_project, "sec-docx")
    _docx_with(proj / "spec.docx", f"Maps key {FAKE_GOOGLE_KEY} here")
    res = run_script(pmos, "pm_context_import.py", "register", "spec.docx", cwd=proj)
    assert res.returncode != 0
    out = res.stdout + res.stderr
    assert "spec.docx  google_api_key" in out and FAKE_GOOGLE_KEY not in out
    assert not (proj / ".history").exists() or not any(
        p.name.endswith("spec.docx") for p in (proj / ".history").iterdir())
    assert any(e["event_type"] == "secrets_blocked" for e in read_events(proj))

    folder = proj / "inbox"
    folder.mkdir()
    _docx_with(folder / "spec.docx", f"Maps key {FAKE_GOOGLE_KEY} here")
    (folder / "brief.md").write_text("# Brief\nClean.\n", encoding="utf-8")
    res = run_script(pmos, "pm_context_import.py", "register", "inbox", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert "(blocked) spec.docx" in res.stdout and FAKE_GOOGLE_KEY not in res.stdout
    assert [s["uri"].replace("\\", "/").rsplit("/", 1)[-1] for s in _sources(proj)] == ["brief.md"]
    assert FAKE_GOOGLE_KEY not in _telemetry_text(proj)


def test_register_allow_secrets_keeps_unredactable_source(pmos, new_project):
    """`--allow-secrets` preserves the .docx verbatim, records `secrets_unredacted`, and
    logs `secrets_allowed` — still without printing the value."""
    proj = _ctx_proj(pmos, new_project, "sec-allow")
    _docx_with(proj / "spec.docx", f"Maps key {FAKE_GOOGLE_KEY} here")
    res = run_script(pmos, "pm_context_import.py", "register", "spec.docx", "--allow-secrets", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert FAKE_GOOGLE_KEY not in res.stdout + res.stderr
    entry = _sources(proj)[-1]
    assert entry["secrets_unredacted"] == 1 and entry["secret_kinds"] == ["google_api_key"]
    assert any(e["event_type"] == "secrets_allowed" for e in read_events(proj))
    assert FAKE_GOOGLE_KEY not in _telemetry_text(proj)


def test_package_blocked_by_secret_then_allowed(pmos, new_project):
    """ACCEPTANCE (handoff): `--package` refuses while the approved PRD holds a key —
    non-zero, NO handoff/ written, `03-prd.md:<line>  google_api_key` reported, value
    never echoed, `secrets_blocked` logged. `--allow-secrets` builds it and logs
    `secrets_allowed`."""
    proj = _approved_prd(pmos, new_project, "sec-pkg", leak=True)
    res = run_script(pmos, "pm_share.py", "--package", cwd=proj)
    assert res.returncode != 0
    out = res.stdout + res.stderr
    assert "03-prd.md:" in out and "google_api_key" in out and "--allow-secrets" in out
    assert FAKE_GOOGLE_KEY not in out
    assert not (proj / "handoff").exists()
    assert any(e["event_type"] == "secrets_blocked" for e in read_events(proj))

    res = run_script(pmos, "pm_share.py", "--package", "--allow-secrets", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert FAKE_GOOGLE_KEY not in res.stdout + res.stderr
    assert (proj / "handoff" / "dev" / "README.md").exists()
    allowed = [e for e in read_events(proj) if e["event_type"] == "secrets_allowed"]
    assert allowed and allowed[-1]["payload"]["surface"] == "handoff_package"
    assert FAKE_GOOGLE_KEY not in _telemetry_text(proj)


def test_raw_export_blocked_by_secret(pmos, new_project):
    """Raw mode prints artifact bodies verbatim, so it is gated too: blocked (no body on
    stdout, no --output file) until `--allow-secrets`."""
    proj = _approved_prd(pmos, new_project, "sec-raw", leak=True)
    res = run_script(pmos, "pm_share.py", "03", "--output", "out.md", cwd=proj)
    assert res.returncode != 0
    assert FAKE_GOOGLE_KEY not in res.stdout + res.stderr
    assert not (proj / "out.md").exists()
    res = run_script(pmos, "pm_share.py", "03", "--output", "out.md", "--allow-secrets", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert (proj / "out.md").exists()


def test_jira_plan_and_csv_blocked_by_secret_then_allowed(pmos, new_project):
    """`pm_handoff.py plan` / `export` refuse while the PRD holds a key (nothing written
    under handoff/, value never echoed) and proceed with `--allow-secrets`. A clean PRD
    exports with no secret events at all."""
    proj = _approved_prd(pmos, new_project, "sec-jira", leak=True)
    for cmd in ("plan", "export"):
        res = run_script(pmos, "pm_handoff.py", cmd, cwd=proj)
        assert res.returncode != 0, cmd
        out = res.stdout + res.stderr
        assert "03-prd.md:" in out and "google_api_key" in out
        assert FAKE_GOOGLE_KEY not in out
    assert not (proj / "handoff").exists()

    res = run_script(pmos, "pm_handoff.py", "plan", "--allow-secrets", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert json.loads((proj / "handoff" / "jira-plan.json").read_text(encoding="utf-8"))["items"]
    res = run_script(pmos, "pm_handoff.py", "export", "--allow-secrets", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert (proj / "handoff" / "jira-import.csv").exists()
    assert FAKE_GOOGLE_KEY not in _telemetry_text(proj)

    clean = _approved_prd(pmos, new_project, "sec-jira-clean", leak=False)
    res = run_script(pmos, "pm_handoff.py", "plan", cwd=clean)
    assert res.returncode == 0, res.stderr
    assert not any(e["event_type"].startswith("secrets_") for e in read_events(clean))
